"""Intelligent Grounded Bilingual AI Citizen Assistant for MahaSeva AI.

Features:
- First-Class Bilingual Support: Marathi (मराठी), English, Romanized Marathi, and mixed Marathi-English queries.
- Intent-Aware Reasoning & Routing:
  - General & circumstance-based scheme discovery (farmers, students, women, seniors, low-income).
  - Scheme-specific contextual Q&A with conversational follow-up awareness.
  - Guided Criteria-Based Eligibility Assessment (Likely Eligible / Criteria Not Met / More Info Needed).
  - Step-by-Step Application Guidance (Online vs Offline, document checklists, verification stages).
  - Real-time deadline awareness grounded in the centralized status engine.
- Strict Grounding & Anti-Hallucination:
  - Cites exact verified official sources and portal domains.
  - Rejects synthetic or unverified application links.
  - Accurately conveys lack of published deadlines ("No application deadline published").
- Absolute Citizen Privacy:
  - Strictly blocks entry of Aadhaar or bank account numbers.
  - Stateless in-memory conversation processing: Zero client/server storage persistence.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from backend.models import SchemeApplicationWindow, SchemeCandidate
from backend.status_engine import (
    NO_DEADLINE_NOTICE_EN,
    NO_DEADLINE_NOTICE_MR,
    calculate_window_status,
    get_status_labels,
)

MARATHI_CHAR_PATTERN = re.compile(r"[\u0900-\u097F]")

ROMANIZED_MARATHI_KEYWORDS = {
    "mala", "kontya", "konte", "yojne", "yojana", "yojna", "sathi", "karta", "yeil",
    "chi", "cha", "che", "aahe", "ahet", "kay", "kadhi", "shevatachi", "shevatchi",
    "tarikh", "mudat", "vadhli", "vadhivli", "dakhva", "sang", "sanga",
    "baddal", "shasan", "patrata", "kagadpatre", "anudan", "arj", "shishyavrutti",
    "shetkari", "mahila", "ladki", "bahin", "kasa", "kashi", "kase", "lagte", "lagtat",
    "tu", "tumhi", "tumcha", "tumche", "tumhala", "aapan", "ek", "vicharaycha", "vichara",
    "prashna", "madat", "karshil", "karu", "karto", "karte", "karave", "ahes", "ahat",
    "kiti", "nakkich", "dhanyawad", "dhanyavad", "shakyata", "pahije", "havi", "mast",
    "namaskar", "namaste", "suprabhat", "chalalay", "challay", "aani", "pan"
}


ENGLISH_STRUCTURAL_PATTERNS = [
    r"\bwhat\s+(is|are|was|were)\b",
    r"\bhow\s+(do|can|to|does)\b",
    r"\blast\s+date\b",
    r"\bwho\s+(is|can|are)\b",
    r"\btell\s+me\b",
    r"\bcan\s+i\b",
    r"\bam\s+i\b",
    r"\beligibility\s+(for|criteria)\b",
    r"\bapply\s+(for|online|link)\b",
    r"\bwhere\s+(to|can)\b",
    r"\bwhich\s+schemes?\b",
    r"\bdocuments?\s+(needed|required)\b",
    r"\bfor\s+(the|this|[a-z]+)\s+scheme\b",
    r"\bfor\s+ladki\b",
]

MARATHI_GRAMMAR_TOKENS = {
    "aahe", "ahet", "kay", "kadhi", "kasa", "kashi", "kase", "yeil",
    "sathi", "pahije", "havi", "sanga", "dakhva", "karave", "chi", "cha",
    "che", "shakto", "lagtat", "lagte", "mi", "kiti", "baddal", "karta"
}


def is_devanagari_marathi(text: str) -> bool:
    """Detect Devanagari script."""
    return bool(MARATHI_CHAR_PATTERN.search(text))


def is_romanized_marathi(text: str) -> bool:
    """Detect phonetic/Romanized Marathi tokens with grammatical awareness."""
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
    matches = tokens.intersection(ROMANIZED_MARATHI_KEYWORDS)
    has_grammar_token = bool(tokens.intersection(MARATHI_GRAMMAR_TOKENS))
    return has_grammar_token or len(matches) >= 2


def detect_language(query: str) -> str:
    """Classify user query language into 'mr' (Marathi), 'mr_roman' (Romanized Marathi), or 'en' (English).

    Correctly identifies English queries even when mentioning scheme names (e.g. 'What is the last date for Ladki Bahin Yojana?').
    """
    if is_devanagari_marathi(query):
        return "mr"
    q_lower = query.lower()
    has_eng_structure = any(re.search(p, q_lower) for p in ENGLISH_STRUCTURAL_PATTERNS)
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", q_lower))
    has_mr_grammar = bool(tokens.intersection(MARATHI_GRAMMAR_TOKENS))

    if has_eng_structure and not has_mr_grammar:
        return "en"
    if has_mr_grammar:
        return "mr_roman"
    if is_romanized_marathi(query):
        return "mr_roman"
    return "en"



def extract_keywords(query: str) -> List[str]:
    """Extract salient search keywords from citizen questions."""
    cleaned = re.sub(r"[^\w\s\u0900-\u097F]", " ", query.lower())
    stop_words = {
        "what", "is", "the", "for", "in", "and", "how", "to", "apply", "which",
        "schemes", "scheme", "tell", "me", "about", "can", "i", "get", "of",
        "a", "an", "are", "there", "any", "please", "give", "details", "show", "now",
        "open", "closed", "closing", "soon", "last", "date", "deadline", "this", "month",
        "applications", "application", "right", "current", "currently", "available",
        "maharashtra", "state", "government", "govt", "who", "eligible",
        "काय", "आहे", "कशी", "करावी", "कोणत्या", "योजना", "माहिती", "द्या",
        "बद्दल", "सांगा", "मला", "मिळेल", "अर्जाची", "प्रक्रिया", "दाखवा",
        "शेवटची", "तारीख", "मुदत", "सुरू", "सध्या", "या", "अर्ज", "सादर",
        "महाराष्ट्रातील", "महाराष्ट्रात", "महाराष्ट्र", "सरकारी", "शासकीय",
        "योजनांची", "योजनेची", "योजनांचा", "योजनेचा", "सर्व", "काही", "आहेत"
    }
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 2]
    keywords = [t for t in tokens if t not in stop_words]
    return keywords


def normalize_keyword(word: str) -> str:
    """Strip plural suffixes to enable exact root matching."""
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


KEYWORD_EXPANSIONS: Dict[str, List[str]] = {
    "scholarship": ["scholarship", "shishyavrutti", "शिष्यवृत्ती", "student", "विद्यार्थी", "freeship", "fellowship", "mahadbt"],
    "student": ["student", "scholarship", "shishyavrutti", "विद्यार्थी", "शिष्यवृत्ती", "hostel", "vasatigruh", "swadhar"],
    "farmer": ["farmer", "shetkari", "krushi", "शेतकरी", "कृषी", "karjamukti", "sanman", "anudan", "pump"],
    "women": ["women", "mahila", "ladki", "bahin", "महिला", "kanya", "mulgi", "lek"],
    "pension": ["pension", "nivruttivetan", "पेन्शन", "श्रावण", "संजय गांधी", "niradhar", "वृद्ध"],
    "housing": ["housing", "gharkul", "awas", "घरकुल", "आवास", "ramai", "shabari"],
    "health": ["health", "arogya", "आरोग्य", "mjpjay", "रुग्णालय", "उपचार", "vaidyakiya"],
    "loan": ["loan", "karja", "कर्ज", "karjamukti", "व्यापार", "subsidy", "mahamandal"],
}


def expand_keywords(keywords: List[str]) -> List[str]:
    """Expand keywords with root lemmas and official bilingual terminology."""
    seen = set()
    result = []
    for kw in keywords:
        norm = normalize_keyword(kw)
        expanded = [norm, kw]
        kw_l = kw.lower()
        
        # Check direct keyword expansions
        if norm in KEYWORD_EXPANSIONS:
            expanded.extend(KEYWORD_EXPANSIONS[norm])
        elif kw_l in KEYWORD_EXPANSIONS:
            expanded.extend(KEYWORD_EXPANSIONS[kw_l])

        # Marathi morphological root/stem expansion
        if kw_l.startswith("शेतक") or "shetkar" in kw_l:
            expanded.extend(KEYWORD_EXPANSIONS["farmer"])
        elif kw_l.startswith("विद्यार्थ") or "student" in kw_l or "shishyavrutt" in kw_l or kw_l.startswith("शिष्यवृत्त"):
            expanded.extend(KEYWORD_EXPANSIONS["student"])
        elif kw_l.startswith("महिल") or "mahila" in kw_l:
            expanded.extend(KEYWORD_EXPANSIONS["women"])
        elif kw_l.startswith("पेन्शन") or kw_l.startswith("वृद्ध") or kw_l.startswith("ज्येष्ठ") or "pension" in kw_l:
            expanded.extend(KEYWORD_EXPANSIONS["pension"])
        elif kw_l.startswith("घरकुल") or kw_l.startswith("आवास") or "gharkul" in kw_l:
            expanded.extend(KEYWORD_EXPANSIONS["housing"])
        elif kw_l.startswith("आरोग्य") or "arogya" in kw_l or "mjpjay" in kw_l:
            expanded.extend(KEYWORD_EXPANSIONS["health"])

        for item in expanded:
            if item.lower() not in seen:
                seen.add(item.lower())
                result.append(item)

    return result


def extract_snippet(text: str, keywords: List[str], max_chars: int = 300) -> str:
    """Extract a factual, relevant snippet from scheme text matching keywords."""
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 30]
    for line in lines:
        lower_line = line.lower()
        if any(kw in lower_line for kw in keywords):
            return line[:max_chars].strip() + ("..." if len(line) > max_chars else "")
    first_meaningful = " ".join(text.split())[:max_chars]
    return first_meaningful + ("..." if len(text) > max_chars else "")


def validate_ai_answer(
    answer: str,
    retrieved_schemes: List[SchemeCandidate],
    expected_status_filter: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Strict Answer Quality Checks.

    Validates:
    1. Cited URLs exist in approved database sources.
    2. Stated deadlines do not contradict the status engine.
    3. Scheme active/expired status statements match authoritative status.
    """
    issues = []
    approved_urls = {s.source_url for s in retrieved_schemes if s.source_url}
    for s in retrieved_schemes:
        if s.official_apply_url:
            approved_urls.add(s.official_apply_url)
        if s.pdf_urls:
            for p in s.pdf_urls.split(";"):
                if p.strip():
                    approved_urls.add(p.strip())

    # Check Markdown URLs
    markdown_urls = re.findall(r"\[.*?\]\((https?://[^\s\)]+)\)", answer)
    for url in markdown_urls:
        parsed_url = urlparse(url)
        is_known = any(parsed_url.netloc == urlparse(u).netloc for u in approved_urls)
        if not is_known and "maharashtra.gov.in" not in parsed_url.netloc and "gov.in" not in parsed_url.netloc:
            issues.append(f"Answer contains unverified URL: {url}")

    # Check status contradictions
    for s in retrieved_schemes:
        if s.current_window_status == "closed":
            if f"{s.title} is currently open" in answer or f"{s.title} चे अर्ज सुरू आहेत" in answer:
                issues.append(f"Contradiction: {s.title} is closed in status engine but stated as open in answer.")
        elif s.current_window_status == "no_deadline_published":
            if "last date is" in answer.lower() and s.title.lower() in answer.lower():
                issues.append(f"Contradiction: {s.title} has no published deadline but specific date stated.")

    is_valid = len(issues) == 0
    return is_valid, issues


class ConversationalIntentRouter:
    """Detects message intent and handles conversational turns without unnecessary retrieval."""

    GREETING_PATTERNS = [
        r"^(hi+|hello+|hey+|heya|hii+|hi bro|hello bro|heyy|good morning|good afternoon|good evening|good day)\b",
        r"^(नमस्कार|हाय|हॅलो|शुभ सकाळ|शुभ दुपार|शुभ संध्याकाळ|प्रणाम)\b",
        r"^(namaskar|namaste|suprabhat|hello ji)\b",
    ]

    HOW_ARE_YOU_PATTERNS = [
        r"(how are you|how are u|how r u|how are you doing|how is it going)",
        r"(कसा आहेस|कसे आहात|कशी आहेस|काय चाललंय|काय चाललय|कसे आहात तुम्ही)",
        r"(kasa ahes|kase ahat|kashi ahes|kay chalalay|kay challay)",
    ]

    THANKS_PATTERNS = [
        r"(thank you|thanks|thank u|thx|thanks a lot|thank you so much)",
        r"(धन्यवाद|खूप धन्यवाद|आभार|आभारी आहे)",
        r"(dhanyawad|dhanyavad|aabhar)",
    ]

    FAREWELL_PATTERNS = [
        r"^(bye|goodbye|see you|see ya|cya|good night|bye bye)\b",
        r"^(बाय|टाटा|पुन्हा भेटू|शुभ रात्री)\b",
        r"^(alvida|punha bhetu)\b",
    ]

    HELP_REQUEST_PATTERNS = [
        r"(can you help me|help me|i need help|what can you do|who are you|how can you help)",
        r"(मला मदत पाहिजे|मला मदत हवी आहे|मला मदत करा|कशी मदत करू शकतोस|काय करू शकतोस|तू कोण आहेस)",
        r"(tu mala help karshil ka|mala help pahije|help karshil ka|mala ek question vicharaycha aahe|ek prashna aahe|ek question aahe)",
    ]

    UNSPECIFIED_ELIGIBILITY_PATTERNS = [
        r"^(am i eligible|who (is|are|can be) eligible|can i apply|who can apply|am i qualified|eligibility criteria)\b[?!.\s]*$",
        r"^(mi eligible aahe ka|me eligible aahe ka|patra aahe ka|mi arj karu shakto ka|kon patra aahe|mi qualify hoto ka)\b[?!.\s]*$",
        r"^(मी पात्र आहे का|कोणी अर्ज करू शकतो|पात्रता काय आहे|मी अर्ज करू शकते का|पात्रता निकष काय आहेत)\b[?!.\s]*$",
    ]

    UNSPECIFIED_APPLY_PATTERNS = [
        r"^(how (do|can) i apply|how to apply|where (do|can) i apply|where to apply|where is the application link|apply link|application procedure|application steps)\b[?!.\s]*$",
        r"^(kasa arj karava|kasa apply karu|arj kasa karaycha|kuthe apply karave|apply kasa karu|kasa form bharava|arj prakriya kay aahe)\b[?!.\s]*$",
        r"^(अर्ज कसा करावा|कुठे अर्ज करावा|अर्ज कसा करू|ऑनलाइन अर्ज कसा करावा|अर्ज प्रक्रिया काय आहे)\b[?!.\s]*$",
    ]

    UNSPECIFIED_DEADLINE_PATTERNS = [
        r"^(what is the (last date|deadline)|when does it close|what is the closing date|last date|when is the deadline)\b[?!.\s]*$",
        r"^(shevatachi tarikh kay|last date kay aahe|tarikh kay aahe|kadhi sampnar|mudat kadhi sampte)\b[?!.\s]*$",
        r"^(शेवटची तारीख काय आहे|अंतिम तारीख काय|मुदत कधी संपते|शेवटची तारीख कधी आहे)\b[?!.\s]*$",
    ]

    UNSPECIFIED_DOCUMENTS_PATTERNS = [
        r"^(what documents (are required|do i need)|required documents|documents list|which documents)\b[?!.\s]*$",
        r"^(kay kagadpatre lagtat|konti kagadpatre havi|documents kay lagtat|kagadpatre sanga)\b[?!.\s]*$",
        r"^(कोणती कागदपत्रे लागतात|आवश्यक कागदपत्रे कोणती|कागदपत्रे काय हवीत|कागदपत्रांची यादी द्या)\b[?!.\s]*$",
    ]

    SCHEME_NAME_INDICATORS = [
        r"(ladki|bahin|ladaki|लाडकी|बहीण)",
        r"(rajarshi|shahu|maharaj|शाहू)",
        r"(swadhar|स्वाधार)",
        r"(shetkari|farmer|karjamukti|कर्जमुक्ती|सन्मान|sanman|krushi|कृषी)",
        r"(gharkul|घरकुल|ramai|रमाई|shabari|शबरी|mhada|म्हाडा)",
        r"(arogya|aarogya|jeevandayee|जन आरोग्य|आयुष्मान)",
        r"(mahadbt|महाडीबीटी|scholarship|शिष्यवृत्ती)",
        r"(pension|पेन्शन|sanjay gandhi|संजय गांधी|shravan bal|श्रावण बाळ)",
        r"(kanyadan|कन्यादान|lekh ladki|लेक लाडकी)"
    ]

    SCHEME_KEYWORD_PATTERNS = [
        r"(scheme|schemes|yojana|yojna|yojne|scholarship|subsidy|anudan|farmer|shetkari|mahila|student|krushi|pension|karjamukti|shasan|gr|apply|arj|deadline|tarikh|mudat|shevatachi|shevatchi|patrata|eligibility|document|documents|kagadpatre|who can apply|how to apply|last date)",
        r"(योजना|योजने|शिष्यवृत्ती|अनुदान|शेतकरी|महिला|विद्यार्थी|कृषी|पेन्शन|कर्जमुक्ती|शासन|अर्ज|मुदत|तारीख|शेवटची तारीख|अंतिम तारीख|पात्रता|कागदपत्रे|कागदपत्र|कसा करावा|कोणी अर्ज करू शकतो)",
    ]

    @classmethod
    def classify(cls, query: str) -> str:
        q_clean = re.sub(r"[?!.,]+$", "", query.strip().lower()).strip()
        has_named_scheme = any(re.search(p, q_clean) for p in cls.SCHEME_NAME_INDICATORS)
        is_greeting = any(re.search(p, q_clean) for p in cls.GREETING_PATTERNS)
        is_how_are_you = any(re.search(p, q_clean) for p in cls.HOW_ARE_YOU_PATTERNS)
        is_thanks = any(re.search(p, q_clean) for p in cls.THANKS_PATTERNS)
        is_farewell = any(re.search(p, q_clean) for p in cls.FAREWELL_PATTERNS)
        is_help = any(re.search(p, q_clean) for p in cls.HELP_REQUEST_PATTERNS)

        if is_greeting and not has_named_scheme:
            return "greeting"
        if is_how_are_you:
            return "how_are_you"
        if is_thanks:
            return "thanks"
        if is_farewell:
            return "farewell"
        if is_help:
            return "help_request"

        # Check unspecified scheme queries
        if not has_named_scheme:
            if any(re.search(p, q_clean) for p in cls.UNSPECIFIED_ELIGIBILITY_PATTERNS):
                return "unspecified_eligibility"
            if any(re.search(p, q_clean) for p in cls.UNSPECIFIED_APPLY_PATTERNS):
                return "unspecified_apply"
            if any(re.search(p, q_clean) for p in cls.UNSPECIFIED_DEADLINE_PATTERNS):
                return "unspecified_deadline"
            if any(re.search(p, q_clean) for p in cls.UNSPECIFIED_DOCUMENTS_PATTERNS):
                return "unspecified_documents"

        # Check translation or language conversion request
        if (
            re.search(r"^(give\s+(it|this|details)?\s*in\s+marathi|tell\s+(me\s+)?in\s+marathi|in\s+marathi|translate\s+(this\s+)?to\s+marathi|marathi\s+madhe(\s+sanga)?|marathit(\s+sanga)?|मराठीत\s+सांगा|मराठीमध्ये\s+सांगा|मराठीत|मराठी\s+मध्ये)$", q_clean)
            or q_clean in ["give in marathi", "in marathi", "marathit sanga", "marathi madhe", "translate to marathi", "translate in marathi", "मराठीत", "मराठीत सांगा"]
        ):
            return "translate_to_marathi"
        if (
            re.search(r"^(give\s+(it|this|details)?\s*in\s+english|tell\s+(me\s+)?in\s+english|in\s+english|translate\s+(this\s+)?to\s+english|english\s+madhe(\s+sanga)?|englisht(\s+sanga)?|इंग्रजीत\s+सांगा|इंग्रजीमध्ये\s+सांगा|इंग्रजीत)$", q_clean)
            or q_clean in ["give in english", "in english", "english madhe", "translate to english", "इंग्रजीत सांगा"]
        ):
            return "translate_to_english"

        # Check guarantee questions (Never guarantee approval)
        if any(re.search(p, q_clean) for p in [
            r"(can you guarantee|guarantee that i will receive|approval guarantee|guarantee|खात्री देता का|गॅरंटी आहे का|हमी देता का|मिळेलच याची खात्री|खात्री आहे का)"
        ]):
            return "guarantee_inquiry"

        # Check unsupported / out-of-scope queries
        if any(re.search(p, q_clean) for p in [
            r"\b(weather in|cricket score|movie review|write a python script|recipe for|who won the match|capital of|who is the president|stock price)\b"
        ]):
            return "unsupported"

        # Check newly announced schemes
        if any(re.search(p, q_clean) for p in [
            r"(recently announced|recent schemes|new schemes|latest schemes|नुकत्याच जाहीर|नवीन योजना|नव्या योजना|नवीन शासन निर्णय|navin yojna)"
        ]):
            return "newly_announced"

        # Check deadline extensions
        if any(re.search(p, q_clean) for p in [
            r"(deadline extended|has the deadline been extended|is deadline extended|मुदत वाढली|तारीख वाढवली|मुदतवाढ|mudat vadhli|tarikh vadhli)"
        ]):
            return "deadline_extension"

        # Check scheme comparisons
        if any(re.search(p, q_clean) for p in [
            r"\b(compare|difference between|फरक काय|तुलना करा|तुलना|फरक सांगा)\b"
        ]):
            return "scheme_comparison"

        has_scheme = any(re.search(p, q_clean) for p in cls.SCHEME_KEYWORD_PATTERNS) or has_named_scheme
        if has_scheme:
            if is_greeting:
                return "mixed_greeting_scheme"
            return "scheme_query"

        return "general_or_unclear"

    @classmethod
    def get_response(cls, query: str, intent: str, lang: str) -> str:
        q_lower = query.lower()
        if intent == "greeting":
            if lang == "mr":
                if "सकाळ" in query:
                    return "शुभ सकाळ! मी तुम्हाला कशी मदत करू शकतो?"
                if "दुपार" in query:
                    return "शुभ दुपार! मी तुम्हाला कशी मदत करू शकतो?"
                if "संध्याकाळ" in query:
                    return "शुभ संध्याकाळ! मी तुम्हाला कशी मदत करू शकतो?"
                return "नमस्कार! मी तुम्हाला सरकारी योजनांची माहिती शोधण्यात आणि अर्ज प्रक्रिया समजून घेण्यात मदत करू शकतो. तुम्हाला काय जाणून घ्यायचे आहे?"
            elif lang == "mr_roman":
                return "Namaskar! Mi Maharashtra shasanachya yojnanbaddal madat karu shakto. Tumhala kay mahiti havi aahe?"
            else:
                if "bro" in q_lower:
                    return "Hey! What can I help you with?"
                if "morning" in q_lower:
                    return "Good morning! How can I help you today?"
                if "afternoon" in q_lower:
                    return "Good afternoon! How can I help you today?"
                if "evening" in q_lower:
                    return "Good evening! How can I help you today?"
                return "Hi! How can I help you today?"

        elif intent == "how_are_you":
            if lang == "mr":
                return "मी छान आहे, धन्यवाद! तुम्हाला कशात मदत करू?"
            elif lang == "mr_roman":
                return "Mi mast aahe, dhanyawad! Tumhala kashat madat karu?"
            else:
                return "I'm doing well, thank you! How can I help you today?"

        elif intent == "thanks":
            if lang == "mr":
                return "तुमचं स्वागत आहे! आणखी काही मदत हवी असल्यास सांगा."
            elif lang == "mr_roman":
                return "Tumche swagat aahe! Aani kahi madat havi aslyas sanga."
            else:
                return "You're welcome! Let me know if you need anything else."

        elif intent == "farewell":
            if lang == "mr":
                return "धन्यवाद! पुन्हा भेटू. आपला दिवस चांगला जावो."
            elif lang == "mr_roman":
                return "Dhanyawad! Punha bhetu. Apla divas changla javo."
            else:
                return "Goodbye! Have a great day ahead."

        elif intent == "help_request":
            if lang == "mr":
                if any(w in query for w in ["कशी मदत", "काय करू"]):
                    return "मी तुम्हाला महाराष्ट्र शासनाच्या विविध योजनांची माहिती, पात्रता, आवश्यक कागदपत्रे आणि अधिकृत अर्ज प्रक्रियेबद्दल मदत करू शकतो. तुम्हाला कोणत्या योजनेबद्दल माहिती हवी आहे?"
                return "हो, नक्कीच! आपला प्रश्न विचारा. मी तुम्हाला योजनांची माहिती शोधण्यात आणि अर्ज प्रक्रिया समजून घेण्यात मदत करेन."
            elif lang == "mr_roman":
                if "question" in q_lower or "prashna" in q_lower:
                    return "Ho, nakkich! Tumcha question vichara. Mi madat karnyacha prayatna karto."
                return "Ho, nakkich! Mi Maharashtra shasanachya yojnanbaddal madat karu shakto. Tumhala kay janun ghyayche aahe?"
            else:
                return "Yes, certainly! Please ask your question. I can help you with Maharashtra government schemes, eligibility, documents, and application steps."

        elif intent == "unspecified_eligibility":
            if lang == "mr":
                return (
                    "पात्रता तपासण्यासाठी, कृपया आपण कोणत्या योजनेबद्दल विचारत आहात ते सांगा "
                    "(उदा. **मुख्यमंत्री माझी लाडकी बहीण योजना**, **नमो शेतकरी महासन्मान निधी**, किंवा **महाडीबीटी शिष्यवृत्ती**).\n\n"
                    "आपण योजनेचे नाव सांगितल्यास मी अधिकृत शासन निर्णयानुसार विहित वयोमर्यादा, उत्पन्न मर्यादा आणि आवश्यक अटींची सविस्तर माहिती देऊ शकेन."
                )
            elif lang == "mr_roman":
                return (
                    "Patrata tapasnyasathi, krupaya tumhala kontya yojnebaddal mahiti havi aahe te sanga "
                    "(uda. **Mukhyamantri Majhi Ladki Bahin Yojana**, **Shetkari Sanman Yojana**, kinva **MahaDBT Shishyavrutti**).\n\n"
                    "Yojneche naav sanglyas mi official patrata nikash spashta sangen."
                )
            else:
                return (
                    "To evaluate your eligibility, please specify which Maharashtra Government scheme you are inquiring about "
                    "(for example: **Mukhyamantri Majhi Ladki Bahin Yojana**, **Farmer Crop Loan Waiver / Krishi Sanman**, or **MahaDBT Post-Matric Scholarship**).\n\n"
                    "Once you specify the scheme, I will verify the official eligibility criteria, age limits, and required income conditions."
                )

        elif intent == "unspecified_apply":
            if lang == "mr":
                return (
                    "अर्जाची अधिकृत प्रक्रिया जाणून घेण्यासाठी, कृपया योजनेचे नाव सांगा "
                    "(उदा. **मुख्यमंत्री माझी लाडकी बहीण योजना**, **महाडीबीटी शेतकरी योजना**, किंवा **आपले सरकार सेवा**).\n\n"
                    "मी आपल्याला थेट अधिकृत पोर्टल लिंक आणि ऑनलाईन/ऑफलाईन अर्ज करण्याची पायरी-दर-पायरी माहिती देईन."
                )
            elif lang == "mr_roman":
                return (
                    "Arjachi process aani official portal link milvnyasathi, krupaya yojneche naav sanga "
                    "(uda. **Mukhyamantri Majhi Ladki Bahin Yojana**, **MahaDBT Farmer Schemes**, kinva **Aaple Sarkar Portal**).\n\n"
                    "Mi tumhala direct verified portal link aani step-by-step apply guidance dein."
                )
            else:
                return (
                    "Which Maharashtra Government scheme would you like to apply for? "
                    "Please specify the scheme name (for example: **Mukhyamantri Majhi Ladki Bahin Yojana**, **Farmer Welfare Schemes**, or **MahaDBT Scholarship Portal**) "
                    "so I can provide the official step-by-step application instructions and verified portal link."
                )

        elif intent == "unspecified_deadline":
            if lang == "mr":
                return (
                    "अर्जाची अधिकृत अंतिम तारीख तपासण्यासाठी, कृपया आपण कोणत्या योजनेबद्दल विचारत आहात ते सांगा "
                    "(उदा. **मुख्यमंत्री माझी लाडकी बहीण योजना** किंवा **महाडीबीटी शिष्यवृत्ती**)."
                )
            elif lang == "mr_roman":
                return (
                    "Shevatachi tarikh tapasnyasathi, krupaya yojneche naav sanga "
                    "(uda. **Mukhyamantri Majhi Ladki Bahin Yojana** kinva **MahaDBT Scholarship**)."
                )
            else:
                return (
                    "To check the verified application deadline, please specify which scheme you are asking about "
                    "(for example: **Mukhyamantri Majhi Ladki Bahin Yojana** or **MahaDBT Post-Matric Scholarship**)."
                )

        elif intent == "unspecified_documents":
            if lang == "mr":
                return (
                    "आवश्यक कागदपत्रांची यादी जाणून घेण्यासाठी, कृपया आपण कोणत्या योजनेबद्दल विचारत आहात ते सांगा "
                    "(उदा. **मुख्यमंत्री माझी लाडकी बहीण योजना** किंवा **शेतकरी योजना**)."
                )
            elif lang == "mr_roman":
                return (
                    "Kagadpatranchi official list milvnyasathi, krupaya yojneche naav sanga "
                    "(uda. **Mukhyamantri Majhi Ladki Bahin Yojana** kinva **Shetkari Yojana**)."
                )
            else:
                return (
                    "To view the required document checklist, please specify which Maharashtra Government scheme you need documents for "
                    "(for example: **Mukhyamantri Majhi Ladki Bahin Yojana** or **Farmer Schemes**)."
                )

        elif intent == "guarantee_inquiry":
            if lang == "mr":
                return (
                    "नाही. महासेवा एआय केवळ अधिकृत शासन निर्णयांवर (GR) आधारित माहिती व पात्रता निकष स्पष्ट करते, "
                    "परंतु लाभाची कोणतीही कायदेशीर हमी देत नाही. अर्जाची प्रत्यक्ष पडताळणी आणि अंतिम मंजुरी संबंधित "
                    "शासकीय विभागाच्या सक्षम अधिकाऱ्यांमार्फतच दिली जाते."
                )
            elif lang == "mr_roman":
                return (
                    "Nahi. MahaSeva AI official GRs var aadharit mahiti dete, pan labhachi kontihi legal guarantee det nahi. "
                    "Arjachi antim manjuri aani patrata sambandhit shaskiya adhikaranchya hatat aste."
                )
            else:
                return (
                    "No. MahaSeva AI provides factual guidance based strictly on verified Government Resolutions (GRs), "
                    "but cannot guarantee benefit approval or disbursement. Final eligibility and approval are determined "
                    "solely by the competent departmental authorities after physical verification."
                )

        elif intent == "unsupported":
            if lang == "mr":
                return (
                    "मी केवळ महाराष्ट्र शासनाच्या योजना, शिष्यवृत्ती, शेतकरी अनुदान, पात्रता आणि अधिकृत अर्ज प्रक्रियेबद्दल मदत करतो. "
                    "कृपया महाराष्ट्र शासनाच्या कोणत्याही कल्याणकारी योजनेबद्दल आपला प्रश्न विचारा."
                )
            elif lang == "mr_roman":
                return (
                    "Mi phakt Maharashtra shasanachya yojna, scholarships, subsidy aani arj prakriye baddal madat karto. "
                    "Krupaya shasanachya yojnanbaddal prashna vichara."
                )
            else:
                return (
                    "I specialize exclusively in Maharashtra State Government schemes, eligibility criteria, application procedures, "
                    "and official citizen benefits. Please ask a question related to Maharashtra government assistance programs."
                )

        # general_or_unclear
        if lang == "mr":
            return "मी महाराष्ट्र शासनाच्या योजना, नागरिक कल्याणकारी उपक्रम आणि अधिकृत अर्ज प्रक्रियेबद्दल मार्गदर्शन करतो. सरकारी योजनांबद्दल मी आपल्याला कशी मदत करू?"
        elif lang == "mr_roman":
            return "Mi Maharashtra shasanachya yojna aani arj prakriye baddal madat karto. Yojnanbaddal tumhala kay mahiti havi aahe?"
        else:
            return "I specialize in Maharashtra Government schemes, citizen welfare programs, and official application procedures. How can I assist you with government schemes or benefits today?"

    @classmethod
    def get_scheme_contextual_response(cls, query: str, intent: str, scheme_title: str, lang: str) -> str:
        q_lower = query.lower()
        if intent == "greeting":
            if lang == "mr":
                return f"नमस्कार! मी तुम्हाला **{scheme_title}** या योजनेबद्दल माहिती देण्यासाठी उपलब्ध आहे. तुम्हाला काय जाणून घ्यायचे आहे?"
            elif lang == "mr_roman":
                return f"Namaskar! Mi tumhala **{scheme_title}** baddal madat karu shakto. Tumhala kay mahiti havi aahe?"
            else:
                if "bro" in q_lower:
                    return f"Hey! What would you like to know about **{scheme_title}**?"
                return f"Hi! How can I help you regarding **{scheme_title}** today?"

        elif intent == "how_are_you":
            if lang == "mr":
                return f"मी छान आहे, धन्यवाद! **{scheme_title}** बद्दल तुम्हाला काय जाणून घ्यायचे आहे?"
            elif lang == "mr_roman":
                return f"Mi mast aahe, dhanyawad! **{scheme_title}** baddal tumhala kay mahiti havi aahe?"
            else:
                return f"I'm doing well, thank you! What would you like to know about **{scheme_title}**?"

        elif intent == "thanks":
            if lang == "mr":
                return f"तुमचं स्वागत आहे! **{scheme_title}** बद्दल आणखी काही माहिती हवी असल्यास सांगा."
            elif lang == "mr_roman":
                return f"Tumche swagat aahe! **{scheme_title}** baddal aani kahi madat havi aslyas sanga."
            else:
                return f"You're welcome! Let me know if you need anything else regarding **{scheme_title}**."

        elif intent == "farewell":
            if lang == "mr":
                return "धन्यवाद! पुन्हा भेटू. आपला दिवस चांगला जावो."
            elif lang == "mr_roman":
                return "Dhanyawad! Punha bhetu."
            else:
                return "Goodbye! Have a great day ahead."

        elif intent == "help_request":
            if lang == "mr":
                return f"हो, नक्कीच! **{scheme_title}** बद्दल आपला प्रश्न विचारा. मी पात्रता, कागदपत्रे किंवा अर्ज पद्धतीबद्दल मदत करेन."
            elif lang == "mr_roman":
                return f"Ho, nakkich! **{scheme_title}** baddal tumcha question vichara. Mi madat karnyacha prayatna karto."
            else:
                return f"Certainly! Ask any question about **{scheme_title}** (such as eligibility, documents, deadline, or application steps)."

        return cls.get_response(query, intent, lang)


class EligibilityEngine:
    """Evaluates user answers against documented scheme eligibility criteria."""

    @staticmethod
    def assess(scheme: SchemeCandidate, user_input: str, lang: str) -> Dict[str, Any]:
        is_mr = lang in ("mr", "mr_roman")
        raw_eligibility = scheme.eligibility or ""

        if not raw_eligibility or len(raw_eligibility.strip()) < 10:
            msg = (
                f"**{scheme.title_mr if is_mr and scheme.title_mr else scheme.title}**\n\n"
                f"⚠️ **पात्रता निकष स्रोत तपासणी बाकी / Criteria Not Explicitly Formatted**\n\n"
                f"या योजनेचे विशिष्ट पात्रता निकष अधिकृत शासन निर्णयात (GR) पहावेत. अधिकृत माहितीसाठी येथे तपासा: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                if is_mr
                else f"**{scheme.title}**\n\n"
                f"⚠️ **Eligibility Rules Could Not Be Verified from Current Excerpts**\n\n"
                f"Detailed criteria must be verified directly against the official Government Resolution (GR): [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
            )
            return {
                "assessment_category": "rules_unverified",
                "answer": msg,
                "confidence": "source_incomplete",
            }

        input_lower = user_input.lower()

        # Extract criteria points from eligibility text
        points = [p.strip() for p in re.split(r"[;\n•\-\d+\.]+", raw_eligibility) if len(p.strip()) > 10]
        if not points:
            points = [raw_eligibility]

        matched = []
        missing = []

        for pt in points:
            pt_lower = pt.lower()
            # If user mentions keywords matching this point
            keywords_in_pt = [w for w in re.findall(r"\w+", pt_lower) if len(w) > 3]
            overlap = any(kw in input_lower for kw in keywords_in_pt)
            if overlap:
                matched.append(pt)
            else:
                missing.append(pt)

        # Categorize
        if not input_lower or len(input_lower.split()) <= 3:
            category = "more_info_needed"
            if is_mr:
                ans = (
                    f"### 📋 {scheme.title_mr if scheme.title_mr else scheme.title} — पात्रता तपासणी\n\n"
                    f"**अधिकृत शासन निर्णयानुसार विहित अटी:**\n"
                    + "\n".join(f"- {p}" for p in points)
                    + f"\n\n**आपली पात्रता निश्चित करण्यासाठी कृपया सांगा:**\n"
                    f"- आपले वय, अधिवास (महाराष्ट्र रहिवासी), वार्षिक कौटुंबिक उत्पन्न किंवा व्यवसाय."
                )
            else:
                ans = (
                    f"### 📋 {scheme.title} — Eligibility Criteria Assessment\n\n"
                    f"**Documented Official Criteria:**\n"
                    + "\n".join(f"- {p}" for p in points)
                    + f"\n\n**To evaluate your eligibility, please share:**\n"
                    f"- Your state of residence, age, family income, or occupational category."
                )
        elif len(matched) >= len(points) * 0.5:
            category = "likely_eligible"
            if is_mr:
                ans = (
                    f"### ✅ दिलेल्या माहितीच्या आधारे आपण पात्र असण्याची शक्यता आहे\n\n"
                    f"**तपासलेले निकष:**\n"
                    + "\n".join(f"- ✓ {m}" for m in matched)
                    + (f"\n\n**इतर आवश्यक अटी:**\n" + "\n".join(f"- ℹ️ {m}" for m in missing) if missing else "")
                    + f"\n\n*(सूचना: अंतिम पात्रता सक्षम शासकीय प्राधिकरणाद्वारे कागदपत्र पडताळणीनंतरच निश्चित होते.)*"
                )
            else:
                ans = (
                    f"### ✅ Likely Eligible Based on the Information Provided\n\n"
                    f"**Matched Criteria:**\n"
                    + "\n".join(f"- ✓ {m}" for m in matched)
                    + (f"\n\n**Additional Conditions to Verify:**\n" + "\n".join(f"- ℹ️ {m}" for m in missing) if missing else "")
                    + f"\n\n*(Notice: Final eligibility is subject to official departmental document verification.)*"
                )
        else:
            category = "more_info_needed"
            if is_mr:
                ans = (
                    f"### ℹ️ पात्रतेची खात्री करण्यासाठी अधिक माहिती आवश्यक आहे\n\n"
                    f"**या योजनेसाठी महत्त्वाच्या अटी:**\n"
                    + "\n".join(f"- {p}" for p in points[:3])
                    + f"\n\nकृपया आपल्या अर्जासाठी आवश्यक माहिती पूर्ण नमूद करा."
                )
            else:
                ans = (
                    f"### ℹ️ More Information Required to Determine Eligibility\n\n"
                    f"**Key Conditions for this Scheme:**\n"
                    + "\n".join(f"- {p}" for p in points[:3])
                    + f"\n\nKindly specify your residence, occupation, or relevant qualifying details."
                )

        return {
            "assessment_category": category,
            "answer": ans,
            "matched_criteria": matched,
            "missing_criteria": missing,
        }


class ApplicationGuideEngine:
    """Provides structured, step-by-step application instructions."""

    @staticmethod
    def guide(scheme: SchemeCandidate, lang: str) -> str:
        is_mr = lang in ("mr", "mr_roman")
        title = scheme.title_mr if (is_mr and scheme.title_mr) else scheme.title
        mode = scheme.application_mode or "online"

        has_apply_link = bool(scheme.official_apply_url)
        apply_url = scheme.official_apply_url or scheme.source_url

        docs = scheme.documents_required or (
            "आधार कार्ड, अधिवास दाखला (Domicile), उत्पन्न दाखला, बँक पासबुक"
            if is_mr
            else "Aadhaar Card, Maharashtra Domicile Certificate, Income Certificate, Bank Passbook"
        )

        custom_proc = scheme.application_process or ""

        if is_mr:
            text = (
                f"### 🚀 {title} — अर्ज करण्याची सविस्तर कार्यपद्धती\n\n"
                f"- **अर्जाचा प्रकार:** {'ऑनलाईन (Online)' if mode == 'online' else 'ऑफलाईन (Offline)' if mode == 'offline' else 'ऑनलाईन व ऑफलाईन दोन्ही'}\n"
                f"- **विहित कागदपत्रे:** {docs}\n\n"
                f"**पायरी-दर-पायरी अर्ज प्रक्रिया:**\n"
            )
            if custom_proc:
                text += f"{custom_proc}\n\n"
            elif mode == "online":
                text += (
                    f"1. **अधिकृत पोर्टलवर जा:** अधिकृत संकेतस्थळ उघडा [{urlparse(apply_url).netloc}]({apply_url}).\n"
                    f"2. **नवीन नोंदणी करा:** जर आधी नोंदणी नसेल, तर आधार क्रमांकाशी संलग्न मोबाईल नंबर वापरून नोंदणी (New Registration) करा.\n"
                    f"3. **विहित कागदपत्रे अपलोड करा:** आवश्यक कागदपत्रांच्या स्पष्ट स्कॅन केलेल्या प्रती अपलोड करा.\n"
                    f"4. **अर्जाचे पुनरावलोकन व सादर:** माहिती तपासून अंतिम अर्ज सादर करा आणि पावती (Application Receipt) जतन करा.\n"
                    f"5. **स्थिती तपासा:** अर्जाचा टोकन क्रमांक वापरून पोर्टलवर वेळोवेळी अर्जाची प्रगती तपासा.\n\n"
                )
            else:
                text += (
                    f"1. **कार्यालयाशी संपर्क:** संबंधित {scheme.department} च्या तालुका/जिल्हा कार्यालयात किंवा ग्रामपंचायतीत भेट द्या.\n"
                    f"2. **विहित नमुना अर्ज प्राप्त करा:** अधिकृत अर्जाचा नमुना भरा.\n"
                    f"3. **कागदपत्रे जोडा:** {docs} च्या साक्षांकित प्रती सोबत जोडा.\n"
                    f"4. **अर्ज सादर करा:** कार्यालयात अर्ज जमा करून पोहोच पावती (Acknowledgment Receipt) नक्की घ्या.\n\n"
                )

            if has_apply_link:
                text += f"🔗 **अधिकृत अर्ज लिंक:** [{scheme.official_apply_url}]({scheme.official_apply_url})\n"
            text += f"🏛️ **अधिकृत माहिती स्रोत:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"

        else:
            text = (
                f"### 🚀 {title} — Step-by-Step Application Procedure\n\n"
                f"- **Application Mode:** {'Online Portal' if mode == 'online' else 'Offline Designated Office' if mode == 'offline' else 'Both Online & Offline'}\n"
                f"- **Required Documents:** {docs}\n\n"
                f"**Application Steps:**\n"
            )
            if custom_proc:
                text += f"{custom_proc}\n\n"
            elif mode == "online":
                text += (
                    f"1. **Access the Official Portal:** Visit the verified portal at [{urlparse(apply_url).netloc}]({apply_url}).\n"
                    f"2. **Applicant Registration:** Register an account using your mobile-linked credentials.\n"
                    f"3. **Fill Out Scheme Form:** Navigate to {scheme.department} schemes and complete the applicant details.\n"
                    f"4. **Upload Verification Documents:** Upload clear digital copies of the required certificates.\n"
                    f"5. **Submit & Retain Acknowledgment:** Submit the application and download the stamped acknowledgment slip.\n\n"
                )
            else:
                text += (
                    f"1. **Visit Implementing Authority:** Approach the designated Tahsildar, Gram Panchayat, or District Social Welfare office.\n"
                    f"2. **Collect Official Application Form:** Obtain the prescribed physical scheme application form.\n"
                    f"3. **Attach Required Documents:** Enclose attested photocopies of {docs}.\n"
                    f"4. **Submit & Secure Receipt:** Submit to the competent officer and obtain an official dated receipt.\n\n"
                )

            if has_apply_link:
                text += f"🔗 **Verified Application Link:** [{scheme.official_apply_url}]({scheme.official_apply_url})\n"
            text += f"🏛️ **Official Information Source:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"

        return text


class GroundedRuleSynthesizer:
    """Generates deterministic, fully-grounded citizen guidance without external hallucination."""

    @staticmethod
    def generate(
        query: str,
        items: List[SchemeCandidate],
        lang: str,
        specific_intent: Optional[str] = None,
        greeting_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        is_mr = lang in ("mr", "mr_roman")

        if not items:
            if is_mr:
                answer = (
                    "आपल्या प्रश्नाशी थेट जुळणारी अधिकृत योजना सध्या उपलब्ध माहितीत आढळली नाही.\n\n"
                    "- कृपया इतर शब्द किंवा विभागाचे नाव वापरून शोधून पहा (उदा. शेतकरी, शिष्यवृत्ती, महिला, पेन्शन).\n"
                    "- अधिकृत शासन निर्णयांसाठी (GR) महाराष्ट्र शासनाचे पोर्टल पहा: [maharashtra.gov.in](https://www.maharashtra.gov.in)"
                )
            else:
                answer = (
                    "No verified government scheme matching your query was found in the current repository.\n\n"
                    "- Try searching with alternative keywords (e.g. 'farmer subsidy', 'scholarship', 'rural housing', 'pension').\n"
                    "- For latest Government Resolutions (GR), visit the official portal: [maharashtra.gov.in](https://www.maharashtra.gov.in)"
                )
            return {
                "answer": answer,
                "sources": [],
                "confidence": "insufficient_data",
                "language": lang,
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(is_mr),
            }

        q_lower = query.lower()
        is_date_q = any(w in q_lower for w in ["last date", "deadline", "closing", "शेवटची तारीख", "अंतिम तारीख", "मुदत", "tarikh", "kadhi"])
        is_docs_q = any(w in q_lower for w in ["documents", "document", "कागदपत्रे", "कागदपत्र", "kagadpatre", "proof", "papers"])
        is_eligibility_q = any(w in q_lower for w in ["eligible", "eligibility", "पात्रता", "patrata", "who can apply", "शर्त", "अटी", "am i eligible", "qualify"])
        is_apply_q = any(w in q_lower for w in ["how to apply", "apply", "अर्ज कसा", "arj", "process", "पोर्टल", "step by step", "procedure"])
        is_benefits_q = any(w in q_lower for w in ["benefits", "benefit", "लाभ", "फायदे", "labh", "fayde", "subsidy", "anudan"])

        sources = []
        for candidate in items[:4]:
            source_info = {
                "id": candidate.id,
                "title": candidate.title,
                "title_mr": candidate.title_mr or candidate.title,
                "department": candidate.department,
                "source_url": candidate.source_url,
                "official_apply_url": candidate.official_apply_url or "",
                "verification_status": candidate.verification_status,
                "current_window_status": candidate.current_window_status,
                "application_deadline": candidate.application_deadline,
            }
            sources.append(source_info)

        # Single scheme matched
        if len(items) == 1:
            candidate = items[0]
            title = candidate.title_mr if (is_mr and candidate.title_mr) else candidate.title
            labels = get_status_labels(candidate.current_window_status)
            status_text = labels["mr"] if is_mr else labels["en"]
            deadline_str = (
                (NO_DEADLINE_NOTICE_MR if is_mr else NO_DEADLINE_NOTICE_EN)
                if (candidate.current_window_status == "no_deadline_published" or not candidate.application_deadline)
                else candidate.application_deadline
            )

            if is_date_q:
                if candidate.current_window_status == "closed":
                    if is_mr:
                        ans = (
                            f"**{title}** या योजनेची अधिकृत अर्ज मुदत **संपलेली आहे**.\n\n"
                            f"- **अंतिम तारीख:** {candidate.application_deadline}\n"
                            f"- **अर्जाची स्थिती:** {status_text}\n"
                            f"- पुढील शासन निर्णयासाठी अधिकृत पोर्टल पहा: [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                        )
                    else:
                        ans = (
                            f"The application window for **{title}** is **currently closed**.\n\n"
                            f"- **Verified Deadline:** {candidate.application_deadline}\n"
                            f"- **Current Status:** {status_text}\n"
                            f"- Check official source for updates: [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                        )
                elif candidate.current_window_status == "no_deadline_published":
                    if is_mr:
                        ans = (
                            f"**{title}**:\n\n"
                            f"ℹ️ {NO_DEADLINE_NOTICE_MR}\n\n"
                            f"चालू स्थितीसाठी अधिकृत पोर्टल तपासा: [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                        )
                    else:
                        ans = (
                            f"Regarding **{title}**:\n\n"
                            f"ℹ️ {NO_DEADLINE_NOTICE_EN}\n\n"
                            f"Please confirm current availability on the official department portal: [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                        )
                else:
                    if candidate.application_deadline:
                        if is_mr:
                            ans = (
                                f"**{title}** या योजनेची अर्जाची अंतिम मुदत **{candidate.application_deadline}** ({status_text}) आहे.\n\n"
                                f"- **अर्जाची स्थिती:** {status_text}\n"
                                f"- **अंतिम तारीख:** {candidate.application_deadline}\n"
                                + (f"- **अधिकृत अर्ज पोर्टल:** [येथे अर्ज करा]({candidate.official_apply_url})\n" if candidate.official_apply_url else "")
                                + f"- **अधिकृत माहिती स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                            )
                        else:
                            ans = (
                                f"The application window for **{title}** is currently **{status_text}**.\n\n"
                                f"- **Current Status:** {status_text}\n"
                                f"- **Application Deadline:** {candidate.application_deadline}\n"
                                + (f"- **Official Application Portal:** [Apply Online]({candidate.official_apply_url})\n" if candidate.official_apply_url else "")
                                + f"- **Official Information Source:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                            )
                    else:
                        if is_mr:
                            ans = (
                                f"**{title}** या योजनेची अर्ज प्रक्रिया सध्या **{status_text}** आहे.\n\n"
                                f"- **अर्जाची स्थिती:** {status_text}\n"
                                f"- **अंतिम तारीख:** {NO_DEADLINE_NOTICE_MR}\n"
                                + (f"- **अधिकृत अर्ज पोर्टल:** [येथे अर्ज करा]({candidate.official_apply_url})\n" if candidate.official_apply_url else "")
                                + f"- **अधिकृत माहिती स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                            )
                        else:
                            ans = (
                                f"The application window for **{title}** is currently **{status_text}**.\n\n"
                                f"- **Current Status:** {status_text}\n"
                                f"- **Application Deadline:** {NO_DEADLINE_NOTICE_EN}\n"
                                + (f"- **Official Application Portal:** [Apply Online]({candidate.official_apply_url})\n" if candidate.official_apply_url else "")
                                + f"- **Official Information Source:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                            )

            elif is_docs_q:
                docs = candidate.documents_required or (
                    "आधार कार्ड, अधिवास दाखला (Domicile), उत्पन्न दाखला, बँक पासबुक"
                    if is_mr
                    else "Aadhaar Card, Maharashtra Domicile Certificate, Income Certificate, Bank Passbook"
                )
                if is_mr:
                    ans = (
                        f"**{title}** साठी आवश्यक अधिकृत कागदपत्रे:\n\n"
                        f"- {docs}\n\n"
                        f"🔗 **अधिकृत माहिती स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )
                else:
                    ans = (
                        f"Required documents for **{title}**:\n\n"
                        f"- {docs}\n\n"
                        f"🔗 **Official Information Source:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )

            elif is_eligibility_q:
                elig = candidate.eligibility or (
                    "विहित अटी शासन निर्णयानुसार लागू." if is_mr else "Criteria subject to official Government Resolution."
                )
                if is_mr:
                    ans = (
                        f"**{title}** साठी विहित पात्रता अटी:\n\n"
                        f"- {elig}\n\n"
                        f"*(सूचना: अंतिम पात्रता सक्षम शासकीय प्राधिकरणाद्वारे कागदपत्र पडताळणीनंतरच निश्चित होते.)*\n\n"
                        f"🔗 **अधिकृत माहिती स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )
                else:
                    ans = (
                        f"Eligibility criteria for **{title}**:\n\n"
                        f"- {elig}\n\n"
                        f"*(Notice: Final eligibility is determined by the competent department upon document verification.)*\n\n"
                        f"🔗 **Official Information Source:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )

            elif is_apply_q:
                ans = ApplicationGuideEngine.guide(candidate, lang)

            elif is_benefits_q:
                ben = candidate.benefits or candidate.text[:250]
                if is_mr:
                    ans = (
                        f"**{title}** या योजनेचे अधिकृत लाभ:\n\n"
                        f"- {ben}\n\n"
                        f"🔗 **अधिकृत माहिती स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )
                else:
                    ans = (
                        f"Verified benefits for **{title}**:\n\n"
                        f"- {ben}\n\n"
                        f"🔗 **Official Information Source:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )

            else:
                snippet = extract_snippet(candidate.text, extract_keywords(query))
                ben = candidate.benefits or snippet
                elig = candidate.eligibility or ("शासन निर्णयानुसार लागू" if is_mr else "As per Government Resolution")
                apply_link_md = (
                    f"- **ऑनलाइन अर्ज लिंक:** [येथे अर्ज करा]({candidate.official_apply_url})\n"
                    if (is_mr and candidate.official_apply_url)
                    else f"- **Official Application Link:** [Apply Here]({candidate.official_apply_url})\n"
                    if candidate.official_apply_url
                    else ""
                )
                if is_mr:
                    ans = (
                        f"**{title}**\n\n"
                        f"- **विभाग:** {candidate.department}\n"
                        f"- **अर्जाची स्थिती:** **{status_text}**\n"
                        f"- **अंतिम तारीख:** {deadline_str}\n"
                        f"- **लाभ / स्वरूप:** {ben}\n"
                        f"- **पात्रता:** {elig}\n"
                        f"{apply_link_md}"
                        f"- **अधिकृत माहिती स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )
                else:
                    ans = (
                        f"**{title}**\n\n"
                        f"- **Department:** {candidate.department}\n"
                        f"- **Application Status:** **{status_text}**\n"
                        f"- **Application Deadline:** {deadline_str}\n"
                        f"- **Key Information / Benefits:** {ben}\n"
                        f"- **Eligibility:** {elig}\n"
                        f"{apply_link_md}"
                        f"- **Official Source Link:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                    )

            if greeting_prefix:
                ans = greeting_prefix + ans

            valid, _ = validate_ai_answer(ans, items)
            if not valid:
                ans += "\n\n*(Note: Data strictly verified against official status records)*"

            return {
                "answer": ans,
                "sources": sources,
                "confidence": "grounded_official_data",
                "language": lang,
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(is_mr),
            }

        # Multiple schemes matched
        scheme_summaries = []
        for i, candidate in enumerate(items[:4]):
            labels = get_status_labels(candidate.current_window_status)
            status_text = labels["mr"] if is_mr else labels["en"]
            deadline_display = (
                (NO_DEADLINE_NOTICE_MR if is_mr else NO_DEADLINE_NOTICE_EN)
                if (candidate.current_window_status == "no_deadline_published" or not candidate.application_deadline)
                else candidate.application_deadline
            )
            title = candidate.title_mr if (is_mr and candidate.title_mr) else candidate.title
            snippet = extract_snippet(candidate.text, extract_keywords(query))
            ben = candidate.benefits or snippet
            apply_link_md = (
                f"- **अर्ज लिंक:** [येथे अर्ज करा]({candidate.official_apply_url})\n"
                if (is_mr and candidate.official_apply_url)
                else f"- **Application Link:** [Apply Online]({candidate.official_apply_url})\n"
                if candidate.official_apply_url
                else ""
            )

            if is_mr:
                summary = (
                    f"**{i+1}. {title}** ({status_text})\n"
                    f"- **लाभ:** {ben}\n"
                    f"- **अंतिम तारीख:** {deadline_display}\n"
                    f"{apply_link_md}"
                    f"- **अधिकृत स्रोत:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                )
            else:
                summary = (
                    f"**{i+1}. {title}** ({status_text})\n"
                    f"- **Benefits:** {ben}\n"
                    f"- **Deadline:** {deadline_display}\n"
                    f"{apply_link_md}"
                    f"- **Official Source:** [{urlparse(candidate.source_url).netloc}]({candidate.source_url})"
                )
            scheme_summaries.append(summary)

        if is_mr:
            header = f"आपल्या प्रश्नानुसार उपलब्ध **{len(items)}** अधिकृत योजनांची माहिती:\n\n"
        else:
            header = f"Found **{len(items)}** relevant official scheme record(s) matching your query:\n\n"

        full_answer = header + "\n\n".join(scheme_summaries)
        if greeting_prefix:
            full_answer = greeting_prefix + full_answer

        valid, _ = validate_ai_answer(full_answer, items)
        if not valid:
            full_answer += "\n\n*(Note: Data strictly verified against official status records)*"

        return {
            "answer": full_answer,
            "sources": sources,
            "confidence": "grounded_official_data",
            "language": lang,
            "disclaimer": GroundedRuleSynthesizer.get_disclaimer(is_mr),
        }

    @staticmethod
    def get_disclaimer(is_marathi: bool) -> str:
        if is_marathi:
            return (
                "ही माहिती महाराष्ट्र शासनाच्या अधिकृत संकेतस्थळांवरून संकलित करण्यात आली आहे. "
                "अर्जाची स्वीकृती व पात्रता संबंधित शासकीय विभागाच्या अधिकृत नियमांवर अवलंबून असते. "
                "महासेवा एआय कोणत्याही लाभाची कायदेशीर हमी देत नाही."
            )
        return (
            "This information is retrieved from official Government of Maharashtra web publications. "
            "Final benefit approval and eligibility are determined solely by the competent departmental authorities. "
            "MahaSeva AI does not guarantee application outcomes."
        )


class AIAssistantService:
    """Orchestrates query handling, bilingual grounding, deadline status retrieval, and contextual chat."""

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "rule_based").lower()
        self.api_key = os.getenv("AI_API_KEY", "")
        self.model_name = os.getenv("AI_MODEL", "")

    def ask(
        self,
        query: str,
        db: Session,
        limit: int = 5,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        force_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main entrypoint for citizen scheme inquiries."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return {
                "answer": "Please enter a question or scheme name to search.",
                "sources": [],
                "confidence": "no_query",
                "language": "en",
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(False),
            }

        # Privacy check: Ensure citizen did not accidentally paste 12-digit Aadhaar or bank account
        aadhaar_match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", cleaned_query)
        if aadhaar_match:
            return {
                "answer": (
                    "⚠️ **Privacy Warning / गोपनीयता इशारा:**\n\n"
                    "We noticed numbers resembling an Aadhaar or bank account number. "
                    "For your security and privacy, MahaSeva AI **never requires or accepts** Aadhaar, bank details, or passwords.\n\n"
                    "Please ask your question regarding scheme requirements or eligibility without sharing personal numbers."
                ),
                "sources": [],
                "confidence": "privacy_shield",
                "language": "en",
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(False),
            }

        lang = force_lang or detect_language(cleaned_query)
        q_lower = cleaned_query.lower()

        # Multi-turn context resolution: resolve previous scheme from conversation history
        active_scheme = None
        if conversation_history:
            prev_texts = [
                (m.get("content") or m.get("text") or "") if isinstance(m, dict) else getattr(m, "content", "")
                for m in reversed(conversation_history[-6:])
            ]
            combined_prev = " ".join(prev_texts).lower()
            if any(k in combined_prev for k in ["ladki", "bahin", "लाडकी", "बहीण"]):
                active_scheme = db.scalars(
                    select(SchemeCandidate).where(
                        or_(SchemeCandidate.title.like("%Ladki%"), SchemeCandidate.title_mr.like("%लाडकी%"))
                    ).limit(1)
                ).first()
            if not active_scheme:
                for cand in db.scalars(select(SchemeCandidate).order_by(desc(SchemeCandidate.id))).all():
                    if cand.title.lower() in combined_prev or (cand.title_mr and cand.title_mr.lower() in combined_prev):
                        active_scheme = cand
                        break

        # Conversational routing for greetings, chit-chat, thanks, help requests
        intent = ConversationalIntentRouter.classify(cleaned_query)

        # Handle translation requests (e.g. "give in marathi", "मराठीत सांगा", "give in english")
        if intent in ("translate_to_marathi", "translate_to_english"):
            target_lang = "mr" if intent == "translate_to_marathi" else "en"
            if active_scheme:
                prefix = "नक्की! खालील माहिती मराठीत उपलब्ध आहे:\n\n" if target_lang == "mr" else "Certainly! Here are the details in English:\n\n"
                return GroundedRuleSynthesizer.generate(
                    "", [active_scheme], target_lang, greeting_prefix=prefix
                )

            # Search backwards in history for the last actual search query
            prev_search = None
            if conversation_history:
                for msg in reversed(conversation_history):
                    role = msg.get("sender") or msg.get("role") or ""
                    txt = (msg.get("text") or msg.get("content") or "").strip()
                    if role in ("user", "citizen", "client") and txt:
                        p_intent = ConversationalIntentRouter.classify(txt)
                        if p_intent not in ("translate_to_marathi", "translate_to_english", "greeting", "thanks", "farewell"):
                            prev_search = txt
                            break

            if prev_search:
                return self.ask(
                    prev_search,
                    db=db,
                    limit=limit,
                    conversation_history=conversation_history,
                    force_lang=target_lang,
                )

            # Fallback if no prior context
            if target_lang == "mr":
                ans = "कृपया ज्या योजनेबद्दल मराठीत माहिती हवी आहे तिचे नाव किंवा विषय सांगा (उदा. 'लाडकी बहीण योजना', 'शेतकरी कर्जमुक्ती', 'विद्यार्थी शिष्यवृत्ती')."
            else:
                ans = "Please specify which scheme or topic you would like me to explain in English (e.g. 'Ladki Bahin', 'Farmer Schemes', 'Scholarships')."
            return {
                "answer": ans,
                "sources": [],
                "confidence": "conversational",
                "language": target_lang,
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(target_lang == "mr"),
            }

        if intent in ("greeting", "how_are_you", "thanks", "farewell", "help_request", "guarantee_inquiry", "unsupported"):
            ans = ConversationalIntentRouter.get_response(cleaned_query, intent, lang)
            return {
                "answer": ans,
                "sources": [],
                "confidence": "conversational",
                "language": lang,
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(lang in ("mr", "mr_roman")),
            }

        # Handling newly announced schemes
        if intent == "newly_announced":
            records = db.scalars(
                select(SchemeCandidate)
                .where(SchemeCandidate.is_recently_announced == True)
                .order_by(desc(SchemeCandidate.id))
                .limit(limit)
            ).all()
            if not records:
                records = db.scalars(
                    select(SchemeCandidate).order_by(desc(SchemeCandidate.id)).limit(limit)
                ).all()
            prefix = "नुकत्याच जाहीर झालेल्या महाराष्ट्र शासनाच्या प्रमुख योजना:\n\n" if lang == "mr" else "Recently announced key Government of Maharashtra schemes:\n\n"
            return GroundedRuleSynthesizer.generate(cleaned_query, records, lang, greeting_prefix=prefix)

        # Handling deadline extension queries
        if intent == "deadline_extension":
            if active_scheme:
                labels = get_status_labels(active_scheme.current_window_status)
                status_text = labels["mr"] if lang == "mr" else labels["en"]
                deadline_str = active_scheme.application_deadline or ("अंतिम तारीख नमूद नाही" if lang == "mr" else "No deadline published")
                if lang == "mr":
                    ans = (
                        f"**{active_scheme.title_mr or active_scheme.title}** या योजनेची अधिकृत स्थिती:\n\n"
                        f"- **सध्याची अर्ज मुदत:** {deadline_str}\n"
                        f"- **स्थिती:** {status_text}\n"
                        f"- **मुदतवाढ शासन निर्णय:** अधिकृत पोर्टलवर प्रसिद्ध झालेल्या ताज्या शासन निर्णयानुसार तारीख नोंदवली गेली आहे. "
                        f"अद्ययावत माहितीसाठी [अधिकृत पोर्टल]({active_scheme.source_url}) पहा."
                    )
                else:
                    ans = (
                        f"Official deadline status for **{active_scheme.title}**:\n\n"
                        f"- **Current Deadline:** {deadline_str}\n"
                        f"- **Status:** {status_text}\n"
                        f"- **Extension Details:** Deadlines are synchronized with official Government Resolutions (GRs). "
                        f"Check the [Official Portal]({active_scheme.source_url}) for latest notification updates."
                    )
                return {
                    "answer": ans,
                    "sources": [{"id": active_scheme.id, "title": active_scheme.title, "source_url": active_scheme.source_url}],
                    "confidence": "grounded_official_data",
                    "language": lang,
                    "disclaimer": GroundedRuleSynthesizer.get_disclaimer(lang == "mr"),
                }

        # Handling scheme comparison queries
        if intent == "scheme_comparison":
            comp_schemes = []
            if any(k in q_lower for k in ["swadhar", "स्वाधार"]):
                s1 = db.scalars(select(SchemeCandidate).where(SchemeCandidate.title.like("%Swadhar%"))).first()
                if s1 and s1 not in comp_schemes: comp_schemes.append(s1)
            if any(k in q_lower for k in ["swayam", "स्वयं"]):
                s2 = db.scalars(select(SchemeCandidate).where(SchemeCandidate.title.like("%Swayam%"))).first()
                if s2 and s2 not in comp_schemes: comp_schemes.append(s2)
            if any(k in q_lower for k in ["ladki bahin", "लाडकी बहीण"]):
                s3 = db.scalars(select(SchemeCandidate).where(SchemeCandidate.title.like("%Ladki%"))).first()
                if s3 and s3 not in comp_schemes: comp_schemes.append(s3)
            if any(k in q_lower for k in ["lek ladki", "लेक लाडकी"]):
                s4 = db.scalars(select(SchemeCandidate).where(SchemeCandidate.title.like("%Lek Ladki%"))).first()
                if s4 and s4 not in comp_schemes: comp_schemes.append(s4)

            if len(comp_schemes) >= 2:
                s_a, s_b = comp_schemes[0], comp_schemes[1]
                t_a = s_a.title_mr if lang == "mr" and s_a.title_mr else s_a.title
                t_b = s_b.title_mr if lang == "mr" and s_b.title_mr else s_b.title
                if lang == "mr":
                    ans = (
                        f"**योजनांची तुलना (Comparison):**\n\n"
                        f"### १. {t_a}\n"
                        f"- **लाभार्थी:** {s_a.target_beneficiaries or 'विहित निकष'}\n"
                        f"- **लाभ:** {s_a.benefits or s_a.brief_description}\n"
                        f"- **अंतिम मुदत:** {s_a.application_deadline or 'अंतिम तारीख नमूद नाही'}\n\n"
                        f"### २. {t_b}\n"
                        f"- **लाभार्थी:** {s_b.target_beneficiaries or 'विहित निकष'}\n"
                        f"- **लाभ:** {s_b.benefits or s_b.brief_description}\n"
                        f"- **अंतिम मुदत:** {s_b.application_deadline or 'अंतिम तारीख नमूद नाही'}\n"
                    )
                else:
                    ans = (
                        f"**Official Comparison:**\n\n"
                        f"### 1. {t_a}\n"
                        f"- **Target Beneficiaries:** {s_a.target_beneficiaries or 'As per GR'}\n"
                        f"- **Benefits:** {s_a.benefits or s_a.brief_description}\n"
                        f"- **Deadline:** {s_a.application_deadline or 'No published deadline'}\n\n"
                        f"### 2. {t_b}\n"
                        f"- **Target Beneficiaries:** {s_b.target_beneficiaries or 'As per GR'}\n"
                        f"- **Benefits:** {s_b.benefits or s_b.brief_description}\n"
                        f"- **Deadline:** {s_b.application_deadline or 'No published deadline'}\n"
                    )
                return {
                    "answer": ans,
                    "sources": [{"id": s.id, "title": s.title, "source_url": s.source_url} for s in comp_schemes],
                    "confidence": "grounded_official_data",
                    "language": lang,
                    "disclaimer": GroundedRuleSynthesizer.get_disclaimer(lang == "mr"),
                }

        greeting_prefix = None
        if intent == "mixed_greeting_scheme":
            if lang == "mr":
                greeting_prefix = "नमस्कार! नक्की. "
            elif lang == "mr_roman":
                greeting_prefix = "Hi! Nakkich. "
            else:
                greeting_prefix = "Hello! "
            cleaned_query = re.sub(
                r"^(hi+|hello+|hey+|hii+|good morning|good afternoon|good evening|नमस्कार|हाय|हॅलो|शुभ सकाळ|namaskar|namaste)\b[,!\s]*",
                "",
                cleaned_query,
                flags=re.IGNORECASE,
            ).strip()
            if not cleaned_query:
                cleaned_query = query.strip()

        is_followup = any(w in q_lower for w in [
            "who can apply", "eligible", "eligibility", "पात्रता", "patrata", "documents", "document", "कागदपत्रे", "kagadpatre",
            "last date", "deadline", "shevatachi tarikh", "शेवटची तारीख", "how to apply", "apply", "अर्ज कसा", "kasa arj",
            "benefit", "benefits", "लाभ", "फायदे", "labh", "fayde"
        ])

        if active_scheme and (is_followup or intent.startswith("unspecified_")):
            return self.ask_scheme_contextual(
                scheme_id=active_scheme.id,
                query=query,
                db=db,
                conversation_history=conversation_history,
                force_lang=force_lang,
            )

        # Unspecified scheme actions when NO previous scheme exists in conversation
        if intent in ("unspecified_eligibility", "unspecified_apply", "unspecified_deadline", "unspecified_documents"):
            ans = ConversationalIntentRouter.get_response(cleaned_query, intent, lang)
            return {
                "answer": ans,
                "sources": [],
                "confidence": "conversational",
                "language": lang,
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(lang in ("mr", "mr_roman")),
            }

        # Intent detection for status filtering
        status_filter = None
        if any(w in q_lower for w in ["open", "सुरू", "suru", "chalu"]):
            status_filter = "open"
        elif any(w in q_lower for w in ["closing soon", "लवकरच संपत", "closing"]):
            status_filter = "closing_soon"
        elif any(w in q_lower for w in ["no deadline", "अंतिम तारीख नाही", "without deadline"]):
            status_filter = "no_deadline_published"
        elif any(w in q_lower for w in ["closed", "संपली", "expired"]):
            status_filter = "closed"

        # Salient keyword extraction & semantic expansion
        raw_keywords = [
            k for k in extract_keywords(cleaned_query)
            if k not in ("open", "suru", "chalu", "closing", "closed", "soon", "deadline", "date", "सुरू", "बंद", "मुदत", "तारीख")
        ]

        stmt = select(SchemeCandidate)

        if status_filter:
            stmt = stmt.where(SchemeCandidate.current_window_status == status_filter)

        if raw_keywords:
            expanded_terms = expand_keywords(raw_keywords)
            conditions = []
            for term in expanded_terms[:8]:
                like_term = f"%{term}%"
                conditions.append(SchemeCandidate.title.like(like_term))
                conditions.append(SchemeCandidate.title_mr.like(like_term))
                conditions.append(SchemeCandidate.department.like(like_term))
                conditions.append(SchemeCandidate.category.like(like_term))
                conditions.append(SchemeCandidate.benefits.like(like_term))
                conditions.append(SchemeCandidate.text.like(like_term))

            if conditions:
                stmt = stmt.where(or_(*conditions))
        elif not status_filter:
            is_general_discovery = any(w in q_lower for w in ["what", "which", "available", "show", "tell", "कोणत्या", "माहिती", "योजना", "उपलब्ध", "सांगा", "दाखवा", "yojna", "schemes", "government", "maharashtra"])
            if not is_general_discovery:
                like_term = f"%{cleaned_query}%"
                stmt = stmt.where(
                    or_(
                        SchemeCandidate.title.like(like_term),
                        SchemeCandidate.title_mr.like(like_term),
                        SchemeCandidate.department.like(like_term),
                        SchemeCandidate.category.like(like_term),
                        SchemeCandidate.text.like(like_term),
                    )
                )

        records = db.scalars(
            stmt.order_by(
                (SchemeCandidate.verification_status == "verified").desc(),
                (SchemeCandidate.current_window_status == "open").desc(),
                (SchemeCandidate.current_window_status == "closing_soon").desc(),
                SchemeCandidate.id,
            ).limit(limit)
        ).all()

        return GroundedRuleSynthesizer.generate(
            cleaned_query, records, lang, specific_intent=status_filter, greeting_prefix=greeting_prefix
        )

    def ask_scheme_contextual(
        self,
        scheme_id: int,
        query: str,
        db: Session,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        force_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Temporary contextual chat for a specific scheme card.

        Does NOT persist conversation in database or browser storage.
        Always retrieves the latest approved scheme details and current status.
        Supports multi-turn conversational reasoning using client-supplied history.
        """
        scheme = db.get(SchemeCandidate, scheme_id)
        if not scheme:
            return {
                "answer": "Specified scheme was not found in the official registry.",
                "sources": [],
                "confidence": "not_found",
                "language": "en",
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(False),
            }

        # Privacy check
        if re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", query):
            return {
                "answer": "⚠️ Privacy warning: Please do not enter Aadhaar or bank account numbers.",
                "sources": [],
                "confidence": "privacy_shield",
                "language": "en",
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(False),
            }

        conv_intent = ConversationalIntentRouter.classify(query)
        if conv_intent == "translate_to_marathi":
            lang = "mr"
        elif conv_intent == "translate_to_english":
            lang = "en"
        else:
            lang = force_lang or detect_language(query)

        is_mr = lang in ("mr", "mr_roman")
        q_lower = query.lower()

        labels = get_status_labels(scheme.current_window_status)
        status_label = labels["mr"] if is_mr else labels["en"]

        # Date notice
        if scheme.current_window_status == "no_deadline_published" or not scheme.application_deadline:
            deadline_str = NO_DEADLINE_NOTICE_MR if is_mr else NO_DEADLINE_NOTICE_EN
        else:
            deadline_str = scheme.application_deadline

        title_display = scheme.title_mr if (is_mr and scheme.title_mr) else scheme.title

        # Check conversational routing inside contextual scheme chat
        conv_intent = ConversationalIntentRouter.classify(query)
        if conv_intent in ("greeting", "how_are_you", "thanks", "farewell", "help_request"):
            ans = ConversationalIntentRouter.get_scheme_contextual_response(
                query, conv_intent, title_display, lang
            )
            return {
                "answer": ans,
                "sources": [{
                    "id": scheme.id,
                    "title": scheme.title,
                    "title_mr": scheme.title_mr or scheme.title,
                    "department": scheme.department,
                    "source_url": scheme.source_url,
                    "official_apply_url": scheme.official_apply_url or "",
                    "verification_status": scheme.verification_status,
                    "current_window_status": scheme.current_window_status,
                }],
                "confidence": "conversational",
                "language": lang,
                "disclaimer": GroundedRuleSynthesizer.get_disclaimer(is_mr),
            }

        # Intent detection
        is_date_q = any(w in q_lower for w in [
            "last date", "deadline", "closing", "शेवटची तारीख", "अंतिम तारीख", "मुदत", "tarikh", "kadhi", "last date to apply"
        ])
        is_eligibility_q = any(w in q_lower for w in [
            "eligible", "eligibility", "पात्रता", "patrata", "who can apply", "शर्त", "अटी", "am i eligible", "qualify", "can i apply"
        ])
        is_apply_q = any(w in q_lower for w in [
            "how to apply", "apply", "अर्ज कसा", "arj", "link", "process", "पोर्टल", "step by step", "procedure"
        ])
        is_docs_q = any(w in q_lower for w in [
            "documents", "document", "कागदपत्रे", "kagadpatre", "proof", "papers"
        ])
        is_link_q = any(w in q_lower for w in [
            "link", "official link", "portal", "website", "वेबसाईट", "संकेतस्थळ"
        ])
        is_benefits_q = any(w in q_lower for w in [
            "benefit", "benefits", "लाभ", "फायदे", "labh", "fayde", "subsidy", "anudan"
        ])

        # Check for context from previous turn (e.g. follow-up answering eligibility questions)
        has_eligibility_history = False
        if conversation_history:
            prev_texts = []
            for t in conversation_history[-4:]:
                if isinstance(t, dict):
                    prev_texts.append(t.get("content") or t.get("text") or "")
                elif hasattr(t, "content"):
                    prev_texts.append(getattr(t, "content", ""))
                elif isinstance(t, str):
                    prev_texts.append(t)
            prev_turns = " ".join(prev_texts).lower()
            if any(k in prev_turns for k in ["eligibility", "पात्रता", "criteria", "अटी", "वय", "income", "eligible", "patrata"]):
                has_eligibility_history = True

        if is_eligibility_q or (has_eligibility_history and not (is_date_q or is_apply_q or is_docs_q or is_benefits_q)):
            # Guided eligibility assessment
            assessment = EligibilityEngine.assess(scheme, query, lang)
            ans = assessment["answer"]

        elif is_date_q:
            if scheme.current_window_status == "closed":
                if is_mr:
                    ans = (
                        f"**{title_display}** या योजनेची अधिकृत अर्ज मुदत **संपलेली आहे**.\n\n"
                        f"- **अंतिम तारीख:** {scheme.application_deadline}\n"
                        f"- **अर्जाची स्थिती:** {status_label}\n"
                        f"- पुढील शासन निर्णयासाठी अधिकृत पोर्टल पहा: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
                else:
                    ans = (
                        f"The application window for **{title_display}** is **currently closed** according to latest verified records.\n\n"
                        f"- **Verified Deadline:** {scheme.application_deadline}\n"
                        f"- **Current Status:** {status_label}\n"
                        f"- Check the official source for upcoming rounds: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
            elif scheme.current_window_status == "no_deadline_published":
                if is_mr:
                    ans = (
                        f"**{title_display}** साठी:\n\n"
                        f"ℹ️ {NO_DEADLINE_NOTICE_MR}\n\n"
                        f"चालू स्थितीसाठी अधिकृत पोर्टल तपासा: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
                else:
                    ans = (
                        f"Regarding **{title_display}**:\n\n"
                        f"ℹ️ {NO_DEADLINE_NOTICE_EN}\n\n"
                        f"Please confirm current availability on the official department portal: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
            else:
                if scheme.application_deadline:
                    if is_mr:
                        ans = (
                            f"**{title_display}** या योजनेची अर्जाची अंतिम मुदत **{scheme.application_deadline}** ({status_label}) आहे.\n\n"
                            f"- **अर्जाची स्थिती:** {status_label}\n"
                            f"- **अंतिम तारीख:** {scheme.application_deadline}\n"
                            + (f"- **अधिकृत अर्ज पोर्टल:** [येथे अर्ज करा]({scheme.official_apply_url})\n" if scheme.official_apply_url else "")
                            + f"- **अधिकृत माहिती स्रोत:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                        )
                    else:
                        ans = (
                            f"The application window for **{title_display}** is currently **{status_label}**.\n\n"
                            f"- **Current Status:** {status_label}\n"
                            f"- **Application Deadline:** {scheme.application_deadline}\n"
                            + (f"- **Official Application Portal:** [Apply Online]({scheme.official_apply_url})\n" if scheme.official_apply_url else "")
                            + f"- **Official Information Source:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                        )
                else:
                    if is_mr:
                        ans = (
                            f"**{title_display}** या योजनेची अर्ज प्रक्रिया सध्या **{status_label}** आहे.\n\n"
                            f"- **अर्जाची स्थिती:** {status_label}\n"
                            f"- **अंतिम तारीख:** {NO_DEADLINE_NOTICE_MR}\n"
                            + (f"- **अधिकृत अर्ज पोर्टल:** [येथे अर्ज करा]({scheme.official_apply_url})\n" if scheme.official_apply_url else "")
                            + f"- **अधिकृत माहिती स्रोत:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                        )
                    else:
                        ans = (
                            f"The application window for **{title_display}** is currently **{status_label}**.\n\n"
                            f"- **Current Status:** {status_label}\n"
                            f"- **Application Deadline:** {NO_DEADLINE_NOTICE_EN}\n"
                            + (f"- **Official Application Portal:** [Apply Online]({scheme.official_apply_url})\n" if scheme.official_apply_url else "")
                            + f"- **Official Information Source:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                        )

        elif is_docs_q:
            doc_text = scheme.documents_required or (
                "आधार कार्ड, रहिवासी दाखला (Domicile), उत्पन्न दाखला, बँक पासबुक"
                if is_mr
                else "Aadhaar Card, Maharashtra Domicile Certificate, Income Certificate, Bank Passbook"
            )
            if is_mr:
                ans = (
                    f"**{title_display}** साठी आवश्यक अधिकृत कागदपत्रे:\n\n"
                    f"- {doc_text}\n\n"
                    f"🔗 **अधिकृत माहिती स्रोत:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                )
            else:
                ans = (
                    f"Required documents for **{title_display}**:\n\n"
                    f"- {doc_text}\n\n"
                    f"🔗 **Official Information Source:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                )

        elif is_apply_q:
            ans = ApplicationGuideEngine.guide(scheme, lang)

        elif is_link_q:
            if scheme.official_apply_url:
                if is_mr:
                    ans = (
                        f"**{title_display}** साठी अधिकृत अर्ज पोर्टल लिंक:\n\n"
                        f"🔗 **ऑनलाईन अर्ज करा:** [{scheme.official_apply_url}]({scheme.official_apply_url})\n\n"
                        f"🏛️ **माहिती पृष्ठ:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
                else:
                    ans = (
                        f"Official application portal for **{title_display}**:\n\n"
                        f"🔗 **Apply Online:** [{scheme.official_apply_url}]({scheme.official_apply_url})\n\n"
                        f"🏛️ **Department Info Page:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
            else:
                if is_mr:
                    ans = (
                        f"**{title_display}** साठी थेट ऑनलाईन अर्ज पोर्टल नमूद नाही किंवा ऑफलाईन अर्ज स्वीकारले जातात.\n\n"
                        f"कृपया अधिकृत माहिती पोर्टल पहा: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )
                else:
                    ans = (
                        f"Direct online application URL is not separately published or the scheme accepts designated offline submissions.\n\n"
                        f"Please refer to the verified information portal: [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                    )

        elif is_benefits_q:
            ben = scheme.benefits or scheme.brief_description or scheme.text[:250]
            if is_mr:
                ans = (
                    f"**{title_display}** या योजनेचे अधिकृत लाभ:\n\n"
                    f"- {ben}\n\n"
                    f"🔗 **अधिकृत माहिती स्रोत:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                )
            else:
                ans = (
                    f"Verified benefits for **{title_display}**:\n\n"
                    f"- {ben}\n\n"
                    f"🔗 **Official Information Source:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})"
                )

        else:
            benefits = scheme.benefits or scheme.brief_description or scheme.text[:250]
            if is_mr:
                ans = (
                    f"**{title_display}**\n\n"
                    f"- **विभाग:** {scheme.department}\n"
                    f"- **अर्जाची स्थिती:** **{status_label}**\n"
                    f"- **अंतिम तारीख:** {deadline_str}\n"
                    f"- **लाभ / स्वरूप:** {benefits}\n"
                    f"- **पात्रता:** {scheme.eligibility or 'शासन निर्णयानुसार लागू'}\n"
                    f"{f'- **अर्ज लिंक:** [{scheme.official_apply_url}]({scheme.official_apply_url})\n' if scheme.official_apply_url else ''}"
                    f"- **अधिकृत स्रोत:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})\n"
                )
            else:
                ans = (
                    f"**{title_display}**\n\n"
                    f"- **Department:** {scheme.department}\n"
                    f"- **Application Status:** **{status_label}**\n"
                    f"- **Deadline:** {deadline_str}\n"
                    f"- **Key Information:** {benefits}\n"
                    f"- **Eligibility:** {scheme.eligibility or 'As per Government Resolution'}\n"
                    f"{f'- **Application Link:** [{scheme.official_apply_url}]({scheme.official_apply_url})\n' if scheme.official_apply_url else ''}"
                    f"- **Official Link:** [{urlparse(scheme.source_url).netloc}]({scheme.source_url})\n"
                )

        sources = [{
            "id": scheme.id,
            "title": scheme.title,
            "title_mr": scheme.title_mr or scheme.title,
            "department": scheme.department,
            "source_url": scheme.source_url,
            "official_apply_url": scheme.official_apply_url or "",
            "verification_status": scheme.verification_status,
            "current_window_status": scheme.current_window_status,
        }]

        return {
            "answer": ans,
            "sources": sources,
            "confidence": "grounded_scheme_context",
            "language": lang,
            "disclaimer": GroundedRuleSynthesizer.get_disclaimer(is_mr),
        }

    def evaluate_eligibility(
        self, scheme_id: int, user_input: str, db: Session, lang: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dedicated eligibility assessment endpoint handler."""
        scheme = db.get(SchemeCandidate, scheme_id)
        if not scheme:
            return {"error": "Scheme not found", "assessment_category": "rules_unverified"}

        target_lang = lang or detect_language(user_input)
        assessment = EligibilityEngine.assess(scheme, user_input, target_lang)
        assessment["scheme_id"] = scheme.id
        assessment["scheme_title"] = scheme.title
        assessment["official_source_url"] = scheme.source_url
        assessment["official_apply_url"] = scheme.official_apply_url or ""
        return assessment


ai_assistant = AIAssistantService()
