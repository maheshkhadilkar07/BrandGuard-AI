# Feature status

Legend: ✅ implemented and tested · 🟡 partially implemented · 🔜 planned (not implemented) · ❌ not implemented

## Round 2 MVP
| Feature | Status | Notes |
|---|:-:|---|
| Registration, login, JWT, password hashing | ✅ | automated tests |
| Logout | 🟡 | stateless: client discards token, event logged; token not revoked server-side |
| Role-based access control (Admin / Creator / Reviewer) | ✅ | tested for every role on key endpoints |
| User management (add, change role, deactivate) | ✅ | |
| Organisation profile | ✅ | |
| Brand guidelines CRUD | ✅ | |
| Approved facts, terminology, prohibited words, claims CRUD | ✅ | with validation |
| Text entry, TXT, PDF, DOCX upload and extraction | ✅ | type, size and signature validation |
| Image upload with OCR | 🟡 | works on clean test image; accuracy depends on image quality; needs Tesseract installed |
| Rule-based compliance engine | ✅ | terminology, prohibited words, facts (price/regex), claims, tone, missing info, readability |
| Severity, explanation, exact text, source rule, confidence | ✅ | confidence is fixed per rule type, not a statistical model |
| "Requires human verification" labelling | ✅ | |
| Correction suggestions: accept / reject / edit / apply | ✅ | original text never overwritten |
| Submit, review queue, approve / reject / request changes, comments | ✅ | AI never decides |
| Status workflow & locking | ✅ | |
| Dashboards (admin / creator / reviewer) with Chart.js | ✅ | API tested; charts compile but were not viewed in a browser by the developer |
| Content history, analysis history, audit log | ✅ | |
| Optional LLM analysis layer | 🟡 | implemented with safety validation; tested only with a mocked provider |
| Basic accessibility checks | 🟡 | long sentences and missing image alt text in DOCX only |
| Alembic migrations on PostgreSQL | ✅ | applied to PostgreSQL 16 |
| Docker / docker-compose | 🟡 | files written; Docker was not available to test them |
| Public deployment | ❌ | instructions in docs/DEPLOYMENT.md; not deployed |

## Planned for Round 3 (NOT implemented)
| Improvement | Status |
|---|:-:|
| Advanced AI analysis of tone, context and unsupported claims | 🔜 |
| Computer vision / OCR-based logo and visual-brand checking (OpenCV) | 🔜 |
| Colour-contrast and other visual accessibility checks | 🔜 |
| Advanced governance analytics, revision comparison, organisation-level audit reports | 🔜 |

## Known gaps
Rate limiting · password reset / e-mail · token revocation · multilingual content · UI tested only by compiling and by API tests.
