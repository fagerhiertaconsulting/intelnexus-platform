from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_root():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

    r_resp = client.get("/")
    assert r_resp.status_code == 200
    assert "IntelNexus Platform" in r_resp.json()["app"]


def test_cases_api():
    create_res = client.post(
        "/api/cases",
        json={"title": "API Test Case", "description": "API Test Desc", "priority": "high", "tags": ["test", "api"]},
    )
    assert create_res.status_code == 200
    case_data = create_res.json()
    case_id = case_data["id"]

    # List cases
    list_res = client.get("/api/cases")
    assert list_res.status_code == 200
    assert any(c["id"] == case_id for c in list_res.json())

    # Get stats
    stats_res = client.get(f"/api/cases/{case_id}/stats")
    assert stats_res.status_code == 200


def test_ner_and_report_api():
    create_res = client.post("/api/cases", json={"title": "NER Case"})
    case_id = create_res.json()["id"]

    sample_text = """
    Under en utredning identifierades VD Anders Lindqvist på bolaget Nordic Tech AB.
    Kontakt togs via anders@example.com och servern på 185.220.101.5.
    Betalningar skedde till BTC: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq.
    """

    ner_res = client.post(
        "/api/analysis/ner",
        json={
            "case_id": case_id,
            "text": sample_text,
            "auto_commit_to_case": True,
        },
    )
    assert ner_res.status_code == 200
    assert ner_res.json()["extracted_count"] >= 3

    # Generate Report
    report_res = client.get(f"/api/analysis/report/{case_id}/markdown")
    assert report_res.status_code == 200
    assert "Utredningsrapport" in report_res.text
