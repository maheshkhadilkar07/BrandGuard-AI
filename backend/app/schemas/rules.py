import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import GUIDELINE_CATEGORIES, SEVERITIES


def _check_sev(v: str) -> str:
    if v not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}")
    return v


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class GuidelineIn(BaseModel):
    category: str
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    source_reference: Optional[str] = Field(default=None, max_length=300)
    severity: str = "Medium"
    params: Optional[dict] = None
    is_active: bool = True

    _sev = field_validator("severity")(_check_sev)

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in GUIDELINE_CATEGORIES:
            raise ValueError(f"category must be one of {GUIDELINE_CATEGORIES}")
        return v

    @model_validator(mode="after")
    def _params(self):
        if self.category == "required_info":
            phrases = (self.params or {}).get("required_phrases")
            if not isinstance(phrases, list) or not phrases or not all(isinstance(p, str) and p.strip() for p in phrases):
                raise ValueError('required_info guidelines need params like {"required_phrases": ["..."]}')
        return self


class GuidelineOut(GuidelineIn, _Out):
    pass


class FactIn(BaseModel):
    subject: str = Field(min_length=2, max_length=200)
    statement: str = Field(min_length=2)
    correct_value: str = Field(min_length=1, max_length=200)
    match_pattern: Optional[str] = Field(default=None, max_length=400)
    source_reference: Optional[str] = Field(default=None, max_length=300)
    valid_until: Optional[date] = None
    is_active: bool = True

    @field_validator("match_pattern")
    @classmethod
    def _regex(cls, v):
        if v:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"invalid regular expression: {e}")
        return v or None


class FactOut(FactIn, _Out):
    pass


class TermIn(BaseModel):
    approved_term: str = Field(min_length=1, max_length=200)
    incorrect_variants: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    source_reference: Optional[str] = Field(default=None, max_length=300)
    is_active: bool = True

    @field_validator("incorrect_variants")
    @classmethod
    def _clean(cls, v):
        return [x.strip() for x in v if x and x.strip()]


class TermOut(TermIn, _Out):
    pass


class ProhibitedIn(BaseModel):
    phrase: str = Field(min_length=1, max_length=300)
    suggested_replacement: Optional[str] = Field(default=None, max_length=300)
    severity: str = "High"
    reason: Optional[str] = None
    source_reference: Optional[str] = Field(default=None, max_length=300)
    is_active: bool = True

    _sev = field_validator("severity")(_check_sev)


class ProhibitedOut(ProhibitedIn, _Out):
    pass


class ClaimIn(BaseModel):
    claim_text: str = Field(min_length=2, max_length=400)
    status: str = "requires_evidence"
    evidence: Optional[str] = None
    source_reference: Optional[str] = Field(default=None, max_length=300)
    is_active: bool = True

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in ("approved", "requires_evidence"):
            raise ValueError("status must be 'approved' or 'requires_evidence'")
        return v

    @model_validator(mode="after")
    def _ev(self):
        if self.status == "approved" and not (self.evidence or "").strip():
            raise ValueError("an approved claim must include its evidence")
        return self


class ClaimOut(ClaimIn, _Out):
    pass
