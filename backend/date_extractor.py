"""Date, Deadline, and Scheme Change Extraction Engine for MahaSeva AI.

Analyzes text extracted from official Maharashtra Government web pages and PDFs
to detect:
- Application start dates and deadlines
- Deadline extensions (e.g. 'मुदतवाढ', 'extended up to')
- Absence of published deadlines ('no_deadline_published')
- Application modes (online, offline, both)
- Official application portal URLs
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.status_engine import (
    NO_DEADLINE_NOTICE_EN,
    NO_DEADLINE_NOTICE_MR,
    parse_flexible_date,
    parse_flexible_time,
)

# Date extraction regexes
DATE_PATTERNS = [
    # YYYY-MM-DD
    r"\b(20\d{2}[-/](?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01]))\b",
    # DD/MM/YYYY or DD-MM-YYYY
    r"\b((?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:20\d{2}))\b",
    # Marathi text: "31 मार्च 2026", "१५ ऑगस्ट २०२६"
    r"\b((?:0?[1-9]|[12]\d|3[01])\s*(?:जानेवारी|फेब्रुवारी|मार्च|एप्रिल|मे|जून|जुलै|ऑगस्ट|सप्टेंबर|ऑक्टोबर|नोव्हेंबर|डिसेंबर)\s*(?:20\d{2}))\b",
    # English text: "31 March 2026", "31st Dec 2026"
    r"\b((?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:20\d{2}))\b",
]

# Keywords indicating application deadline
DEADLINE_KEYWORDS_MR = [
    "अंतिम तारीख", "शेवटची तारीख", "मुदत", "अर्ज सादर करण्याची अंतिम तारीख",
    "मुदतवाढ", "शेवटचा दिनांक", "अंतिम मुदत", "नोंदणीची अंतिम तारीख"
]

DEADLINE_KEYWORDS_EN = [
    "last date", "deadline", "closing date", "apply before",
    "extended date", "end date", "application deadline", "last date of application",
    "extended up to", "submission deadline"
]

START_KEYWORDS_MR = [
    "सुरू होण्याची तारीख", "प्रारंभ दिनांक", "अर्ज सुरू", "सुरुवात", "नोंदणी सुरू"
]

START_KEYWORDS_EN = [
    "start date", "commencement date", "applications open", "registration begins",
    "opening date", "portal opens"
]

EXTENSION_KEYWORDS = [
    "मुदतवाढ", "तारीख वाढवली", "मुदत वाढविण्यात आली", "मुदतवाढ देण्यात आली",
    "extended", "extension", "date extended", "extended till", "extended up to"
]


def extract_dates_and_deadlines(text: str) -> Dict[str, Any]:
    """Extract start dates, deadlines, and extension notices from text.

    Returns:
        {
            "start_date": "YYYY-MM-DD" or None,
            "deadline_date": "YYYY-MM-DD" or None,
            "closing_time": "HH:MM:SS" or None,
            "is_extension": bool,
            "has_no_deadline": bool,
            "date_verification_status": "verified" | "no_deadline" | "date_unverified",
            "evidence": str
        }
    """
    if not text:
        return {
            "start_date": None,
            "deadline_date": None,
            "closing_time": None,
            "is_extension": False,
            "has_no_deadline": True,
            "date_verification_status": "no_deadline",
            "evidence": "",
        }

    sample = text[:25000]
    lines = [line.strip() for line in sample.splitlines() if line.strip()]

    start_date_val: Optional[str] = None
    deadline_date_val: Optional[str] = None
    closing_time_val: Optional[str] = None
    is_extension = False
    evidence_pieces: List[str] = []

    # Check for extension
    for ext_kw in EXTENSION_KEYWORDS:
        if ext_kw.lower() in sample.lower():
            is_extension = True
            break

    # Search line by line for contextual date keywords
    for line in lines:
        lower_line = line.lower()

        # Check deadline in line
        has_deadline_kw = any(kw in lower_line for kw in DEADLINE_KEYWORDS_EN) or any(kw in line for kw in DEADLINE_KEYWORDS_MR)
        if has_deadline_kw and not deadline_date_val:
            for pattern in DATE_PATTERNS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    parsed_d = parse_flexible_date(m.group(1))
                    if parsed_d:
                        deadline_date_val = parsed_d.isoformat()
                        evidence_pieces.append(f"Deadline found: '{line[:150]}'")
                        # Check closing time on the same line (e.g. 17:00 or 23:59)
                        time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?\s*(?:pm|am|hrs)?\b", line, re.IGNORECASE)
                        if time_match:
                            parsed_t = parse_flexible_time(time_match.group(0))
                            if parsed_t:
                                closing_time_val = parsed_t.isoformat()
                        break

        # Check start date in line
        has_start_kw = any(kw in lower_line for kw in START_KEYWORDS_EN) or any(kw in line for kw in START_KEYWORDS_MR)
        if has_start_kw and not start_date_val:
            for pattern in DATE_PATTERNS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    parsed_d = parse_flexible_date(m.group(1))
                    if parsed_d:
                        start_date_val = parsed_d.isoformat()
                        evidence_pieces.append(f"Start date found: '{line[:150]}'")
                        break

    # If no deadline explicitly matched with keyword, check general date occurrences
    # but only classify as date_unverified if date is unattached to deadline keyword
    date_verification_status = "verified"
    if not deadline_date_val:
        has_no_deadline = True
        date_verification_status = "no_deadline"
    else:
        has_no_deadline = False
        date_verification_status = "verified"

    return {
        "start_date": start_date_val,
        "deadline_date": deadline_date_val,
        "closing_time": closing_time_val,
        "is_extension": is_extension,
        "has_no_deadline": has_no_deadline,
        "date_verification_status": date_verification_status,
        "evidence": " | ".join(evidence_pieces),
    }


def extract_application_mode(text: str) -> str:
    """Detect whether scheme mode is online, offline, or both."""
    sample = text.lower()
    online_kw = ["online apply", "portal", "mahait", "mahadbt", "ऑनलाईन अर्ज", "ऑनलाइन अर्ज", "वेबसाईटवर अर्ज"]
    offline_kw = ["offline", "ग्रामपंचायत", "तहसीलदार", "ऑफलाईन अर्ज", "जिल्हा परिषद", "कार्यालयात अर्ज सादर"]

    has_online = any(k in sample for k in online_kw)
    has_offline = any(k in sample for k in offline_kw)

    if has_online and has_offline:
        return "both"
    if has_online:
        return "online"
    if has_offline:
        return "offline"
    return "online"


def extract_scheme_category(title: str, text: str, department: str) -> str:
    """Categorize scheme based on departmental scope and keywords."""
    combined = (title + " " + department + " " + text[:5000]).lower()

    if any(k in combined for k in ["krushi", "shetkari", "farmer", "agriculture", "शेतकरी", "कृषी", "पीक", "सिंचन"]):
        return "Agriculture & Farmers"
    if any(k in combined for k in ["social justice", "विशेष सहाय्य", "मागासवर्गीय", "divyang", "अपंग", "sanman", "pension"]):
        return "Social Justice & Special Assistance"
    if any(k in combined for k in ["urban", "नगर विकास", "smart city", "amrut", "महानगर"]):
        return "Urban Development"
    if any(k in combined for k in ["rural", "ग्राम विकास", "panchayat", "स्वच्छ भारत", "जलजीवन"]):
        return "Rural Development"
    if any(k in combined for k in ["education", "scholarship", "शिष्यवृत्ती", "विद्यार्थी", "school", "college"]):
        return "Education & Scholarships"
    if any(k in combined for k in ["women", "child", "ladki bahin", "महिला", "बाल विकास", "अंगणवाडी", "किशोरी"]):
        return "Women & Child Development"
    if any(k in combined for k in ["health", "aarogya", "आरोग्य", "रुग्णालय", "medical", "आयुष्मान"]):
        return "Public Health & Medicine"
    if any(k in combined for k in ["employment", "skill", "रोजगार", "कौशल्य", "उद्योजकता", "mudra"]):
        return "Skill Development & Employment"
    if any(k in combined for k in ["co-operation", "marketing", "textiles", "सहकार", "कापूस", "साखर"]):
        return "Co-operation & Textiles"

    return "General Citizen Welfare"
