# DocuQuest — Document Intelligence & Question Extraction Service

Implementation plan for the Round 2 assignment. Each phase is checked off as completed.

## Phase 0 — Scaffolding
- [x] plan.md
- [x] Repo layout, requirements.txt, Dockerfile, docker-compose.yml, .env.example

## Phase 1 — Core infra
- [x] FastAPI app skeleton, environment-based config (pydantic-settings)
- [x] SQLAlchemy models + Alembic migrations
- [x] DB session/dependency wiring

## Phase 2 — Auth
- [x] User model, JWT register/login, password hashing
- [x] `get_current_user` dependency, per-resource ownership checks

## Phase 3 — Upload & storage
- [x] DocumentGroup + Document models
- [x] Upload endpoint: validation (type/size), secure local storage, status=pending

## Phase 4 — Async pipeline
- [x] Celery app wired to Redis broker/backend
- [x] `process_document` task, status transitions (pending→processing→completed/failed)

## Phase 5 — Text/OCR extraction
- [x] PyMuPDF text-layer extraction for digital PDFs
- [x] pdf2image + pytesseract OCR fallback for scans/images, rotation correction
- [x] Page-level persistence with per-page OCR confidence

## Phase 6 — Question parsing engine
- [x] Numbering/option regex segmentation, question-type detection
- [x] Multi-page question continuation handling
- [x] Confidence scoring per question

## Phase 7 — Answer key detection & association
- [x] Detect answer-key sections/documents, parse mappings
- [x] Associate answers to questions across documents in a group
- [x] Flag unmatched/uncertain answers

## Phase 8 — API surface
- [x] Upload, status, list/get questions, answer-key, review items, group management endpoints

## Phase 9 — Confidence & review system
- [x] ReviewItem model + population during extraction
- [x] Status enums: success/partial/review; source page refs preserved

## Phase 10 — Sample data
- [x] Script to generate sample question-paper PDF, answer-key PDF, scanned-style image, low-quality/rotated sample
- [x] Sample extracted output JSON committed (`sample_data/sample_extracted_output.json`)

## Phase 11 — Tests
- [x] Unit tests for extraction/parsing (20 tests, pure functions, no I/O)
- [x] API integration tests (pytest + FastAPI TestClient against real Postgres test DB) — all passing

## Phase 12 — API docs & Postman
- [x] Swagger/OpenAPI via FastAPI (automatic, at /docs)
- [x] Postman collection covering full workflow (15 requests, register → ... → review items)

## Phase 13 — Architecture documentation
- [x] ARCHITECTURE.md covering all required topics + Mermaid diagram

## Phase 14 — Final wiring & demo pass
- [x] docker-compose up smoke test — fixed 4 real runtime bugs (bcrypt/passlib
      incompatibility, missing email-validator, enum value vs name mismatch,
      double enum-type creation in migration, page-marker boundary bug in extractor)
- [x] Ran full demo scenario end-to-end against live containers: register, login,
      create group, upload digital PDF + separate answer key PDF + degraded scan +
      rejected unsupported file, verified multi-page question (Q5 spans pages 2-3),
      verified cross-document answer-key matching, verified review-item flagging
      on the degraded scan

All phases complete.
