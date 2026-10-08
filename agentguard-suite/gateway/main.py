"""AgentGuard Suite Gateway.
Central reverse proxy, authentication, and static asset server for the unified product.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure gateway directory is on sys.path
GATEWAY_DIR = str(Path(__file__).resolve().parent)
SUITE_ROOT = Path(__file__).resolve().parent.parent
if GATEWAY_DIR not in sys.path:
    sys.path.insert(0, GATEWAY_DIR)

import httpx
import websockets
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from auth import load_users, verify_password, create_token, decode_token

app = FastAPI(title="AgentGuard Suite Gateway", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Upstream Backend URLs
PROJECT1_BACKEND = os.getenv("P1_URL", "http://127.0.0.1:8001")
PROJECT2_BACKEND = os.getenv("P2_URL", "http://127.0.0.1:8002")
PROJECT3_BACKEND = os.getenv("P3_URL", "http://127.0.0.1:8003")

PORTAL_DIR = SUITE_ROOT / "portal"
P1_STATIC_DIR = SUITE_ROOT / "projects" / "project1" / "static"
P2_STATIC_DIR = SUITE_ROOT / "projects" / "project2" / "backend" / "static"
P3_STATIC_DIR = SUITE_ROOT / "projects" / "project3" / "static"


# ------------------------------------------------------------------ Authentication
class LoginRequest(BaseModel):
    username: str
    password: str
    project: Optional[str] = None


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract auth token with Authorization header prioritized over cookie."""
    # 1. Authorization Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    # 2. Cookie
    token = request.cookies.get("ag_suite_token")
    if token:
        return token
    # 3. Query Param
    return request.query_params.get("token") or request.query_params.get("ag_suite_token")


def require_auth(request: Request) -> Dict[str, Any]:
    """Dependency: Extract and validate user token."""
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in at /.")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session token. Please log in again.")
    return payload


@app.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    users = load_users()
    user = users.get(req.username.strip())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if req.project and req.project not in user.get("allowed_projects", []):
        raise HTTPException(
            status_code=403,
            detail=f"User '{req.username}' is not authorized to access '{req.project}'."
        )

    token = create_token(user, project=req.project)
    response.set_cookie(
        key="ag_suite_token",
        value=token,
        httponly=True,
        max_age=8 * 3600,
        path="/",
        samesite="lax"
    )
    return {
        "status": "ok",
        "token": token,
        "user": {
            "username": user["username"],
            "name": user.get("name", user["username"]),
            "allowed_projects": user.get("allowed_projects", [])
        },
        "project": req.project
    }


@app.get("/auth/me")
async def get_me(user: Dict[str, Any] = Depends(require_auth)):
    return {
        "username": user.get("sub"),
        "name": user.get("name"),
        "allowed_projects": user.get("allowed_projects", []),
        "project": user.get("project")
    }


@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="ag_suite_token", path="/")
    return {"status": "ok", "message": "Logged out"}


# ------------------------------------------------------------------ Health Aggregator
@app.get("/health")
async def suite_health():
    async with httpx.AsyncClient(timeout=3.0) as client:
        # Check Project 1
        p1_res = None
        try:
            r1 = await client.get(f"{PROJECT1_BACKEND}/health")
            p1_res = r1.json() if r1.status_code == 200 else {"status": "error", "code": r1.status_code}
        except Exception as e:
            p1_res = {"status": "down", "error": str(e)}

        # Check Project 2
        p2_res = None
        try:
            r2 = await client.get(f"{PROJECT2_BACKEND}/health")
            p2_res = r2.json() if r2.status_code == 200 else {"status": "error", "code": r2.status_code}
        except Exception as e:
            p2_res = {"status": "down", "error": str(e)}

        # Check Project 3
        p3_res = None
        try:
            r3 = await client.get(f"{PROJECT3_BACKEND}/health")
            p3_res = r3.json() if r3.status_code == 200 else {"status": "error", "code": r3.status_code}
        except Exception as e:
            p3_res = {"status": "down", "error": str(e)}

    p1_ok = isinstance(p1_res, dict) and p1_res.get("status") == "ok"
    p2_ok = isinstance(p2_res, dict) and p2_res.get("status") == "ok"
    p3_ok = isinstance(p3_res, dict) and p3_res.get("status") == "ok"

    return {
        "status": "ok" if (p1_ok and p2_ok and p3_ok) else ("degraded" if (p1_ok or p2_ok or p3_ok) else "down"),
        "gateway": "ok",
        "project1": p1_res,
        "project2": p2_res,
        "project3": p3_res
    }


# ------------------------------------------------------------------ HTTP Reverse Proxy
async def proxy_request(request: Request, upstream_base: str, project_name: str, path: str):
    # Verify Authentication & Project Authorization
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail=f"Authentication required to access {project_name} API.")
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired. Please re-authenticate.")
    if project_name not in user.get("allowed_projects", []):
        raise HTTPException(status_code=403, detail=f"Access forbidden: account '{user.get('sub')}' is not authorized for {project_name}.")

    target_url = f"{upstream_base}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Filter headers
    excluded_headers = {"host", "content-length", "cookie"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in excluded_headers}

    body = await request.body()

    client = httpx.AsyncClient(timeout=30.0)
    try:
        upstream_req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body
        )
        upstream_resp = await client.send(upstream_req, stream=True)
        return StreamingResponse(
            upstream_resp.aiter_raw(),
            status_code=upstream_resp.status_code,
            headers=dict(upstream_resp.headers),
            background=client.aclose
        )
    except httpx.RequestError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Upstream {project_name} unavailable: {exc}")


@app.api_route("/p1/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def p1_api_proxy(request: Request, path: str):
    return await proxy_request(request, PROJECT1_BACKEND, "project1", path)


@app.api_route("/p2/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def p2_api_proxy(request: Request, path: str):
    return await proxy_request(request, PROJECT2_BACKEND, "project2", path)


@app.api_route("/p3/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def p3_api_proxy(request: Request, path: str):
    return await proxy_request(request, PROJECT3_BACKEND, "project3", path)


# ------------------------------------------------------------------ WebSocket Reverse Proxy
@app.websocket("/p1/api/ws/{path:path}")
@app.websocket("/p1/api/{path:path}")
async def p1_websocket_proxy(websocket: WebSocket, path: str):
    await websocket.accept()

    # Verify WebSocket auth
    token = websocket.cookies.get("ag_suite_token") or websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    user = decode_token(token)
    if not user or "project1" not in user.get("allowed_projects", []):
        await websocket.close(code=1008, reason="Unauthorized project access")
        return

    # Upstream ws target
    ws_upstream = PROJECT1_BACKEND.replace("http://", "ws://").replace("https://", "wss://")
    upstream_url = f"{ws_upstream}/{path}"
    if websocket.scope.get("query_string"):
        upstream_url = f"{upstream_url}?{websocket.scope['query_string'].decode()}"

    try:
        async with websockets.connect(upstream_url) as upstream_ws:
            async def client_to_upstream():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await upstream_ws.send(msg)
                except (WebSocketDisconnect, websockets.ConnectionClosed):
                    pass

            async def upstream_to_client():
                try:
                    async for msg in upstream_ws:
                        await websocket.send_text(msg)
                except (WebSocketDisconnect, websockets.ConnectionClosed):
                    pass

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception as e:
        try:
            await websocket.close(code=1011, reason=f"Upstream error: {e}")
        except Exception:
            pass


# ------------------------------------------------------------------ Static File Serving
@app.get("/switch-widget.js")
async def serve_switch_widget():
    widget_path = PORTAL_DIR / "switch-widget.js"
    if widget_path.exists():
        return FileResponse(str(widget_path), media_type="application/javascript")
    return Response(status_code=404)


@app.get("/")
async def serve_portal(request: Request):
    portal_html = PORTAL_DIR / "index.html"
    if portal_html.exists():
        return FileResponse(str(portal_html))
    return HTMLResponse("<h1>AgentGuard Suite Portal</h1>")


def inject_widget(html_content: str) -> str:
    """Inject floating switch-widget script before closing body tag."""
    widget_script = '<script src="/switch-widget.js"></script>'
    if "</body>" in html_content:
        return html_content.replace("</body>", f"{widget_script}</body>")
    return html_content + widget_script


@app.get("/p1/{path:path}")
@app.get("/p1")
async def serve_p1_spa(request: Request, path: str = ""):
    token = get_token_from_request(request)
    if not token or not decode_token(token):
        return HTMLResponse(
            "<script>alert('Please log in through the unified portal first.'); window.location.href='/';</script>",
            status_code=401
        )
    user = decode_token(token)
    if "project1" not in user.get("allowed_projects", []):
        return HTMLResponse(
            f"<script>alert('Account {user.get('sub')} does not have permission to access Project 1.'); window.location.href='/';</script>",
            status_code=403
        )

    file_path = P1_STATIC_DIR / path if path else P1_STATIC_DIR / "index.html"
    if not file_path.exists() or file_path.is_dir():
        file_path = P1_STATIC_DIR / "index.html"

    if file_path.suffix == ".html":
        content = file_path.read_text(encoding="utf-8")
        return HTMLResponse(inject_widget(content))
    return FileResponse(str(file_path))


@app.get("/p2/{path:path}")
@app.get("/p2")
async def serve_p2_spa(request: Request, path: str = ""):
    token = get_token_from_request(request)
    if not token or not decode_token(token):
        return HTMLResponse(
            "<script>alert('Please log in through the unified portal first.'); window.location.href='/';</script>",
            status_code=401
        )
    user = decode_token(token)
    if "project2" not in user.get("allowed_projects", []):
        return HTMLResponse(
            f"<script>alert('Account {user.get('sub')} does not have permission to access Project 2.'); window.location.href='/';</script>",
            status_code=403
        )

    file_path = P2_STATIC_DIR / path if path else P2_STATIC_DIR / "index.html"
    if not file_path.exists() or file_path.is_dir():
        file_path = P2_STATIC_DIR / "index.html"

    if file_path.suffix == ".html":
        content = file_path.read_text(encoding="utf-8")
        return HTMLResponse(inject_widget(content))
    return FileResponse(str(file_path))


@app.get("/p3/{path:path}")
@app.get("/p3")
async def serve_p3_spa(request: Request, path: str = ""):
    token = get_token_from_request(request)
    if not token or not decode_token(token):
        return HTMLResponse(
            "<script>alert('Please log in through the unified portal first.'); window.location.href='/';</script>",
            status_code=401
        )
    user = decode_token(token)
    if "project3" not in user.get("allowed_projects", []):
        return HTMLResponse(
            f"<script>alert('Account {user.get('sub')} does not have permission to access Project 3.'); window.location.href='/';</script>",
            status_code=403
        )

    file_path = P3_STATIC_DIR / path if path else P3_STATIC_DIR / "index.html"
    if not file_path.exists() or file_path.is_dir():
        file_path = P3_STATIC_DIR / "index.html"

    if file_path.suffix == ".html":
        content = file_path.read_text(encoding="utf-8")
        return HTMLResponse(inject_widget(content))
    return FileResponse(str(file_path))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "9000"))
    print(f"\n   AgentGuard Gateway running at http://localhost:{port}   (Ctrl+C to stop)\n")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
