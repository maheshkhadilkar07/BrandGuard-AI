"""Optional AI layer (OpenAI-compatible chat-completions API).

The rule engine never depends on this module. When no API key is configured, `review` returns an
empty list and a status message. AI findings are always:
  * tied to a stored rule (the model must cite a rule reference we supplied; others are discarded),
  * located in the text (the quoted text must really appear in the content; others are discarded),
  * marked as requiring human verification.
"""
from __future__ import annotations

import json
import re
from typing import List, Tuple

import httpx

from app.core.config import get_settings
from app.services.compliance import Finding, RuleSet, _overlaps

MAX_CHARS = 12_000
_SEV = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}

SYSTEM_PROMPT = (
    "You are a brand-compliance assistant. You are given an organisation's approved rules and a piece of "
    "content. Report only problems that clearly conflict with one of the supplied rules, such as tone that "
    "does not fit the brand voice, a statement that contradicts an approved fact, or an unsupported "
    "promotional claim. Use ONLY the supplied rules; never invent rules or facts. Respond with a JSON array "
    "and nothing else. Each item must have: flagged_text (an exact quote from the content), rule_ref (one of "
    "the supplied reference codes), category, severity (Critical|High|Medium|Low), explanation, "
    "suggested_text (a short corrected wording or an empty string) and confidence (0 to 1). "
    "If there are no problems, return []."
)


def rules_for_prompt(rules: RuleSet) -> Tuple[str, dict]:
    lines, index = [], {}
    for g in rules.guidelines:
        code = f"G{g.id}"; index[code] = ("guideline", g.id, f"Guideline #{g.id}: {g.title}", f"{g.title}: {g.description}")
        lines.append(f"{code} [{g.category}] {g.title}: {g.description}")
    for f in rules.facts:
        code = f"F{f.id}"; index[code] = ("fact", f.id, f"Approved fact #{f.id}: {f.subject}", f"{f.subject}: {f.statement}")
        lines.append(f"{code} [fact] {f.subject}: {f.statement} (approved value: {f.correct_value})")
    for t in rules.terms:
        code = f"T{t.id}"; index[code] = ("terminology", t.id, f"Terminology #{t.id}: “{t.approved_term}”", f"Approved term {t.approved_term}")
        lines.append(f"{code} [term] Use “{t.approved_term}”, not {', '.join(t.incorrect_variants)}")
    for p in rules.prohibited:
        code = f"P{p.id}"; index[code] = ("prohibited_word", p.id, f"Prohibited word #{p.id}: “{p.phrase}”", f"Prohibited phrase {p.phrase}")
        lines.append(f"{code} [prohibited] “{p.phrase}”")
    for c in rules.claims:
        code = f"C{c.id}"; index[code] = ("claim", c.id, f"Claim #{c.id}: “{c.claim_text}”", f"Claim {c.claim_text} ({c.status})")
        lines.append(f"{code} [claim:{c.status}] “{c.claim_text}”")
    return "\n".join(lines), index


def parse_items(raw: str):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in model response")
    return json.loads(raw[start:end + 1])


def build_findings(items, text: str, index: dict, taken: List[Tuple[int, int]]) -> List[Finding]:
    out: List[Finding] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        ref = index.get(str(it.get("rule_ref", "")).strip())
        quote = str(it.get("flagged_text", "")).strip()
        if not ref or not quote:
            continue  # must cite a real stored rule
        pos = text.find(quote)
        if pos == -1:
            continue  # must quote real content
        span = (pos, pos + len(quote))
        if _overlaps(span, taken):
            continue
        taken.append(span)
        try:
            conf = max(0.0, min(1.0, float(it.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        sugg = str(it.get("suggested_text", "") or "").strip()
        rule_type, rule_id, rule_ref, snap = ref
        out.append(Finding(
            title=f"AI-detected issue: {str(it.get('category', 'Compliance'))[:60]}",
            category=str(it.get("category", "Compliance"))[:60],
            severity=_SEV.get(str(it.get("severity", "")).lower(), "Medium"),
            flagged_text=quote, start=span[0], end=span[1],
            explanation=str(it.get("explanation", ""))[:1500] or "Flagged by the AI layer.",
            rule_type=rule_type, rule_id=rule_id, rule_reference=rule_ref, rule_snapshot=snap,
            suggested_text=sugg, action="replace" if sugg else "manual",
            suggestion_explanation="AI-generated suggestion. A human must verify it.",
            confidence=conf, requires_human_verification=True, detection_method="ai"))
    return out


def review(text: str, rules: RuleSet, taken: List[Tuple[int, int]]) -> Tuple[List[Finding], str]:
    s = get_settings()
    if not s.llm_enabled:
        return [], "not_configured: AI layer is off; only rule-based checks were run."
    clipped = text[:MAX_CHARS]
    rules_text, index = rules_for_prompt(rules)
    body = {
        "model": s.LLM_MODEL, "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": f"RULES:\n{rules_text}\n\nCONTENT:\n{clipped}"}],
    }
    try:
        r = httpx.post(f"{s.LLM_API_BASE.rstrip('/')}/chat/completions", json=body,
                       headers={"Authorization": f"Bearer {s.LLM_API_KEY}"}, timeout=s.LLM_TIMEOUT_SECONDS)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        findings = build_findings(parse_items(content), text, index, taken)
    except Exception as exc:  # network, auth, bad JSON... never break the rule-based result
        return [], f"error: AI layer failed ({exc.__class__.__name__}); only rule-based results are shown."
    note = " (content truncated for AI review)" if len(text) > MAX_CHARS else ""
    return findings, f"ok: {len(findings)} AI finding(s){note}"
