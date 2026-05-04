from __future__ import annotations


def test_chat_works_without_openrouter_key(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "I want to start a food processing business in Bengaluru with 20 employees"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "START_BUSINESS"
    assert payload["llm_used"] is False
    assert payload["fallback_used"] is True
    assert "recommended_departments" in payload["structured_output"]
