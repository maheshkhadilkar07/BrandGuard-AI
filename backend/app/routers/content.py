import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.constants import (EDITABLE_STATUSES, ROLE_ADMIN, ROLE_CREATOR, ROLE_REVIEWER, ST_ANALYZED,
                                ST_DRAFT, ST_SUBMITTED, STATUSES)
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import (AnalysisRun, ComplianceIssue, ContentSubmission, CorrectionSuggestion, Review, User, utcnow)
from app.schemas.content import (ContentCreate, ContentDetail, ContentListItem, ContentUpdate, IssueOut, ReviewOut,
                                 RunOut, SuggestionOut, SuggestionUpdate)
from app.services import analysis, audit
from app.services.extraction import ALLOWED_EXTENSIONS, ExtractionError, extract_text, signature_ok

router = APIRouter(tags=["Content"])
settings = get_settings()
creator_only = require_roles(ROLE_CREATOR)


# ------------------------------------------------------------------ helpers
def get_submission(db: Session, user: User, content_id: int, owner_only: bool = False) -> ContentSubmission:
    sub = db.get(ContentSubmission, content_id)
    if sub is None or sub.organisation_id != user.organisation_id:
        raise HTTPException(404, "Content not found.")
    if user.role == ROLE_CREATOR and sub.creator_id != user.id:
        raise HTTPException(404, "Content not found.")  # creators only see their own content
    if owner_only and sub.creator_id != user.id:
        raise HTTPException(403, "Only the creator can do this.")
    return sub


def latest_issues(db: Session, sub: ContentSubmission, run: Optional[int] = None):
    run_no = run or sub.run_count
    if not run_no:
        return []
    return db.scalars(select(ComplianceIssue).options(selectinload(ComplianceIssue.suggestion))
                      .where(ComplianceIssue.submission_id == sub.id, ComplianceIssue.run_number == run_no)
                      .order_by(ComplianceIssue.id)).all()


def review_out(r: Review, title: Optional[str] = None) -> ReviewOut:
    return ReviewOut(id=r.id, submission_id=r.submission_id, reviewer_id=r.reviewer_id,
                     reviewer_name=r.reviewer.full_name, decision=r.decision, comment=r.comment,
                     decided_at=r.decided_at, content_title=title)


def detail(db: Session, sub: ContentSubmission) -> ContentDetail:
    runs = db.scalars(select(AnalysisRun).where(AnalysisRun.submission_id == sub.id)
                      .order_by(AnalysisRun.run_number.desc())).all()
    reviews = db.scalars(select(Review).where(Review.submission_id == sub.id).order_by(Review.decided_at)).all()
    return ContentDetail(
        id=sub.id, title=sub.title, source_type=sub.source_type, original_filename=sub.original_filename,
        status=sub.status, creator_id=sub.creator_id, creator_name=sub.creator.full_name,
        original_text=sub.original_text, revised_text=sub.revised_text, current_text=sub.current_text,
        extraction_meta=sub.extraction_meta, run_count=sub.run_count, created_at=sub.created_at,
        updated_at=sub.updated_at, submitted_at=sub.submitted_at,
        issues=[IssueOut.model_validate(i) for i in latest_issues(db, sub)],
        runs=[RunOut.model_validate(r) for r in runs], reviews=[review_out(r) for r in reviews])


def _new_submission(db, user, title, text, source_type, filename=None, stored=None, meta=None):
    if len(text) > settings.MAX_TEXT_CHARS:
        raise HTTPException(413, f"Text is too long (limit {settings.MAX_TEXT_CHARS:,} characters).")
    sub = ContentSubmission(organisation_id=user.organisation_id, creator_id=user.id, title=title.strip(),
                            source_type=source_type, original_filename=filename, stored_filename=stored,
                            original_text=text, extraction_meta=meta, status=ST_DRAFT)
    db.add(sub)
    db.flush()
    audit.log(db, user, "content.created", "content", sub.id, f"source={source_type}")
    db.commit()
    db.refresh(sub)
    return sub


# ------------------------------------------------------------------ create / read
@router.post("/content", response_model=ContentDetail, status_code=201)
def create_text_content(data: ContentCreate, user: User = Depends(creator_only), db: Session = Depends(get_db)):
    return detail(db, _new_submission(db, user, data.title, data.text, "text"))


@router.post("/content/upload", response_model=ContentDetail, status_code=201)
async def upload_content(file: UploadFile = File(...), title: Optional[str] = Form(None),
                         user: User = Depends(creator_only), db: Session = Depends(get_db)):
    original = Path(file.filename or "").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Unsupported file type. Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS)))
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is too large (limit {settings.MAX_UPLOAD_MB} MB).")
    if not data:
        raise HTTPException(422, "The file is empty.")
    if not signature_ok(ext, data[:16]):
        raise HTTPException(422, f"The file content does not look like a valid {ext} file.")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"  # never use the client's file name on disk
    path = upload_dir / stored
    path.write_bytes(data)
    try:
        text, meta = extract_text(path, ext, settings.OCR_ENABLED)
    except ExtractionError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, str(exc))
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "The file could not be processed.")
    try:
        sub = _new_submission(db, user, (title or original or "Untitled").strip() or "Untitled", text,
                              ALLOWED_EXTENSIONS[ext], original, stored, meta)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    return detail(db, sub)


@router.get("/content", response_model=list[ContentListItem])
def list_content(status: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(ContentSubmission).options(selectinload(ContentSubmission.creator)) \
        .where(ContentSubmission.organisation_id == user.organisation_id)
    if user.role == ROLE_CREATOR:
        q = q.where(ContentSubmission.creator_id == user.id)
    if status:
        if status not in STATUSES:
            raise HTTPException(422, "Unknown status filter.")
        q = q.where(ContentSubmission.status == status)
    subs = db.scalars(q.order_by(ContentSubmission.updated_at.desc())).all()
    counts: dict = {}
    if subs:
        rows = db.execute(
            select(ComplianceIssue.submission_id, ComplianceIssue.severity, func.count())
            .join(ContentSubmission, ContentSubmission.id == ComplianceIssue.submission_id)
            .where(ComplianceIssue.submission_id.in_([s.id for s in subs]),
                   ComplianceIssue.run_number == ContentSubmission.run_count)
            .group_by(ComplianceIssue.submission_id, ComplianceIssue.severity)).all()
        for sid, sev, n in rows:
            counts.setdefault(sid, {})[sev] = n
    return [ContentListItem(
        id=s.id, title=s.title, source_type=s.source_type, status=s.status, creator_id=s.creator_id,
        creator_name=s.creator.full_name, created_at=s.created_at, updated_at=s.updated_at,
        submitted_at=s.submitted_at, issue_count=sum(counts.get(s.id, {}).values()),
        severity_counts=counts.get(s.id, {})) for s in subs]


@router.get("/content/{content_id}", response_model=ContentDetail)
def read_content(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return detail(db, get_submission(db, user, content_id))


@router.put("/content/{content_id}", response_model=ContentDetail)
def update_content(content_id: int, data: ContentUpdate, user: User = Depends(creator_only),
                   db: Session = Depends(get_db)):
    sub = get_submission(db, user, content_id, owner_only=True)
    if sub.status not in EDITABLE_STATUSES:
        raise HTTPException(409, "This content is locked while it is under review or after a final decision.")
    if data.title is not None:
        sub.title = data.title.strip()
    if data.text is not None:
        if not data.text.strip():
            raise HTTPException(422, "Text must not be blank.")
        if len(data.text) > settings.MAX_TEXT_CHARS:
            raise HTTPException(413, "Text is too long.")
        if data.text != sub.original_text or sub.revised_text is not None:
            sub.original_text = data.text
            sub.revised_text = None
            sub.status = ST_DRAFT  # earlier analysis no longer matches the text
    audit.log(db, user, "content.edited", "content", sub.id)
    db.commit()
    db.refresh(sub)
    return detail(db, sub)


@router.delete("/content/{content_id}", status_code=204)
def delete_content(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = get_submission(db, user, content_id)
    if user.role == ROLE_REVIEWER:
        raise HTTPException(403, "You do not have permission to do this.")
    if user.role == ROLE_CREATOR and sub.status != ST_DRAFT:
        raise HTTPException(409, "Only drafts can be deleted.")
    if sub.stored_filename:
        (Path(settings.UPLOAD_DIR) / sub.stored_filename).unlink(missing_ok=True)
    audit.log(db, user, "content.deleted", "content", sub.id, sub.title)
    db.delete(sub)
    db.commit()


# ------------------------------------------------------------------ analysis
@router.post("/content/{content_id}/analyze", response_model=ContentDetail)
def analyze_content(content_id: int, user: User = Depends(creator_only), db: Session = Depends(get_db)):
    sub = get_submission(db, user, content_id, owner_only=True)
    if sub.status not in EDITABLE_STATUSES:
        raise HTTPException(409, "This content is locked while it is under review or after a final decision.")
    analysis.run_analysis(db, sub, user)
    db.commit()
    db.refresh(sub)
    return detail(db, sub)


@router.get("/content/{content_id}/issues", response_model=list[IssueOut])
def issues(content_id: int, run: Optional[int] = None, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    return latest_issues(db, get_submission(db, user, content_id), run)


# ------------------------------------------------------------------ suggestions
@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def decide_suggestion(suggestion_id: int, data: SuggestionUpdate, user: User = Depends(creator_only),
                      db: Session = Depends(get_db)):
    s = db.get(CorrectionSuggestion, suggestion_id)
    sub = db.get(ContentSubmission, s.issue.submission_id) if s else None
    if s is None or sub is None or sub.organisation_id != user.organisation_id or sub.creator_id != user.id:
        raise HTTPException(404, "Suggestion not found.")
    if sub.status not in EDITABLE_STATUSES or s.issue.run_number != sub.run_count:
        raise HTTPException(409, "This suggestion can no longer be changed.")
    if data.status == "pending":
        s.status, s.final_text = "pending", None
    elif data.status == "rejected":
        s.status, s.final_text = "rejected", None
    else:
        final = data.final_text if data.final_text is not None else s.suggested_text
        if s.action == "manual" and data.final_text is None:
            raise HTTPException(422, "There is no automatic replacement: enter your own corrected text.")
        s.final_text = final
        s.status = "edited" if final != s.suggested_text else "accepted"
    s.decided_at = utcnow() if s.status != "pending" else None
    audit.log(db, user, f"suggestion.{s.status}", "suggestion", s.id)
    db.commit()
    db.refresh(s)
    return s


@router.get("/content/{content_id}/revised-preview")
def revised_preview(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = get_submission(db, user, content_id)
    text, applied, skipped = analysis.apply_suggestions(sub, latest_issues(db, sub))
    return {"revised_text": text, "applied": applied, "skipped": skipped}


@router.post("/content/{content_id}/apply-suggestions", response_model=ContentDetail)
def apply_suggestions(content_id: int, user: User = Depends(creator_only), db: Session = Depends(get_db)):
    """Creates revised text from accepted suggestions. The original text is kept unchanged. The content
    returns to Draft because the revised text must be checked again."""
    sub = get_submission(db, user, content_id, owner_only=True)
    if sub.status not in EDITABLE_STATUSES:
        raise HTTPException(409, "This content is locked while it is under review or after a final decision.")
    text, applied, skipped = analysis.apply_suggestions(sub, latest_issues(db, sub))
    if applied == 0:
        raise HTTPException(422, "No accepted suggestions could be applied.")
    sub.revised_text = text
    sub.status = ST_DRAFT
    audit.log(db, user, "content.suggestions_applied", "content", sub.id, f"applied={applied}, skipped={skipped}")
    db.commit()
    db.refresh(sub)
    return detail(db, sub)


# ------------------------------------------------------------------ submit for review
@router.post("/content/{content_id}/submit", response_model=ContentDetail)
def submit_for_review(content_id: int, user: User = Depends(creator_only), db: Session = Depends(get_db)):
    sub = get_submission(db, user, content_id, owner_only=True)
    if sub.status != ST_ANALYZED:
        raise HTTPException(409, "Run the compliance check on the current text before submitting for review.")
    sub.status = ST_SUBMITTED
    sub.submitted_at = utcnow()
    audit.log(db, user, "content.submitted", "content", sub.id)
    db.commit()
    db.refresh(sub)
    return detail(db, sub)


@router.get("/content/{content_id}/history")
def content_history(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import AuditLog
    sub = get_submission(db, user, content_id)
    rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "content", AuditLog.entity_id == sub.id)
                      .order_by(AuditLog.created_at)).all()
    return [{"id": r.id, "action": r.action, "details": r.details, "created_at": r.created_at,
             "user": r.user.full_name if r.user else None} for r in rows]
