# Architecture

```
React (Vite)  ──HTTPS/JSON + JWT──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL
                                        │
                                        ├─ services/extraction.py   TXT · PDF (PyMuPDF) · DOCX (python-docx) · image (Tesseract OCR)
                                        ├─ services/compliance.py   deterministic rule engine (no DB, no network)
                                        ├─ services/llm.py          OPTIONAL AI layer (OpenAI-compatible API)
                                        └─ services/analysis.py     loads rules → runs engine (+AI) → stores issues & suggestions
```

## Backend layers
| Folder | Role |
|---|---|
| `core/` | settings (`.env`), database session, password hashing, JWT, role dependencies |
| `models/` | SQLAlchemy tables (13) |
| `schemas/` | Pydantic request/response validation |
| `routers/` | REST endpoints (`/api/...`) |
| `services/` | business logic: extraction, compliance engine, AI layer, audit, seed |

## Data model
Organisation · User · BrandGuideline · ApprovedFact · Terminology · ProhibitedWord · ApprovedClaim · ContentSubmission ·
AnalysisRun · ComplianceIssue · CorrectionSuggestion · Review · AuditLog. Managed by Alembic (`migrations/versions/0001`).

## How a check works
1. Active rules of the user's organisation are loaded.
2. Claims marked *approved* create "allowed" zones in the text.
3. Rule checks run in a fixed order: prohibited phrases → terminology → facts → claims needing evidence → pattern-based
   claim heuristics → tone → capitalisation → readability → required information → accessibility (DOCX alt text).
   A piece of text is reported once (first match wins).
4. Every finding stores: severity, exact text and position, explanation, **rule type + id + a copy (snapshot) of the rule**,
   detection method (rule / AI), confidence, "requires human verification", and a suggestion.
5. If the AI layer is configured, its findings are validated (real rule, real quote) and added, marked for human verification.
6. The content moves to **Analyzed**. Only a human reviewer can move it to Approved / Rejected / Changes Requested.

Rule-based findings always cite a stored rule. Pattern-based heuristics (e.g. "best", "guaranteed", ALL-CAPS) are only
produced if the organisation has stored the matching guideline, so they too cite a stored rule, and they are labelled as
pattern-based and needing human verification where relevant.

## Status workflow
`draft → analyzed → submitted → approved | rejected | changes_requested → (edit) draft → …`
Editing, or applying suggestions, returns content to *draft* because the earlier analysis no longer matches the text.
Submitted and finally-decided content is locked.

## Security measures implemented
bcrypt password hashing · JWT bearer auth (role read from the database on every request) · role checks on every endpoint ·
organisation isolation on every query · creators see only their own content · upload checks (extension whitelist, size limit,
file-signature check, random server-side file names, no execution of uploads) · input validation (Pydantic) · secrets only
from environment variables · safe generic error for unexpected failures · audit log of important actions.
