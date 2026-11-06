from datetime import date

from app.services.compliance import (ClaimR, FactR, GuidelineR, ProhibitedR, RuleSet, TermR, analyze,
                                     derive_price_pattern)


def rules(**kw) -> RuleSet:
    base = RuleSet(
        guidelines=[GuidelineR(1, "brand_voice", "Tone", "Professional"),
                    GuidelineR(2, "claims", "Claims need evidence", "x"),
                    GuidelineR(3, "required_info", "Terms notice", "x", "Medium",
                               {"required_phrases": ["Terms and conditions apply"], "applies_if_contains": "₹"})],
        facts=[FactR(1, "Price", "costs ₹999 per month", "₹999 per month")],
        terms=[TermR(1, "TechNova Cloud", ["Tech Nova Cloud"])],
        prohibited=[ProhibitedR(1, "100% guaranteed results", None, "Critical", "No absolute guarantees")],
        claims=[ClaimR(1, "India's No. 1 cloud platform", "requires_evidence"),
                ClaimR(2, "99.9% uptime SLA", "approved", "SLA-2025")])
    for k, v in kw.items():
        setattr(base, k, v)
    return base


def titles(findings):
    return [f.title for f in findings]


def test_demo_scenario_finds_all_expected_issues():
    text = ("Tech Nova Cloud is India's No. 1 cloud platform at only ₹1,299 per month. "
            "We give 100% guaranteed results.")
    findings, _ = analyze(text, rules())
    by_type = {(f.rule_type, f.rule_id) for f in findings}
    assert ("terminology", 1) in by_type
    assert ("claim", 1) in by_type
    assert ("fact", 1) in by_type
    assert ("prohibited_word", 1) in by_type
    price = next(f for f in findings if f.rule_type == "fact")
    assert price.flagged_text == "₹1,299 per month" and price.suggested_text == "₹999 per month"
    assert price.severity == "High"


def test_every_finding_refers_to_a_stored_rule():
    text = "Tech Nova Cloud is the best! It is gonna be great. ₹1,299 per month."
    findings, _ = analyze(text, rules())
    assert findings
    for f in findings:
        assert f.rule_id > 0 and f.rule_reference and f.rule_snapshot


def test_correct_price_is_not_flagged_and_formats_are_understood():
    for ok in ("It costs ₹999 per month.", "Only Rs. 999/month.", "INR 999 monthly Terms and conditions apply"):
        findings, _ = analyze(ok, rules())
        assert not [f for f in findings if f.rule_type == "fact"], ok
    findings, _ = analyze("Only Rs 1299/month today.", rules())
    assert any(f.rule_type == "fact" for f in findings)


def test_approved_claim_is_allowed_and_not_double_flagged():
    findings, _ = analyze("Enjoy a 99.9% uptime SLA on every plan.", rules())
    assert not [f for f in findings if "uptime" in f.flagged_text or "99.9" in f.flagged_text]


def test_prohibited_phrase_allowed_if_explicitly_approved_as_claim():
    rs = rules(claims=[ClaimR(9, "100% guaranteed results", "approved", "Signed legal approval")])
    findings, _ = analyze("We deliver 100% guaranteed results.", rs)
    assert not [f for f in findings if f.rule_type == "prohibited_word"]


def test_matching_is_case_and_whitespace_insensitive():
    findings, _ = analyze("we use TECH   NOVA cloud daily", rules())
    assert any(f.rule_type == "terminology" for f in findings)


def test_unstored_claim_is_labelled_for_human_verification():
    findings, _ = analyze("We are the best provider.", rules())
    f = next(f for f in findings if f.category == "Unsupported claim")
    assert f.requires_human_verification and f.confidence < 1


def test_claim_heuristics_need_a_stored_claims_guideline():
    rs = rules(guidelines=[GuidelineR(1, "brand_voice", "Tone", "x")])
    findings, _ = analyze("We are the best provider.", rs)
    assert not findings  # no stored rule to cite, so nothing is invented


def test_tone_checks():
    findings, _ = analyze("This is AMAZING and we are gonna win! 😀", rules())
    cats = [f.title for f in findings if f.category == "Tone and language"]
    assert any("ALL-CAPS" in t for t in cats)
    assert any("gonna" in t for t in cats)
    assert any("Exclamation" in t for t in cats)
    assert any("Emoji" in t for t in cats)


def test_missing_required_info_only_when_triggered():
    findings, _ = analyze("Plans start at ₹999 per month.", rules())
    miss = [f for f in findings if f.category == "Missing information"]
    assert len(miss) == 1 and miss[0].action == "append" and miss[0].suggested_text == "Terms and conditions apply"
    findings, _ = analyze("We build cloud software.", rules())
    assert not [f for f in findings if f.category == "Missing information"]
    findings, _ = analyze("₹999 per month. Terms and conditions apply.", rules())
    assert not [f for f in findings if f.category == "Missing information"]


def test_expired_fact_is_flagged_as_possibly_outdated():
    rs = rules(facts=[FactR(1, "Price", "x", "₹999 per month", valid_until=date(2020, 1, 1))])
    findings, _ = analyze("Only ₹999 per month.", rs, today=date(2026, 1, 1))
    f = next(f for f in findings if f.rule_type == "fact")
    assert f.category == "Outdated information" and f.requires_human_verification


def test_explicit_pattern_facts():
    rs = rules(facts=[FactR(2, "Launch year", "x", "2021", match_pattern=r"launched\s+in\s+(\d{4})")])
    findings, _ = analyze("It launched in 2022.", rs)
    f = next(f for f in findings if f.rule_type == "fact")
    assert f.flagged_text == "2022" and f.suggested_text == "2021"
    findings, _ = analyze("It launched in 2021.", rs)
    assert not [f for f in findings if f.rule_type == "fact"]


def test_invalid_regex_is_skipped_with_warning():
    rs = rules(facts=[FactR(3, "Bad", "x", "5", match_pattern="(unclosed")])
    findings, warnings = analyze("hello", rs)
    assert warnings and "invalid" in warnings[0]


def test_long_sentence_and_missing_alt_text():
    rs = rules(guidelines=[GuidelineR(4, "writing", "Short sentences", "x"),
                           GuidelineR(5, "accessibility", "Alt text", "x")])
    long = " ".join(["word"] * 45) + "."
    findings, _ = analyze(long, rs, meta={"images_without_alt": 2})
    cats = {f.category for f in findings}
    assert "Readability" in cats and "Accessibility" in cats


def test_capitalisation_of_approved_term():
    findings, _ = analyze("We love technova cloud.", rules())
    f = next(f for f in findings if "capitalisation" in f.title)
    assert f.suggested_text == "TechNova Cloud"


def test_engine_is_deterministic():
    text = "Tech Nova Cloud is the best at ₹1,299 per month!"
    a, _ = analyze(text, rules())
    b, _ = analyze(text, rules())
    assert [(f.title, f.start) for f in a] == [(f.title, f.start) for f in b]


def test_derive_price_pattern():
    assert derive_price_pattern("₹999 per month") is not None
    assert derive_price_pattern("2021") is None
