"""Integration Test Suite for AgentGuard Suite Gateway and Unified Products."""
import os
import sys
from pathlib import Path

# Add suite directory to path
SUITE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUITE_ROOT))
sys.path.insert(0, str(SUITE_ROOT / "gateway"))

import pytest
from fastapi.testclient import TestClient
from gateway.main import app
from gateway.auth import load_users, hash_password


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Verify gateway health aggregator endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["gateway"] == "ok"
    assert "project1" in data
    assert "project2" in data
    assert "project3" in data


def test_portal_page_serving(client):
    """Verify portal root serves index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "AgentGuard Suite" in response.text or "Unified Defense" in response.text


def test_switch_widget_serving(client):
    """Verify floating switch widget JS serves properly."""
    response = client.get("/switch-widget.js")
    assert response.status_code == 200
    assert "ag-suite-bar" in response.text


def test_login_success_admin(client):
    """Verify admin user login."""
    response = client.post("/auth/login", json={
        "username": "admin",
        "password": "admin123",
        "project": "project1"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "token" in data
    assert data["user"]["username"] == "admin"
    assert set(data["user"]["allowed_projects"]) == {"project1", "project2", "project3"}
    assert "ag_suite_token" in response.cookies


def test_login_invalid_credentials(client):
    """Verify failed login on wrong password."""
    response = client.post("/auth/login", json={
        "username": "admin",
        "password": "wrongpassword123"
    })
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_login_unauthorized_project_request(client):
    """Verify analyst1 cannot request project2 at login time."""
    response = client.post("/auth/login", json={
        "username": "analyst1",
        "password": "analyst123",
        "project": "project2"
    })
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]


def test_auth_me_authenticated_vs_unauthenticated(client):
    """Verify /auth/me with and without token."""
    # Unauthenticated
    unauth_resp = client.get("/auth/me")
    assert unauth_resp.status_code == 401

    # Authenticated
    login_resp = client.post("/auth/login", json={
        "username": "analyst1",
        "password": "analyst123"
    })
    token = login_resp.json()["token"]

    auth_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code == 200
    assert auth_resp.json()["username"] == "analyst1"
    assert auth_resp.json()["allowed_projects"] == ["project1"]


def test_role_based_access_control(client):
    """Verify RBAC: analyst1 (p1), analyst2 (p2), analyst3 (p3), admin (all)."""
    # 1. Login analyst1
    t_a1 = client.post("/auth/login", json={"username": "analyst1", "password": "analyst123"}).json()["token"]

    # 2. Login analyst2
    t_a2 = client.post("/auth/login", json={"username": "analyst2", "password": "analyst234"}).json()["token"]

    # 3. Login analyst3
    t_a3 = client.post("/auth/login", json={"username": "analyst3", "password": "analyst345"}).json()["token"]

    # 4. Login admin
    t_admin = client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]

    # Analyst1 access to P2 API must return 403 Forbidden
    c1 = TestClient(app)
    p2_forbidden = c1.get("/p2/api/health", headers={"Authorization": f"Bearer {t_a1}"})
    assert p2_forbidden.status_code == 403

    # Analyst2 access to P1 API must return 403 Forbidden
    c2 = TestClient(app)
    p1_forbidden = c2.get("/p1/api/health", headers={"Authorization": f"Bearer {t_a2}"})
    assert p1_forbidden.status_code == 403

    # Analyst3 access to P1 API must return 403 Forbidden
    c3 = TestClient(app)
    p1_f3 = c3.get("/p1/api/health", headers={"Authorization": f"Bearer {t_a3}"})
    assert p1_f3.status_code == 403

    # Unauthenticated access to /p1/api, /p2/api, /p3/api must return 401
    c4 = TestClient(app)
    assert c4.get("/p1/api/health").status_code == 401
    assert c4.get("/p2/api/health").status_code == 401
    assert c4.get("/p3/api/health").status_code == 401


def test_project_spa_pages_access(client):
    """Verify /p1/, /p2/, and /p3/ SPA serving with authentication and widget injection."""
    # Login admin
    res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    token = res.json()["token"]

    # P1 SPA page
    p1_page = client.get("/p1/", headers={"Authorization": f"Bearer {token}"})
    assert p1_page.status_code == 200
    assert "switch-widget.js" in p1_page.text

    # P2 SPA page
    p2_page = client.get("/p2/", headers={"Authorization": f"Bearer {token}"})
    assert p2_page.status_code == 200
    assert "switch-widget.js" in p2_page.text

    # P3 SPA page
    p3_page = client.get("/p3/", headers={"Authorization": f"Bearer {token}"})
    assert p3_page.status_code == 200
    assert "switch-widget.js" in p3_page.text
    assert "PROJECT 3" in p3_page.text


def test_logout(client):
    """Verify logout removes auth cookie."""
    login_resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert "ag_suite_token" in login_resp.cookies

    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 200
