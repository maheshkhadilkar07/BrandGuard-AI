"""The AI layer is optional. These tests mock the network: no real AI provider was called."""
import json

import httpx

from app.core.config import get_settings
from app.services import llm
from app.services.compliance import GuidelineR, RuleSet, FactR


def rs():
    return RuleSet(guidelines=[GuidelineR(1, "brand_voice", "Tone", "Professional")],
                   facts=[FactR(1, "Price", "costs ₹999", "₹999")])


def test_disabled_without_key():
    findings, status = llm.review("hello", rs(), [])
    assert findings == [] and status.startswith("not_configured")


def test_findings_must_cite_real_rules_and_real_text():
    text = "We totally crush every competitor."
    items = [
        {"flagged_text": "totally crush every competitor", "rule_ref": "G1", "category": "Tone", "severity": "high",
         "explanation": "Aggressive tone.", "suggested_text": "compete effectively", "confidence": 0.8},
        {"flagged_text": "totally crush every competitor", "rule_ref": "G999", "category": "Tone"},   # unknown rule
        {"flagged_text": "text that is not in the content", "rule_ref": "G1"},                       # not in text
    ]
    _, index = llm.rules_for_prompt(rs())
    out = llm.build_findings(items, text, index, [])
    assert len(out) == 1
    f = out[0]
    assert f.rule_reference.startswith("Guideline #1") and f.requires_human_verification and f.detection_method == "ai"
    assert f.severity == "High" and 0 <= f.confidence <= 1 and f.start == text.find("totally")


def test_parse_handles_code_fences():
    assert llm.parse_items('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_review_with_mocked_provider(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(s, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(s, "LLM_MODEL", "test-model")
    reply = [{"flagged_text": "crush", "rule_ref": "G1", "category": "Tone", "severity": "Low",
              "explanation": "Aggressive.", "suggested_text": "beat", "confidence": 0.7}]

    def fake_post(url, json=None, headers=None, timeout=None):
        return httpx.Response(200, json={"choices": [{"message": {"content": __import__("json").dumps(reply)}}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    findings, status = llm.review("We crush them.", rs(), [])
    assert len(findings) == 1 and status.startswith("ok")


def test_provider_failure_never_breaks_analysis(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(s, "LLM_API_KEY", "k")
    monkeypatch.setattr(s, "LLM_MODEL", "m")

    def boom(*a, **k):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(llm.httpx, "post", boom)
    findings, status = llm.review("hello", rs(), [])
    assert findings == [] and status.startswith("error")
