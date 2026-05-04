from __future__ import annotations


def test_risk_calculation_for_ubid(client) -> None:
    response = client.post("/api/risk/calculate", json={"ubid": "KA-BLRU-560058-000001"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ubid"] == "KA-BLRU-560058-000001"
    assert payload["risk_score"] >= 0
    assert payload["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
