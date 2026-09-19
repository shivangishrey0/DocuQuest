# DocuQuest

Document Intelligence & Question Extraction Service — accepts PDF/image question-bank
documents, processes them asynchronously (OCR + rule-based extraction), and exposes
structured questions, answer-key associations, and review flags through a versioned
REST API.

Built for the Pragati Bharti Full Stack Developer Round 2 assignment. See
[ARCHITECTURE.md](ARCHITECTURE.md) for design decisions, trade-offs, and diagrams.

## Stack

- **API**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 16 (SQLAlchemy 2.0 + Alembic migrations)
- **Queue / async processing**: Celery + Redis
- **OCR / parsing**: PyMuPDF (digital PDF text layer), pdf2image + Tesseract OCR
  (scans/images), a rule-based regex extraction engine (no external AI service
  required by default)
- **Auth**: JWT (OAuth2 password flow)

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d --build
```

This starts Postgres, Redis, the FastAPI app (port `8000`), and a Celery worker.
Migrations run automatically on API container start (`alembic upgrade head`).

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### Generate sample documents

Sample input documents are already committed under `sample_data/`. To regenerate them:

```bash
docker run --rm -v "$(pwd)/sample_data:/app/sample_data" docuquest-api python -m scripts.generate_samples
```

This produces:
| File | Purpose |
|---|---|
| `question_paper_digital.pdf` | Clean digital PDF, 6 questions, MCQ + true/false + short-answer, one question (`5`) deliberately spans two pages |
| `answer_key.pdf` | Separate document with answers for questions 1–5 (6 and 7 intentionally omitted to demo unmatched-answer handling) |
| `scanned_lowquality.png` | Rotated, noised, blurred image simulating a poor phone-camera scan (demonstrates OCR + confidence/review flagging) |
| `unsupported.txt` | Plain text file to demonstrate rejection of unsupported uploads |

### Run the demo workflow

Import [`postman/DocuQuest.postman_collection.json`](postman/DocuQuest.postman_collection.json)
into Postman. It walks through: register → login → create group → upload question
paper + answer key + scanned image + (rejected) unsupported file → poll status →
list questions → list group questions (with matched answers) → get answer key →
get review items.

Postman's `file` form-data values point at `sample_data/...`, relative to wherever
Postman is run from — set the working directory or replace with absolute paths.

### Run tests

```bash
docker compose exec api pytest -q
```

Tests run against a real Postgres database (`docuquest_test`, created automatically
inside the same Postgres container) since the schema uses Postgres-specific types
(UUID, JSONB, native enums) — see [ARCHITECTURE.md](ARCHITECTURE.md#testing).

## Configuration

All configuration is environment-based (see `.env.example`). Nothing is hardcoded;
no secrets are committed. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis/Celery wiring |
| `JWT_SECRET_KEY` | Sign/verify access tokens — **change in production** |
| `STORAGE_ROOT` | Where uploaded files and rendered page images are stored |
| `MAX_UPLOAD_SIZE_MB`, `ALLOWED_EXTENSIONS` | Upload validation limits |
| `OPENAI_API_KEY` (optional) | Not required — the system runs fully offline with the rule-based extractor. Reserved for an optional future AI-assisted extraction pass. |

## API surface (summary)

| Method & Path | Purpose |
|---|---|
| `POST /api/v1/auth/register` | Create a user |
| `POST /api/v1/auth/login` | OAuth2 password login → JWT |
| `POST /api/v1/documents/upload` | Upload a PDF/image (optionally `?group_id=`) |
| `GET /api/v1/documents` | List your documents |
| `GET /api/v1/documents/{id}` | Get one document |
| `GET /api/v1/documents/{id}/status` | Poll processing status |
| `GET /api/v1/documents/{id}/questions` | List extracted questions (filter `?status=`) |
| `GET /api/v1/questions/{id}` | Get one question |
| `GET /api/v1/documents/{id}/answer-key` | Raw parsed answer-key entries for a document |
| `GET /api/v1/documents/{id}/review-items` | Warnings/flags raised during processing |
| `POST /api/v1/groups` / `GET /api/v1/groups` / `GET /api/v1/groups/{id}` | Manage document groups (e.g. question paper + its answer key) |
| `POST /api/v1/groups/{id}/documents` | Attach a document to a group |
| `GET /api/v1/groups/{id}/questions` | List a group's questions, including answers matched from a sibling answer-key document |

Full request/response schemas are in Swagger UI (`/docs`).

## Repository layout

```
app/
  api/routes/       FastAPI routers (auth, documents, questions, groups)
  models/           SQLAlchemy models
  schemas/          Pydantic request/response models
  services/         Storage validation, OCR, question extraction, answer-key parsing
  workers/          Celery app + the process_document task (the pipeline)
  tests/            pytest unit + API integration tests
alembic/            DB migrations
scripts/            Sample-document generator
sample_data/        Generated sample inputs
postman/            Postman collection
```

## Known limitations

See [ARCHITECTURE.md](ARCHITECTURE.md#trade-offs-and-limitations) for the full list —
notably, the extraction engine is regex/heuristic-based (not a trained ML model), so
highly irregular numbering schemes or heavily degraded scans will land in `review`
status rather than being silently guessed.
