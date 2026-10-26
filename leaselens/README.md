# LeaseLens

**A privacy-first assistant that flags risky clauses in contracts before you sign them, using Gemma 4 on your own computer.**

> ⚠️ **Not legal advice.** LeaseLens is an informational tool, not a lawyer. It can miss or misjudge clauses, and it does not decide whether a term is legal, enforceable or safe. For important decisions, ask a qualified legal professional in your jurisdiction.

## The problem

People sign leases, job offers and loan papers without fully understanding them. Auto-renewals, deposit deductions, one-sided changes and penalty clauses are easy to miss. Many people don't want to upload private documents to an online service.

## What LeaseLens does

1. You upload a **PDF, JPG or PNG** of a rental agreement, employment contract, loan agreement or other contract.
2. It **extracts the text** (PDF text, or OCR for scans) and lets you check and correct it.
3. It splits the text into clauses and reviews them **two independent ways**:
   - **keyword rules** that are transparent, configurable and testable
   - **Gemma 4** (local through Ollama by default), which classifies clauses and explains them in plain English
4. It shows a **report**: risk level per clause (High / Medium / Low / Uncertain), the original excerpt with its page number, why it was flagged, possible impact, questions to ask, and supporting **general guidance** from a small local knowledge base.
5. You pick findings and it **drafts a polite negotiation email**, which you edit and copy. It never sends anything.
6. An **analysis timeline** shows each step it took, with no document text stored.

## Main features

- Local-first: Ollama + `gemma4` by default. The optional Google Gemini API (`gemma-4-26b-a4b-it`) runs only after explicit consent each time
- Drag-and-drop upload with file type, signature and size checks
- PDF text extraction (PyMuPDF), with OCR fallback (Tesseract, or the local Gemma model's vision if Tesseract is missing)
- Editable extracted text before analysis
- Rules + AI risk scoring with an "evidence agreement" indicator
- TF-IDF retrieval over local guidance, with source ids and relevance explanations
- Filters by risk level and clause category; copy report / copy email
- Prompt-injection defences (escaping, flagging, independent rules, excerpts always taken from the source text)
- Temporary files are deleted after every request, including on errors

## Tech stack

| Part | Technology |
|---|---|
| Frontend | Angular 21 (standalone components, signals), TypeScript strict, Vitest |
| Backend | Python 3.11+, FastAPI, Pydantic v2, pydantic-settings, httpx |
| Documents | PyMuPDF, Pillow, pytesseract (Tesseract OCR) |
| AI | Ollama `/api/chat` with `gemma4` (default); optional `google-genai` SDK with `gemma-4-26b-a4b-it` |
| Retrieval | Pure-Python TF-IDF over `backend/app/knowledge_base/guidance.json` |
| Tests | pytest + pytest-asyncio (backend), Vitest via `ng test` (frontend) |

No database, Docker or Redis is needed for this version.

## Architecture

```
Browser (Angular, localhost:4200)
   │  /api/*  (dev proxy)
   ▼
FastAPI (localhost:8000)
   ├─ api/routes.py              HTTP endpoints only
   ├─ services/
   │   ├─ file_validation.py     extension, MIME, signature, size
   │   ├─ temp_files.py          random temp file, always deleted
   │   ├─ extraction.py + ocr.py PDF text → OCR → local vision fallback
   │   ├─ clause_segmentation.py clauses with page numbers
   │   ├─ rule_screening.py      keyword rules (knowledge_base/risk_rules.json)
   │   ├─ clause_analysis.py     Gemma JSON → Pydantic validation, 1 retry
   │   ├─ retrieval.py           TF-IDF guidance search
   │   ├─ risk_scoring.py        combine rules + AI (table in the file)
   │   ├─ injection.py           prompt-injection checks and escaping
   │   └─ email_drafting.py      negotiation email
   ├─ agents/contract_review.py  the workflow: input → segment → safety → rules → AI → retrieve → score → review
   └─ providers/                 one interface: ollama.py (default), google.py (optional), registry.py (consent rule)
```

## Prerequisites

- **Python 3.11+**
- **Node.js 20.19+, 22.12+ or 24+** (for Angular 21) and npm
- **Ollama**: https://ollama.com/download
- **Optional, for scanned PDFs and photos: Tesseract OCR**
  - Windows: `winget install UB-Mannheim.TesseractOCR` (then set `TESSERACT_CMD` if it is not on PATH)
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`

## Setup

### 1. Configuration

From the project root:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# macOS / Linux
cp .env.example .env
```

The defaults use local Ollama. You do not need a Google API key.

### 2. Ollama and Gemma 4

Install Ollama, then pull the model. The local tag is `gemma4`. Note that the Ollama tag is **not** the same as the Google model id.

```bash
ollama pull gemma4
ollama list          # should show gemma4:latest
```

`gemma4` is about 9.6 GB. On a less powerful computer, use `gemma4:e2b` and set `OLLAMA_MODEL=gemma4:e2b` in `.env`. Ollama normally runs in the background after installation. If not, run `ollama serve`.

### 3. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Check http://127.0.0.1:8000/api/health. API docs (development only): http://127.0.0.1:8000/api/docs

### 4. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm start
```

Open **http://localhost:4200**. The Angular dev server forwards `/api` to the backend (`frontend/proxy.conf.json`).

To try it, upload `samples/sample-rental-agreement.pdf`, a fictional lease written for testing.

## Optional: Google Gemini API provider

1. Create an API key in Google AI Studio.
2. In `.env`, set `GOOGLE_API_KEY=your-key` (keep `GOOGLE_MODEL=gemma-4-26b-a4b-it`).
3. Restart the backend. In step 1 of the app, choose **Google Gemini API** and tick the consent box.

The key stays on the backend and is never sent to the browser. If Google does not offer the configured model for your key, the app shows "model not available" and does **not** switch to a different model. The integration follows https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api (`from google import genai`, `client.models.generate_content`). That page is now marked as deprecated in favour of gemma.ai, so check it if the API changes.

## Environment variables

All settings are in `.env.example` with comments. The most important:

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `ollama` | Default provider (`ollama` or `google`) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `gemma4` | Local model tag |
| `GOOGLE_API_KEY` | empty | Enables the Google provider |
| `GOOGLE_MODEL` | `gemma-4-26b-a4b-it` | Google model id |
| `MAX_UPLOAD_MB` | `10` | Upload limit |
| `TESSERACT_CMD` | empty | Path to `tesseract` if not on PATH |
| `CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` | Allowed browser origins |

**CORS:** in development the browser talks to the Angular dev server, which proxies `/api`, so CORS is not normally involved. If you serve the frontend from another origin, list it in `CORS_ORIGINS`. With `ENVIRONMENT=production`, the backend refuses to start if `CORS_ORIGINS` contains `*`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/providers` | Provider availability (never returns secrets) |
| POST | `/api/documents/extract` | Upload (multipart `file`) and extract page text |
| POST | `/api/analyze` | Run the clause-review workflow on reviewed text |
| POST | `/api/negotiation-email` | Draft an email from selected findings |
| GET | `/api/knowledge-base` | Guidance categories and entries |

Errors always look like `{"error": {"code": "...", "message": "..."}}`, with no stack traces or file paths.

## Running tests

```bash
# Backend (no Ollama, Tesseract or API key needed: AI responses are mocked)
cd backend
pytest

# Frontend
cd frontend
npm test -- --watch=false
```

## How risk levels are decided

Each finding is a (clause, category) pair, found by the keyword rules, the AI, or both.

| Rules | AI | Final level | Evidence agreement |
|---|---|---|---|
| level R | not assessed / uncertain | R | low |
| none | uncertain, or any level with low confidence | Uncertain | low |
| none | level A | A | medium |
| level R | level A | the higher of R and A | high if equal, medium if one step apart, low if they disagree |

"Evidence agreement" shows how well the two checks agree. **It is not legal certainty.** You can edit the rules in `backend/app/knowledge_base/risk_rules.json`, and the guidance in `guidance.json`.

## Privacy notes

- **Local mode (default):** extraction, OCR and analysis happen on your computer. Document text is sent only to Ollama at `OLLAMA_BASE_URL`, which is local by default. Do not point it at a remote or `-cloud` model if you need local processing.
- **Google mode:** the extracted text, and later the findings you select for an email, are sent to Google. Google's terms decide how that data is handled. LeaseLens cannot verify retention.
- Uploaded files are written to a randomly named temporary file and deleted after extraction, including when errors occur. Leftovers from a crash are removed on the next start. The extracted text then lives only in your browser tab until you click "Start over" or close the page.
- Logs contain stages, counts and error types only: never document text, file names or keys.
- No analytics or third-party logging.

## Current limitations

- Rule patterns and guidance are general, written in English, and not jurisdiction-specific.
- Clause splitting is heuristic; clauses that run across a page break are split in two.
- Local models can be slow: a long document may take several minutes on a laptop CPU, and a model answer can still be wrong.
- OCR quality depends on the scan. Always check the extracted text.
- Nothing is saved between sessions (by design for this version).
- The `brand/` folder currently has **placeholder** files (see below).

## Brand files

The UI loads `brand/theme.css` (imported in `frontend/src/styles.css`) and follows the page structure of `brand/template.html`. The official brand files were not available when this project was created, so `brand/` contains clearly marked placeholders. Replace `brand/template.html`, `brand/theme.css` and `brand/STYLE_GUIDE.md` with the official versions. If their token or class names differ, update `frontend/src/styles.css` to match.

## Future improvements

- Streaming progress (Server-Sent Events) during long analyses
- Embedding-based retrieval (for example `embeddinggemma`) alongside TF-IDF
- Jurisdiction packs with reviewed, cited guidance
- Side-by-side comparison of two contract versions
- Optional encrypted local history (SQLite)
- Desktop packaging and a browser extension for online terms

## Troubleshooting

| Message | Fix |
|---|---|
| "Cannot reach the LeaseLens server" | Start the backend (`uvicorn app.main:app --port 8000`) |
| "Ollama is not reachable" | Install or start Ollama, then click **Refresh status** |
| "Model 'gemma4' is not installed" | `ollama pull gemma4` |
| "Ollama did not answer within … seconds" | Use a smaller model (`gemma4:e2b`), a shorter document, or raise `OLLAMA_TIMEOUT_SECONDS` |
| "No OCR engine is available" | Install Tesseract, or set `TESSERACT_CMD` to its full path |
| "The Google provider is not configured" | Set `GOOGLE_API_KEY` in `.env` and restart the backend |
| `ng` / Angular CLI says Node is too old | Install Node 22 LTS or 24 LTS |
