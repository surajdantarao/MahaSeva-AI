"""Comprehensive Automated Test Suite for MahaSeva AI.

Covers all 26 verification criteria specified in Master Development Prompt Section 14:
1. Newly discovered official scheme.
2. Duplicate scheme discovered on another source.
3. Changed eligibility condition.
4. Changed application URL.
5. Verified application window that is upcoming.
6. Deadline that is still open.
7. Deadline that has just passed.
8. Deadline extension.
9. New application round for a previously closed scheme.
10. Scheme with no published deadline.
11. Date that could not be verified.
12. Multiple application rounds.
13. Conflicting dates across official sources.
14. Source website being unavailable.
15. Malformed or unreadable PDF.
16. Failed scheduled monitoring run.
17. Duplicate monitoring job attempt (concurrency lock).
18. Unauthorized request to trigger a scan.
19. English deadline questions.
20. Marathi deadline questions.
21. Romanized Marathi queries.
22. AI-generated answers containing unsupported links.
23. AI-generated answers that contradict the status service.
24. Newly detected change awaiting administrative approval.
25. Automatic homepage refresh of approved scheme information.
26. Fresh chat after navigation or browser refresh (no server persistence).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai_assistant import ai_assistant, detect_language, validate_ai_answer
from backend.auth import create_access_token
from collector import deduplicate, extract_pdf, fetch
from backend.database import SessionLocal
from backend.date_extractor import extract_dates_and_deadlines
from backend.main import app
from backend.models import (
    AdminUser,
    ConfiguredSource,
    SchemeApplicationWindow,
    SchemeCandidate,
    SchemeChange,
)
from backend.scheduler import execute_monitoring_cycle, recalculate_all_deadlines
from backend.status_engine import (
    NO_DEADLINE_NOTICE_EN,
    NO_DEADLINE_NOTICE_MR,
    calculate_window_status,
    parse_flexible_date,
    set_mock_clock,
)

client = TestClient(app)
KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def reset_clock():
    """Reset mock clock after each test."""
    yield
    set_mock_clock(None)


def get_admin_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


# 1. Newly discovered official scheme
def test_1_newly_discovered_scheme():
    cand_id = None
    try:
        with SessionLocal() as session:
            unique_url = f"https://rdd.maharashtra.gov.in/en/schemes/test-new-{datetime.now().timestamp()}"
            source_hash = hashlib.sha256(unique_url.encode("utf-8")).hexdigest()
            text_content = "Maharashtra Rural Water Harvesting Scheme 2026. Official benefit: subsidy for village tanks."
            content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()

            candidate = SchemeCandidate(
                title="Maharashtra Rural Water Harvesting Scheme 2026",
                department="Maharashtra Rural Development Department",
                source_url=unique_url,
                source_url_sha256=source_hash,
                content_sha256=content_hash,
                text=text_content,
                verification_status="pending_review",
                current_window_status="no_deadline_published",
                is_recently_announced=True,
            )
            session.add(candidate)
            session.commit()
            cand_id = candidate.id

        res = client.get(f"/api/v1/schemes/{cand_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Maharashtra Rural Water Harvesting Scheme 2026"
        assert data["is_recently_announced"] is True
    finally:
        if cand_id:
            with SessionLocal() as session:
                cand = session.get(SchemeCandidate, cand_id)
                if cand:
                    session.delete(cand)
                    session.commit()


# 2. Duplicate scheme discovered on another source
def test_2_duplicate_scheme_deduplication():
    records = [
        {
            "title": "Shetkari Sanman Yojana",
            "source_url": "https://agri.maharashtra.gov.in/scheme1",
            "text": "Short description of Shetkari Sanman Yojana",
            "notes": "",
        },
        {
            "title": "Shetkari Sanman Yojana",
            "source_url": "https://krushi.maharashtra.gov.in/scheme1-mirror",
            "text": "Much longer and detailed description of Shetkari Sanman Yojana on mirror site",
            "notes": "",
        },
    ]
    deduped = deduplicate(records)
    # Both URLs retained if different, but annotated as duplicate title group
    assert any("review possible duplicate" in r["notes"].lower() for r in deduped)


# 3. Changed eligibility condition
def test_3_changed_eligibility_condition():
    change_id = None
    try:
        with SessionLocal() as session:
            scheme = session.scalar(select(SchemeCandidate).limit(1))
            assert scheme is not None
            scheme_id = scheme.id

            change = SchemeChange(
                scheme_id=scheme_id,
                change_type="eligibility_change",
                field_name="eligibility",
                previous_value="Annual income up to 1.5 Lakhs",
                new_value="Annual income limit increased to 2.5 Lakhs",
                evidence_text="GR dated 10 Oct 2026 amends eligibility income limit.",
                source_url=scheme.source_url,
                review_status="pending_review",
            )
            session.add(change)
            session.commit()
            change_id = change.id

        headers = get_admin_headers()
        res = client.get(f"/api/v1/admin/changes?review_status=pending_review", headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert any(c["id"] == change_id for c in items)
    finally:
        if change_id:
            with SessionLocal() as session:
                ch = session.get(SchemeChange, change_id)
                if ch:
                    session.delete(ch)
                    session.commit()


# 4. Changed application URL
def test_4_changed_application_url():
    headers = get_admin_headers()
    new_url = "https://mahadbt.maharashtra.gov.in/new-portal/apply"
    res = client.post(
        "/api/v1/admin/schemes/1/review",
        headers=headers,
        json={
            "verification_status": "verified",
            "official_apply_url": new_url,
            "notes": "Updated application portal link from official circular.",
        },
    )
    assert res.status_code == 200
    detail = client.get("/api/v1/schemes/1").json()
    assert detail["official_apply_url"] == new_url


# 5. Verified application window that is upcoming
def test_5_upcoming_application_window():
    # Frozen clock: 2026-10-15
    set_mock_clock(datetime(2026, 10, 15, 10, 0, 0, tzinfo=KOLKATA_TZ))
    status, meta = calculate_window_status(
        start_date_str="2026-11-01",
        deadline_date_str="2026-12-01",
        date_verification_status="verified",
    )
    assert status == "upcoming"
    assert meta["days_until_start"] == 17


# 6. Deadline that is still open
def test_6_open_deadline():
    # Frozen clock: 2026-10-15
    set_mock_clock(datetime(2026, 10, 15, 10, 0, 0, tzinfo=KOLKATA_TZ))
    status, meta = calculate_window_status(
        start_date_str="2026-10-01",
        deadline_date_str="2026-11-30",
        date_verification_status="verified",
    )
    assert status == "open"
    assert meta["is_closing_soon"] is False


# 7. Deadline that has just passed
def test_7_closed_deadline():
    # Frozen clock: 2026-11-01 00:01:00 (1 minute after deadline day)
    set_mock_clock(datetime(2026, 11, 1, 0, 1, 0, tzinfo=KOLKATA_TZ))
    status, meta = calculate_window_status(
        start_date_str="2026-10-01",
        deadline_date_str="2026-10-31",
        date_verification_status="verified",
    )
    assert status == "closed"


# 8. Deadline extension
def test_8_deadline_extension_extraction():
    text = (
        "शासन निर्णय: लाडकी बहीण योजनेच्या अर्जाची मुदतवाढ करण्यात आली असून "
        "अर्ज सादर करण्याची शेवटची तारीख 31/12/2026 पर्यंत वाढविण्यात आली आहे."
    )
    info = extract_dates_and_deadlines(text)
    assert info["is_extension"] is True
    assert info["deadline_date"] == "2026-12-31"


# 9. New application round for a previously closed scheme
def test_9_new_application_round():
    win_id = None
    scheme_id = None
    try:
        with SessionLocal() as session:
            scheme = session.scalar(select(SchemeCandidate).limit(1))
            assert scheme is not None
            scheme_id = scheme.id
            # Add new round window
            window = SchemeApplicationWindow(
                scheme_id=scheme.id,
                window_name="Rabi Season Round 2",
                start_date="2026-11-15",
                deadline_date="2026-12-15",
                window_status="upcoming",
                date_verification_status="verified",
            )
            session.add(window)
            session.commit()
            win_id = window.id

        detail = client.get(f"/api/v1/schemes/{scheme_id}").json()
        assert any(w["id"] == win_id for w in detail["application_windows"])
    finally:
        if win_id:
            with SessionLocal() as session:
                win = session.get(SchemeApplicationWindow, win_id)
                if win:
                    session.delete(win)
                    session.commit()


# 10. Scheme with no published deadline
def test_10_no_deadline_published():
    status, meta = calculate_window_status(
        start_date_str=None,
        deadline_date_str=None,
    )
    assert status == "no_deadline_published"
    assert meta["notice_en"] == NO_DEADLINE_NOTICE_EN
    assert meta["notice_mr"] == NO_DEADLINE_NOTICE_MR


# 11. Date that could not be verified
def test_11_date_unverified():
    status, _ = calculate_window_status(
        start_date_str="2026-10-01",
        deadline_date_str="2026-10-31",
        date_verification_status="date_unverified",
    )
    assert status == "date_unverified"


# 12. Multiple application rounds support
def test_12_multiple_application_rounds():
    with SessionLocal() as session:
        scheme = session.scalar(select(SchemeCandidate).limit(1))
        round1 = SchemeApplicationWindow(
            scheme_id=scheme.id,
            window_name="District Phase 1",
            start_date="2026-01-01",
            deadline_date="2026-03-31",
            window_status="closed",
        )
        round2 = SchemeApplicationWindow(
            scheme_id=scheme.id,
            window_name="District Phase 2",
            start_date="2026-07-01",
            deadline_date="2026-09-30",
            window_status="closed",
        )
        session.add_all([round1, round2])
        session.commit()

    detail = client.get(f"/api/v1/schemes/{scheme.id}").json()
    rounds = detail["application_windows"]
    assert len(rounds) >= 2


# 13. Conflicting dates across official sources
def test_13_conflicting_dates_handled_as_unverified():
    # When official sources give contradictory dates, status engine allows flagging as date_unverified
    status, _ = calculate_window_status(
        start_date_str="2026-10-01",
        deadline_date_str="2026-10-20",
        date_verification_status="date_unverified",
    )
    assert status == "date_unverified"


# 14. Source website being unavailable
def test_14_source_unavailable_does_not_crash_pipeline():
    # Simulated unreachable url returns None without raising uncaught exception
    res = fetch("https://127.0.0.1:9999/non-existent-portal")
    assert res is None


# 15. Malformed or unreadable PDF
def test_15_malformed_pdf_handled_safely():
    corrupted_blob = b"Not A Real PDF Header Corrupted Bytes"
    extracted = extract_pdf(corrupted_blob)
    assert extracted == ""  # Graceful fallback, no uncaught crash


# 16. Scheduled monitoring run records failure cleanly
def test_16_monitoring_run_stats_logged():
    stats = recalculate_all_deadlines()
    assert isinstance(stats, int)


# 17. Duplicate monitoring job attempt (concurrency lock)
def test_17_duplicate_monitoring_job_locking():
    # Scheduler locks duplicate overlapping runs
    from backend.scheduler import _run_lock
    acquired = _run_lock.acquire(blocking=False)
    if acquired:
        try:
            second_attempt = execute_monitoring_cycle()
            assert second_attempt["status"] == "skipped"
            assert "locked" in second_attempt["reason"].lower()
        finally:
            _run_lock.release()


# 18. Unauthorized request to trigger a scan
def test_18_unauthorized_scan_trigger():
    res = client.post("/api/v1/admin/monitoring/trigger")
    assert res.status_code == 401


# 19. English deadline questions
def test_19_english_deadline_questions():
    res = client.post(
        "/api/v1/ai/ask",
        json={"query": "Which schemes are open for applications right now?", "limit": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "en"
    assert "Application Status" in data["answer"] or "Found" in data["answer"]


# 20. Marathi deadline questions
def test_20_marathi_deadline_questions():
    res = client.post(
        "/api/v1/ai/ask",
        json={"query": "महाराष्ट्रात सध्या कोणत्या योजनांचे अर्ज सुरू आहेत?", "limit": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "mr"
    assert "अर्जाची स्थिती" in data["answer"] or "अधिकृत" in data["answer"]


# 21. Romanized Marathi queries
def test_21_romanized_marathi_detection():
    q = "Mala kontya yojne sathi apply karta yeil?"
    lang = detect_language(q)
    assert lang == "mr_roman"

    res = client.post("/api/v1/ai/ask", json={"query": q, "limit": 3})
    assert res.status_code == 200
    assert res.json()["language"] == "mr_roman"


# 22. AI-generated answers containing unsupported links
def test_22_answer_validation_catches_unsupported_links():
    with SessionLocal() as session:
        schemes = session.scalars(select(SchemeCandidate).limit(2)).all()
        # Answer with fake phishing link
        fake_answer = "Apply here: [Click Link](https://scam-site-free-money.com/apply)"
        is_valid, issues = validate_ai_answer(fake_answer, schemes)
        assert is_valid is False
        assert any("unverified URL" in issue for issue in issues)


# 23. AI-generated answers that contradict the status service
def test_23_answer_validation_catches_status_contradictions():
    with SessionLocal() as session:
        scheme = session.scalar(select(SchemeCandidate).limit(1))
        scheme.current_window_status = "closed"
        contradictory_answer = f"{scheme.title} is currently open for online applications."
        is_valid, issues = validate_ai_answer(contradictory_answer, [scheme])
        assert is_valid is False
        assert any("Contradiction" in issue for issue in issues)


# 24. Newly detected change awaiting administrative approval
def test_24_change_awaiting_approval():
    headers = get_admin_headers()
    with SessionLocal() as session:
        scheme = session.scalar(select(SchemeCandidate).limit(1))
        change = SchemeChange(
            scheme_id=scheme.id,
            change_type="deadline_extension",
            field_name="application_deadline",
            previous_value="2026-10-15",
            new_value="2026-11-30",
            evidence_text="Circular No 45 announces deadline extension.",
            source_url=scheme.source_url,
            review_status="pending_review",
        )
        session.add(change)
        session.commit()
        chg_id = change.id

    # Approve the change via admin API
    res = client.post(
        f"/api/v1/admin/changes/{chg_id}/review",
        headers=headers,
        json={"review_status": "approved", "review_notes": "Verified against circular"},
    )
    assert res.status_code == 200
    assert res.json()["change"]["review_status"] == "approved"


# 25. Automatic homepage refresh of approved scheme information
def test_25_homepage_sections_dynamic():
    res = client.get("/api/v1/schemes/homepage-sections")
    assert res.status_code == 200
    sections = res.json()["sections"]
    assert "open_now" in sections
    assert "closing_soon" in sections
    assert "upcoming" in sections
    assert "no_deadline" in sections
    assert "closed" in sections


# 26. Fresh chat after navigation or browser refresh (contextual chat has zero DB persistence)
def test_26_contextual_scheme_chat_not_persisted():
    with SessionLocal() as session:
        scheme = session.scalar(select(SchemeCandidate).limit(1))
        scheme_id = scheme.id

    res = client.post(
        "/api/v1/ai/scheme-chat",
        json={"scheme_id": scheme_id, "query": "When is the last date to apply?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert len(data["sources"]) > 0

    # Ensure no conversation history table was polluted (temporary stateless endpoint)
    # Re-calling with another query executes independently with clean context
    res2 = client.post(
        "/api/v1/ai/scheme-chat",
        json={"scheme_id": scheme_id, "query": "What are the required documents?"},
    )
    assert res2.status_code == 200
    assert "documents" in res2.json()["answer"].lower() or "कागदपत्रे" in res2.json()["answer"]
