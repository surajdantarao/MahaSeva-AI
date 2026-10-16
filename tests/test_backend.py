"""Automated backend test suite for MahaSeva AI."""

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth import hash_password, verify_password, create_access_token, decode_token
from backend.import_csv import import_candidates, sha256_text, normalize_url
from backend.monitor import run_monitoring_sync

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "mahaseva-ai-api"


def test_scheme_summary():
    res = client.get("/api/v1/schemes/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_candidates" in data
    assert data["total_candidates"] >= 174
    assert "statuses" in data
    assert "department_counts" in data


def test_list_departments():
    res = client.get("/api/v1/schemes/departments")
    assert res.status_code == 200
    data = res.json()
    assert "departments" in data
    assert len(data["departments"]) > 0
    dept_names = [d["name"] for d in data["departments"]]
    assert any("Rural Development" in name for name in dept_names)


def test_search_schemes():
    # Test query search
    res = client.get("/api/v1/schemes?q=farmer&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 5


def test_search_department_and_status_filter():
    # Filter by specific department
    res = client.get(
        "/api/v1/schemes?department=Maharashtra Rural Development Department&limit=5"
    )
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["department"] == "Maharashtra Rural Development Department"

    # Filter by verification status
    res_status = client.get("/api/v1/schemes?verification_status=pending_review&limit=5")
    assert res_status.status_code == 200
    for item in res_status.json()["items"]:
        assert item["verification_status"] == "pending_review"


def test_search_empty_and_pagination():
    res = client.get("/api/v1/schemes?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 10
    assert data["offset"] == 0

    res2 = client.get("/api/v1/schemes?limit=10&offset=10")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 10
    if data["items"] and data2["items"]:
        assert data["items"][0]["id"] != data2["items"][0]["id"]


def test_scheme_detail_success_and_404():
    # Fetch first scheme
    list_res = client.get("/api/v1/schemes?limit=1")
    items = list_res.json()["items"]
    assert len(items) > 0
    first_id = items[0]["id"]

    res = client.get(f"/api/v1/schemes/{first_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == first_id
    assert "title" in detail
    assert "department" in detail
    assert "source_url" in detail
    assert "verification_status" in detail

    # Fetch non-existent ID
    res_404 = client.get("/api/v1/schemes/99999999")
    assert res_404.status_code == 404


def test_ai_assistant_grounded_answer_english():
    res = client.post(
        "/api/v1/ai/ask",
        json={"query": "Which schemes help farmers with subsidies?", "limit": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "sources" in data
    assert "disclaimer" in data
    assert data["language"] == "en"
    assert len(data["sources"]) > 0
    for src in data["sources"]:
        assert "http" in src["source_url"]


def test_ai_assistant_grounded_answer_marathi():
    res = client.post(
        "/api/v1/ai/ask",
        json={"query": "शेतकऱ्यांसाठी कोणत्या योजना आहेत?", "limit": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert data["language"] == "mr"
    assert "विभाग" in data["answer"] or "योजना" in data["answer"]


def test_ai_privacy_filter():
    res = client.post(
        "/api/v1/ai/ask",
        json={"query": "My Aadhaar is 1234 5678 9012, give me scheme", "limit": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert "Privacy Warning" in data["answer"]


def test_admin_auth_and_protected_endpoints():
    res_unauth = client.post(
        "/api/v1/admin/schemes/1/review", json={"verification_status": "verified"}
    )
    assert res_unauth.status_code == 401

    login_res = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "MahaSevaAdmin@2026!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    me_res = client.get("/api/v1/admin/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "admin"

    review_res = client.post(
        "/api/v1/admin/schemes/1/review",
        headers=headers,
        json={
            "verification_status": "verified",
            "notes": "Verified against official GR.",
            "brief_description": "Official crop loan interest waiver scheme.",
            "benefits": "Interest waiver on agricultural loans.",
            "eligibility": "Small and marginal farmers residing in Maharashtra.",
        },
    )
    assert review_res.status_code == 200
    assert review_res.json()["candidate"]["verification_status"] == "verified"

    audit_res = client.get("/api/v1/admin/audit-logs?candidate_id=1", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()["items"]
    assert len(logs) > 0
    assert logs[0]["reviewer_username"] == "admin"
    assert logs[0]["new_status"] == "verified"


def test_sources_endpoint():
    res = client.get("/api/v1/sources")
    assert res.status_code == 200
    data = res.json()
    assert "sources" in data
    assert len(data["sources"]) >= 6


def test_auth_crypto_helpers():
    hashed = hash_password("SecurePassword@2026")
    assert verify_password("SecurePassword@2026", hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    token = create_access_token({"sub": "test_officer", "role": "reviewer"})
    payload = decode_token(token)
    assert payload["sub"] == "test_officer"
    assert payload["role"] == "reviewer"


def test_csv_import_idempotence():
    # Rerunning import must be idempotent (0 inserted, all skipped)
    stats = import_candidates()
    assert stats["inserted"] == 0
    assert stats["skipped"] >= 174
    assert stats["failed"] == 0


def test_monitor_sync_run():
    # Verify monitor run logs to collection_runs table and succeeds
    stats = run_monitoring_sync(trigger_crawler=False)
    assert stats["total_rows"] >= 174
    assert stats["failed"] == 0
