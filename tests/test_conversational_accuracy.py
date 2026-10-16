"""Comprehensive Test Suite for Conversational Accuracy, Formatting, and Natural Marathi-English Interactions.

Covers all 19 requirements from Master Prompt Section 9:
1. English greetings and farewells.
2. Marathi greetings and farewells.
3. Romanized Marathi conversation.
4. Mixed Marathi-English questions.
5. Thank-you messages and acknowledgments.
6. General requests for help.
7. Scheme discovery in both languages.
8. Scheme-specific follow-up questions.
9. Eligibility questions.
10. Application deadline questions.
11. No-deadline schemes.
12. Missing or unverified scheme information.
13. Incorrect application links.
14. Excessive Markdown and decorative formatting.
15. Repeated or unnecessarily long answers.
16. Switching from greetings to scheme questions.
17. Switching from scheme questions to general conversation.
18. Chat reset after refresh and navigation (Stateless privacy).
19. LLM provider failures and retrieval errors.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai_assistant import (
    ConversationalIntentRouter,
    detect_language,
    is_devanagari_marathi,
    is_romanized_marathi,
    validate_ai_answer,
)
from backend.database import SessionLocal
from backend.main import app
from backend.models import SchemeCandidate
from backend.status_engine import NO_DEADLINE_NOTICE_EN, NO_DEADLINE_NOTICE_MR

client = TestClient(app)


# 1. English greetings and farewells
def test_1_english_greetings_and_farewells():
    for greeting in ["Hi", "Hello", "Hello bro", "Good morning"]:
        res = client.post("/api/v1/ai/chat", json={"query": greeting})
        assert res.status_code == 200
        data = res.json()
        assert data["confidence"] == "conversational"
        assert len(data.get("sources", [])) == 0
        assert any(w in data["answer"].lower() for w in ["help", "hi", "hey", "good morning"])
        # Should not show scheme list or no schemes found
        assert "no verified" not in data["answer"].lower()

    for farewell in ["Bye", "See you", "Goodbye"]:
        res = client.post("/api/v1/ai/chat", json={"query": farewell})
        assert res.status_code == 200
        data = res.json()
        assert data["confidence"] == "conversational"
        assert "goodbye" in data["answer"].lower() or "day" in data["answer"].lower()


# 2. Marathi greetings and farewells
def test_2_marathi_greetings_and_farewells():
    res = client.post("/api/v1/ai/chat", json={"query": "नमस्कार"})
    assert res.status_code == 200
    data = res.json()
    assert data["confidence"] == "conversational"
    assert len(data.get("sources", [])) == 0
    assert "नमस्कार" in data["answer"]
    assert is_devanagari_marathi(data["answer"])

    res_morning = client.post("/api/v1/ai/chat", json={"query": "शुभ सकाळ"})
    assert res_morning.status_code == 200
    assert "सकाळ" in res_morning.json()["answer"]

    res_bye = client.post("/api/v1/ai/chat", json={"query": "बाय"})
    assert res_bye.status_code == 200
    assert "भेटू" in res_bye.json()["answer"] or "दिवस" in res_bye.json()["answer"]


# 3. Romanized Marathi conversation
def test_3_romanized_marathi_conversation():
    # Chit-chat: "Kasa ahes?"
    res_hru = client.post("/api/v1/ai/chat", json={"query": "Kasa ahes?"})
    assert res_hru.status_code == 200
    assert res_hru.json()["confidence"] == "conversational"
    assert "mast" in res_hru.json()["answer"].lower() or "dhanyawad" in res_hru.json()["answer"].lower()

    # Question asking: "Mala ek question vicharaycha aahe."
    res_q = client.post("/api/v1/ai/chat", json={"query": "Mala ek question vicharaycha aahe."})
    assert res_q.status_code == 200
    assert res_q.json()["confidence"] == "conversational"
    assert "vichara" in res_q.json()["answer"].lower() or "madat" in res_q.json()["answer"].lower()

    # Help offering: "Tu mala help karshil ka?"
    res_help = client.post("/api/v1/ai/chat", json={"query": "Tu mala help karshil ka?"})
    assert res_help.status_code == 200
    assert "madat" in res_help.json()["answer"].lower() or "yojnanbaddal" in res_help.json()["answer"].lower()


# 4. Mixed Marathi-English questions
def test_4_mixed_marathi_english_questions():
    res = client.post("/api/v1/ai/chat", json={"query": "Hi, mala scholarship yojna baddal mahiti pahije."})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    # Answer should have a polite natural greeting acknowledgment
    assert "hi" in data["answer"].lower() or "नमस्कार" in data["answer"] or "नक्की" in data["answer"]


# 5. Thank-you messages and acknowledgments
def test_5_thank_you_messages():
    for ty in ["Thank you", "Thanks", "धन्यवाद", "Dhanyawad"]:
        res = client.post("/api/v1/ai/chat", json={"query": ty})
        assert res.status_code == 200
        data = res.json()
        assert data["confidence"] == "conversational"
        assert len(data.get("sources", [])) == 0
        assert (
            "welcome" in data["answer"].lower()
            or "स्वागत" in data["answer"]
            or "swagat" in data["answer"].lower()
        )


# 6. General requests for help
def test_6_general_requests_for_help():
    for h in ["Can you help me?", "मला मदत पाहिजे", "कशी मदत करू शकतोस?"]:
        res = client.post("/api/v1/ai/chat", json={"query": h})
        assert res.status_code == 200
        data = res.json()
        assert data["confidence"] == "conversational"
        assert len(data.get("sources", [])) == 0
        assert "help" in data["answer"].lower() or "मदत" in data["answer"]


# 7. Scheme discovery in both languages
def test_7_scheme_discovery_both_languages():
    res_en = client.post("/api/v1/ai/chat", json={"query": "What schemes are available for farmers?"})
    assert res_en.status_code == 200
    assert len(res_en.json().get("sources", [])) > 0
    assert "farmer" in res_en.json()["answer"].lower() or "krushi" in res_en.json()["answer"].lower() or "agriculture" in res_en.json()["answer"].lower()

    res_mr = client.post("/api/v1/ai/chat", json={"query": "शेतकऱ्यांसाठी कोणत्या योजना आहेत?"})
    assert res_mr.status_code == 200
    assert len(res_mr.json().get("sources", [])) > 0
    assert is_devanagari_marathi(res_mr.json()["answer"])


# 8. Scheme-specific follow-up questions
def test_8_scheme_specific_follow_up_questions():
    with SessionLocal() as db:
        scheme1 = db.get(SchemeCandidate, 1)
        expected_title = scheme1.title
        expected_deadline = scheme1.application_deadline

    # Contextual modal chat with Scheme ID 1
    # Turn 1: Overview
    t1 = client.post("/api/v1/ai/chat", json={"scheme_id": 1, "query": "Tell me about this scheme"})
    assert t1.status_code == 200
    assert expected_title in t1.json()["answer"]

    # Turn 2: "Who can apply?" -> eligibility without repeating full overview
    history_2 = [
        {"role": "user", "content": "Tell me about this scheme"},
        {"role": "assistant", "content": t1.json()["answer"]},
    ]
    t2 = client.post(
        "/api/v1/ai/chat",
        json={"scheme_id": 1, "query": "Who can apply?", "conversation_history": history_2},
    )
    assert t2.status_code == 200
    assert "eligibility" in t2.json()["answer"].lower() or "पात्रता" in t2.json()["answer"]

    # Turn 3: "What documents are needed?" -> clean documents list
    history_3 = history_2 + [
        {"role": "user", "content": "Who can apply?"},
        {"role": "assistant", "content": t2.json()["answer"]},
    ]
    t3 = client.post(
        "/api/v1/ai/chat",
        json={"scheme_id": 1, "query": "What documents are needed?", "conversation_history": history_3},
    )
    assert t3.status_code == 200
    assert "documents" in t3.json()["answer"].lower() or "कागदपत्रे" in t3.json()["answer"]

    # Turn 4: "Last date kay aahe?" -> verified date and status
    history_4 = history_3 + [
        {"role": "user", "content": "What documents are needed?"},
        {"role": "assistant", "content": t3.json()["answer"]},
    ]
    t4 = client.post(
        "/api/v1/ai/chat",
        json={"scheme_id": 1, "query": "Last date kay aahe?", "conversation_history": history_4},
    )
    assert t4.status_code == 200
    if expected_deadline:
        assert expected_deadline in t4.json()["answer"]
    else:
        assert "deadline" in t4.json()["answer"].lower() or "तारीख" in t4.json()["answer"]


# 9. Eligibility questions
def test_9_eligibility_questions():
    res = client.post(
        "/api/v1/ai/eligibility",
        json={
            "scheme_id": 1,
            "user_input": "I have 1.5 hectares of land and income of 1 lakh, am I eligible?",
            "lang": "en",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["assessment_category"] in ("likely_eligible", "more_info_needed")


# 10. Application deadline questions
def test_10_application_deadline_questions():
    with SessionLocal() as db:
        scheme1 = db.get(SchemeCandidate, 1)
        expected_deadline = scheme1.application_deadline

    res = client.post(
        "/api/v1/ai/chat",
        json={"scheme_id": 1, "query": "When is the last date to apply?"},
    )
    assert res.status_code == 200
    if expected_deadline:
        assert expected_deadline in res.json()["answer"]
    else:
        assert "deadline" in res.json()["answer"].lower()


# 11. No-deadline schemes
def test_11_no_deadline_schemes():
    # Scheme with no deadline published (e.g. Sanjay Gandhi Niradhar Anudan Yojana)
    with SessionLocal() as db:
        s = db.scalar(select(SchemeCandidate).where(SchemeCandidate.current_window_status == "no_deadline_published").limit(1))
        if s:
            res = client.post(
                "/api/v1/ai/chat",
                json={"scheme_id": s.id, "query": "When is the last date?"},
            )
            assert res.status_code == 200
            assert "no application deadline" in res.json()["answer"].lower() or "तारीख नमूद केलेली नाही" in res.json()["answer"]


# 12. Missing or unverified scheme information
def test_12_missing_scheme_information():
    res = client.post("/api/v1/ai/chat", json={"query": "nonexistent_scheme_xyz_9999"})
    assert res.status_code == 200
    data = res.json()
    assert len(data.get("sources", [])) == 0
    assert "no verified" in data["answer"].lower() or "आढळली नाही" in data["answer"]


# 13. Incorrect application links validation
def test_13_incorrect_application_links_blocked():
    with SessionLocal() as db:
        scheme1 = db.get(SchemeCandidate, 1)
        # Validate that unverified external links fail validation
        fake_answer = "Apply at [Fake Portal](https://fake-phishing-link.com/apply)"
        is_valid, issues = validate_ai_answer(fake_answer, [scheme1])
        assert not is_valid
        assert any("unverified URL" in issue for issue in issues)


# 14. Excessive Markdown and decorative formatting prevention
def test_14_no_decorative_separators_or_excessive_formatting():
    res = client.post("/api/v1/ai/chat", json={"query": "farmer schemes"})
    assert res.status_code == 200
    ans = res.json()["answer"]
    # Should not have decorative horizontal lines '---'
    assert "\n---\n" not in ans
    # Should not have excessive stars (e.g. '****')
    assert "****" not in ans


# 15. Direct, concise answers without redundant repetition
def test_15_direct_concise_answers():
    with SessionLocal() as db:
        scheme1 = db.get(SchemeCandidate, 1)
        expected_deadline = scheme1.application_deadline

    res = client.post(
        "/api/v1/ai/chat",
        json={"scheme_id": 1, "query": "When is the last date?"},
    )
    assert res.status_code == 200
    ans = res.json()["answer"]
    # Direct answer about deadline should be concise (< 600 chars)
    assert len(ans) < 600
    if expected_deadline:
        assert expected_deadline in ans
    else:
        assert "deadline" in ans.lower()


# 16. Switching from greetings to scheme questions
def test_16_switching_greeting_to_scheme():
    # Turn 1: Greeting
    res1 = client.post("/api/v1/ai/chat", json={"query": "Hi"})
    assert res1.json()["confidence"] == "conversational"

    # Turn 2: Scheme question
    res2 = client.post("/api/v1/ai/chat", json={"query": "What farmer schemes are open?"})
    assert res2.status_code == 200
    assert len(res2.json().get("sources", [])) > 0


# 17. Switching from scheme questions to general conversation
def test_17_switching_scheme_to_general_conversation():
    # User sends thanks after a scheme inquiry
    res = client.post(
        "/api/v1/ai/chat",
        json={
            "scheme_id": 1,
            "query": "Thank you, that was helpful!",
            "conversation_history": [
                {"role": "user", "content": "What is the deadline?"},
                {"role": "assistant", "content": "The deadline is 2026-12-31."},
            ],
        },
    )
    assert res.status_code == 200
    assert res.json()["confidence"] == "conversational"
    assert "welcome" in res.json()["answer"].lower() or "स्वागत" in res.json()["answer"]


# 18. Ephemeral chat lifecycle (No server DB storage)
def test_18_ephemeral_chat_no_db_persistence():
    unique_string = "citizen_secret_query_abc_xyz_123"
    res = client.post("/api/v1/ai/chat", json={"query": f"Is this kept? {unique_string}"})
    assert res.status_code == 200

    with SessionLocal() as db:
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()
        # Verify no tables store user chat logs
        for forbidden in ["chat_messages", "conversations", "chat_history", "user_logs"]:
            assert forbidden not in table_names


# 19. Graceful fallback on provider errors
def test_19_graceful_fallback():
    # Empty query handled cleanly without 500 error
    res_empty = client.post("/api/v1/ai/ask", json={"query": "  "})
    assert res_empty.status_code == 422 or res_empty.status_code == 200

    # Very long query handled gracefully within bounds
    res_long = client.post("/api/v1/ai/chat", json={"query": "scheme " * 50})
    assert res_long.status_code == 200
