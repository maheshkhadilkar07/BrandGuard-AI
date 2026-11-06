from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN, ROLE_REVIEWER, ST_APPROVED, ST_CHANGES, ST_REJECTED, ST_SUBMITTED
from app.core.database import get_db
from app.core.deps import require_roles
from app.models import ContentSubmission, Review, User
from app.routers.content import detail, get_submission, review_out
from app.schemas.content import ContentDetail, ContentListItem, ReviewIn, ReviewOut
from app.services import audit

router = APIRouter(tags=["Review and approval"])
reviewer_only = require_roles(ROLE_REVIEWER)
staff = require_roles(ROLE_REVIEWER, ROLE_ADMIN)

_NEXT = {"approved": ST_APPROVED, "rejected": ST_REJECTED, "changes_requested": ST_CHANGES}


@router.get("/reviews/queue", response_model=list[ContentListItem])
def queue(user: User = Depends(staff), db: Session = Depends(get_db)):
    from app.routers.content import list_content
    return list_content(status=ST_SUBMITTED, user=user, db=db)


@router.post("/content/{content_id}/review", response_model=ContentDetail)
def decide(content_id: int, data: ReviewIn, user: User = Depends(reviewer_only), db: Session = Depends(get_db)):
    """Only a human Reviewer can approve, reject or request changes. The AI never does."""
    sub = get_submission(db, user, content_id)
    if sub.status != ST_SUBMITTED:
        raise HTTPException(409, "Only content that has been submitted for review can be reviewed.")
    if sub.creator_id == user.id:
        raise HTTPException(403, "You cannot review your own content.")
    if data.decision in ("rejected", "changes_requested") and not (data.comment or "").strip():
        raise HTTPException(422, "Please give a reason or comment for this decision.")
    db.add(Review(submission_id=sub.id, reviewer_id=user.id, decision=data.decision,
                  comment=(data.comment or "").strip() or None))
    sub.status = _NEXT[data.decision]
    audit.log(db, user, f"review.{data.decision}", "content", sub.id, (data.comment or "")[:200])
    db.commit()
    db.refresh(sub)
    return detail(db, sub)


@router.get("/reviews", response_model=list[ReviewOut])
def review_history(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.execute(select(Review, ContentSubmission.title)
                      .join(ContentSubmission, ContentSubmission.id == Review.submission_id)
                      .where(ContentSubmission.organisation_id == user.organisation_id)
                      .order_by(Review.decided_at.desc())).all()
    return [review_out(r, t) for r, t in rows]
