from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint, CheckConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Organisation(Base, TimestampMixin):
    __tablename__ = "organisations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text)
    brand_voice: Mapped[Optional[str]] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role in ('admin','creator','reviewer')", name="ck_user_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    organisation: Mapped[Organisation] = relationship()


class _RuleBase(TimestampMixin):
    """Columns shared by every kind of stored brand rule."""
    id: Mapped[int] = mapped_column(primary_key=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BrandGuideline(Base, _RuleBase):
    __tablename__ = "brand_guidelines"
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="Medium", nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSON)  # e.g. {"required_phrases": [...]}


class ApprovedFact(Base, _RuleBase):
    __tablename__ = "approved_facts"
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    correct_value: Mapped[str] = mapped_column(String(200), nullable=False)
    match_pattern: Mapped[Optional[str]] = mapped_column(String(400))  # optional regex; group 1 = value
    valid_until: Mapped[Optional[date]] = mapped_column(Date)


class Terminology(Base, _RuleBase):
    __tablename__ = "terminology"
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    approved_term: Mapped[str] = mapped_column(String(200), nullable=False)
    incorrect_variants: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)


class ProhibitedWord(Base, _RuleBase):
    __tablename__ = "prohibited_words"
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    phrase: Mapped[str] = mapped_column(String(300), nullable=False)
    suggested_replacement: Mapped[Optional[str]] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(10), default="High", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)


class ApprovedClaim(Base, _RuleBase):
    __tablename__ = "approved_claims"
    __table_args__ = (CheckConstraint("status in ('approved','requires_evidence')", name="ck_claim_status"),)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="requires_evidence", nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text)


class ContentSubmission(Base, TimestampMixin):
    __tablename__ = "content_submissions"
    __table_args__ = (Index("ix_content_org_status", "organisation_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), default="text", nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(300))
    stored_filename: Mapped[Optional[str]] = mapped_column(String(100))
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    revised_text: Mapped[Optional[str]] = mapped_column(Text)
    extraction_meta: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    creator: Mapped[User] = relationship()

    @property
    def current_text(self) -> str:
        return self.revised_text if self.revised_text is not None else self.original_text


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (UniqueConstraint("submission_id", "run_number", name="uq_run"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    analysed_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_status: Mapped[str] = mapped_column(String(300), default="not_configured", nullable=False)
    issue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ComplianceIssue(Base):
    __tablename__ = "compliance_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    flagged_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_char: Mapped[Optional[int]] = mapped_column(Integer)
    end_char: Mapped[Optional[int]] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    rule_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(10), default="rule", nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    requires_human_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    suggestion: Mapped[Optional["CorrectionSuggestion"]] = relationship(
        back_populates="issue", uselist=False, cascade="all, delete-orphan")


class CorrectionSuggestion(Base):
    __tablename__ = "correction_suggestions"
    __table_args__ = (
        CheckConstraint("status in ('pending','accepted','rejected','edited')", name="ck_sugg_status"),
        CheckConstraint("action in ('replace','append','manual')", name="ck_sugg_action"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("compliance_issues.id", ondelete="CASCADE"), unique=True)
    action: Mapped[str] = mapped_column(String(10), default="replace", nullable=False)
    original_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    issue: Mapped[ComplianceIssue] = relationship(back_populates="suggestion")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("decision in ('approved','rejected','changes_requested')", name="ck_review_decision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewer: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(40))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user: Mapped[Optional[User]] = relationship()
