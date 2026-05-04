from __future__ import annotations


def test_sources_endpoint_lists_loaded_files(client) -> None:
    response = client.get("/api/data/sources")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_loaded"] is True
    assert payload["source_count"] >= 8
    names = {item["logical_name"] for item in payload["loaded_sources"]}
    assert "normalized_business_records" in names
    assert "ubid_registry" in names
