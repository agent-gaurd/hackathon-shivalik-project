# AgentGuard Suite — Unified Integration & Architecture Guide

## Executive Summary
**AgentGuard Suite** merges two independent payment fraud interception platforms into a single, cohesive, production-ready product with unified authentication, role-based project selection, and reverse-proxy routing under **Port 9000**.

---

## 1. Discovery Findings (Step 0)

### Project 1: AgentGuard 6-Agent Core Engine & Interception Pipeline
- **Original Source Folder:** `agentguard-main/hackathon-shivalik-project-main/hackathon-shivalik-project-main`
- **Suite Target Path:** `agentguard-suite/projects/project1`
- **Stack:** Python 3.11/3.12, FastAPI, XGBoost, Scikit-learn, NetworkX, Pandas, Uvicorn, WebSockets.
- **Backend Entry Point:** `backend.main:app` (started with `uvicorn backend.main:app --port 8001`).
  - *Known Issue & Resolution:* Uses relative imports (`from .models...`, `from .pipeline...`). Must be invoked from the project root (`projects/project1`) as `uvicorn backend.main:app`, never from inside `backend/`.
- **Backend Assigned Port:** `8001` (Internal / Proxied)
- **Primary Routes:**
  - `POST /analyze` — Pre-transaction 6-agent real-time risk scoring.
  - `GET /ws/feed` — Real-time WebSocket streaming feed of payment decisions.
  - `GET /review-queue` & `POST /review/{id}` — Analyst investigation & decisioning.
  - `GET /ledger/verify`, `POST /ledger/tamper`, `POST /ledger/demo-repair` — SHA-256 hash-chain audit ledger.
  - `GET /drift`, `POST /drift/reset` — PSI Population Stability Index feature drift monitor.
  - `POST /simulate/{name}` — Scripted fraud typologies (UPI Scam, Mule Chain, Structuring, Cycle, Takeover, Device Farm).
  - `GET /health` — Service health probe.
- **CORS Config:** Updated to allow `http://localhost:9000`, `http://127.0.0.1:9000`.
- **Original Tests:** `python -m backend.tests.smoke_test`, `python -m backend.tests.e2e_test`, `python -m backend.tests.api_test`.

### Project 2: AgentGuard Money Map & Policy Console
- **Original Source Folder:** `agentguard-main`
- **Suite Target Path:** `agentguard-suite/projects/project2`
- **Stack:** Python 3.11/3.12, FastAPI, SQLite in-memory, YAML Policy Engine, Memory Graph, Vanilla HTML5/JS single-page console.
- **Backend Entry Point:** `backend.main:app` (started with `uvicorn main:app --port 8002` from `backend/` or `uvicorn backend.main:app`).
- **Backend Assigned Port:** `8002` (Internal / Proxied)
- **Primary Routes:**
  - `GET /stats`, `GET /transactions` — Summary KPIs and recent transactions.
  - `GET /graph` — Full money-flow network graph (nodes, edges, risk scores).
  - `GET /v1/accounts`, `GET /v1/graph/account/{id}` — Single-account Money Map exploration and 1/2-hop neighborhood expansion.
  - `GET /ledger`, `GET /ledger/verify`, `POST /ledger/tamper` — SQLite tamper-evident ledger.
  - `POST /simulate/{name}` — Typology simulation (normal, digital_arrest, mule_fanin, etc.).
  - `GET /health` — Service health probe.
- **CORS Config:** `CORSMiddleware` with `allow_origins=["*"]`.
- **Original Tests:** `pytest backend/tests` (`test_money_map.py`).

### Port Clash Resolution
- **Port 9000:** Unified Gateway (Public Facing Entrypoint).
- **Port 8001:** Project 1 Backend (Internal).
- **Port 8002:** Project 2 Backend (Internal).

---

## 2. Target Architecture & Directory Layout (Step 1)

```text
agentguard-suite/
├── gateway/                    # Unified Reverse Proxy & Auth Service (Port 9000)
│   ├── auth.py                 # PBKDF2 password hashing & HMAC-SHA256 JWT tokens
│   ├── main.py                 # Reverse proxy, WebSocket piping, static & health aggregator
│   └── users.json              # Hashed credentials & RBAC configuration
├── portal/                     # Single Landing & Login Portal
│   ├── index.html              # Responsive login with selectable project cards & session detection
│   └── switch-widget.js        # Floating top-right project switcher & logout control
├── projects/
│   ├── project1/               # Project 1: 6-Agent Core Engine (Port 8001)
│   │   ├── backend/            # FastAPI models, agents, pipeline, tests
│   │   ├── static/index.html   # Live 6-Agent real-time dashboard UI
│   │   ├── requirements.txt    # ML and core dependencies
│   │   └── README.md
│   └── project2/               # Project 2: Money Map Console (Port 8002)
│       ├── backend/            # FastAPI app, policy engine, memory graph, static dashboard
│       ├── pytest.ini          # Test runner config
│       ├── requirements.txt    # Web framework dependencies
│       └── README.md
├── tests/
│   └── test_integration.py     # End-to-end pytest suite for Gateway, RBAC, and Proxy
├── run.bat                     # Master one-click startup launcher
├── stop.bat                    # Master clean shutdown script
└── INTEGRATION.md              # Architectural documentation
```

---

## 3. Gateway & Security Model (Step 2)

### Authentication & Token Flow
1. **Login (`POST /auth/login`):**
   - Payload: `{ "username": "...", "password": "...", "project": "project1" | "project2" }`
   - Validates user and checks PBKDF2-SHA256 password hash.
   - Enforces RBAC: verifies requested project is in `user.allowed_projects`.
   - Generates an HMAC-SHA256 signed token (valid for 8 hours) containing `{ sub, allowed_projects, exp, iat }`.
   - Stores token in HttpOnly, SameSite=Lax cookie (`ag_suite_token`) and returns it in JSON for API clients.
2. **Current Session (`GET /auth/me`):**
   - Returns authenticated user details and accessible projects.
3. **Logout (`POST /auth/logout`):**
   - Invalidates session by deleting the auth cookie.

### Secret Key Resolution
- Reads from `AG_SUITE_SECRET` environment variable.
- Fallback for local development: `"agentguard-suite-dev-secret-key-2026-fallback"` (logs a prominent warning on startup).

### Demo User Accounts & Access Matrix

| Username | Password | Role / Title | Allowed Projects | Access Permission |
| :--- | :--- | :--- | :--- | :--- |
| **`admin`** | `admin123` | Master Administrator | `project1`, `project2` | Full access to both platforms |
| **`analyst1`** | `analyst123` | UPI Fraud Interception Analyst | `project1` | Access to Project 1 only (403 on Project 2) |
| **`analyst2`** | `analyst234` | Money Map & Network Analyst | `project2` | Access to Project 2 only (403 on Project 1) |

---

## 4. Reverse Proxying & Sub-Path Routing (Steps 3 & 4)

### Route Mapping

| Route Pattern | Target Upstream | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `/` | `portal/index.html` | No | Unified Login & Project Selector Portal |
| `/switch-widget.js` | `portal/switch-widget.js` | No | Floating project switch & logout widget |
| `/health` | Gateway + Backends | No | Aggregated health status of all 3 services |
| `/p1/` | `projects/project1/static/index.html` | Yes (`project1`) | Project 1 Live 6-Agent Interceptor UI |
| `/p1/api/*` | `http://127.0.0.1:8001/*` | Yes (`project1`) | Project 1 REST API Proxy (Prefix stripped) |
| `/p1/api/ws/feed` | `ws://127.0.0.1:8001/ws/feed` | Yes (`project1`) | Project 1 Live WebSocket Stream Proxy |
| `/p2/` | `projects/project2/backend/static/index.html` | Yes (`project2`) | Project 2 Money Map & Policy Console UI |
| `/p2/api/*` | `http://127.0.0.1:8002/*` | Yes (`project2`) | Project 2 REST API Proxy (Prefix stripped) |

### Dynamic API Base Path Configuration
- Frontend JavaScript files resolve their API base dynamically using:
  ```javascript
  const API_BASE = window.API_BASE_URL || (location.pathname.startsWith('/p1') ? '/p1/api' : (location.pathname.startsWith('/p2') ? '/p2/api' : ''));
  ```
- All relative HTTP calls and WebSocket handshakes route through the Gateway on Port 9000, ensuring unified auth without cross-origin issues.

---

## 5. How to Run and Stop (Step 6)

### One-Click Startup (Windows)
```bat
# From repository root or agentguard-suite:
.\run.bat
```
- Automatically detects Python (`py -3`, `python`, `python3`).
- Validates pre-trained ML models (`backend/models/saved/*.joblib`).
- Starts Project 1 backend on port `8001`.
- Starts Project 2 backend on port `8002`.
- Starts Gateway on port `9000`.
- Polls `/health` until all services are ready.
- Automatically launches your browser at **`http://localhost:9000`**.

### Clean Shutdown
```bat
# Double-click or run:
.\stop.bat
```
- Safely terminates all background processes listening on ports `9000`, `8001`, and `8002`.

---

## 6. How to Add a 3rd Project

To integrate a new platform (e.g. `project3`):
1. **Place Code:** Copy the project into `agentguard-suite/projects/project3/`.
2. **Assign Port:** Allocate an unused port (e.g. `8003`).
3. **Register in Gateway (`gateway/main.py`):**
   ```python
   PROJECT3_BACKEND = os.getenv("P3_URL", "http://127.0.0.1:8003")

   @app.api_route("/p3/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
   async def p3_api_proxy(request: Request, path: str):
       return await proxy_request(request, PROJECT3_BACKEND, "project3", path)
   ```
4. **Update RBAC (`gateway/users.json`):** Add `"project3"` to authorized users' `allowed_projects` array.
5. **Add Portal Card (`portal/index.html`):** Add a card for Project 3 in the selector grid.
6. **Update Launcher (`run.bat` & `stop.bat`):** Include port `8003` in the startup and shutdown loops.

---

## 7. Test Verification & Proof (Step 7)

### Test Execution Matrix

| Test Suite | Command | Result |
| :--- | :--- | :--- |
| **Suite Integration Test** | `python -m pytest agentguard-suite/tests/test_integration.py` | **10/10 PASSED** (Auth, RBAC, Proxy, Health) |
| **Project 1 Smoke Test** | `python -m backend.tests.smoke_test` (in `project1`) | **PASSED** (Exit 0, 100% AML caught, 123 ms latency) |
| **Project 1 E2E Test** | `python -m backend.tests.e2e_test` (in `project1`) | **PASSED** (Exit 0, all typologies verified) |
| **Project 1 API Test** | `python -m backend.tests.api_test` (in `project1`) | **PASSED** (Exit 0, WebSocket, Drift, Ledger verified) |
| **Project 2 Unit Tests** | `python -m pytest backend/tests` (in `project2`) | **5/5 PASSED** (Money Map, Account Hops, Ring Clusters) |

---

## 8. Summary of All File Modifications

| File Path | Purpose / Modification Summary |
| :--- | :--- |
| [`agentguard-suite/gateway/main.py`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/gateway/main.py) | Created unified reverse proxy, WebSocket piping, RBAC auth, health checks, and SPA serving. |
| [`agentguard-suite/gateway/auth.py`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/gateway/auth.py) | Created PBKDF2-SHA256 password hashing and HMAC-SHA256 JWT-compatible token generation/verification. |
| [`agentguard-suite/gateway/users.json`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/gateway/users.json) | Configured hashed demo credentials and RBAC access permissions for admin, analyst1, and analyst2. |
| [`agentguard-suite/portal/index.html`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/portal/index.html) | Created unified landing portal with selectable project cards, session persistence, and error handling. |
| [`agentguard-suite/portal/switch-widget.js`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/portal/switch-widget.js) | Created floating top-right project switch bar and logout button automatically injected into project pages. |
| [`agentguard-suite/projects/project1/backend/main.py`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/projects/project1/backend/main.py) | Added `/health` probe and updated CORS to authorize Gateway on Port 9000. |
| [`agentguard-suite/projects/project1/static/index.html`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/projects/project1/static/index.html) | Created dedicated live 6-agent interceptor UI dashboard with WebSocket feed and drift monitor. |
| [`agentguard-suite/projects/project2/backend/static/index.html`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/projects/project2/backend/static/index.html) | Configured dynamic API URL (`/p2/api`) to support gateway sub-path routing. |
| [`agentguard-suite/tests/test_integration.py`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/tests/test_integration.py) | Created 10 automated test cases verifying health, auth, RBAC enforcement, proxying, and SPA delivery. |
| [`agentguard-suite/run.bat`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/run.bat) | Created master launcher starting both backends and gateway with health check polling. |
| [`agentguard-suite/stop.bat`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/agentguard-suite/stop.bat) | Created clean shutdown script terminating all services on ports 9000, 8001, and 8002. |
| [`run.bat`](file:///c:/Users/parth/OneDrive/Documents/agentguard-main_final/run.bat) | Updated root batch script to delegate directly to `agentguard-suite/run.bat`. |
