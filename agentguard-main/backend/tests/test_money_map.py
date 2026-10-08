import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from main import app, ensure_account, svcs, scenario_txns

client = TestClient(app)

def test_v1_accounts_endpoint():
    response = client.get("/v1/accounts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "id" in data[0]
    assert "display_name" in data[0]
    assert "role" in data[0]

def test_v1_graph_account_empty_history():
    # Account with no history
    response = client.get("/v1/graph/account/new_user_empty_test?hops=1")
    assert response.status_code == 200
    data = response.json()
    assert data["account"]["id"] == "new_user_empty_test"
    assert data["account"]["risk_level"] == "Safe"
    assert data["account"]["risk_score"] == 0.0
    assert len(data["received"]["senders"]) == 0
    assert data["received"]["total_amount"] == 0.0
    assert len(data["sent"]["payees"]) == 0
    assert data["sent"]["total_amount"] == 0.0
    assert "No money" in data["summary_sentence"] or "Received ₹0" in data["summary_sentence"]

def test_v1_graph_account_mule_fanin():
    # Simulate mule fanin
    sim_resp = client.post("/simulate/mule_fanin")
    assert sim_resp.status_code == 200

    # Find the mule in accounts
    accounts = client.get("/v1/accounts").json()
    mule_acc = next((a for a in accounts if a["role"] == "mule"), None)
    assert mule_acc is not None

    res = client.get(f"/v1/graph/account/{mule_acc['id']}?hops=1")
    assert res.status_code == 200
    mule_data = res.json()

    # Mule must not be low risk
    assert mule_data["account"]["risk_level"] == "High risk"
    assert mule_data["account"]["risk_score"] >= 80
    assert len(mule_data["received"]["senders"]) >= 5
    assert mule_data["received"]["total_amount"] > 0
    assert len(mule_data["account"]["verdict_reasons"]) >= 2
    assert "summary_sentence" in mule_data

def test_v1_graph_account_cashout():
    accounts = client.get("/v1/accounts").json()
    sink_acc = next((a for a in accounts if a["role"] == "ring"), None)
    assert sink_acc is not None

    res = client.get(f"/v1/graph/account/{sink_acc['id']}?hops=1")
    assert res.status_code == 200
    sink_data = res.json()

    assert sink_data["account"]["risk_level"] == "High risk"
    assert sink_data["account"]["risk_score"] >= 80
    assert sink_data["received"]["total_amount"] > 0

def test_v1_graph_account_normal_customer():
    # Simulate normal
    client.post("/simulate/normal")
    res = client.get("/v1/graph/account/acc_1?hops=1")
    assert res.status_code == 200
    normal_data = res.json()
    assert normal_data["account"]["id"] == "acc_1"
    assert normal_data["account"]["risk_level"] in ("Safe", "Watch")
    assert "display_name" in normal_data["account"]
