"""MahaSeva AI - Centralized Maharashtra Government Scheme Discovery & Assistance Platform.

FastAPI application providing public citizen APIs, grounded AI guidance, deadline monitoring,
and secured administrative verification workflows.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.ai_assistant import (
    ApplicationGuideEngine,
    EligibilityEngine,
    ai_assistant,
)
from backend.auth import (
    create_access_token,
    get_current_admin,
    require_admin_role,
    verify_password,
)
from backend.database import SessionLocal
from backend.models import (
    AdminUser,
    CollectionRun,
    ConfiguredSource,
    SchemeApplicationWindow,
    SchemeCandidate,
    SchemeChange,
    VerificationAudit,
)
from backend.scheduler import (
    execute_monitoring_cycle,
    get_scheduler_status,
    recalculate_all_deadlines,
    start_background_scheduler,
    stop_background_scheduler,
)
from backend.status_engine import (
    NO_DEADLINE_NOTICE_EN,
    NO_DEADLINE_NOTICE_MR,
    calculate_window_status,
    get_status_labels,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Launch background monitoring scheduler
    start_background_scheduler(check_interval_seconds=1800)
    yield
    # Shutdown: Stop scheduler thread
    stop_background_scheduler()


app = FastAPI(
    title="MahaSeva AI API",
    description="Authoritative Maharashtra Government Scheme Discovery & Citizen Assistance API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS setup
cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


# ==============================================================================
# Pydantic Schemas
# ==============================================================================


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6)


class AIAskRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


class AISchemeChatRequest(BaseModel):
    scheme_id: int = Field(..., ge=1)
    query: str = Field(..., min_length=1, max_length=1000)


class AIChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., max_length=4000)


class AIChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    scheme_id: Optional[int] = Field(default=None, ge=1)
    conversation_history: Optional[List[AIChatMessage]] = Field(default=None)
    lang: Optional[str] = Field(default=None)


class AIEligibilityRequest(BaseModel):
    scheme_id: int = Field(..., ge=1)
    user_input: str = Field(..., min_length=1, max_length=2000)
    lang: Optional[str] = Field(default=None)


class SchemeReviewRequest(BaseModel):
    verification_status: str = Field(
        ...,
        pattern="^(pending_review|verified|rejected|needs_update|outdated)$",
        description="Updated verification workflow status",
    )
    notes: Optional[str] = Field(default="")
    brief_description: Optional[str] = None
    benefits: Optional[str] = None
    eligibility: Optional[str] = None
    documents_required: Optional[str] = None
    application_process: Optional[str] = None
    official_apply_url: Optional[str] = None
    # Deadline & category overrides
    category: Optional[str] = None
    application_start_date: Optional[str] = None
    application_deadline: Optional[str] = None
    closing_time: Optional[str] = None
    current_window_status: Optional[str] = None


class ChangeReviewRequest(BaseModel):
    review_status: str = Field(..., pattern="^(approved|rejected)$")
    review_notes: Optional[str] = Field(default="")


class SourceCreateUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    department: Optional[str] = Field(default="")
    source_category: Optional[str] = Field(default="Departmental Portal")
    start_urls: List[str] = Field(..., min_length=1)
    allowed_domains: List[str] = Field(..., min_length=1)
    provider_hint: str = Field(default="state")
    is_active: bool = Field(default=True)
    monitoring_frequency_hours: int = Field(default=24, ge=1, le=168)
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")


# ==============================================================================
# Public Citizen Endpoints
# ==============================================================================


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "mahaseva-ai-api",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
    }


@app.get("/api/v1/system/status")
def system_status(db: Session = Depends(get_db)):
    """Real-time system health dashboard metrics."""
    try:
        total = db.scalar(select(func.count()).select_from(SchemeCandidate)) or 0
        verified = db.scalar(
            select(func.count()).select_from(SchemeCandidate).where(
                SchemeCandidate.verification_status == "verified"
            )
        ) or 0
        pending = db.scalar(
            select(func.count()).select_from(SchemeCandidate).where(
                SchemeCandidate.verification_status == "pending_review"
            )
        ) or 0
        dept_count = db.scalar(
            select(func.count(func.distinct(SchemeCandidate.department)))
        ) or 0
        latest_run = db.scalar(
            select(CollectionRun).order_by(desc(CollectionRun.started_at)).limit(1)
        )
        source_count = db.scalar(
            select(func.count()).select_from(ConfiguredSource).where(
                ConfiguredSource.is_active == True
            )
        ) or 0
        scheduler_info = get_scheduler_status()

        return {
            "status": "operational",
            "database": "connected",
            "schemes": {
                "total": total,
                "verified": verified,
                "pending_review": pending,
                "departments": dept_count,
            },
            "sources": {"active_count": source_count},
            "last_collection_run": {
                "started_at": latest_run.started_at.isoformat() if latest_run else None,
                "status": latest_run.status if latest_run else None,
                "new_candidates": latest_run.new_candidates if latest_run else 0,
            } if latest_run else None,
            "scheduler": scheduler_info,
            "ai_provider": os.getenv("AI_PROVIDER", "rule_based"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "database": "error",
            "error": str(exc),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/v1/schemes/summary")
def scheme_summary(db: Session = Depends(get_db)):
    """Summary metrics of registered scheme candidates, verified records, and deadline states."""
    total = db.scalar(select(func.count()).select_from(SchemeCandidate)) or 0

    status_rows = db.execute(
        select(SchemeCandidate.verification_status, func.count()).group_by(
            SchemeCandidate.verification_status
        )
    ).all()

    window_rows = db.execute(
        select(SchemeCandidate.current_window_status, func.count()).group_by(
            SchemeCandidate.current_window_status
        )
    ).all()

    dept_rows = db.execute(
        select(SchemeCandidate.department, func.count()).group_by(
            SchemeCandidate.department
        )
    ).all()

    category_rows = db.execute(
        select(SchemeCandidate.category, func.count()).group_by(
            SchemeCandidate.category
        )
    ).all()

    return {
        "total_candidates": total,
        "verified_count": sum(c for s, c in status_rows if s == "verified"),
        "pending_count": sum(c for s, c in status_rows if s == "pending_review"),
        "statuses": {status_name: count for status_name, count in status_rows},
        "deadline_statuses": {win_name: count for win_name, count in window_rows},
        "department_counts": {dept: count for dept, count in dept_rows},
        "category_counts": {cat: count for cat, count in category_rows},
    }


@app.get("/api/v1/schemes/departments")
def list_departments(db: Session = Depends(get_db)):
    """List all available government departments with candidate counts."""
    dept_rows = db.execute(
        select(
            SchemeCandidate.department,
            func.count(SchemeCandidate.id).label("total"),
            func.sum(
                func.if_(SchemeCandidate.verification_status == "verified", 1, 0)
            ).label("verified"),
        )
        .group_by(SchemeCandidate.department)
        .order_by(SchemeCandidate.department)
    ).all()

    return {
        "departments": [
            {
                "name": d[0],
                "total_schemes": d[1],
                "verified_schemes": int(d[2] or 0),
            }
            for d in dept_rows
        ]
    }


@app.get("/api/v1/schemes/categories")
def list_categories(db: Session = Depends(get_db)):
    """List all available scheme categories with counts, icons, and bilingual labels."""
    category_rows = db.execute(
        select(
            SchemeCandidate.category,
            func.count(SchemeCandidate.id).label("total"),
            func.sum(
                func.if_(SchemeCandidate.verification_status == "verified", 1, 0)
            ).label("verified"),
        )
        .group_by(SchemeCandidate.category)
        .order_by(func.count(SchemeCandidate.id).desc())
    ).all()

    category_meta = {
        "Agriculture": {"icon": "tractor", "name_mr": "कृषी व शेतकरी कल्याण"},
        "Education": {"icon": "graduation-cap", "name_mr": "शिक्षण व शिष्यवृत्ती"},
        "Social Justice": {"icon": "users", "name_mr": "सामाजिक न्याय"},
        "Women and Child": {"icon": "heart", "name_mr": "महिला व बालकल्याण"},
        "Health": {"icon": "activity", "name_mr": "आरोग्य व वैद्यकीय मदत"},
        "Housing": {"icon": "home", "name_mr": "गृहनिर्माण व निवारा"},
        "Employment": {"icon": "briefcase", "name_mr": "रोजगार व कौशल्य विकास"},
        "General": {"icon": "info", "name_mr": "इतर सर्वसाधारण योजना"},
    }

    results = []
    for row in category_rows:
        cat_name = row[0] or "General"
        meta = category_meta.get(cat_name, {"icon": "bookmark", "name_mr": cat_name})
        results.append({
            "name": cat_name,
            "name_mr": meta["name_mr"],
            "icon": meta["icon"],
            "total_schemes": row[1],
            "verified_schemes": int(row[2] or 0),
        })

    return {"categories": results}


def _format_scheme_item(item: SchemeCandidate) -> Dict[str, Any]:
    labels = get_status_labels(item.current_window_status)
    return {
        "id": item.id,
        "title": item.title,
        "title_mr": item.title_mr or item.title,
        "department": item.department,
        "category": item.category or "General",
        "target_beneficiaries": item.target_beneficiaries or "",
        "application_mode": item.application_mode or "online",
        "source_url": item.source_url,
        "source_type": item.source_type,
        "provider_classification": item.provider_classification,
        "verification_status": item.verification_status,
        "current_window_status": item.current_window_status,
        "status_label_en": labels["en"],
        "status_label_mr": labels["mr"],
        "badge_class": labels["badge_class"],
        "application_start_date": item.application_start_date,
        "application_deadline": item.application_deadline,
        "closing_time": item.closing_time,
        "no_deadline_notice_en": NO_DEADLINE_NOTICE_EN if item.current_window_status == "no_deadline_published" else None,
        "no_deadline_notice_mr": NO_DEADLINE_NOTICE_MR if item.current_window_status == "no_deadline_published" else None,
        "brief_description": item.brief_description or item.text[:220].strip() + "...",
        "benefits": item.benefits or "",
        "eligibility": item.eligibility or "",
        "official_apply_url": item.official_apply_url or "",
        "pdf_urls": [u for u in item.pdf_urls.split(";") if u.strip()],
        "is_recently_announced": item.is_recently_announced,
        "is_recently_updated": item.is_recently_updated,
        "retrieved_at_utc": item.retrieved_at_utc,
        "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
        "notes": item.notes,
    }


@app.get("/api/v1/schemes/homepage-sections")
def homepage_sections(db: Session = Depends(get_db)):
    """Retrieve dynamic scheme groups for the homepage sections without static content."""
    base_stmt = select(SchemeCandidate).order_by(desc(SchemeCandidate.id))

    open_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.current_window_status == "open")
        .order_by(SchemeCandidate.application_deadline.asc())
        .limit(6)
    ).all()

    closing_soon_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.current_window_status == "closing_soon")
        .order_by(SchemeCandidate.application_deadline.asc())
        .limit(6)
    ).all()

    upcoming_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.current_window_status == "upcoming")
        .order_by(SchemeCandidate.application_start_date.asc())
        .limit(6)
    ).all()

    no_deadline_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.current_window_status == "no_deadline_published")
        .order_by(desc(SchemeCandidate.id))
        .limit(6)
    ).all()

    recent_announced_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.is_recently_announced == True)
        .order_by(desc(SchemeCandidate.id))
        .limit(6)
    ).all()

    recent_updated_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.is_recently_updated == True)
        .order_by(desc(SchemeCandidate.id))
        .limit(6)
    ).all()

    closed_items = db.scalars(
        select(SchemeCandidate)
        .where(SchemeCandidate.current_window_status == "closed")
        .order_by(desc(SchemeCandidate.application_deadline))
        .limit(6)
    ).all()

    return {
        "sections": {
            "open_now": {
                "title_en": "Applications Open Now",
                "title_mr": "अर्ज आता सुरू आहेत",
                "count": len(open_items),
                "items": [_format_scheme_item(i) for i in open_items],
            },
            "closing_soon": {
                "title_en": "Closing Soon",
                "title_mr": "लवकरच मुदत संपत आहे",
                "count": len(closing_soon_items),
                "items": [_format_scheme_item(i) for i in closing_soon_items],
            },
            "upcoming": {
                "title_en": "Upcoming Schemes",
                "title_mr": "लवकरच सुरू होणाऱ्या योजना",
                "count": len(upcoming_items),
                "items": [_format_scheme_item(i) for i in upcoming_items],
            },
            "no_deadline": {
                "title_en": "No Published Deadline",
                "title_mr": "अंतिम तारीख नमूद नसलेल्या योजना",
                "count": len(no_deadline_items),
                "items": [_format_scheme_item(i) for i in no_deadline_items],
            },
            "recently_announced": {
                "title_en": "Recently Announced Schemes",
                "title_mr": "नुकत्याच जाहीर झालेल्या योजना",
                "count": len(recent_announced_items),
                "items": [_format_scheme_item(i) for i in recent_announced_items],
            },
            "recently_updated": {
                "title_en": "Recently Updated Schemes",
                "title_mr": "नुकतीच माहिती अद्ययावत झालेल्या योजना",
                "count": len(recent_updated_items),
                "items": [_format_scheme_item(i) for i in recent_updated_items],
            },
            "closed": {
                "title_en": "Closed Application Windows",
                "title_mr": "अर्ज मुदत संपलेल्या योजना",
                "count": len(closed_items),
                "items": [_format_scheme_item(i) for i in closed_items],
            },
        }
    }


@app.get("/api/v1/schemes")
def search_schemes(
    q: str = Query(default="", max_length=200, description="Keyword search"),
    department: str = Query(default="", max_length=300, description="Department filter"),
    category: str = Query(default="", max_length=200, description="Category filter"),
    verification_status: str = Query(default="", max_length=50, description="Status filter"),
    deadline_status: str = Query(default="", max_length=50, description="Deadline state filter"),
    provider_classification: str = Query(default="", max_length=100, description="Provider filter"),
    application_mode: str = Query(default="", max_length=50, description="Application mode filter"),
    sort_by: str = Query(default="id_desc", description="Sorting criteria (id_desc, id_asc, title_asc, deadline_asc)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Search scheme records with multi-criteria filtering and pagination."""
    statement = select(SchemeCandidate)

    if q.strip():
        raw_q = q.strip()
        term = f"%{raw_q}%"
        tokens = [t for t in raw_q.split() if len(t) > 1]

        # Expand Marathi keywords to English & transliterated equivalents
        marathi_synonyms = {
            "शेतकरी": ["shetkari", "farmer", "agriculture", "krishi"],
            "कृषी": ["krushi", "krishi", "agriculture", "crop"],
            "कर्ज": ["loan", "credit", "karjamukti"],
            "कर्जमुक्ती": ["karjamukti", "debt waiver", "loan waiver"],
            "महिला": ["women", "mahila", "woman"],
            "बाल": ["child", "bal"],
            "शिष्यवृत्ती": ["scholarship", "stipend"],
            "विद्यार्थी": ["student", "vidyarthi"],
            "पेन्शन": ["pension"],
            "अनुदान": ["subsidy", "grant", "assistance"],
            "आरोग्य": ["health", "medical", "arogya"],
            "शिक्षण": ["education", "school", "shikshan"],
            "पाणी": ["water", "pani"],
            "सिंचन": ["irrigation", "sinchan"],
            "घरकुल": ["housing", "gharkul", "shelter"],
            "गृहनिर्माण": ["housing"],
            "रोजगार": ["employment", "job", "rojgar"],
            "दिव्यांग": ["disability", "handicap", "divyang"],
            "अपंग": ["disability", "handicap"],
            "सहकार": ["co-operation", "cooperative"],
            "कापूस": ["cotton"],
            "उद्योग": ["industry", "business"],
            "अल्पसंख्याक": ["minority"],
        }

        extra_terms: List[str] = []
        for m_key, eng_equivs in marathi_synonyms.items():
            if m_key in raw_q:
                extra_terms.extend(eng_equivs)

        conditions = [
            SchemeCandidate.title.like(term),
            SchemeCandidate.title_mr.like(term),
            SchemeCandidate.department.like(term),
            SchemeCandidate.category.like(term),
            SchemeCandidate.text.like(term),
            SchemeCandidate.brief_description.like(term),
            SchemeCandidate.benefits.like(term),
            SchemeCandidate.eligibility.like(term),
        ]

        # Match any expanded terms
        for ext in extra_terms[:6]:
            ext_term = f"%{ext}%"
            conditions.extend([
                SchemeCandidate.title.like(ext_term),
                SchemeCandidate.brief_description.like(ext_term),
                SchemeCandidate.benefits.like(ext_term),
            ])

        if len(tokens) > 1:
            for tok in tokens[:4]:
                tok_term = f"%{tok}%"
                conditions.extend([
                    SchemeCandidate.title.like(tok_term),
                    SchemeCandidate.title_mr.like(tok_term),
                    SchemeCandidate.department.like(tok_term),
                    SchemeCandidate.brief_description.like(tok_term),
                ])

        statement = statement.where(or_(*conditions))

    if department.strip():
        statement = statement.where(SchemeCandidate.department == department.strip())

    if category.strip():
        cat_clean = category.strip()
        cat_lower = cat_clean.lower()
        if any(k in cat_lower for k in ("agri", "farm", "शेतकरी", "कृषी")):
            statement = statement.where(
                or_(
                    SchemeCandidate.category.like("%Agri%"),
                    SchemeCandidate.category == "Agriculture",
                )
            )
        elif any(k in cat_lower for k in ("social", "welfare", "सामाजिक")):
            statement = statement.where(
                or_(
                    SchemeCandidate.category.like("%Social%"),
                    SchemeCandidate.category == "Social Justice & Welfare",
                )
            )
        elif any(k in cat_lower for k in ("women", "child", "महिला", "बाल")):
            statement = statement.where(
                or_(
                    SchemeCandidate.category.like("%Women%"),
                    SchemeCandidate.category.like("%Child%"),
                    SchemeCandidate.department.like("%Women%"),
                )
            )
        elif any(k in cat_lower for k in ("urban", "नगर")):
            statement = statement.where(
                or_(
                    SchemeCandidate.category.like("%Urban%"),
                    SchemeCandidate.department.like("%Urban%"),
                )
            )
        elif any(k in cat_lower for k in ("textil", "co-op", "सहकार", "वस्त्रोद्योग")):
            statement = statement.where(
                or_(
                    SchemeCandidate.category.like("%Textil%"),
                    SchemeCandidate.category.like("%Co-op%"),
                )
            )
        else:
            statement = statement.where(
                or_(
                    SchemeCandidate.category == cat_clean,
                    SchemeCandidate.category.like(f"%{cat_clean}%"),
                )
            )

    if verification_status.strip():
        statement = statement.where(
            SchemeCandidate.verification_status == verification_status.strip()
        )

    if deadline_status.strip():
        statement = statement.where(
            SchemeCandidate.current_window_status == deadline_status.strip()
        )

    if provider_classification.strip():
        statement = statement.where(
            SchemeCandidate.provider_classification == provider_classification.strip()
        )

    if application_mode.strip():
        statement = statement.where(
            SchemeCandidate.application_mode == application_mode.strip()
        )

    # Sorting
    if sort_by == "title_asc":
        statement = statement.order_by(SchemeCandidate.title.asc())
    elif sort_by == "id_asc":
        statement = statement.order_by(SchemeCandidate.id.asc())
    elif sort_by == "deadline_asc":
        statement = statement.order_by(SchemeCandidate.application_deadline.asc().nulls_last())
    else:
        statement = statement.order_by(desc(SchemeCandidate.id))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = db.scalars(statement.offset(offset).limit(limit)).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_format_scheme_item(item) for item in records],
    }


@app.get("/api/v1/schemes/{scheme_id}")
def get_scheme_details(scheme_id: int, db: Session = Depends(get_db)):
    """Retrieve complete verified scheme or candidate record details including application windows."""
    item = db.get(SchemeCandidate, scheme_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {scheme_id} was not found.",
        )

    # Fetch application windows
    windows = db.scalars(
        select(SchemeApplicationWindow).where(SchemeApplicationWindow.scheme_id == scheme_id)
    ).all()

    labels = get_status_labels(item.current_window_status)

    return {
        "id": item.id,
        "title": item.title,
        "title_mr": item.title_mr or item.title,
        "department": item.department,
        "category": item.category or "General",
        "target_beneficiaries": item.target_beneficiaries or "",
        "application_mode": item.application_mode or "online",
        "source_url": item.source_url,
        "source_type": item.source_type,
        "text": item.text,
        "pdf_urls": [u for u in item.pdf_urls.split(";") if u.strip()],
        "provider_classification": item.provider_classification,
        "verification_status": item.verification_status,
        "current_window_status": item.current_window_status,
        "status_label_en": labels["en"],
        "status_label_mr": labels["mr"],
        "badge_class": labels["badge_class"],
        "application_start_date": item.application_start_date,
        "application_deadline": item.application_deadline,
        "closing_time": item.closing_time,
        "no_deadline_notice_en": NO_DEADLINE_NOTICE_EN if item.current_window_status == "no_deadline_published" else None,
        "no_deadline_notice_mr": NO_DEADLINE_NOTICE_MR if item.current_window_status == "no_deadline_published" else None,
        "brief_description": item.brief_description or "",
        "benefits": item.benefits or "",
        "eligibility": item.eligibility or "",
        "documents_required": item.documents_required or "",
        "application_process": item.application_process or "",
        "official_apply_url": item.official_apply_url or "",
        "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
        "reviewed_by": item.reviewed_by or None,
        "retrieved_at_utc": item.retrieved_at_utc,
        "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
        "imported_at": item.imported_at.isoformat(),
        "is_recently_announced": item.is_recently_announced,
        "is_recently_updated": item.is_recently_updated,
        "notes": item.notes,
        "application_windows": [
            {
                "id": w.id,
                "window_name": w.window_name,
                "start_date": w.start_date,
                "deadline_date": w.deadline_date,
                "closing_time": w.closing_time,
                "window_status": w.window_status,
                "date_verification_status": w.date_verification_status,
                "official_source_url": w.official_source_url,
                "notes": w.notes,
            }
            for w in windows
        ],
    }


@app.get("/api/v1/schemes/{scheme_id}/sources")
def get_scheme_sources(scheme_id: int, db: Session = Depends(get_db)):
    """Retrieve supporting official government sources, GRs, and portals for a scheme."""
    item = db.get(SchemeCandidate, scheme_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {scheme_id} was not found.",
        )

    pdf_list = [u for u in item.pdf_urls.split(";") if u.strip()]
    return {
        "scheme_id": item.id,
        "title": item.title,
        "title_mr": item.title_mr or item.title,
        "department": item.department,
        "source_url": item.source_url,
        "official_apply_url": item.official_apply_url or None,
        "source_type": item.source_type,
        "pdf_urls": pdf_list,
        "retrieved_at_utc": item.retrieved_at_utc,
        "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
        "verification_status": item.verification_status,
        "is_official_gov_domain": any(
            d in item.source_url.lower() for d in [".gov.in", ".nic.in", "maharashtra.gov.in"]
        ),
    }


@app.get("/api/v1/schemes/{scheme_id}/application-guide")
def get_scheme_application_guide(scheme_id: int, db: Session = Depends(get_db)):
    """Retrieve structured, verified step-by-step application guidance in English and Marathi."""
    item = db.get(SchemeCandidate, scheme_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {scheme_id} was not found.",
        )

    return {
        "scheme_id": item.id,
        "title": item.title,
        "title_mr": item.title_mr or item.title,
        "department": item.department,
        "application_mode": item.application_mode or "online",
        "official_apply_url": item.official_apply_url or None,
        "official_source_url": item.source_url,
        "documents_required": item.documents_required or "",
        "guide_en": ApplicationGuideEngine.guide(item, lang="en"),
        "guide_mr": ApplicationGuideEngine.guide(item, lang="mr"),
    }


@app.post("/api/v1/ai/ask")
def ask_ai_assistant(req: AIAskRequest, db: Session = Depends(get_db)):
    """Citizen AI Assistant: Grounded RAG with official source attribution and bilingual answers."""
    try:
        response = ai_assistant.ask(query=req.query, db=db, limit=req.limit)
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI retrieval error: {str(exc)}",
        )


@app.post("/api/v1/ai/scheme-chat")
def ask_ai_scheme_contextual(req: AISchemeChatRequest, db: Session = Depends(get_db)):
    """Temporary contextual chat on a specific scheme card. Does NOT persist conversation in database."""
    try:
        response = ai_assistant.ask_scheme_contextual(
            scheme_id=req.scheme_id, query=req.query, db=db
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contextual chat error: {str(exc)}",
        )


@app.post("/api/v1/ai/chat")
def ai_chat(req: AIChatRequest, db: Session = Depends(get_db)):
    """Temporary citizen conversational chat with optional scheme context and ephemeral multi-turn history.

    CRITICAL PRIVACY: Does NOT persist transcripts to database, cookies, or files.
    All multi-turn state is passed in-memory by client in req.conversation_history.
    """
    try:
        history_list = []
        if req.conversation_history:
            for msg in req.conversation_history:
                history_list.append({"role": msg.role, "content": msg.content})

        if req.scheme_id:
            response = ai_assistant.ask_scheme_contextual(
                scheme_id=req.scheme_id,
                query=req.query,
                db=db,
                conversation_history=history_list,
                force_lang=req.lang,
            )
            response["scheme_id"] = req.scheme_id
        else:
            response = ai_assistant.ask(
                query=req.query,
                db=db,
                limit=5,
                conversation_history=history_list,
                force_lang=req.lang,
            )

        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI chat error: {str(exc)}",
        )


@app.post("/api/v1/ai/eligibility")
def evaluate_scheme_eligibility(req: AIEligibilityRequest, db: Session = Depends(get_db)):
    """Evaluate user circumstances against documented official eligibility criteria for a scheme."""
    item = db.get(SchemeCandidate, req.scheme_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID {req.scheme_id} was not found.",
        )

    res = ai_assistant.evaluate_eligibility(
        scheme_id=req.scheme_id, user_input=req.user_input, db=db, lang=req.lang
    )
    return res


@app.get("/api/v1/sources")
def get_configured_sources(db: Session = Depends(get_db)):
    """List official government sources registered for monitoring."""
    sources = db.scalars(select(ConfiguredSource).where(ConfiguredSource.is_active == True)).all()
    return {
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "department": s.department or s.name,
                "source_category": s.source_category or "Departmental Portal",
                "start_urls": [u for u in s.start_urls.split(";") if u],
                "allowed_domains": [d for d in s.allowed_domains.split(";") if d],
                "provider_hint": s.provider_hint,
                "priority": s.priority or "medium",
                "monitoring_frequency_hours": s.monitoring_frequency_hours,
                "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                "last_error": s.last_error,
            }
            for s in sources
        ]
    }


# ==============================================================================
# Administrator & Verification Endpoints (Protected by JWT)
# ==============================================================================


@app.post("/api/v1/admin/auth/login")
def admin_login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate administrator or reviewer credentials."""
    user = db.scalar(
        select(AdminUser).where(
            AdminUser.username == req.username,
            AdminUser.is_active == True,
        )
    )

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
    }


@app.get("/api/v1/admin/auth/me")
def admin_me(current_admin: AdminUser = Depends(get_current_admin)):
    """Return currently authenticated administrator profile."""
    return {
        "id": current_admin.id,
        "username": current_admin.username,
        "email": current_admin.email,
        "role": current_admin.role,
        "is_active": current_admin.is_active,
    }


@app.post("/api/v1/admin/schemes/{scheme_id}/review")
def review_scheme_candidate(
    scheme_id: int,
    req: SchemeReviewRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Review, verify, edit, or reject a scheme candidate. Enforces audit logging."""
    candidate = db.get(SchemeCandidate, scheme_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {scheme_id} not found.",
        )

    previous_status = candidate.verification_status
    new_status = req.verification_status

    candidate.verification_status = new_status
    candidate.last_reviewed_at = datetime.now(timezone.utc)
    candidate.reviewed_by = current_admin.username

    if req.notes:
        candidate.notes = (candidate.notes or "") + f"\n[{current_admin.username}]: {req.notes}"

    if req.brief_description is not None:
        candidate.brief_description = req.brief_description
    if req.benefits is not None:
        candidate.benefits = req.benefits
    if req.eligibility is not None:
        candidate.eligibility = req.eligibility
    if req.documents_required is not None:
        candidate.documents_required = req.documents_required
    if req.application_process is not None:
        candidate.application_process = req.application_process
    if req.official_apply_url is not None:
        candidate.official_apply_url = req.official_apply_url

    if req.category is not None:
        candidate.category = req.category
    if req.application_start_date is not None:
        candidate.application_start_date = req.application_start_date
    if req.application_deadline is not None:
        candidate.application_deadline = req.application_deadline
    if req.closing_time is not None:
        candidate.closing_time = req.closing_time

    # Recalculate status using status engine
    new_win_status, _ = calculate_window_status(
        start_date_str=candidate.application_start_date,
        deadline_date_str=candidate.application_deadline,
        closing_time_str=candidate.closing_time,
        override_status=req.current_window_status,
    )
    candidate.current_window_status = new_win_status

    # Record audit trail
    audit_log = VerificationAudit(
        candidate_id=candidate.id,
        reviewer_username=current_admin.username,
        action=f"status_change_to_{new_status}",
        previous_status=previous_status,
        new_status=new_status,
        notes=req.notes or f"Status changed from {previous_status} to {new_status}",
    )
    db.add(audit_log)
    db.commit()
    db.refresh(candidate)

    return {
        "message": f"Scheme #{candidate.id} successfully updated to status '{new_status}'.",
        "candidate": {
            "id": candidate.id,
            "title": candidate.title,
            "verification_status": candidate.verification_status,
            "current_window_status": candidate.current_window_status,
            "reviewed_by": candidate.reviewed_by,
            "last_reviewed_at": candidate.last_reviewed_at.isoformat(),
        },
    }


@app.get("/api/v1/admin/changes")
def list_scheme_changes(
    review_status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List detected scheme changes awaiting verification or reviewed."""
    stmt = select(SchemeChange).order_by(desc(SchemeChange.detection_timestamp))
    if review_status:
        stmt = stmt.where(SchemeChange.review_status == review_status)

    changes = db.scalars(stmt.limit(limit)).all()
    return {
        "items": [
            {
                "id": c.id,
                "scheme_id": c.scheme_id,
                "change_type": c.change_type,
                "field_name": c.field_name,
                "previous_value": c.previous_value,
                "new_value": c.new_value,
                "evidence_text": c.evidence_text,
                "source_url": c.source_url,
                "detection_timestamp": c.detection_timestamp.isoformat(),
                "review_status": c.review_status,
                "reviewed_by": c.reviewed_by,
                "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
                "review_notes": c.review_notes,
            }
            for c in changes
        ]
    }


@app.post("/api/v1/admin/changes/{change_id}/review")
def review_detected_change(
    change_id: int,
    req: ChangeReviewRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Approve or reject a detected scheme change."""
    chg = db.get(SchemeChange, change_id)
    if not chg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change with ID {change_id} not found.",
        )

    chg.review_status = req.review_status
    chg.reviewed_by = current_admin.username
    chg.reviewed_at = datetime.now(timezone.utc)
    chg.review_notes = req.review_notes

    # If approved, apply the field update to the scheme if field is application_deadline
    if req.review_status == "approved" and chg.scheme_id:
        scheme = db.get(SchemeCandidate, chg.scheme_id)
        if scheme and chg.field_name == "application_deadline" and chg.new_value:
            scheme.application_deadline = chg.new_value
            # Recalculate status
            calc_st, _ = calculate_window_status(
                start_date_str=scheme.application_start_date,
                deadline_date_str=scheme.application_deadline,
                closing_time_str=scheme.closing_time,
            )
            scheme.current_window_status = calc_st

    db.commit()
    db.refresh(chg)
    return {
        "message": f"Change #{change_id} marked as {req.review_status}.",
        "change": {
            "id": chg.id,
            "review_status": chg.review_status,
            "reviewed_by": chg.reviewed_by,
        },
    }


@app.get("/api/v1/admin/monitoring/stats")
def monitoring_stats(current_admin: AdminUser = Depends(get_current_admin)):
    """Return live scheduler health, execution history, and metrics."""
    return get_scheduler_status()


@app.post("/api/v1/admin/monitoring/trigger")
def trigger_monitoring_scan(
    current_admin: AdminUser = Depends(require_admin_role),
):
    """Trigger an immediate manual monitoring run across official sources."""
    result = execute_monitoring_cycle()
    return {
        "message": "Monitoring run executed.",
        "result": result,
        "triggered_by": current_admin.username,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/admin/audit-logs")
def list_audit_logs(
    candidate_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """View verification audit history."""
    stmt = select(VerificationAudit).order_by(desc(VerificationAudit.created_at))
    if candidate_id:
        stmt = stmt.where(VerificationAudit.candidate_id == candidate_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    audits = db.scalars(stmt.offset(offset).limit(limit)).all()

    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "candidate_id": a.candidate_id,
                "reviewer_username": a.reviewer_username,
                "action": a.action,
                "previous_status": a.previous_status,
                "new_status": a.new_status,
                "notes": a.notes,
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ],
    }


@app.get("/api/v1/admin/collection-runs")
def list_collection_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List past crawl and monitoring runs."""
    runs = db.scalars(
        select(CollectionRun).order_by(desc(CollectionRun.started_at)).limit(limit)
    ).all()

    return {
        "runs": [
            {
                "id": r.id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "status": r.status,
                "total_candidates": r.total_candidates,
                "new_candidates": r.new_candidates,
                "updated_candidates": r.updated_candidates,
                "errors_count": r.errors_count,
                "log_summary": r.log_summary,
            }
            for r in runs
        ]
    }


@app.post("/api/v1/admin/collection-runs/trigger")
def trigger_collection_sync(
    background_tasks: BackgroundTasks,
    current_admin: AdminUser = Depends(require_admin_role),
):
    """Trigger candidate sync & monitoring run in background."""
    background_tasks.add_task(execute_monitoring_cycle)
    return {
        "message": "Candidate collection sync initiated in background.",
        "triggered_by": current_admin.username,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
