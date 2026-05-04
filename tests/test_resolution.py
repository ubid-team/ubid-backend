from __future__ import annotations


def test_resolution_returns_ranked_matches(client) -> None:
    response = client.post(
        "/api/resolve",
        json={
            "record": {
                "business_name": "Ravi Food Processing",
                "address": "Peenya Industrial Area Bengaluru",
                "pin_code": "560058",
                "phone": "9876543210",
                "pan_hash": "HASH_PAN_001",
                "gstin_hash": "HASH_GST_001",
                "source": "USER_INTAKE",
            },
            "limit": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_matches"]
    top = payload["candidate_matches"][0]
    assert top["ubid"] == "KA-BLRU-560058-000001"
    assert top["decision"] == "AUTO_LINK"
    assert top["explanation"]["gstin_score"] == 15
