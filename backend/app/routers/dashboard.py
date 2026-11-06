from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN, ROLE_CREATOR, ROLE_REVIEWER, SEVERITIES, STATUSES
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import (ApprovedClaim, ApprovedFact, AuditLog, BrandGuideline, ComplianceIssue, ContentSubmission,
                        ProhibitedWord, Review, Terminology, User)

router = APIRouter(tags=["Dashboard, analytics and audit"])


def _scope(user: User):
    conds = [ContentSubmission.organisation_id == user.organisation_id]
    if user.role == ROLE_CREATOR:
        conds.append(ContentSubmission.creator_id == user.id)
    return conds


def _issue_rows(db, user, column):
    """Counts of issues from each submission's latest analysis run."""
    return db.execute(
        select(column, func.count()).select_from(ComplianceIssue)
        .join(ContentSubmission, ContentSubmission.id == ComplianceIssue.submission_id)
        .where(*_scope(user), ComplianceIssue.run_number == ContentSubmission.run_count)
        .group_by(column).order_by(func.count().desc())).all()


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status_rows = dict(db.execute(select(ContentSubmission.status, func.count()).where(*_scope(user))
                                  .group_by(ContentSubmission.status)).all())
    by_status = {s: status_rows.get(s, 0) for s in STATUSES}
    sev = dict(_issue_rows(db, user, ComplianceIssue.severity))
    by_severity = {s: sev.get(s, 0) for s in SEVERITIES}
    audit_q = select(AuditLog).where(AuditLog.organisation_id == user.organisation_id)
    if user.role == ROLE_CREATOR:
        audit_q = audit_q.where(AuditLog.user_id == user.id)
    recent = [{"id": a.id, "action": a.action, "details": a.details, "entity_type": a.entity_type,
               "entity_id": a.entity_id, "user": a.user.full_name if a.user else None, "created_at": a.created_at}
              for a in db.scalars(audit_q.order_by(AuditLog.created_at.desc()).limit(10))]
    out = {
        "role": user.role,
        "total_submissions": sum(by_status.values()),
        "awaiting_review": by_status["submitted"],
        "approved": by_status["approved"],
        "rejected": by_status["rejected"],
        "changes_requested": by_status["changes_requested"],
        "by_status": by_status,
        "total_issues": sum(by_severity.values()),
        "issues_by_severity": by_severity,
        "issues_by_category": [{"category": c, "count": n} for c, n in _issue_rows(db, user, ComplianceIssue.category)],
        "recent_activity": recent,
    }
    if user.role == ROLE_ADMIN:
        out["users"] = db.scalar(select(func.count(User.id)).where(User.organisation_id == user.organisation_id))
        org = user.organisation_id
        out["rule_counts"] = {
            "guidelines": db.scalar(select(func.count(BrandGuideline.id)).where(BrandGuideline.organisation_id == org)),
            "facts": db.scalar(select(func.count(ApprovedFact.id)).where(ApprovedFact.organisation_id == org)),
            "terminology": db.scalar(select(func.count(Terminology.id)).where(Terminology.organisation_id == org)),
            "prohibited_words": db.scalar(select(func.count(ProhibitedWord.id)).where(ProhibitedWord.organisation_id == org)),
            "claims": db.scalar(select(func.count(ApprovedClaim.id)).where(ApprovedClaim.organisation_id == org)),
        }
    if user.role == ROLE_REVIEWER:
        out["my_decisions"] = db.scalar(select(func.count(Review.id)).where(Review.reviewer_id == user.id))
    return out


@router.get("/analytics")
def analytics(user: User = Depends(require_roles(ROLE_ADMIN, ROLE_REVIEWER)), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=14)
    per_day = db.execute(
        select(func.date(ContentSubmission.created_at), func.count()).where(
            *_scope(user), ContentSubmission.created_at >= since)
        .group_by(func.date(ContentSubmission.created_at)).order_by(func.date(ContentSubmission.created_at))).all()
    decisions = dict(db.execute(
        select(Review.decision, func.count()).join(ContentSubmission, ContentSubmission.id == Review.submission_id)
        .where(*_scope(user)).group_by(Review.decision)).all())
    top_rules = db.execute(
        select(ComplianceIssue.rule_reference, func.count()).select_from(ComplianceIssue)
        .join(ContentSubmission, ContentSubmission.id == ComplianceIssue.submission_id)
        .where(*_scope(user)).group_by(ComplianceIssue.rule_reference)
        .order_by(func.count().desc()).limit(10)).all()
    return {
        "issues_by_category": [{"category": c, "count": n} for c, n in _issue_rows(db, user, ComplianceIssue.category)],
        "issues_by_severity": [{"severity": s, "count": n} for s, n in _issue_rows(db, user, ComplianceIssue.severity)],
        "most_violated_rules": [{"rule": r, "count": n} for r, n in top_rules],
        "submissions_per_day": [{"date": str(d), "count": n} for d, n in per_day],
        "review_decisions": {k: decisions.get(k, 0) for k in ("approved", "rejected", "changes_requested")},
    }


@router.get("/audit")
def audit_log(limit: int = 100, user: User = Depends(require_roles(ROLE_ADMIN)), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = db.scalars(select(AuditLog).where(AuditLog.organisation_id == user.organisation_id)
                      .order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": a.id, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
             "details": a.details, "user": a.user.full_name if a.user else None, "created_at": a.created_at}
            for a in rows]
