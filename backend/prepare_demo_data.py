"""
BrandGuard demo-data target script.

Creates 28 demo submissions and routes 13 existing analyzed submissions
through the review workflow. It preserves existing submission text, runs,
issues, and reviews.

The script:
- creates a consistent SQLite backup first;
- verifies the database still matches the expected starting state;
- checks candidate texts with the real compliance engine;
- applies all changes in one database transaction;
- rolls back if the final dashboard totals are not exact;
- refuses to run twice if its demo batch already exists.

Run from the backend folder with the project's virtual environment activated:
    python prepare_demo_data.py
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from shutil import copy2
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.database import SessionLocal, engine
from app.models import (
    AuditLog,
    ComplianceIssue,
    ContentSubmission,
    Review,
    User,
    utcnow,
)
from app.services import analysis, audit, compliance


CREATOR_EMAIL = "creator@technova.demo"
REVIEWER_ID = 3
BATCH_PREFIX = "DEMO-BATCH-50-"
EXPECTED_START_TOTAL = 22
EXPECTED_START_LATEST_ISSUES = 49
TARGET_TOTAL = 50
TARGET_LATEST_ISSUES = 120

# Existing analyzed submissions:
# 4 remain awaiting review, 5 approved, 2 rejected, 2 changes requested.
EXISTING_PLAN = {
    "submitted": 4,
    "approved": 5,
    "rejected": 2,
    "changes_requested": 2,
}

# New 28 submissions:
# 7 awaiting review, 9 approved, 5 rejected, 7 changes requested.
NEW_PLAN = {
    "submitted": 7,
    "approved": 9,
    "rejected": 5,
    "changes_requested": 7,
}

STATUS_FOR_DECISION = {
    "approved": "approved",
    "rejected": "rejected",
    "changes_requested": "changes_requested",
}

COMMENTS = {
    "rejected": "Demo review: please remove unsupported promotional claims before publication.",
    "changes_requested": "Demo review: please correct the terminology and revise the flagged wording.",
}


def database_file() -> Path:
    url = make_url(str(engine.url))
    if not url.database:
        raise RuntimeError("Could not determine the SQLite database file from DATABASE_URL.")
    path = Path(url.database)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        raise RuntimeError(f"Database file not found: {path}")
    return path


def make_backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}_backup_{stamp}{db_path.suffix}")

    # SQLite's backup API gives a consistent backup, including when WAL is in use.
    source = sqlite3.connect(str(db_path))
    destination = sqlite3.connect(str(backup_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    return backup_path


def make_candidate_text(index: int) -> str:
    # The first 15 texts should produce 3 rule-based findings each:
    # incorrect terminology, prohibited phrase, and an unsupported "best" claim.
    # The remaining 13 should produce 2 each:
    # incorrect terminology and prohibited phrase.
    if index <= 15:
        return (
            "Tech Nova Cloud never fails. "
            "This is the best cloud service for teams."
        )
    return "Tech Nova Cloud never fails. This cloud service supports teams."


def count_latest_issues(db, creator_id: int) -> int:
    from app.models import ComplianceIssue

    return int(
        db.scalar(
            select(func.count())
            .select_from(ComplianceIssue)
            .join(ContentSubmission, ContentSubmission.id == ComplianceIssue.submission_id)
            .where(
                ContentSubmission.creator_id == creator_id,
                ComplianceIssue.run_number == ContentSubmission.run_count,
            )
        ) or 0
    )


def status_counts(db, creator_id: int) -> dict[str, int]:
    rows = db.execute(
        select(ContentSubmission.status, func.count())
        .where(ContentSubmission.creator_id == creator_id)
        .group_by(ContentSubmission.status)
    ).all()
    return {status: int(count) for status, count in rows}


def add_audit(db, user, action: str, submission_id: int, details: str | None = None) -> None:
    audit.log(db, user, action, "content", submission_id, details)


def apply_review(db, submission, reviewer, decision: str) -> None:
    submission.status = STATUS_FOR_DECISION[decision]
    db.add(
        Review(
            submission_id=submission.id,
            reviewer_id=reviewer.id,
            decision=decision,
            comment=COMMENTS.get(decision),
            decided_at=utcnow(),
        )
    )
    db.add(
        AuditLog(
            organisation_id=submission.organisation_id,
            user_id=reviewer.id,
            action=f"content.reviewed.{decision}",
            entity_type="content",
            entity_id=submission.id,
            details=COMMENTS.get(decision),
            created_at=utcnow(),
        )
    )


def main() -> None:
    db_path = database_file()
    backup_path = make_backup(db_path)
    print(f"Database backup created: {backup_path}")

    db = SessionLocal()
    try:
        with db.begin():
            creator = db.scalar(select(User).where(User.email == CREATOR_EMAIL))
            reviewer = db.get(User, REVIEWER_ID)

            if creator is None or creator.role != "creator":
                raise RuntimeError(f"Creator account not found: {CREATOR_EMAIL}")
            if reviewer is None or reviewer.role != "reviewer":
                raise RuntimeError(f"Reviewer account id {REVIEWER_ID} was not found or is not a reviewer.")
            if creator.organisation_id != reviewer.organisation_id:
                raise RuntimeError("Creator and reviewer belong to different organisations.")

            existing_batch = db.scalar(
                select(func.count())
                .select_from(ContentSubmission)
                .where(
                    ContentSubmission.creator_id == creator.id,
                    ContentSubmission.title.like(f"{BATCH_PREFIX}%"),
                )
            )
            if existing_batch:
                raise RuntimeError(
                    f"A demo batch with prefix {BATCH_PREFIX!r} already exists. "
                    "No changes were made; this script will not duplicate it."
                )

            total = int(
                db.scalar(
                    select(func.count())
                    .select_from(ContentSubmission)
                    .where(ContentSubmission.creator_id == creator.id)
                ) or 0
            )
            if total != EXPECTED_START_TOTAL:
                raise RuntimeError(
                    f"Expected {EXPECTED_START_TOTAL} creator submissions, found {total}. "
                    "The database may have changed since the last check. No changes were made."
                )

            before_statuses = status_counts(db, creator.id)
            expected_statuses = {
                "analyzed": 17,
                "approved": 1,
                "changes_requested": 1,
                "draft": 1,
                "rejected": 1,
                "submitted": 1,
            }
            if before_statuses != expected_statuses:
                raise RuntimeError(
                    f"Starting status counts differ from the verified snapshot: {before_statuses}. "
                    "No changes were made."
                )

            before_issues = count_latest_issues(db, creator.id)
            if before_issues != EXPECTED_START_LATEST_ISSUES:
                raise RuntimeError(
                    f"Expected {EXPECTED_START_LATEST_ISSUES} latest-run issues, found {before_issues}. "
                    "No changes were made."
                )

            analyzed_submissions = db.scalars(
                select(ContentSubmission)
                .where(
                    ContentSubmission.creator_id == creator.id,
                    ContentSubmission.status == "analyzed",
                )
                .order_by(ContentSubmission.id)
            ).all()
            if len(analyzed_submissions) != 17:
                raise RuntimeError("Expected exactly 17 analyzed submissions. No changes were made.")

            # Preview all 28 texts with the real rules and compliance engine before writing rows.
            rules = analysis.load_ruleset(db, creator.organisation_id)
            candidate_texts = [make_candidate_text(i) for i in range(1, 29)]
            preview_counts = [
                len(compliance.analyze(text, rules, None, date.today())[0])
                for text in candidate_texts
            ]
            preview_total = sum(preview_counts)
            if preview_total != TARGET_LATEST_ISSUES - EXPECTED_START_LATEST_ISSUES:
                raise RuntimeError(
                    "The real compliance engine did not produce the required "
                    f"{TARGET_LATEST_ISSUES - EXPECTED_START_LATEST_ISSUES} new findings. "
                    f"It previewed {preview_total}. No database changes were made. "
                    f"Per-submission counts: {preview_counts}"
                )

            # Create and analyze the 28 new submissions using the application's own service.
            new_submissions = []
            for i, text in enumerate(candidate_texts, start=1):
                sub = ContentSubmission(
                    organisation_id=creator.organisation_id,
                    creator_id=creator.id,
                    title=f"{BATCH_PREFIX}{i:02d} - TechNova campaign demo",
                    source_type="text",
                    original_text=text,
                    status="draft",
                    run_count=0,
                )
                db.add(sub)
                db.flush()
                add_audit(db, creator, "content.created", sub.id, "source=text; demo batch")
                analysis.run_analysis(db, sub, creator)
                db.flush()
                new_submissions.append(sub)

            actual_new_issues = sum(
                int(sub.run_count and db.scalar(
                    select(func.count())
                    .select_from(ComplianceIssue)
                    .where(
                        ComplianceIssue.submission_id == sub.id,
                        ComplianceIssue.run_number == sub.run_count,
                    )
                ) or 0)
                for sub in new_submissions
            )
            if actual_new_issues != TARGET_LATEST_ISSUES - EXPECTED_START_LATEST_ISSUES:
                raise RuntimeError(
                    f"Expected 71 new findings after analysis, got {actual_new_issues}. "
                    "The transaction will be rolled back."
                )

            # Route 13 of the existing analyzed submissions through the review workflow.
            existing_index = 0
            for decision, count in EXISTING_PLAN.items():
                for _ in range(count):
                    sub = analyzed_submissions[existing_index]
                    existing_index += 1
                    sub.status = "submitted"
                    sub.submitted_at = utcnow()
                    add_audit(db, creator, "content.submitted", sub.id)
                    if decision != "submitted":
                        apply_review(db, sub, reviewer, decision)

            # Route all 28 new submissions through submission/review.
            new_index = 0
            for decision, count in NEW_PLAN.items():
                for _ in range(count):
                    sub = new_submissions[new_index]
                    new_index += 1
                    sub.status = "submitted"
                    sub.submitted_at = utcnow()
                    add_audit(db, creator, "content.submitted", sub.id)
                    if decision != "submitted":
                        apply_review(db, sub, reviewer, decision)

            db.flush()

            final_total = int(
                db.scalar(
                    select(func.count())
                    .select_from(ContentSubmission)
                    .where(ContentSubmission.creator_id == creator.id)
                ) or 0
            )
            final_statuses = status_counts(db, creator.id)
            final_issues = count_latest_issues(db, creator.id)

            expected_final = {
                "analyzed": 4,
                "approved": 15,
                "changes_requested": 10,
                "draft": 1,
                "rejected": 8,
                "submitted": 12,
            }
            if final_total != TARGET_TOTAL:
                raise RuntimeError(f"Final total should be {TARGET_TOTAL}, got {final_total}.")
            if final_statuses != expected_final:
                raise RuntimeError(f"Final status counts do not match: {final_statuses}")
            if final_issues != TARGET_LATEST_ISSUES:
                raise RuntimeError(
                    f"Final latest-run issue total should be {TARGET_LATEST_ISSUES}, got {final_issues}."
                )

            print("Pre-commit verification passed:")
            print(f"  Total submissions: {final_total}")
            print(f"  Status counts: {final_statuses}")
            print(f"  Latest-run compliance issues: {final_issues}")
            print("Committing changes...")

        print("\nSUCCESS: Demo data was added and verified.")
        print(f"Backup: {backup_path}")
        print("Refresh the Creator Dashboard to see the updated totals.")

    except Exception:
        db.rollback()
        print("\nSTOPPED: No demo changes were committed.")
        print(f"Your original database backup is available at: {backup_path}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
