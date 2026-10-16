"""Database models for MahaSeva AI (compatible with SQLAlchemy 1.4 & 2.0+).

Stores scheme candidates, verified schemes, historical versions, application windows,
audit logs, and source registries.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import foreign, relationship

from backend.database import Base


class SchemeCandidate(Base):
    """Stores scheme candidates discovered from official Maharashtra government portals."""

    __tablename__ = "scheme_candidates"

    __table_args__ = (
        UniqueConstraint(
            "source_url_sha256",
            "content_sha256",
            name="uq_candidate_source_content",
        ),
        Index("idx_candidate_dept", "department"),
        Index("idx_candidate_status", "verification_status"),
        Index("idx_candidate_title", "title"),
        Index("idx_candidate_window_status", "current_window_status"),
        Index("idx_candidate_category", "category"),
    )

    id = Column(Integer, primary_key=True)

    title = Column(String(1000), nullable=False)
    title_mr = Column(String(1000), nullable=True, default="")
    department = Column(String(500), nullable=False)
    category = Column(String(200), nullable=False, default="General")
    target_beneficiaries = Column(Text, nullable=True, default="")
    application_mode = Column(String(50), nullable=False, default="online")  # online, offline, both

    source_url = Column(String(2048), nullable=False)
    source_url_sha256 = Column(String(64), nullable=False)

    source_type = Column(String(100), default="", nullable=False)
    retrieved_at_utc = Column(String(100), default="", nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    text = Column(MEDIUMTEXT, nullable=False)
    pdf_urls = Column(Text, nullable=False, default="")

    provider_classification = Column(String(100), nullable=False, default="unverified")
    # Verification workflow: pending_review, verified, rejected, needs_update, outdated
    verification_status = Column(String(50), nullable=False, default="pending_review")
    notes = Column(Text, nullable=False, default="")

    imported_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Structured verification fields
    brief_description = Column(Text, nullable=True, default="")
    benefits = Column(Text, nullable=True, default="")
    eligibility = Column(Text, nullable=True, default="")
    documents_required = Column(Text, nullable=True, default="")
    application_process = Column(Text, nullable=True, default="")
    official_apply_url = Column(String(2048), nullable=True, default="")
    last_reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True, default="")

    # Application Window & Deadline Tracking
    # Machine readable states: open, closing_soon, upcoming, closed, no_deadline_published, date_unverified, temporarily_unavailable, discontinued
    current_window_status = Column(String(50), nullable=False, default="no_deadline_published")
    application_start_date = Column(String(50), nullable=True)  # YYYY-MM-DD
    application_deadline = Column(String(50), nullable=True)  # YYYY-MM-DD
    closing_time = Column(String(50), nullable=True)  # HH:MM:SS or HH:MM
    date_verification_status = Column(String(50), nullable=False, default="unverified")  # verified, unverified, conflicting, no_deadline

    # Discovery & Update Metadata
    is_recently_announced = Column(Boolean, nullable=False, default=False)
    is_recently_updated = Column(Boolean, nullable=False, default=False)
    announced_date = Column(String(50), nullable=True)
    effective_date = Column(String(50), nullable=True)
    official_notification_url = Column(String(2048), nullable=True, default="")
    last_checked_at = Column(DateTime, nullable=True)

    # Relationships
    audit_logs = relationship(
        "VerificationAudit",
        primaryjoin="SchemeCandidate.id == foreign(VerificationAudit.candidate_id)",
        order_by="desc(VerificationAudit.created_at)",
    )
    application_windows = relationship(
        "SchemeApplicationWindow",
        primaryjoin="SchemeCandidate.id == foreign(SchemeApplicationWindow.scheme_id)",
        order_by="desc(SchemeApplicationWindow.id)",
    )
    changes = relationship(
        "SchemeChange",
        primaryjoin="SchemeCandidate.id == foreign(SchemeChange.scheme_id)",
        order_by="desc(SchemeChange.id)",
    )


class SchemeApplicationWindow(Base):
    """Stores distinct application periods, rounds, and extensions for a scheme."""

    __tablename__ = "scheme_application_windows"

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, nullable=False, index=True)
    window_name = Column(String(255), nullable=False, default="General Application Window")
    start_date = Column(String(50), nullable=True)
    deadline_date = Column(String(50), nullable=True)
    closing_time = Column(String(50), nullable=True)
    window_status = Column(String(50), nullable=False, default="no_deadline_published")
    date_verification_status = Column(String(50), nullable=False, default="verified")
    official_source_url = Column(String(2048), nullable=True, default="")
    notes = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SchemeChange(Base):
    """Tracks detected changes to schemes, deadlines, eligibility, or benefits."""

    __tablename__ = "scheme_changes"

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, nullable=True, index=True)
    change_type = Column(
        String(100),
        nullable=False,
    )  # new_scheme_candidate, deadline_extension, eligibility_change, benefits_change, new_round, url_change, discontinuation
    field_name = Column(String(100), nullable=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=True)
    source_url = Column(String(2048), nullable=False)
    detection_timestamp = Column(DateTime, nullable=False, server_default=func.now())
    review_status = Column(String(50), nullable=False, default="pending_review")  # pending_review, approved, rejected
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True, default="")


class SchemeSourceVersion(Base):
    """Stores historical versions, content hashes, and auditable excerpts."""

    __tablename__ = "scheme_source_versions"

    id = Column(Integer, primary_key=True)
    source_url = Column(String(2048), nullable=False)
    source_url_sha256 = Column(String(64), nullable=False, index=True)
    content_sha256 = Column(String(64), nullable=False)
    retrieved_at = Column(DateTime, nullable=False, server_default=func.now())
    http_status = Column(Integer, default=200, nullable=False)
    content_excerpt = Column(Text, nullable=True)
    detected_changes_count = Column(Integer, default=0, nullable=False)


class AdminUser(Base):
    """Administrative user accounts for scheme verification and monitoring."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="admin")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class VerificationAudit(Base):
    """Audit log tracking all changes to candidate verification status and details."""

    __tablename__ = "verification_audits"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, nullable=False, index=True)
    reviewer_username = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    previous_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True, default="")
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class CollectionRun(Base):
    """Tracks collection / crawl runs, stats, and failures."""

    __tablename__ = "collection_runs"

    id = Column(Integer, primary_key=True)
    started_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="running")
    total_candidates = Column(Integer, default=0, nullable=False)
    new_candidates = Column(Integer, default=0, nullable=False)
    updated_candidates = Column(Integer, default=0, nullable=False)
    errors_count = Column(Integer, default=0, nullable=False)
    log_summary = Column(Text, nullable=True, default="")


class ConfiguredSource(Base):
    """Configured Maharashtra Government source registries."""

    __tablename__ = "configured_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    department = Column(String(500), nullable=True)
    source_category = Column(String(100), nullable=True, default="Departmental Portal")
    start_urls = Column(Text, nullable=False)
    allowed_domains = Column(Text, nullable=False)
    provider_hint = Column(String(50), default="state", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    monitoring_frequency_hours = Column(Integer, default=24, nullable=False)
    crawl_depth = Column(Integer, default=2, nullable=False)
    max_pages = Column(Integer, default=50, nullable=False)
    priority = Column(String(50), default="medium", nullable=False)  # high, medium, low
    verification_required = Column(Boolean, default=True, nullable=False)
    last_crawled_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_changed_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
