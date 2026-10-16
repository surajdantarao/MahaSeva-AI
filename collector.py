#!/usr/bin/env python3
"""MahaSeva AI official Maharashtra scheme candidate collector.

Crawls configured public government pages, extracts HTML/PDF text, tracks sources,
and creates a human-review queue. This is a candidate collector, not a guarantee
of complete coverage or legal/provider verification.
"""
import hashlib
import json
import logging
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import pymupdf
import pandas as pd
import requests
import trafilatura
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((ROOT / "sites.json").read_text(encoding="utf-8"))

USER_AGENT = os.getenv(
    "COLLECTOR_USER_AGENT",
    "MahaSevaSchemeResearchBot/1.0 (student project; replace-with-contact)"
)
DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", "1.5"))
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
MAX_PAGES_PER_SITE = int(os.getenv("MAX_PAGES_PER_SITE", "80"))
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(OUT / "collector.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("mahaseva")
session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8"
})
robots_cache = {}
last_request = {}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def clean_url(url):
    if not url:
        return ""
    url, _fragment = urldefrag(url.strip())
    return url if urlparse(url).scheme in ("http", "https") else ""


def allowed(url, domains):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in domains)


def get_robots(url):
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in robots_cache:
        rp = RobotFileParser()
        robots_url = urljoin(origin, "/robots.txt")
        rp.set_url(robots_url)
        try:
            response = session.get(robots_url, timeout=TIMEOUT)
            if response.status_code < 400:
                rp.parse(response.text.splitlines())
            else:
                # Fail conservatively if robots.txt cannot be checked.
                rp.parse(["User-agent: *", "Disallow: /"])
                log.warning("Could not read robots.txt for %s; skipping host.", origin)
        except requests.RequestException as exc:
            rp.parse(["User-agent: *", "Disallow: /"])
            log.warning("robots.txt request failed for %s: %s", origin, exc)
        robots_cache[origin] = rp
    return robots_cache[origin]


def fetch(url):
    if not get_robots(url).can_fetch(USER_AGENT, url):
        log.info("Robots.txt disallows: %s", url)
        return None

    host = urlparse(url).netloc.lower()
    wait = DELAY - (time.time() - last_request.get(host, 0))
    if wait > 0:
        time.sleep(wait)

    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    last_request[host] = time.time()

    if response.status_code in (401, 403, 429):
        log.warning("HTTP %s; not bypassing access/rate limit: %s", response.status_code, url)
        return None

    response.raise_for_status()
    return response


def sha256_text(text):
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_title(title):
    value = title.lower()
    value = re.sub(r"\.(pdf|html?)$", "", value)
    value = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_pdf(blob):
    try:
        with pymupdf.open(stream=blob, filetype="pdf") as doc:
            return "\n".join(page.get_text("text") for page in doc).strip()
    except Exception as exc:
        log.warning("PDF extraction failed: %s", exc)
        return ""


def classify_provider(title, text):
    sample = (title + "\n" + text[:8000]).lower()
    central_markers = [
        "government of india", "central government", "centrally sponsored",
        "ministry of", "pradhan mantri", "भारत सरकार", "प्रधानमंत्री",
        "national food security mission", "pmksy", "rashtriya krushi vikas yojana"
    ]
    state_markers = [
        "government of maharashtra", "maharashtra government",
        "महाराष्ट्र शासन", "महाराष्ट्र सरकार", "शासन निर्णय",
        "महिला व बाल विकास विभाग", "महाराष्ट्र राज्य"
    ]
    central = any(marker in sample for marker in central_markers)
    state = any(marker in sample for marker in state_markers)

    if central and state:
        return "state_or_joint_review", "State and central indicators found; verify scheme funding/provider."
    if central:
        return "central_or_joint_review", "Central indicators found; do not include as state-only without evidence."
    if state:
        return "likely_state", "State indicators found; verify against current GR/official order."
    return "unverified", "Provider not clear from extracted text; manual review required."


def is_candidate(title, text):
    keywords = [
        "scheme", "yojana", "programme", "program", "benefit", "subsidy",
        "pension", "scholarship", "ladki bahin", "majhi ladki bahin",
        "farmer scheme", "agriculture scheme", "farm mechanization",
        "micro-irrigation", "crop insurance", "farm equipment",
        "krushi", "shetkari", "phalbaag", "namo shetkari",
        "नमो शेतकरी", "लाडकी बहीण", "कृषी योजना", "शेतकरी योजना",
        "योजना", "अनुदान", "शिष्यवृत्ती", "लाभ", "शासन निर्णय"
    ]
    combined = (title + " " + text[:12000]).lower()
    return len(text.strip()) >= 80 and any(k in combined for k in keywords)


def make_record(title, department, url, source_type, text, pdf_urls=""):
    provider, note = classify_provider(title, text)
    return {
        "title": title or "Untitled",
        "department": department,
        "source_url": url,
        "source_type": source_type,
        "retrieved_at_utc": now_utc(),
        "content_sha256": sha256_text(text),
        "text": text[:100000],
        "pdf_urls": pdf_urls,
        "provider_classification": provider,
        "verification_status": "needs_human_review",
        "notes": note + " Confirm this is a distinct, current Maharashtra State Government scheme."
    }


def parse_url(url, department, allowed_domains):
    response = fetch(url)
    if response is None:
        return None, []

    final_url = clean_url(response.url)
    content_type = response.headers.get("Content-Type", "").lower()
    is_pdf = "application/pdf" in content_type or final_url.lower().split("?")[0].endswith(".pdf")

    if is_pdf:
        if len(response.content) > MAX_PDF_MB * 1024 * 1024:
            log.warning("PDF exceeds %s MB; skipping: %s", MAX_PDF_MB, final_url)
            return None, []
        text = extract_pdf(response.content)
        if not text:
            log.warning("No selectable text found in PDF; scanned PDF may need OCR: %s", final_url)
            return None, []
        title = Path(urlparse(final_url).path).name or "Government PDF"
        return make_record(title, department, final_url, "pdf", text, final_url), []

    if "text/html" not in content_type and "<html" not in response.text[:1000].lower():
        return None, []

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)

    extracted = trafilatura.extract(response.text, include_tables=True)
    if extracted and len(extracted) > len(text) * 0.25:
        text = extracted

    links, pdf_links = [], []
    for anchor in soup.find_all("a", href=True):
        href = clean_url(urljoin(final_url, anchor["href"]))
        if not href:
            continue
        path = urlparse(href).path.lower()
        if path.endswith(".pdf"):
            # Permit PDFs only on the configured official domains.
            if allowed(href, allowed_domains):
                pdf_links.append(href)
        elif allowed(href, allowed_domains) and not urlparse(href).query:
            links.append(href)

    record = None
    if is_candidate(title, text):
        record = make_record(
            title, department, final_url, "html", text,
            ";".join(sorted(set(pdf_links)))
        )
    return record, links


def crawl_site(site):
    domains = site["allowed_domains"]
    department = site["name"]
    queue = deque(clean_url(u) for u in site["start_urls"])
    seen = set()
    records = []

    while queue and len(seen) < MAX_PAGES_PER_SITE:
        url = queue.popleft()
        if not url or url in seen or not allowed(url, domains):
            continue
        seen.add(url)

        try:
            record, links = parse_url(url, department, domains)
            if record:
                records.append(record)
                # Fetch same-domain PDFs linked from candidate pages.
                for pdf_url in record.get("pdf_urls", "").split(";"):
                    if pdf_url and pdf_url not in seen and allowed(pdf_url, domains):
                        try:
                            pdf_record, _ = parse_url(pdf_url, department, domains)
                            if pdf_record:
                                records.append(pdf_record)
                            seen.add(pdf_url)
                        except requests.RequestException as exc:
                            log.warning("PDF request failed %s: %s", pdf_url, exc)

            for link in links:
                path = urlparse(link).path.lower()
                if link not in seen and not any(
                    token in path for token in ["/login", "/logout", "/wp-admin"]
                ):
                    queue.append(link)

        except requests.RequestException as exc:
            log.warning("Request failed %s: %s", url, exc)
        except Exception:
            log.exception("Unexpected extraction error: %s", url)

    log.info("%s: visited %d URLs, candidates %d", department, len(seen), len(records))
    return records


def deduplicate(records):
    # Exact URL/title duplicates are removed. Same titles on different URLs are flagged.
    kept = {}
    for record in records:
        key = (clean_url(record["source_url"]), normalize_title(record["title"]))
        if key not in kept or len(record.get("text", "")) > len(kept[key].get("text", "")):
            kept[key] = record

    result = list(kept.values())
    title_groups = {}
    for record in result:
        title_groups.setdefault(normalize_title(record["title"]), []).append(record)

    for group in title_groups.values():
        if len(group) > 1:
            for record in group:
                record["notes"] += "; Same normalized title found at another URL; review possible duplicate."
    return result


def main():
    all_records = []
    for site in CONFIG["sites"]:
        log.info("Crawling %s", site["name"])
        all_records.extend(crawl_site(site))

    records = deduplicate(all_records)
    df = pd.DataFrame(records)

    columns = [
        "title", "department", "source_url", "source_type", "retrieved_at_utc",
        "content_sha256", "text", "pdf_urls", "provider_classification",
        "verification_status", "notes"
    ]
    if df.empty:
        df = pd.DataFrame(columns=columns)
    else:
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns].sort_values(["department", "title"], na_position="last")

    df.to_csv(OUT / "schemes_candidates.csv", index=False, encoding="utf-8-sig")
    df.to_json(OUT / "schemes_candidates.json", orient="records", force_ascii=False, indent=2)
    review_columns = [
        "title", "department", "source_url", "source_type",
        "provider_classification", "verification_status", "notes", "pdf_urls"
    ]
    df[review_columns].to_csv(OUT / "review_queue.csv", index=False, encoding="utf-8-sig")

    manifest = {
        "generated_at_utc": now_utc(),
        "candidate_records": len(df),
        "configured_sources": [site["name"] for site in CONFIG["sites"]],
        "limitations": [
            "This is not a complete catalogue of all Maharashtra schemes.",
            "All records require human verification.",
            "MahaDBT contains central and joint schemes as well as state schemes.",
            "Some portals require JavaScript or may block crawling.",
            "Scanned PDFs may require OCR.",
            "Provider classification is heuristic and not proof of scheme funding."
        ]
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("Done. %d candidate records. See %s", len(df), OUT)


if __name__ == "__main__":
    main()
