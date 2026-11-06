"""Glue between the database, the rule engine and the optional AI layer."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ST_ANALYZED
from app.models import (AnalysisRun, ApprovedClaim, ApprovedFact, BrandGuideline, ComplianceIssue,
                        ContentSubmission, CorrectionSuggestion, ProhibitedWord, Terminology, User)
from app.services import audit, compliance, llm


def load_ruleset(db: Session, org_id: int) -> compliance.RuleSet:
    def rows(model):
        return db.scalars(select(model).where(model.organisation_id == org_id, model.is_active.is_(True))
                          .order_by(model.id)).all()
    return compliance.RuleSet(
        guidelines=[compliance.GuidelineR(g.id, g.category, g.title, g.description, g.severity,
                                          g.params or {}, g.source_reference) for g in rows(BrandGuideline)],
        facts=[compliance.FactR(f.id, f.subject, f.statement, f.correct_value, f.match_pattern, f.valid_until,
                                f.source_reference) for f in rows(ApprovedFact)],
        terms=[compliance.TermR(t.id, t.approved_term, list(t.incorrect_variants or []), t.note,
                                t.source_reference) for t in rows(Terminology)],
        prohibited=[compliance.ProhibitedR(p.id, p.phrase, p.suggested_replacement, p.severity, p.reason,
                                           p.source_reference) for p in rows(ProhibitedWord)],
        claims=[compliance.ClaimR(c.id, c.claim_text, c.status, c.evidence, c.source_reference)
                for c in rows(ApprovedClaim)],
    )


def run_analysis(db: Session, sub: ContentSubmission, user: User) -> AnalysisRun:
    text = sub.current_text
    rules = load_ruleset(db, sub.organisation_id)
    findings, warnings = compliance.analyze(text, rules, sub.extraction_meta, date.today())

    taken = [(f.start, f.end) for f in findings if f.start is not None]
    ai_findings, ai_status = llm.review(text, rules, taken)
    findings.extend(ai_findings)
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.start if f.start is not None else 10 ** 9))

    sub.run_count += 1
    run = AnalysisRun(submission_id=sub.id, run_number=sub.run_count, analysed_text=text,
                      ai_status=(ai_status + (" | " + "; ".join(warnings) if warnings else ""))[:300],
                      issue_count=len(findings))
    db.add(run)
    for f in findings:
        issue = ComplianceIssue(
            submission_id=sub.id, run_number=sub.run_count, title=f.title, category=f.category,
            severity=f.severity, flagged_text=f.flagged_text, start_char=f.start, end_char=f.end,
            explanation=f.explanation, rule_type=f.rule_type, rule_id=f.rule_id,
            rule_reference=f.rule_reference, rule_snapshot=f.rule_snapshot,
            detection_method=f.detection_method, confidence=f.confidence,
            requires_human_verification=f.requires_human_verification)
        issue.suggestion = CorrectionSuggestion(
            action=f.action, original_text=f.flagged_text, suggested_text=f.suggested_text,
            explanation=f.suggestion_explanation or "No automatic suggestion available.")
        db.add(issue)
    sub.status = ST_ANALYZED
    audit.log(db, user, "content.analyzed", "content", sub.id,
              f"run {sub.run_count}: {len(findings)} issue(s); ai={ai_status.split(':')[0]}")
    return run


def apply_suggestions(sub: ContentSubmission, issues) -> tuple[str, int, int]:
    """Build revised text from accepted/edited suggestions of the latest run. Never mutates `sub`."""
    text = sub.current_text
    applied = skipped = 0
    replaces, appends = [], []
    for i in issues:
        s = i.suggestion
        if not s or s.status not in ("accepted", "edited"):
            continue
        new = s.final_text if s.final_text is not None else s.suggested_text
        if s.action == "append":
            if new.strip():
                appends.append(new.strip())
            continue
        if i.start_char is None or i.end_char is None or text[i.start_char:i.end_char] != i.flagged_text:
            skipped += 1
            continue
        if s.action == "manual" and s.final_text is None:
            skipped += 1
            continue
        replaces.append((i.start_char, i.end_char, new))
    for start, end, new in sorted(replaces, reverse=True):
        text = text[:start] + new + text[end:]
        applied += 1
    for a in appends:
        if a.lower() not in text.lower():
            text = text.rstrip() + "\n" + a
            applied += 1
    return text, applied, skipped
