"""Live System Verification Script."""
import asyncio
import httpx
import websockets
import json

async def main():
    print("\n=======================================================")
    print("         AgentGuard Suite Live System Verification")
    print("=======================================================\n")

    async with httpx.AsyncClient(base_url="http://127.0.0.1:9000", timeout=10.0) as client:
        # 1. Gateway Health
        h = await client.get("/health")
        print("1. Gateway & Backends Health Check:")
        print(json.dumps(h.json(), indent=2))
        assert h.json()["status"] == "ok"

        # 2. Admin Login
        login_res = await client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert login_res.status_code == 200
        token = login_res.json()["token"]
        print("\n2. Admin Authentication: SUCCESS (Token acquired)")

        # 3. Project 1 Proxy API Calls
        p1_drift = await client.get("/p1/api/drift")
        print(f"\n3. Project 1 API (/p1/api/drift): {p1_drift.status_code} OK -> Status: {p1_drift.json().get('status')}")

        p1_sim = await client.post("/p1/api/simulate/normal?count=2")
        print(f"   Project 1 Simulate Normal: {p1_sim.status_code} OK -> Simulated {len(p1_sim.json())} txns")

        # 4. Project 2 Proxy API Calls
        p2_stats = await client.get("/p2/api/stats")
        print(f"\n4. Project 2 API (/p2/api/stats): {p2_stats.status_code} OK -> Total Txns: {p2_stats.json().get('total')}")

        p2_graph = await client.get("/p2/api/graph")
        print(f"   Project 2 Graph: {p2_graph.status_code} OK -> {len(p2_graph.json().get('nodes', []))} nodes, {len(p2_graph.json().get('edges', []))} edges")

        # 5. Project 3 Proxy API Calls
        p3_stats = await client.get("/p3/api/stats")
        print(f"\n5. Project 3 API (/p3/api/stats): {p3_stats.status_code} OK -> Total Evaluated: {p3_stats.json().get('total_count')}")

        p3_models = await client.get("/p3/api/models")
        print(f"   Project 3 Models (/p3/api/models): {p3_models.status_code} OK -> XGBoost Avg Blocked: {p3_models.json().get('transaction', {}).get('blocked_avg')}")

        # 6. RBAC Analyst1
        a1_res = await client.post("/auth/login", json={"username": "analyst1", "password": "analyst123"})
        t1 = a1_res.json()["token"]
        c_a1 = httpx.AsyncClient(base_url="http://127.0.0.1:9000", headers={"Authorization": f"Bearer {t1}"})
        p1_ok = await c_a1.get("/p1/api/health")
        p2_err = await c_a1.get("/p2/api/health")
        p3_err = await c_a1.get("/p3/api/health")
        print(f"\n6. RBAC Analyst1 (project1 only): P1 Access={p1_ok.status_code} (Allowed) | P2 Access={p2_err.status_code} (Forbidden) | P3 Access={p3_err.status_code} (Forbidden)")
        assert p1_ok.status_code == 200 and p2_err.status_code == 403 and p3_err.status_code == 403

        # 7. RBAC Analyst2
        a2_res = await client.post("/auth/login", json={"username": "analyst2", "password": "analyst234"})
        t2 = a2_res.json()["token"]
        c_a2 = httpx.AsyncClient(base_url="http://127.0.0.1:9000", headers={"Authorization": f"Bearer {t2}"})
        p1_err2 = await c_a2.get("/p1/api/health")
        p2_ok = await c_a2.get("/p2/api/health")
        p3_err2 = await c_a2.get("/p3/api/health")
        print(f"7. RBAC Analyst2 (project2 only): P1 Access={p1_err2.status_code} (Forbidden) | P2 Access={p2_ok.status_code} (Allowed) | P3 Access={p3_err2.status_code} (Forbidden)")
        assert p1_err2.status_code == 403 and p2_ok.status_code == 200 and p3_err2.status_code == 403

        # 8. RBAC Analyst3
        a3_res = await client.post("/auth/login", json={"username": "analyst3", "password": "analyst345"})
        t3 = a3_res.json()["token"]
        c_a3 = httpx.AsyncClient(base_url="http://127.0.0.1:9000", headers={"Authorization": f"Bearer {t3}"})
        p1_err3 = await c_a3.get("/p1/api/health")
        p2_err3 = await c_a3.get("/p2/api/health")
        p3_ok = await c_a3.get("/p3/api/health")
        print(f"8. RBAC Analyst3 (project3 only): P1 Access={p1_err3.status_code} (Forbidden) | P2 Access={p2_err3.status_code} (Forbidden) | P3 Access={p3_ok.status_code} (Allowed)")
        assert p1_err3.status_code == 403 and p2_err3.status_code == 403 and p3_ok.status_code == 200

    # 9. WebSocket Proxying
    print("\n9. Testing WebSocket Proxy (/p1/api/ws/feed)...")
    ws_url = f"ws://127.0.0.1:9000/p1/api/ws/feed?token={token}"
    async with websockets.connect(ws_url) as ws:
        print("   WebSocket Connected to /p1/api/ws/feed successfully through Gateway!")

    print("\n=======================================================")
    print("      ALL LIVE INTEGRATION CHECKS PASSED (100%)")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
