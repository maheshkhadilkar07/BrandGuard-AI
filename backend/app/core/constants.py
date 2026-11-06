ROLE_ADMIN = "admin"
ROLE_CREATOR = "creator"
ROLE_REVIEWER = "reviewer"
ROLES = (ROLE_ADMIN, ROLE_CREATOR, ROLE_REVIEWER)

# Content workflow statuses
ST_DRAFT = "draft"
ST_ANALYZED = "analyzed"
ST_SUBMITTED = "submitted"
ST_CHANGES = "changes_requested"
ST_APPROVED = "approved"
ST_REJECTED = "rejected"
STATUSES = (ST_DRAFT, ST_ANALYZED, ST_SUBMITTED, ST_CHANGES, ST_APPROVED, ST_REJECTED)
EDITABLE_STATUSES = (ST_DRAFT, ST_ANALYZED, ST_CHANGES)

SEVERITIES = ("Critical", "High", "Medium", "Low")
SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}

GUIDELINE_CATEGORIES = (
    "brand_voice", "writing", "claims", "required_info", "accessibility", "terminology", "general",
)
DECISIONS = ("approved", "rejected", "changes_requested")
