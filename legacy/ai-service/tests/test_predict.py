from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "model_loaded" in data


def test_large_round_number_transaction_high_risk():
    """A $10,000 round-number, off-hours transaction should score > 0.5."""
    res = client.post("/predict-risk", json={
        "fromWallet": "0x" + "a" * 40,
        "toWallet": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "amount": 10000,
        "currency": "USD",
        "timestamp": "2026-01-15T03:00:00Z",
        "velocityCount": 8,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["risk_score"] > 0.4, f"Expected risk_score > 0.4, got {data['risk_score']}"
    assert 0 <= data["confidence"] <= 1
    assert len(data["explanation"]) > 0


def test_small_normal_transaction_low_risk():
    """A $50 normal-hours transaction from a regular wallet should score < 0.5."""
    res = client.post("/predict-risk", json={
        "fromWallet": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "toWallet": "0xab5801a7d398351b8be11c439e05c5b3259aec9b",
        "amount": 50,
        "currency": "USD",
        "timestamp": "2026-01-15T14:30:00Z",
        "velocityCount": 0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["risk_score"] < 0.5, f"Expected risk_score < 0.5, got {data['risk_score']}"


def test_response_shape():
    """Response must include all required fields."""
    res = client.post("/predict-risk", json={
        "fromWallet": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "toWallet": "0xab5801a7d398351b8be11c439e05c5b3259aec9b",
        "amount": 100,
        "currency": "ETH",
    })
    assert res.status_code == 200
    data = res.json()
    assert "risk_score" in data
    assert "confidence" in data
    assert "explanation" in data
    assert "features_used" in data
    assert 0 <= data["risk_score"] <= 1
    assert 0 <= data["confidence"] <= 1
