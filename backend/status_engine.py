"""Centralized Application Deadline and Scheme Status Calculation Engine for MahaSeva AI.

Operates strictly in Asia/Kolkata timezone.
Determines authoritative application window states:
- 'upcoming': Verified window start date is in the future.
- 'open': Verified window started and deadline has not passed.
- 'closing_soon': Verified window open and deadline is within warning period (default 15 days).
- 'closed': Verified application deadline has passed.
- 'no_deadline_published': Official sources do not publish an application deadline.
- 'date_unverified': Dates were found but could not be verified.
- 'temporarily_unavailable': Officially reported as temporarily unavailable.
- 'discontinued': Authoritative source confirms discontinuation.

Provides deterministic status calculation that can be frozen with a test clock for reproducibility.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

# Standard bilingual notice when no official deadline is published
NO_DEADLINE_NOTICE_EN = "No application deadline published by the available official sources."
NO_DEADLINE_NOTICE_MR = "उपलब्ध अधिकृत स्रोतांमध्ये अर्जाची अंतिम तारीख नमूद केलेली नाही."

CLOSING_SOON_THRESHOLD_DAYS = 15

MARATHI_MONTHS = {
    "जानेवारी": 1, "फेब्रुवारी": 2, "मार्च": 3, "एप्रिल": 4,
    "मे": 5, "जून": 6, "जुलै": 7, "ऑगस्ट": 8,
    "सप्टेंबर": 9, "ऑक्टोबर": 10, "नोव्हेंबर": 11, "डिसेंबर": 12
}

ENGLISH_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_mock_clock: Optional[datetime] = None


def set_mock_clock(dt: Optional[datetime]) -> None:
    """Set a fixed clock for reproducible date-boundary testing."""
    global _mock_clock
    if dt is not None and dt.tzinfo is None:
        _mock_clock = dt.replace(tzinfo=KOLKATA_TZ)
    else:
        _mock_clock = dt


def get_current_kolkata_time() -> datetime:
    """Return current datetime in Asia/Kolkata timezone (or mock clock if active)."""
    if _mock_clock is not None:
        return _mock_clock
    return datetime.now(KOLKATA_TZ)


def parse_flexible_date(date_str: Optional[str]) -> Optional[date]:
    """Parse flexible date strings (ISO, DD/MM/YYYY, DD-MM-YYYY, or textual) safely."""
    if not date_str:
        return None
    cleaned = date_str.strip().lower()
    if not cleaned:
        return None

    # Try ISO YYYY-MM-DD
    iso_match = re.search(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b", cleaned)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # Try DD/MM/YYYY or DD-MM-YYYY
    dmy_match = re.search(r"\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.](20\d{2})\b", cleaned)
    if dmy_match:
        try:
            return date(int(dmy_match.group(3)), int(dmy_match.group(2)), int(dmy_match.group(1)))
        except ValueError:
            pass

    # Try Marathi textual: e.g. "31 मार्च 2026"
    for m_name, m_num in MARATHI_MONTHS.items():
        if m_name in cleaned:
            m_match = re.search(rf"\b(0?[1-9]|[12]\d|3[01])\s*{re.escape(m_name)}\s*(20\d{{2}})\b", cleaned)
            if m_match:
                try:
                    return date(int(m_match.group(2)), m_num, int(m_match.group(1)))
                except ValueError:
                    pass

    # Try English textual: e.g. "31st March 2026", "15 Dec 2026"
    for e_name, e_num in ENGLISH_MONTHS.items():
        if e_name in cleaned:
            e_match = re.search(rf"\b(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+{re.escape(e_name)}[a-z]*\s+(20\d{{2}})\b", cleaned)
            if e_match:
                try:
                    return date(int(e_match.group(2)), e_num, int(e_match.group(1)))
                except ValueError:
                    pass

    return None


def parse_flexible_time(time_str: Optional[str]) -> Optional[time]:
    """Parse time string like HH:MM:SS or HH:MM safely."""
    if not time_str:
        return None
    cleaned = time_str.strip()
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?\b", cleaned)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        s = int(match.group(3)) if match.group(3) else 0
        return time(h, m, s)
    return None


def calculate_window_status(
    start_date_str: Optional[str],
    deadline_date_str: Optional[str],
    closing_time_str: Optional[str] = None,
    date_verification_status: str = "verified",
    override_status: Optional[str] = None,
    warning_period_days: int = CLOSING_SOON_THRESHOLD_DAYS,
) -> Tuple[str, Dict[str, Any]]:
    """Authoritative calculation of application window status.

    Returns:
        (status_code, details_dict)
    """
    now = get_current_kolkata_time()

    if override_status in ("temporarily_unavailable", "discontinued"):
        return override_status, {
            "status": override_status,
            "reason": f"Scheme status overridden to {override_status}",
            "calculated_at": now.isoformat(),
        }

    if date_verification_status == "date_unverified":
        return "date_unverified", {
            "status": "date_unverified",
            "reason": "Application dates found but could not be reliably verified.",
            "calculated_at": now.isoformat(),
        }

    start_d = parse_flexible_date(start_date_str)
    deadline_d = parse_flexible_date(deadline_date_str)

    # If no deadline published
    if not deadline_d:
        # If there is a future start date, it is upcoming
        if start_d:
            start_dt = datetime.combine(start_d, time(0, 0, 0), tzinfo=KOLKATA_TZ)
            if now < start_dt:
                return "upcoming", {
                    "status": "upcoming",
                    "start_date": start_d.isoformat(),
                    "deadline_date": None,
                    "days_until_start": (start_dt.date() - now.date()).days,
                    "calculated_at": now.isoformat(),
                }
        return "no_deadline_published", {
            "status": "no_deadline_published",
            "start_date": start_d.isoformat() if start_d else None,
            "deadline_date": None,
            "notice_en": NO_DEADLINE_NOTICE_EN,
            "notice_mr": NO_DEADLINE_NOTICE_MR,
            "calculated_at": now.isoformat(),
        }

    # Deadline exists - calculate closing datetime conservatively in Asia/Kolkata
    closing_t = parse_flexible_time(closing_time_str)
    if closing_t is None:
        # Conservative: end of stated deadline day
        closing_t = time(23, 59, 59, 999000)

    closing_dt = datetime.combine(deadline_d, closing_t, tzinfo=KOLKATA_TZ)

    # Check start date if present
    if start_d:
        start_dt = datetime.combine(start_d, time(0, 0, 0), tzinfo=KOLKATA_TZ)
        if now < start_dt:
            days_left = (start_dt.date() - now.date()).days
            return "upcoming", {
                "status": "upcoming",
                "start_date": start_d.isoformat(),
                "deadline_date": deadline_d.isoformat(),
                "closing_time": closing_t.isoformat(),
                "days_until_start": days_left,
                "calculated_at": now.isoformat(),
            }

    # Has deadline passed?
    if now > closing_dt:
        return "closed", {
            "status": "closed",
            "start_date": start_d.isoformat() if start_d else None,
            "deadline_date": deadline_d.isoformat(),
            "closing_time": closing_t.isoformat(),
            "closed_since": (now.date() - deadline_d).days,
            "calculated_at": now.isoformat(),
        }

    # Within deadline: open or closing_soon
    time_left = closing_dt - now
    days_left = time_left.days
    is_closing_soon = days_left <= warning_period_days

    st = "closing_soon" if is_closing_soon else "open"
    return st, {
        "status": st,
        "start_date": start_d.isoformat() if start_d else None,
        "deadline_date": deadline_d.isoformat(),
        "closing_time": closing_t.isoformat(),
        "days_remaining": days_left,
        "is_closing_soon": is_closing_soon,
        "calculated_at": now.isoformat(),
    }


def get_status_labels(status_code: str) -> Dict[str, str]:
    """Return accessible bilingual labels for application status."""
    labels = {
        "open": {
            "en": "Applications Open Now",
            "mr": "अर्ज सुरू आहेत",
            "badge_class": "status-open",
        },
        "closing_soon": {
            "en": "Closing Soon",
            "mr": "लवकरच संपत आहे",
            "badge_class": "status-closing-soon",
        },
        "upcoming": {
            "en": "Upcoming",
            "mr": "लवकरच सुरू होणार",
            "badge_class": "status-upcoming",
        },
        "closed": {
            "en": "Application Closed",
            "mr": "अर्ज मुदत संपली",
            "badge_class": "status-closed",
        },
        "no_deadline_published": {
            "en": "No Published Deadline",
            "mr": "अंतिम तारीख नमूद नाही",
            "badge_class": "status-no-deadline",
        },
        "date_unverified": {
            "en": "Dates Unverified",
            "mr": "तारीख पडताळणी बाकी",
            "badge_class": "status-unverified",
        },
        "temporarily_unavailable": {
            "en": "Temporarily Unavailable",
            "mr": "तात्पुरते अनुपलब्ध",
            "badge_class": "status-unavailable",
        },
        "discontinued": {
            "en": "Discontinued",
            "mr": "योजना बंद करण्यात आली आहे",
            "badge_class": "status-discontinued",
        },
    }
    return labels.get(
        status_code,
        {
            "en": status_code.replace("_", " ").title(),
            "mr": status_code,
            "badge_class": "status-default",
        },
    )
