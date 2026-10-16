"""Tests for Bilingual Translation, RAG scheme matching, and expanded scheme registry."""
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import SchemeCandidate
from sqlalchemy import select, func

client = TestClient(app)

def test_scheme_database_expansion_above_250():
    """Verify database has been expanded significantly past the initial 176 schemes."""
    db = SessionLocal()
    count = db.scalar(select(func.count(SchemeCandidate.id)))
    db.close()
    assert count >= 250, f"Expected at least 250 schemes in DB, found {count}"

def test_student_scholarships_rag_retrieval():
    """Verify 'Student Scholarships' matches relevant higher/technical/social scholarships."""
    res = client.post(
        "/api/v1/ai/ask",
        json={"query": "Student Scholarships", "limit": 4},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "en"
    assert "Found" in data["answer"] or "Scholarship" in data["answer"]
    assert len(data["sources"]) > 0

def test_bilingual_translation_give_in_marathi():
    """Verify 'give in marathi' converts previous search context into Marathi."""
    history = [
        {"role": "user", "content": "Student Scholarships"},
        {"role": "assistant", "content": "Found 3 relevant official schemes: 1. Post-Matric Scholarship"},
    ]
    res = client.post(
        "/api/v1/ai/chat",
        json={
            "query": "give in marathi",
            "conversation_history": history,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "mr"
    # Must contain Marathi text
    assert any('\u0900' <= char <= '\u097F' for char in data["answer"])

def test_bilingual_translation_give_in_english():
    """Verify 'give in english' converts Marathi search context into English."""
    history = [
        {"role": "user", "content": "माझी लाडकी बहीण योजना"},
        {"role": "assistant", "content": "मुख्यमंत्री माझी लाडकी बहीण योजना दरमहा १५०० रुपये"},
    ]
    res = client.post(
        "/api/v1/ai/chat",
        json={
            "query": "give in english",
            "conversation_history": history,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "en"
    assert "Ladki" in data["answer"] or "Department" in data["answer"]
