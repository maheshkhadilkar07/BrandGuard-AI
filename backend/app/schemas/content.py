from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _nonblank(cls, v):
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=250)
    text: Optional[str] = Field(default=None, min_length=1)


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    original_text: str
    suggested_text: str
    explanation: str
    status: str
    final_text: Optional[str] = None
    decided_at: Optional[datetime] = None


class SuggestionUpdate(BaseModel):
    status: str
    final_text: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in ("pending", "accepted", "rejected"):
            raise ValueError("status must be pending, accepted or rejected")
        return v


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_number: int
    title: str
    category: str
    severity: str
    flagged_text: str
    start_char: Optional[int]
    end_char: Optional[int]
    explanation: str
    rule_type: str
    rule_id: int
    rule_reference: str
    rule_snapshot: str
    detection_method: str
    confidence: Optional[float]
    requires_human_verification: bool
    suggestion: Optional[SuggestionOut] = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    run_number: int
    ai_status: str
    issue_count: int
    created_at: datetime


class ReviewIn(BaseModel):
    decision: str
    comment: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("decision")
    @classmethod
    def _d(cls, v):
        if v not in ("approved", "rejected", "changes_requested"):
            raise ValueError("decision must be approved, rejected or changes_requested")
        return v


class ReviewOut(BaseModel):
    id: int
    submission_id: int
    reviewer_id: int
    reviewer_name: str
    decision: str
    comment: Optional[str]
    decided_at: datetime
    content_title: Optional[str] = None


class ContentListItem(BaseModel):
    id: int
    title: str
    source_type: str
    status: str
    creator_id: int
    creator_name: str
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    issue_count: int
    severity_counts: dict


class ContentDetail(BaseModel):
    id: int
    title: str
    source_type: str
    original_filename: Optional[str]
    status: str
    creator_id: int
    creator_name: str
    original_text: str
    revised_text: Optional[str]
    current_text: str
    extraction_meta: Optional[dict]
    run_count: int
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    issues: List[IssueOut]
    runs: List[RunOut]
    reviews: List[ReviewOut]
