"""Rule-based brand compliance engine.

This module is deliberately free of database and web code so it can be tested on its own.
Every finding it returns refers to a *stored* rule (a guideline, fact, term, prohibited phrase or
claim that an administrator entered). The engine never invents rules or facts.

Detection is deterministic: the same text and rules always give the same findings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

# --------------------------------------------------------------------------- rule snapshots
# Plain data copies of the stored rules (so the engine does not depend on SQLAlchemy objects).


@dataclass
class GuidelineR:
    id: int
    category: str
    title: str
    description: str
    severity: str = "Medium"
    params: dict = field(default_factory=dict)
    source_reference: Optional[str] = None


@dataclass
class FactR:
    id: int
    subject: str
    statement: str
    correct_value: str
    match_pattern: Optional[str] = None
    valid_until: Optional[date] = None
    source_reference: Optional[str] = None


@dataclass
class TermR:
    id: int
    approved_term: str
    incorrect_variants: List[str]
    note: Optional[str] = None
    source_reference: Optional[str] = None


@dataclass
class ProhibitedR:
    id: int
    phrase: str
    suggested_replacement: Optional[str] = None
    severity: str = "High"
    reason: Optional[str] = None
    source_reference: Optional[str] = None


@dataclass
class ClaimR:
    id: int
    claim_text: str
    status: str  # approved | requires_evidence
    evidence: Optional[str] = None
    source_reference: Optional[str] = None


@dataclass
class RuleSet:
    guidelines: List[GuidelineR] = field(default_factory=list)
    facts: List[FactR] = field(default_factory=list)
    terms: List[TermR] = field(default_factory=list)
    prohibited: List[ProhibitedR] = field(default_factory=list)
    claims: List[ClaimR] = field(default_factory=list)

    def guideline(self, category: str) -> Optional[GuidelineR]:
        for g in self.guidelines:
            if g.category == category:
                return g
        return None


@dataclass
class Finding:
    title: str
    category: str
    severity: str
    flagged_text: str
    start: Optional[int]
    end: Optional[int]
    explanation: str
    rule_type: str
    rule_id: int
    rule_reference: str
    rule_snapshot: str
    suggested_text: str = ""
    action: str = "replace"  # replace | append | manual
    suggestion_explanation: str = ""
    confidence: Optional[float] = 1.0
    requires_human_verification: bool = False
    detection_method: str = "rule"


# --------------------------------------------------------------------------- helpers

def phrase_regex(phrase: str) -> re.Pattern:
    """Case-insensitive, whitespace-flexible, whole-word match for a phrase."""
    words = [re.escape(w) for w in phrase.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def _overlaps(a: Tuple[int, int], spans: List[Tuple[int, int]]) -> bool:
    return any(a[0] < e and s < a[1] for s, e in spans)


_CURRENCY = r"(?:₹|Rs\.?|INR|\$|USD|€|EUR)"
_VALUE_RE = re.compile(r"^\s*(₹|Rs\.?|INR|\$|USD|€|EUR)?\s*([\d,]+(?:\.\d+)?)\s*(.*?)\s*$", re.IGNORECASE)
_UNITS = [
    (re.compile(r"^(per\s+month|/\s*month|monthly|a\s+month|/\s*mo)$", re.I),
     r"(?:per\s+month|/\s*month|monthly|a\s+month|/\s*mo\b)"),
    (re.compile(r"^(per\s+year|/\s*year|yearly|annually|a\s+year|/\s*yr)$", re.I),
     r"(?:per\s+year|/\s*year|yearly|annually|a\s+year|/\s*yr\b)"),
]


def _to_number(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def derive_price_pattern(correct_value: str) -> Optional[str]:
    """If the approved value looks like a price (e.g. '₹999 per month'), build a pattern that finds
    other prices written the same way. Group 1 is the amount."""
    m = _VALUE_RE.match(correct_value)
    if not m or not m.group(1):  # needs a currency symbol
        return None
    unit = m.group(3)
    unit_re = ""
    if unit:
        for rx, pat in _UNITS:
            if rx.match(unit):
                unit_re = r"\s*" + pat
                break
        else:
            unit_re = r"\s+" + r"\s+".join(re.escape(w) for w in unit.split())
    return _CURRENCY + r"\s?([\d,]+(?:\.\d+)?)" + unit_re


def _sentences(text: str):
    for m in re.finditer(r"[^.!?\n]+[.!?]*", text):
        s = m.group().strip()
        if s:
            yield m.start() + (len(m.group()) - len(m.group().lstrip())), s


# --------------------------------------------------------------------------- built-in heuristics
CLAIM_PATTERNS = [
    (r"(?:no\.?\s*1|number\s+(?:one|1)|#\s*1)\b", "a 'number one' ranking"),
    (r"\b(?:best|greatest|finest)\b(?:\s+in\s+(?:class|the\s+world|india))?", "a 'best' superlative"),
    (r"\b(?:world|industry|market)[- ]leading\b", "a 'leading' claim"),
    (r"\bworld[- ]class\b", "a 'world-class' claim"),
    (r"\bunbeatable\b|\bunmatched\b|\bunrivalled\b|\bunrivaled\b", "an absolute comparison"),
    (r"\bguarantee[ds]?\b", "a guarantee"),
    (r"\b100\s*%", "an absolute '100%' statement"),
]

INFORMAL = {
    "gonna": "going to", "wanna": "want to", "gotta": "have to", "kinda": "somewhat", "sorta": "somewhat",
    "hey guys": "Hello", "awesome": "excellent", "mind-blowing": "impressive", "crazy": "remarkable",
    "lol": "", "omg": "",
}
ACRONYM_ALLOW = {"HTTP", "HTTPS", "HTML", "JSON", "SAAS", "PAAS", "IAAS", "DEMO", "USD", "INR", "EURO", "FAQS",
                 "LINK", "NOTE", "TERMS"}
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]+")
LONG_SENTENCE_WORDS = 40


# --------------------------------------------------------------------------- engine

class Engine:
    def __init__(self, text: str, rules: RuleSet, meta: Optional[dict] = None, today: Optional[date] = None):
        self.text = text
        self.rules = rules
        self.meta = meta or {}
        self.today = today or date.today()
        self.findings: List[Finding] = []
        self.warnings: List[str] = []
        self.taken: List[Tuple[int, int]] = []       # spans already reported
        self.protected: List[Tuple[int, int]] = []   # spans covered by an approved claim

    # -- bookkeeping
    def _add(self, f: Finding) -> bool:
        if f.start is not None and f.end is not None:
            span = (f.start, f.end)
            if _overlaps(span, self.taken) or _overlaps(span, self.protected):
                return False
            self.taken.append(span)
        self.findings.append(f)
        return True

    # -- main
    def run(self) -> List[Finding]:
        self._protect_approved_claims()
        self._prohibited()
        self._terminology()
        self._facts()
        self._stored_claims()
        self._claim_heuristics()
        self._tone()
        self._term_capitalisation()
        self._readability()
        self._required_info()
        self._accessibility()
        order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        self.findings.sort(key=lambda f: (order.get(f.severity, 9), f.start if f.start is not None else 10**9))
        return self.findings

    # -- 0. approved claims are allowed
    def _protect_approved_claims(self):
        for c in self.rules.claims:
            if c.status == "approved":
                for m in phrase_regex(c.claim_text).finditer(self.text):
                    self.protected.append((m.start(), m.end()))

    # -- 1. prohibited words
    def _prohibited(self):
        for p in self.rules.prohibited:
            for m in phrase_regex(p.phrase).finditer(self.text):
                repl = (p.suggested_replacement or "").strip()
                self._add(Finding(
                    title=f"Prohibited phrase: “{p.phrase}”",
                    category="Prohibited word", severity=p.severity,
                    flagged_text=m.group(), start=m.start(), end=m.end(),
                    explanation=(p.reason or "This phrase is on the organisation's prohibited list."),
                    rule_type="prohibited_word", rule_id=p.id,
                    rule_reference=f"Prohibited word #{p.id}: “{p.phrase}”",
                    rule_snapshot=f"Prohibited phrase “{p.phrase}”. " + (p.reason or ""),
                    suggested_text=repl, action="replace" if repl else "manual",
                    suggestion_explanation=(f"Use the approved wording “{repl}”." if repl else
                                            "No approved replacement is stored. Remove or rewrite this phrase."),
                ))

    # -- 2. terminology
    def _terminology(self):
        for t in self.rules.terms:
            for variant in t.incorrect_variants or []:
                if not variant.strip() or variant.strip().lower() == t.approved_term.lower():
                    continue
                for m in phrase_regex(variant).finditer(self.text):
                    self._add(Finding(
                        title=f"Incorrect terminology: “{m.group()}”",
                        category="Terminology", severity="High",
                        flagged_text=m.group(), start=m.start(), end=m.end(),
                        explanation=(f"The approved term is “{t.approved_term}”. " + (t.note or "")).strip(),
                        rule_type="terminology", rule_id=t.id,
                        rule_reference=f"Terminology #{t.id}: “{t.approved_term}”",
                        rule_snapshot=f"Approved term “{t.approved_term}”; incorrect variants: "
                                      + ", ".join(t.incorrect_variants),
                        suggested_text=t.approved_term, action="replace",
                        suggestion_explanation=f"Replace with the official term “{t.approved_term}”.",
                    ))

    # -- 3. facts
    def _facts(self):
        for f in self.rules.facts:
            pattern = f.match_pattern or derive_price_pattern(f.correct_value)
            if not pattern:
                continue  # not auto-checkable; only offered to the optional AI layer
            try:
                rx = re.compile(pattern, re.IGNORECASE)
            except re.error:
                self.warnings.append(f"Fact #{f.id} has an invalid match pattern and was skipped.")
                continue
            expected_num = None
            vm = _VALUE_RE.match(f.correct_value)
            if not f.match_pattern and vm:
                expected_num = _to_number(vm.group(2))
            expired = f.valid_until is not None and f.valid_until < self.today
            for m in rx.finditer(self.text):
                grp = 1 if rx.groups >= 1 else 0
                found = m.group(grp)
                if f.match_pattern:
                    ok = found.strip().lower() == f.correct_value.strip().lower()
                else:
                    ok = expected_num is not None and _to_number(found) == expected_num
                start, end = (m.start(grp), m.end(grp)) if f.match_pattern else (m.start(), m.end())
                flagged = self.text[start:end]
                snap = f"Approved fact – {f.subject}: {f.statement} (approved value: {f.correct_value})"
                ref = f"Approved fact #{f.id}: {f.subject}"
                if expired:
                    self._add(Finding(
                        title=f"Possibly outdated fact: {f.subject}", category="Outdated information",
                        severity="Medium", flagged_text=flagged, start=start, end=end,
                        explanation=f"The approved fact “{f.subject}” expired on {f.valid_until.isoformat()}. "
                                    "A human must confirm that this information is still current.",
                        rule_type="fact", rule_id=f.id, rule_reference=ref, rule_snapshot=snap,
                        action="manual", suggestion_explanation="Confirm the current value with the fact owner.",
                        confidence=0.9, requires_human_verification=True))
                elif not ok:
                    self._add(Finding(
                        title=f"Incorrect fact: {f.subject}", category="Incorrect information",
                        severity="High", flagged_text=flagged, start=start, end=end,
                        explanation=f"The content states “{flagged}”, but the approved value for "
                                    f"“{f.subject}” is “{f.correct_value}”.",
                        rule_type="fact", rule_id=f.id, rule_reference=ref, rule_snapshot=snap,
                        suggested_text=f.correct_value, action="replace",
                        suggestion_explanation=f"Use the approved value “{f.correct_value}”."))

    # -- 4. stored claims that need evidence
    def _stored_claims(self):
        for c in self.rules.claims:
            if c.status != "requires_evidence":
                continue
            for m in phrase_regex(c.claim_text).finditer(self.text):
                self._add(Finding(
                    title=f"Unsupported promotional claim: “{c.claim_text}”",
                    category="Unsupported claim", severity="High",
                    flagged_text=m.group(), start=m.start(), end=m.end(),
                    explanation="This claim is registered as requiring approved evidence, and none is on file. "
                                "It needs human verification before publication.",
                    rule_type="claim", rule_id=c.id,
                    rule_reference=f"Claim #{c.id}: “{c.claim_text}” (evidence required)",
                    rule_snapshot=f"Claim “{c.claim_text}” – status: requires evidence. " + (c.evidence or ""),
                    action="manual",
                    suggestion_explanation="Remove the claim, or ask the brand team to approve it with evidence.",
                    confidence=1.0, requires_human_verification=True))

    # -- 5. generic claim heuristics (only if a claims guideline is stored)
    def _claim_heuristics(self):
        g = self.rules.guideline("claims")
        if not g:
            return
        for pattern, label in CLAIM_PATTERNS:
            for m in re.finditer(pattern, self.text, re.IGNORECASE):
                self._add(Finding(
                    title="Possible unsupported promotional claim", category="Unsupported claim",
                    severity="Medium", flagged_text=m.group(), start=m.start(), end=m.end(),
                    explanation=f"This looks like {label}. No approved claim with evidence covers it, so it "
                                "requires human verification. (Pattern-based detection, not a verified fact.)",
                    rule_type="guideline", rule_id=g.id,
                    rule_reference=f"Guideline #{g.id}: {g.title}",
                    rule_snapshot=f"{g.title}: {g.description}",
                    action="manual",
                    suggestion_explanation="Rewrite without the absolute wording, or obtain approved evidence.",
                    confidence=0.6, requires_human_verification=True))

    # -- 6. tone
    def _tone(self):
        g = self.rules.guideline("brand_voice")
        if not g:
            return
        ref, snap = f"Guideline #{g.id}: {g.title}", f"{g.title}: {g.description}"

        def tone(title, m, sugg, expl, action="replace"):
            self._add(Finding(title=title, category="Tone and language", severity="Low",
                              flagged_text=m.group(), start=m.start(), end=m.end(), explanation=expl,
                              rule_type="guideline", rule_id=g.id, rule_reference=ref, rule_snapshot=snap,
                              suggested_text=sugg, action=action,
                              suggestion_explanation="Adjust the wording to match the approved brand voice.",
                              confidence=0.7))
        for m in re.finditer(r"!+", self.text):
            tone("Exclamation mark in professional copy", m, ".",
                 "The brand voice guideline asks for a professional tone; exclamation marks read as informal.")
        for m in re.finditer(r"\b[A-Z]{4,}\b", self.text):
            w = m.group()
            if w in ACRONYM_ALLOW or any(w == t.approved_term.upper() for t in self.rules.terms):
                continue
            tone("ALL-CAPS word", m, w.capitalize(), "Words in capital letters read as shouting and are off-brand.")
        for word, repl in INFORMAL.items():
            for m in phrase_regex(word).finditer(self.text):
                tone(f"Informal wording: “{m.group()}”", m, repl,
                     "Informal or exaggerated wording does not match a professional, informative tone.",
                     action="replace" if repl else "manual")
        for m in EMOJI_RE.finditer(self.text):
            tone("Emoji in professional copy", m, "", "Emojis are not part of the professional brand voice.")

    # -- 7. capitalisation of approved terms
    def _term_capitalisation(self):
        for t in self.rules.terms:
            for m in phrase_regex(t.approved_term).finditer(self.text):
                if m.group() != t.approved_term:
                    self._add(Finding(
                        title=f"Incorrect capitalisation: “{m.group()}”", category="Terminology", severity="Low",
                        flagged_text=m.group(), start=m.start(), end=m.end(),
                        explanation=f"The official spelling is “{t.approved_term}”.",
                        rule_type="terminology", rule_id=t.id,
                        rule_reference=f"Terminology #{t.id}: “{t.approved_term}”",
                        rule_snapshot=f"Approved term “{t.approved_term}”",
                        suggested_text=t.approved_term, action="replace",
                        suggestion_explanation=f"Use the exact spelling “{t.approved_term}”."))

    # -- 8. readability
    def _readability(self):
        g = self.rules.guideline("writing") or self.rules.guideline("accessibility")
        if not g:
            return
        for start, s in _sentences(self.text):
            n = len(s.split())
            if n > LONG_SENTENCE_WORDS:
                self._add(Finding(
                    title="Very long sentence", category="Readability", severity="Low",
                    flagged_text=s, start=start, end=start + len(s),
                    explanation=f"This sentence has {n} words. Sentences over {LONG_SENTENCE_WORDS} words are "
                                "hard to read, especially for people using assistive technology.",
                    rule_type="guideline", rule_id=g.id, rule_reference=f"Guideline #{g.id}: {g.title}",
                    rule_snapshot=f"{g.title}: {g.description}", action="manual",
                    suggestion_explanation="Split the sentence into two or three shorter ones.", confidence=0.8))

    # -- 9. missing required information
    def _required_info(self):
        for g in self.rules.guidelines:
            if g.category != "required_info":
                continue
            params = g.params or {}
            trigger = params.get("applies_if_contains")
            if trigger and trigger.lower() not in self.text.lower():
                continue
            for phrase in params.get("required_phrases", []):
                if phrase.lower() not in self.text.lower():
                    self._add(Finding(
                        title=f"Missing required information: “{phrase}”", category="Missing information",
                        severity=g.severity, flagged_text="", start=None, end=None,
                        explanation=f"The guideline “{g.title}” requires this wording, but it is not in the content.",
                        rule_type="guideline", rule_id=g.id, rule_reference=f"Guideline #{g.id}: {g.title}",
                        rule_snapshot=f"{g.title}: {g.description}",
                        suggested_text=phrase, action="append",
                        suggestion_explanation=f"Add “{phrase}” to the end of the content."))

    # -- 10. accessibility (from extraction metadata)
    def _accessibility(self):
        g = self.rules.guideline("accessibility")
        n = int(self.meta.get("images_without_alt", 0) or 0)
        if g and n > 0:
            self._add(Finding(
                title=f"{n} image(s) without alternative text", category="Accessibility", severity="Medium",
                flagged_text="", start=None, end=None,
                explanation="Images in the document have no alternative text, so screen-reader users cannot "
                            "understand them.",
                rule_type="guideline", rule_id=g.id, rule_reference=f"Guideline #{g.id}: {g.title}",
                rule_snapshot=f"{g.title}: {g.description}", action="manual",
                suggestion_explanation="Add a short description to each image in the source document.",
                confidence=1.0))


def analyze(text: str, rules: RuleSet, meta: Optional[dict] = None, today: Optional[date] = None):
    """Run every check. Returns (findings, warnings)."""
    eng = Engine(text, rules, meta, today)
    findings = eng.run()
    return findings, eng.warnings
