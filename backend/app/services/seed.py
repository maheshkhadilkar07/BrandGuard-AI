"""Demonstration data. Everything here is FICTIONAL (TechNova Solutions is not a real company)."""
import sys
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (AnalysisRun, ApprovedClaim, ApprovedFact, AuditLog, BrandGuideline, ComplianceIssue,
                        ContentSubmission, CorrectionSuggestion, Organisation, ProhibitedWord, Review, Terminology,
                        User)

DEMO_ORG = "TechNova Solutions"
DEMO_USERS = [
    ("Asha Admin", "admin@technova.demo", "Admin@123", "admin"),
    ("Chirag Creator", "creator@technova.demo", "Creator@123", "creator"),
    ("Riya Reviewer", "reviewer@technova.demo", "Reviewer@123", "reviewer"),
]
DEMO_TAG = "DEMO DATA (fictional)"

SAMPLE_TEXT = (
    "Introducing Tech Nova Cloud, India's No. 1 cloud platform! "
    "Get started for only ₹1,299 per month with 100% guaranteed results. "
    "TechNova Cloud launched in 2022 and includes a 30-day free trial. "
    "Our AMAZING team is gonna make your migration painless. "
    "Enjoy a 99.9% uptime SLA on every plan."
)


def reset_demo(db: Session) -> None:
    org = db.scalar(select(Organisation).where(Organisation.name == DEMO_ORG))
    if not org:
        return
    sub_ids = select(ContentSubmission.id).where(ContentSubmission.organisation_id == org.id)
    issue_ids = select(ComplianceIssue.id).where(ComplianceIssue.submission_id.in_(sub_ids))
    db.execute(delete(CorrectionSuggestion).where(CorrectionSuggestion.issue_id.in_(issue_ids)))
    db.execute(delete(ComplianceIssue).where(ComplianceIssue.submission_id.in_(sub_ids)))
    db.execute(delete(AnalysisRun).where(AnalysisRun.submission_id.in_(sub_ids)))
    db.execute(delete(Review).where(Review.submission_id.in_(sub_ids)))
    db.execute(delete(ContentSubmission).where(ContentSubmission.organisation_id == org.id))
    for m in (AuditLog, ApprovedClaim, ProhibitedWord, Terminology, ApprovedFact, BrandGuideline, User):
        db.execute(delete(m).where(m.organisation_id == org.id))
    db.delete(org)
    db.commit()


def seed_demo(db: Session, reset: bool = False) -> Organisation:
    if reset:
        reset_demo(db)
    org = db.scalar(select(Organisation).where(Organisation.name == DEMO_ORG))
    if org:
        return org
    org = Organisation(
        name=DEMO_ORG, industry="Cloud software (fictional)", is_demo=True,
        description=f"{DEMO_TAG}. TechNova Solutions is an invented company used to demonstrate BrandGuard AI.",
        brand_voice="Professional, clear and informative.")
    db.add(org)
    db.flush()
    o = org.id
    for name, email, pw, role in DEMO_USERS:
        db.add(User(organisation_id=o, full_name=name, email=email, password_hash=hash_password(pw), role=role))

    ref = lambda s: f"{s} – {DEMO_TAG}"
    db.add_all([
        BrandGuideline(organisation_id=o, category="brand_voice", title="Professional and informative tone",
                       description="Write in a professional, clear and informative tone. Avoid slang, exclamation "
                                   "marks, capital-letter shouting and emojis.",
                       source_reference=ref("TechNova Brand Book §2"), severity="Low"),
        BrandGuideline(organisation_id=o, category="claims", title="Superlatives and guarantees need approved evidence",
                       description="Claims such as 'best', 'No. 1' or 'guaranteed' may only be used if the claim is "
                                   "approved with evidence by the Brand team.",
                       source_reference=ref("TechNova Marketing Policy §4"), severity="Medium"),
        BrandGuideline(organisation_id=o, category="required_info", title="Pricing statements need a terms notice",
                       description="Any content that mentions a price must include the phrase 'Terms and conditions apply'.",
                       source_reference=ref("TechNova Marketing Policy §6"), severity="Medium",
                       params={"required_phrases": ["Terms and conditions apply"], "applies_if_contains": "₹"}),
        BrandGuideline(organisation_id=o, category="writing", title="Keep sentences short and readable",
                       description="Prefer sentences under 40 words so content is easy to read.",
                       source_reference=ref("TechNova Brand Book §3"), severity="Low"),
        BrandGuideline(organisation_id=o, category="accessibility", title="Describe images for screen readers",
                       description="Every image in a document must have alternative text.",
                       source_reference=ref("TechNova Accessibility Standard §1"), severity="Medium"),
    ])
    db.add_all([
        ApprovedFact(organisation_id=o, subject="TechNova Cloud monthly price",
                     statement="TechNova Cloud costs ₹999 per month.", correct_value="₹999 per month",
                     source_reference=ref("TechNova Price List v1")),
        ApprovedFact(organisation_id=o, subject="TechNova Cloud launch year",
                     statement="TechNova Cloud launched in 2021.", correct_value="2021",
                     match_pattern=r"launched\s+in\s+(\d{4})", source_reference=ref("Company timeline")),
        ApprovedFact(organisation_id=o, subject="Free trial length",
                     statement="The free trial lasts 14 days.", correct_value="14",
                     match_pattern=r"(\d+)[- ]day\s+free\s+trial", source_reference=ref("Offer sheet")),
    ])
    db.add_all([
        Terminology(organisation_id=o, approved_term="TechNova Cloud",
                    incorrect_variants=["Tech Nova Cloud", "TechNova-Cloud", "Techno Cloud"],
                    note="Always write the product name as one word followed by 'Cloud'.",
                    source_reference=ref("TechNova Brand Book §1")),
        Terminology(organisation_id=o, approved_term="TechNova Solutions",
                    incorrect_variants=["Tech Nova Solutions"], source_reference=ref("TechNova Brand Book §1")),
    ])
    db.add_all([
        ProhibitedWord(organisation_id=o, phrase="100% guaranteed results", severity="Critical",
                       reason="Absolute guarantees create legal risk. Permitted only if explicitly approved as a claim.",
                       source_reference=ref("TechNova Legal Guidance §2")),
        ProhibitedWord(organisation_id=o, phrase="never fails", suggested_replacement="is built for high reliability",
                       severity="High", reason="Absolute reliability statements cannot be proven.",
                       source_reference=ref("TechNova Legal Guidance §2")),
    ])
    db.add_all([
        ApprovedClaim(organisation_id=o, claim_text="India's No. 1 cloud platform", status="requires_evidence",
                      source_reference=ref("TechNova Marketing Policy §4"),
                      evidence=None),
        ApprovedClaim(organisation_id=o, claim_text="99.9% uptime SLA", status="approved",
                      evidence="Service Level Agreement SLA-2025 (fictional document).",
                      source_reference=ref("TechNova SLA")),
    ])
    db.flush()
    creator = db.scalar(select(User).where(User.email == "creator@technova.demo"))
    db.add(ContentSubmission(organisation_id=o, creator_id=creator.id,
                             title="DEMO: TechNova Cloud launch announcement (deliberate violations)",
                             source_type="text", original_text=SAMPLE_TEXT, status="draft"))
    db.commit()
    return org


def main():
    with SessionLocal() as s:
        seed_demo(s, reset="--reset" in sys.argv)
    print("Demo data ready. Logins: admin@technova.demo / Admin@123, creator@technova.demo / Creator@123, "
          "reviewer@technova.demo / Reviewer@123")


if __name__ == "__main__":
    main()
