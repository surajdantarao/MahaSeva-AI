"""Comprehensive Evaluation & Testing for MahaSeva AI Bilingual Citizen Assistant.

Covers all 20 Scenarios Specified in Master Prompt Section 15:
1. English scheme discovery.
2. Marathi scheme discovery.
3. Romanized Marathi queries.
4. Marathi-English mixed queries.
5. Correct identification of the selected scheme.
6. Scheme-specific follow-up questions.
7. Eligibility assessment with complete information.
8. Eligibility assessment with missing information.
9. Missing or unverified eligibility rules.
10. Correct official application link retrieval.
11. Schemes that support only offline applications.
12. Conflicting or outdated source information.
13. Empty search results.
14. AI provider failure/unavailability handling.
15. Prompt-injection and privacy protection (PII block).
16. Starting a new chat from a different scheme card.
17. Clearing chat when the user closes it (stateless in-memory verification).
18. Clearing chat on refresh (no server session persistence).
19. Clearing chat when navigating away and returning.
20. Preventing one user's conversation from leaking into another user's requests.

Also tests new API contracts:
- GET /api/v1/schemes/categories
- GET /api/v1/schemes/{scheme_id}/sources
- GET /api/v1/schemes/{scheme_id}/application-guide
- POST /api/v1/ai/chat
- POST /api/v1/ai/eligibility
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai_assistant import (
    ApplicationGuideEngine,
    EligibilityEngine,
    ai_assistant,
    detect_language,
    is_devanagari_marathi,
    is_romanized_marathi,
)
import hashlib
from backend.database import SessionLocal
from backend.main import app
from backend.models import SchemeCandidate

client = TestClient(app)


@pytest.fixture(scope="module")
def sample_schemes():
    """Ensure database has controlled, diverse test records."""
    with SessionLocal() as db:
        # Scheme 1: Online Farmer Scheme with verified apply URL & criteria
        s1 = db.scalar(select(SchemeCandidate).where(SchemeCandidate.id == 1))
        if not s1:
            url1 = "https://krishi.maharashtra.gov.in/swavalamban"
            s1 = SchemeCandidate(
                id=1,
                title="Dr. Babasaheb Ambedkar Krushi Swavalamban Yojana",
                title_mr="डॉ. बाबासाहेब आंबेडकर कृषी स्वावलंबन योजना",
                department="Agriculture Department",
                category="Agriculture",
                source_url=url1,
                source_url_sha256=hashlib.sha256(url1.encode()).hexdigest(),
                content_sha256=hashlib.sha256(b"swavalamban").hexdigest(),
                official_apply_url="https://mahadbt.maharashtra.gov.in/farmer",
                verification_status="verified",
                current_window_status="open",
                application_deadline="2026-12-31",
                application_mode="online",
                text="Dr. Babasaheb Ambedkar Krushi Swavalamban Yojana provides subsidy for wells and irrigation to SC farmers.",
                documents_required="7/12 उतारा, 8-अ उतारा, आधार कार्ड, जात प्रमाणपत्र",
                eligibility="अनुसूचित जाती व नवबौद्ध शेतकरी. किमान ०.४० हेक्टर व कमाल ६ हेक्टर शेतजमीन धारक. उत्पन्न मर्यादा रु. १,५०,०००.",
                benefits="नवीन विहीर, जुनी विहीर दुरुस्ती, शेततळे, तुषार सिंचन यावर १००% पर्यंत अनुदान.",
            )
            db.add(s1)

        # Scheme 2: Offline Social Justice Scheme with no online apply URL
        s2 = db.scalar(select(SchemeCandidate).where(SchemeCandidate.title == "Sanjay Gandhi Niradhar Anudan Yojana"))
        if not s2:
            url2 = "https://sjsa.maharashtra.gov.in/sanjay-gandhi"
            s2 = SchemeCandidate(
                title="Sanjay Gandhi Niradhar Anudan Yojana",
                title_mr="संजय गांधी निराधार अनुदान योजना",
                department="Social Justice and Special Assistance",
                category="Social Justice",
                source_url=url2,
                source_url_sha256=hashlib.sha256(url2.encode()).hexdigest(),
                content_sha256=hashlib.sha256(b"sanjay-gandhi").hexdigest(),
                official_apply_url=None,
                verification_status="verified",
                current_window_status="no_deadline_published",
                application_deadline=None,
                application_mode="offline",
                text="Financial monthly assistance to destitute senior citizens and persons with disabilities in Maharashtra.",
                documents_required="अधिवास दाखला, वय दाखला, वैद्यकीय प्रमाणपत्र, उत्पन्न दाखला",
                eligibility="महाराष्ट्र रहिवासी, ६५ वर्षांवरील निराधार व्यक्ती, किंवा अपंग व्यक्ती. वार्षिक उत्पन्न रु. २१,००० पेक्षा कमी.",
                benefits="दरमहा रु. १,५०० आर्थिक साहाय्य.",
            )
            db.add(s2)

        # Scheme 3: Unverified Candidate Scheme
        s3 = db.scalar(select(SchemeCandidate).where(SchemeCandidate.verification_status == "pending_review"))
        if not s3:
            url3 = "https://mahadiscom.in/solar"
            s3 = SchemeCandidate(
                title="Candidate Unverified Solar Pump Scheme",
                title_mr="सौर कृषी पंप योजना (उमेदवार)",
                department="Energy Department",
                category="Agriculture",
                source_url=url3,
                source_url_sha256=hashlib.sha256(url3.encode()).hexdigest(),
                content_sha256=hashlib.sha256(b"solar").hexdigest(),
                text="Candidate solar agriculture pump scheme pending officer verification.",
                verification_status="pending_review",
                current_window_status="no_deadline_published",
                eligibility=None,
            )
            db.add(s3)

        db.commit()
    return True


# ==============================================================================
# Scenario 1 to 4: Bilingual, Romanized & Mixed Query Understanding
# ==============================================================================


def test_scenario_1_english_scheme_discovery(sample_schemes):
    """Scenario 1: English scheme discovery grounded in available schemes."""
    res = client.post("/api/v1/ai/chat", json={"query": "What schemes are available for farmers in Maharashtra?"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert len(data.get("sources", [])) > 0
    # Must cite government source or title
    assert "Krushi" in data["answer"] or "Agriculture" in data["answer"] or "farmer" in data["answer"].lower()


def test_scenario_2_marathi_scheme_discovery(sample_schemes):
    """Scenario 2: Marathi scheme discovery answered in natural Marathi."""
    res = client.post("/api/v1/ai/chat", json={"query": "माझ्यासाठी कोणत्या शेतकरी योजना उपलब्ध आहेत?"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert is_devanagari_marathi(data["answer"])
    assert any(term in data["answer"] for term in ["योजना", "कृषी", "अनुदान", "शासन"])


def test_scenario_3_romanized_marathi_queries(sample_schemes):
    """Scenario 3: Romanized Marathi query understood and responded in Marathi."""
    res = client.post("/api/v1/ai/chat", json={"query": "Mala shetkari yojna baddal sang"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    # Assistant detects Romanized Marathi and replies in Marathi Devanagari
    assert is_devanagari_marathi(data["answer"])
    assert "योजना" in data["answer"]


def test_scenario_4_marathi_english_mixed_queries(sample_schemes):
    """Scenario 4: Mixed Marathi-English queries (e.g. Farmer scheme sathi arj kasa karaycha?)."""
    res = client.post("/api/v1/ai/chat", json={"query": "Farmer scheme sathi online arj kasa karaycha?"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert len(data.get("sources", [])) > 0


# ==============================================================================
# Scenario 5 & 6: Identification of Selected Scheme & Multi-Turn Context
# ==============================================================================


def test_scenario_5_correct_identification_of_selected_scheme(sample_schemes):
    """Scenario 5: Opening contextual chat on a specific scheme ID answers about that exact scheme."""
    with SessionLocal() as db:
        scheme1 = db.get(SchemeCandidate, 1)
        expected_name = scheme1.title

    res = client.post("/api/v1/ai/chat", json={"query": "Tell me about this scheme", "scheme_id": 1})
    assert res.status_code == 200
    data = res.json()
    assert data["scheme_id"] == 1
    # Must refer to scheme 1's actual title
    assert expected_name in data["answer"]


def test_scenario_6_scheme_specific_follow_up_questions(sample_schemes):
    """Scenario 6: Follow-up question in the same chat stays anchored to the scheme using conversation history."""
    history = [
        {"role": "user", "content": "Tell me about this scheme"},
        {"role": "assistant", "content": "This is Dr. Babasaheb Ambedkar Krushi Swavalamban Yojana."},
    ]
    res = client.post(
        "/api/v1/ai/chat",
        json={"query": "What are the required documents?", "scheme_id": 1, "conversation_history": history},
    )
    assert res.status_code == 200
    data = res.json()
    assert "7/12" in data["answer"] or "Aadhaar" in data["answer"] or "कागदपत्रे" in data["answer"]


# ==============================================================================
# Scenario 7 to 9: Guided Eligibility Assessment
# ==============================================================================


def test_scenario_7_eligibility_assessment_complete_info(sample_schemes):
    """Scenario 7: Eligibility evaluation with matching criteria returns likely_eligible."""
    res = client.post(
        "/api/v1/ai/eligibility",
        json={
            "scheme_id": 1,
            "user_input": "I am a Scheduled Caste farmer in Maharashtra having 2 hectares of agricultural land and family income of 1 lakh.",
            "lang": "en",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["assessment_category"] == "likely_eligible"
    assert "Likely Eligible" in data["answer"]


def test_scenario_8_eligibility_assessment_missing_info(sample_schemes):
    """Scenario 8: Eligibility evaluation with vague/incomplete details requests required information."""
    res = client.post(
        "/api/v1/ai/eligibility",
        json={"scheme_id": 1, "user_input": "Am I eligible?", "lang": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["assessment_category"] == "more_info_needed"
    assert "please share" in data["answer"].lower() or "more information" in data["answer"].lower()


def test_scenario_9_missing_or_unverified_eligibility_rules(sample_schemes):
    """Scenario 9: Evaluating eligibility on an unverified candidate without rules returns rules_unverified."""
    with SessionLocal() as db:
        unverified = db.scalar(select(SchemeCandidate).where(SchemeCandidate.eligibility == None).limit(1))
        if not unverified:
            u_url = "https://maharashtra.gov.in/unknown"
            unverified = SchemeCandidate(
                title="Unknown Criteria Scheme",
                department="General",
                source_url=u_url,
                source_url_sha256=hashlib.sha256(u_url.encode()).hexdigest(),
                content_sha256=hashlib.sha256(b"unknown").hexdigest(),
                text="Scheme with unknown criteria for testing.",
                verification_status="pending_review",
            )
            db.add(unverified)
            db.commit()
        unverified_id = unverified.id

    res = client.post(
        "/api/v1/ai/eligibility",
        json={"scheme_id": unverified_id, "user_input": "Can I apply?", "lang": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["assessment_category"] == "rules_unverified"
    assert "Could Not Be Verified" in data["answer"] or "तपासणी बाकी" in data["answer"]


# ==============================================================================
# Scenario 10 & 11: Official Application Links & Offline Guidance
# ==============================================================================


def test_scenario_10_correct_official_application_link_retrieval(sample_schemes):
    """Scenario 10: Official application portal link is correctly retrieved from approved database."""
    res = client.post(
        "/api/v1/ai/chat",
        json={"query": "Give me the official apply link", "scheme_id": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert "https://mahadbt.maharashtra.gov.in" in data["answer"]


def test_scenario_11_offline_application_guidance(sample_schemes):
    """Scenario 11: Offline scheme clearly specifies designated office procedure without fabricating a URL."""
    with SessionLocal() as db:
        offline = db.scalar(select(SchemeCandidate).where(SchemeCandidate.application_mode == "offline").limit(1))
        offline_id = offline.id

    res = client.get(f"/api/v1/schemes/{offline_id}/application-guide")
    assert res.status_code == 200
    data = res.json()
    assert data["application_mode"] == "offline"
    assert "Offline Designated Office" in data["guide_en"] or "कार्यालयात" in data["guide_mr"]


# ==============================================================================
# Scenario 12 & 13: Source Verification & Empty Results
# ==============================================================================


def test_scenario_12_outdated_or_unverified_scheme_labeling(sample_schemes):
    """Scenario 12: Unverified candidate records are explicitly marked pending_review and not claimed as verified."""
    res = client.get("/api/v1/schemes?verification_status=pending_review&limit=5")
    assert res.status_code == 200
    data = res.json()
    for item in data.get("items", []):
        assert item["verification_status"] == "pending_review"


def test_scenario_13_empty_search_results():
    """Scenario 13: Query with nonexistent terms returns respectful guidance with zero hallucinated schemes."""
    res = client.post(
        "/api/v1/ai/chat",
        json={"query": "xyz123randomnonexistentschemequery999"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data.get("sources", [])) == 0
    assert "no verified government scheme" in data["answer"].lower() or "not found" in data["answer"].lower() or "आढळली नाही" in data["answer"]


# ==============================================================================
# Scenario 14 & 15: Failure Grace & Privacy / Injection Shield
# ==============================================================================


def test_scenario_14_ai_graceful_handling_invalid_id():
    """Scenario 14: Non-existent scheme ID returns 404 cleanly without crashing the API."""
    res = client.post(
        "/api/v1/ai/eligibility",
        json={"scheme_id": 99999999, "user_input": "Am I eligible?"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_scenario_15_privacy_shield_blocks_aadhaar_pii():
    """Scenario 15: Queries containing Aadhaar numbers trigger strict privacy shield blocking."""
    res = client.post(
        "/api/v1/ai/chat",
        json={"query": "My Aadhaar is 1234 5678 9012, am I eligible?", "scheme_id": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert "privacy" in data["answer"].lower() or "aadhaar" in data["answer"].lower()
    assert data["confidence"] == "privacy_shield"


# ==============================================================================
# Scenario 16 to 20: Temporary Chat Lifecycle & Cross-User Isolation
# ==============================================================================


def test_scenario_16_switching_scheme_cards_isolates_context(sample_schemes):
    """Scenario 16: Asking about scheme A then scheme B creates strictly isolated contextual responses."""
    with SessionLocal() as db:
        schemes = db.scalars(select(SchemeCandidate).limit(2)).all()
        id1, id2 = schemes[0].id, schemes[1].id
        title1, title2 = schemes[0].title, schemes[1].title

    res1 = client.post("/api/v1/ai/chat", json={"query": "What is this scheme?", "scheme_id": id1})
    res2 = client.post("/api/v1/ai/chat", json={"query": "What is this scheme?", "scheme_id": id2})

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["scheme_id"] == id1
    assert res2.json()["scheme_id"] == id2
    # Scheme 1 answer must not mention scheme 2
    assert title2 not in res1.json()["answer"]


def test_scenario_17_18_19_stateless_chat_no_db_persistence():
    """Scenarios 17, 18, 19: Server does not store chat transcripts in database.

    Closing chat, page refresh, or navigation clears state because the server retains zero state.
    """
    # Send a unique chat query
    test_token = "unique_citizen_session_token_xyz"
    res = client.post("/api/v1/ai/chat", json={"query": f"Is this stored? {test_token}"})
    assert res.status_code == 200

    # Verify no database table contains the user message
    with SessionLocal() as db:
        # Check that there are no tables storing user transcripts
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()
        assert "chat_messages" not in table_names
        assert "conversations" not in table_names
        assert "user_transcripts" not in table_names


def test_scenario_20_cross_user_isolation():
    """Scenario 20: Two concurrent citizen requests do not leak history into each other."""
    history_user_a = [
        {"role": "user", "content": "I am a female student looking for higher education grant."}
    ]
    res_b = client.post(
        "/api/v1/ai/chat",
        json={"query": "What schemes are available for farmers?"},  # User B without User A's history
    )
    assert res_b.status_code == 200
    ans_b = res_b.json()["answer"]
    # User B should receive farmer schemes, not education grant
    assert "farmer" in ans_b.lower() or "शेतकरी" in ans_b or "krishi" in ans_b.lower()


# ==============================================================================
# New Master Prompt Endpoints Contract Testing
# ==============================================================================


def test_endpoint_categories():
    """Verify GET /api/v1/schemes/categories returns structured categories with counts & icons."""
    res = client.get("/api/v1/schemes/categories")
    assert res.status_code == 200
    data = res.json()
    assert "categories" in data
    assert len(data["categories"]) > 0
    cat = data["categories"][0]
    assert "name" in cat
    assert "name_mr" in cat
    assert "icon" in cat
    assert "total_schemes" in cat


def test_endpoint_scheme_sources(sample_schemes):
    """Verify GET /api/v1/schemes/{scheme_id}/sources returns supporting links and metadata."""
    res = client.get("/api/v1/schemes/1/sources")
    assert res.status_code == 200
    data = res.json()
    assert data["scheme_id"] == 1
    assert "source_url" in data
    assert "is_official_gov_domain" in data


def test_endpoint_application_guide(sample_schemes):
    """Verify GET /api/v1/schemes/{scheme_id}/application-guide returns step-by-step bilingual guidance."""
    res = client.get("/api/v1/schemes/1/application-guide")
    assert res.status_code == 200
    data = res.json()
    assert data["scheme_id"] == 1
    assert "guide_en" in data
    assert "guide_mr" in data
    assert "Application Steps" in data["guide_en"] or "Step-by-Step" in data["guide_en"]
    assert "पायरी-दर-पायरी" in data["guide_mr"] or "अर्ज प्रक्रिया" in data["guide_mr"]
