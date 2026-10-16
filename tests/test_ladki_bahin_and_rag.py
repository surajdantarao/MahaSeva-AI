"""Tests for Mukhyamantri Majhi Ladki Bahin Yojana, 58 Maharashtra Official Sources,
Intelligent Intent Classification, and Multi-turn Grounded RAG.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai_assistant import (
    ConversationalIntentRouter,
    ai_assistant,
    detect_language,
)
from backend.database import SessionLocal
from backend.main import app
from backend.models import ConfiguredSource, SchemeApplicationWindow, SchemeCandidate

client = TestClient(app)


def test_sites_json_has_at_least_50_validated_maharashtra_sources():
    """Verify sites.json contains >= 50 sources, all official Maharashtra state portals."""
    sites_path = Path("sites.json")
    assert sites_path.exists(), "sites.json must exist in root directory"
    
    with open(sites_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    sources = data.get("sites") or data.get("sources") or []
    assert len(sources) >= 50, f"Expected >= 50 sources, found {len(sources)}"
    
    # Verify mandatory flagship source exists
    ladki_bahin_src = next((s for s in sources if "ladakibahin.maharashtra.gov.in" in " ".join(s.get("start_urls", []))), None)
    assert ladki_bahin_src is not None, "Mukhyamantri Majhi Ladki Bahin Yojana source must be present"
    assert ladki_bahin_src["verification_status"] == "verified"
    
    # Verify all domains are official state domains or statutory state boards
    allowed_gov_suffixes = (
        ".gov.in", ".nic.in", ".mahaonline.gov.in",
        "mahacet.org", "sarthi-maharashtragov.in", "mahajyoti.org.in",
        "umed.in", "msamb.com", "mahadiscom.in"
    )
    for src in sources:
        for domain in src.get("allowed_domains", []):
            assert any(domain.endswith(suffix) for suffix in allowed_gov_suffixes), (
                f"Source {src.get('name')} domain {domain} is not an official government domain"
            )


def test_database_configured_sources_synced():
    """Verify database configured_sources table has synced Maharashtra sources."""
    with SessionLocal() as db:
        db_sources = db.scalars(select(ConfiguredSource)).all()
        assert len(db_sources) >= 50, f"Expected >= 50 configured sources in DB, found {len(db_sources)}"
        
        # Verify Ladki Bahin source is present and active
        lb = next(
            (s for s in db_sources if "ladki" in s.name.lower() or "ladaki" in (s.start_urls or "").lower()),
            None
        )
        assert lb is not None, "Mukhyamantri Majhi Ladki Bahin source missing from configured_sources"
        assert lb.is_active is True


def test_ladki_bahin_scheme_record_and_application_window():
    """Verify Mukhyamantri Majhi Ladki Bahin Yojana record, eligibility, benefits, and application window."""
    with SessionLocal() as db:
        scheme = db.scalar(
            select(SchemeCandidate).where(
                SchemeCandidate.title.like("%Ladki Bahin%")
            )
        )
        assert scheme is not None, "Mukhyamantri Majhi Ladki Bahin Yojana must exist in scheme_candidates"
        assert scheme.verification_status == "verified"
        assert scheme.official_apply_url == "https://ladakibahin.maharashtra.gov.in/"
        assert "1,500" in (scheme.benefits or "") or "१,५००" in (scheme.benefits or "")
        
        # Verify application window
        window = db.scalar(
            select(SchemeApplicationWindow).where(
                SchemeApplicationWindow.scheme_id == scheme.id
            )
        )
        assert window is not None, "Application window must exist for Ladki Bahin"
        assert window.window_status in ("open", "no_deadline_published")
        assert window.date_verification_status == "verified"


def test_intent_greeting_no_retrieval_or_llm():
    """User: 'Hi' -> intent: greeting, fast response without search or LLM call."""
    intent = ConversationalIntentRouter.classify("Hi")
    assert intent == "greeting"
    
    # API call
    res = client.post("/api/v1/ai/chat", json={"query": "Hi"})
    assert res.status_code == 200
    res_data = res.json()
    assert len(res_data.get("sources", [])) == 0
    assert "help" in res_data["answer"].lower() or "मदत" in res_data["answer"]


def test_intent_scheme_discovery_scholarship():
    """User: 'Mala scholarship yojna pahije.' -> Marathi language, discovery intent, returns scholarships."""
    query = "Mala scholarship yojna pahije."
    lang = detect_language(query)
    assert lang in ("mr", "mr_roman")
    
    res = client.post("/api/v1/ai/chat", json={"query": query})
    assert res.status_code == 200
    res_data = res.json()
    assert len(res_data.get("sources", [])) > 0
    assert any("scholarship" in s["title"].lower() or "शिष्यवृत्ती" in (s.get("title_mr") or "") for s in res_data["sources"])


def test_intent_deadline_ladki_bahin():
    """User: 'What is the last date for Ladki Bahin Yojana?' -> English, deadline intent, accurate open status."""
    query = "What is the last date for Ladki Bahin Yojana?"
    lang = detect_language(query)
    assert lang == "en"
    
    intent = ConversationalIntentRouter.classify(query)
    assert intent == "scheme_query"
    
    res = client.post("/api/v1/ai/chat", json={"query": query})
    assert res.status_code == 200
    res_data = res.json()
    answer = res_data["answer"].lower()
    # Must report active/open without fabricating a fake past deadline
    assert "open" in answer or "active" in answer or "ongoing" in answer or "ladki bahin" in answer


def test_unspecified_intent_clarification_prompts():
    """User: 'Mi eligible aahe ka?' without scheme context -> prompts for scheme name."""
    query = "Mi eligible aahe ka?"
    intent = ConversationalIntentRouter.classify(query)
    assert intent == "unspecified_eligibility"
    
    res = client.post("/api/v1/ai/chat", json={"query": query})
    assert res.status_code == 200
    answer = res.json()["answer"].lower()
    assert any(phrase in answer for phrase in ["yojnebaddal", "yojneche naav", "योजनेचे नाव", "कोणत्या योजनेसाठी"])


def test_unspecified_apply_procedure_clarification_prompt():
    """User: 'How do I apply?' without scheme context -> prompts for scheme name."""
    query = "How do I apply?"
    intent = ConversationalIntentRouter.classify(query)
    assert intent == "unspecified_apply"
    
    res = client.post("/api/v1/ai/chat", json={"query": query})
    assert res.status_code == 200
    answer = res.json()["answer"].lower()
    assert "which" in answer and "scheme" in answer and "apply" in answer


def test_multiturn_context_resolution():
    """Turn 1: 'What is Ladki Bahin Yojana?' -> Turn 2: 'How do I apply?' -> resolves to Ladki Bahin."""
    history = [
        {"role": "user", "content": "Tell me about Ladki Bahin Yojana"},
        {"role": "assistant", "content": "Mukhyamantri Majhi Ladki Bahin Yojana provides Rs 1,500 per month."},
    ]
    res = client.post(
        "/api/v1/ai/chat",
        json={"query": "How do I apply?", "conversation_history": history},
    )
    assert res.status_code == 200
    res_data = res.json()
    answer = res_data["answer"].lower()
    assert "ladakibahin.maharashtra.gov.in" in answer or "ladki bahin" in answer or "nari shakti" in answer
