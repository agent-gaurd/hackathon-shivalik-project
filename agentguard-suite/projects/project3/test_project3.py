"""Unit tests for Project 3 Analytics Engine and API."""
import sys
from pathlib import Path

P3_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(P3_DIR / "backend"))

import pytest
from fastapi.testclient import TestClient
from main import app
from engine import engine, CATEGORY_ALLOWED, CATEGORY_STEPPED_UP, CATEGORY_BLOCKED


@pytest.fixture
def client():
    return TestClient(app)


def test_project3_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "ok"
    assert d["service"] == "project3-analytics"
    assert d["total_evaluated"] > 0


def test_project3_stats(client):
    res = client.get("/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "allowed" in data
    assert "stepped_up" in data
    assert "blocked" in data
    assert "comparison" in data
    assert data["allowed"]["count"] > 0
    assert data["stepped_up"]["count"] > 0
    assert data["blocked"]["count"] > 0
    # Blocked score must be significantly higher than allowed score
    assert data["blocked"]["avg_score"] > data["allowed"]["avg_score"]


def test_project3_models(client):
    res = client.get("/models")
    assert res.status_code == 200
    data = res.json()
    assert "transaction" in data
    assert "behavior" in data
    assert "mule" in data
    assert "aml" in data
    # Models should show higher scores on blocked vs allowed
    assert data["transaction"]["blocked_avg"] > data["transaction"]["allowed_avg"]
    assert data["behavior"]["blocked_avg"] > data["behavior"]["allowed_avg"]


def test_project3_distribution(client):
    res = client.get("/distribution")
    assert res.status_code == 200
    data = res.json()
    assert "bins" in data
    assert len(data["bins"]) == 10
    assert len(data["ALLOWED"]) == 10
    assert len(data["STEPPED_UP"]) == 10
    assert len(data["BLOCKED"]) == 10


def test_project3_typologies(client):
    res = client.get("/typologies")
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    assert len(rows) > 0
    first = rows[0]
    assert "typology_name" in first
    assert "allowed_count" in first
    assert "blocked_count" in first


def test_project3_signals(client):
    res = client.get("/signals")
    assert res.status_code == 200
    sigs = res.json()
    assert isinstance(sigs, list)
    assert len(sigs) > 0


def test_project3_simulate(client):
    res = client.post("/simulate", json={"scenario": "digital_arrest", "count": 3})
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "ok"
    assert d["simulated"] == 3


def test_project3_transactions_filter(client):
    res = client.get("/transactions?category=BLOCKED&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) <= 10
    for item in data["items"]:
        assert item["category"] == "BLOCKED"
