<div align="center">

# 🔍 SpecTrace

### AI-powered requirement traceability for Python projects

Upload a Python project · State your requirements · Instantly know which ones are implemented — backed by real code evidence.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Tests](https://img.shields.io/badge/tests-183%20passing-brightgreen)](backend/backend)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

## What is SpecTrace?

SpecTrace is a developer tool that bridges the gap between **written requirements** and **actual code**. Given a Python project (uploaded as a ZIP) and a list of natural-language requirements, SpecTrace performs a deep static analysis — combining AST parsing, test discovery, and Gemini AI semantic reasoning — to produce a per-requirement verdict with cited evidence from the real source code.

**The core question it answers:** *"Is this requirement actually implemented in the codebase?"*

No more manually grepping through files. No more guessing which features are done. SpecTrace gives every requirement a status (`implemented`, `partially_implemented`, `missing`, `not_verified`) with file paths, line numbers, and code snippets as proof.

### Who is it for?

| Role | Use case |
|---|---|
| **Developer** | Verify which backlog items are shipped before a release |
| **QA / Test Engineer** | Find implementation gaps before writing test cases |
| **Tech Lead / Architect** | Audit a new codebase against its design spec |
| **Hackathon Team** | Demonstrate completeness of a submission |

---

## Features

### ✅ Multi-phase AI Analysis Engine
A 5-stage pipeline processes every requirement independently:

1. **AST Index** — parses every `.py` file into a structured index of classes, functions, decorators, imports, and call sites without executing any code.
2. **Static Test Discovery** — finds test functions, scores their relevance to each requirement by keyword overlap, and records them (never runs them).
3. **Gemini Semantic Matching** — batches requirements against relevant source context and sends them to `gemini-2.0-flash` with a strict JSON response schema. Identifies implementing code with file, line, and snippet evidence.
4. **Source Validation** — every piece of evidence returned by Gemini is verified against the actual files on disk (file must exist, line range must be valid, snippet must match).
5. **Risk Classification** — assigns a 4-level risk (`critical` / `high` / `medium` / `low`) to non-`not_verified` requirements based on status and confidence.

### ✅ Strict Evidence Policy
- `missing` status **cannot** be returned with empty or entirely invalid evidence — it is automatically downgraded to `not_verified`.
- `not_verified` is excluded from all risk-level counts and reported separately.
- Static test relevance scores are never treated as semantic confidence.
- Uploaded code is **never imported or executed**.

### ✅ Hybrid Analysis Mode
- When Gemini is available, results use semantic AI analysis (`gemini` mode).
- If some batches fail, per-requirement provenance is preserved; the run is marked `hybrid`.
- If Gemini is entirely unavailable, pure static analysis provides `static_fallback` results.
- The Gemini model is configurable via the `GEMINI_MODEL` environment variable.

### ✅ Full REST API (FastAPI)
Eight endpoints covering project upload, requirement submission, analysis triggering, and result retrieval. Structured errors with machine-readable codes. Swagger UI at `/docs`.

### ✅ React Frontend
Single-page application with four views:
- **Dashboard** — lists all uploaded projects with status chips and timestamps
- **Upload Project** — drag-and-drop ZIP upload with validation feedback
- **Requirements** — multi-line text area to submit natural-language requirements
- **Results** — per-requirement cards with status badges, evidence citations, risk levels, and a summary panel with counts

### ✅ MongoDB Persistence
Three collections (`projects`, `requirements`, `analysis_results`) with four indexes. All IDs are stable (`project_<12hex>`, `requirement_<12hex>`, `result_<12hex>`). Timestamps are stored as real BSON dates.

### ✅ Security-first ZIP Handling
Path traversal checks, zip-bomb protection (entry count + expanded size caps), symlink rejection, extension whitelist, isolated per-project storage. Server paths are never returned by the API.

---

## Tech Stack

| Layer | Technology | Version | Role |
|---|---|---|---|
| Frontend | React | 19 | UI framework |
| Frontend | Vite | 8.3.5 | Build tool & dev server |
| Frontend | Tailwind CSS | 4 | Utility-first styling |
| Backend | FastAPI | 0.110+ | REST API framework |
| Backend | Python | 3.11+ | Runtime |
| Backend | Uvicorn | latest | ASGI server |
| Backend | Pydantic v2 | latest | Schema validation |
| Database | MongoDB Atlas | M0+ | Persistent storage |
| Database | Motor | latest | Async MongoDB driver |
| AI | Google Gemini 2.0 Flash | `google-genai ≥2.28` | Semantic requirement matching |
| AI | Python `ast` module | stdlib | Static code analysis |
| Testing | pytest | latest | 183 tests, 1 skipped |
| Testing | mongomock | latest | In-memory MongoDB for tests |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (Vite)                    │
│  Dashboard · Upload · Requirements · Results                 │
│                    api.js (fetch wrapper)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/JSON  (port 5173 → 8001)
┌───────────────────────▼─────────────────────────────────────┐
│                  FastAPI Backend  (port 8001)                │
│                                                             │
│  routes/          services/          database/              │
│  projects.py  →  project_service  →  operations.py          │
│  requirements →  req_service      →  ─── MongoDB Atlas ───  │
│  analysis.py  →  analysis_service →  operations.py          │
│                      │                                       │
│               analysis/adapter.py                           │
│                      │                                       │
└──────────────────────┼──────────────────────────────────────┘
                        │ Python function call
┌───────────────────────▼─────────────────────────────────────┐
│                   AI Engine (ai_engine/)                     │
│                                                             │
│  analyzer.py         ← orchestrates all stages              │
│  ├─ ast_visitor.py   ← AST parsing  (never executes code)   │
│  ├─ static_tests.py  ← test discovery + relevance scoring   │
│  ├─ gemini_matcher.py← batched Gemini API calls             │
│  ├─ source_validator.py ← evidence verification vs. disk    │
│  ├─ risk_analyzer.py ← 4-level risk classification          │
│  └─ backend_adapter.py ← result format translation          │
│                                                             │
│              ↕  google-genai SDK                            │
│         Google Gemini 2.0 Flash (external)                  │
└─────────────────────────────────────────────────────────────┘
```

### Request → Response flow

```
POST /projects/{id}/analyze
    → analysis_service.run_analysis()
        → file_handler: locate extracted project directory
        → adapter.py: select real engine or mock
            → analyzer.analyze()
                → ast_visitor.extract_ast_index()       [Stage 1]
                → static_tests.discover_static_tests()  [Stage 2]
                → gemini_matcher.match_requirements()   [Stage 3]
                    → batch requirements (≤50k chars context budget)
                    → call Gemini API with response_schema
                    → fallback to static if Gemini unavailable
                → source_validator.validate_evidence()  [Stage 4]
                    → reject evidence with bad file/line/snippet
                    → downgrade missing→not_verified if no valid evidence
                → risk_analyzer.evaluate_risk()         [Stage 5]
        → analysis_service._validate_and_build_docs()
        → operations.replace_results()
    → GET /projects/{id}/results returns persisted docs
```

---

## Project Structure

```
SpecTrace/
├── backend/
│   └── backend/
│       ├── app/
│       │   ├── main.py                  # FastAPI app, CORS, error handlers
│       │   ├── config.py                # Environment settings (Pydantic)
│       │   ├── routes/
│       │   │   ├── projects.py          # Upload, list, detail endpoints
│       │   │   ├── requirements.py      # Submit & retrieve requirements
│       │   │   └── analysis.py          # Trigger & retrieve analysis
│       │   ├── services/
│       │   │   ├── project_service.py
│       │   │   ├── requirement_service.py
│       │   │   └── analysis_service.py  # Orchestration + risk summary
│       │   ├── database/
│       │   │   ├── connection.py        # Motor async client
│       │   │   └── operations.py        # All MongoDB reads/writes
│       │   ├── schemas/
│       │   │   ├── project.py
│       │   │   ├── requirement.py
│       │   │   └── result.py            # ResultOut, SummaryOut
│       │   ├── analysis/
│       │   │   ├── contract.py          # Engine I/O contract (documented)
│       │   │   ├── adapter.py           # Real engine dispatcher
│       │   │   └── mock_adapter.py      # Always-not_verified mock
│       │   └── utils/
│       │       ├── file_handler.py      # ZIP extraction & security
│       │       ├── errors.py            # Structured error responses
│       │       └── ids.py               # ID generation (uuid4 hex)
│       ├── ai_engine/
│       │   ├── analyzer.py              # Main pipeline orchestrator
│       │   ├── ast_visitor.py           # AST index builder
│       │   ├── static_tests.py          # Test discovery & relevance
│       │   ├── gemini_matcher.py        # Batched Gemini API calls
│       │   ├── source_validator.py      # Evidence file/line validation
│       │   ├── risk_analyzer.py         # Risk classification rules
│       │   └── backend_adapter.py       # Format translation
│       ├── tests/                       # 183 tests (183 pass, 1 skip)
│       ├── .env.example
│       ├── requirements.txt
│       └── pytest.ini
└── frontend/
    ├── src/
    │   ├── App.jsx                      # Router + global state
    │   ├── api.js                       # All fetch calls to backend
    │   ├── components/
    │   │   ├── Dashboard.jsx
    │   │   ├── UploadProject.jsx
    │   │   ├── Requirements.jsx
    │   │   ├── Results.jsx
    │   │   ├── ProjectDetails.jsx
    │   │   ├── Navbar.jsx
    │   │   └── Sidebar.jsx
    │   ├── index.css
    │   └── results.css
    ├── .env.example
    ├── package.json
    └── vite.config.js
```

---

## Setup & Installation

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **MongoDB Atlas** free cluster (M0) — [create one here](https://www.mongodb.com/atlas/database)
- **Google AI Studio API key** — [get one here](https://aistudio.google.com/apikey)

---

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/SpecTrace.git
cd SpecTrace
```

---

### 2. Backend setup

```bash
cd backend/backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

Edit `.env` and fill in your values:

```env
# MongoDB Atlas
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGODB_DB_NAME=spectrace

# Google Gemini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash          # optional — this is the default

# Server
PORT=8001
MAX_UPLOAD_MB=50
ANALYSIS_ENGINE=real                   # set to "mock" to skip AI calls
```

**MongoDB Atlas quick setup:**
1. Create a free M0 cluster
2. Database Access → add a user (no special characters in password)
3. Network Access → Allow access from anywhere (`0.0.0.0/0`)
4. Connect → Drivers → Python → copy connection string into `MONGODB_URI`

Collections and indexes are created automatically on first run.

**Start the backend:**

```bash
uvicorn app.main:app --reload --port 8001
```

Health check: `http://localhost:8001/` should return `{"status": "ok", "database": "connected"}`.

Swagger UI: `http://localhost:8001/docs`

---

### 3. Frontend setup

```bash
cd frontend

# Copy environment template
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

The `.env` should contain:

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

```bash
# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend: `http://localhost:5173`

---

### 4. Run tests

```bash
cd backend/backend
python -m pytest --tb=short -q
```

Tests use `mongomock` (in-memory MongoDB). No Atlas connection required. Tests that need a real connection skip themselves if `.env` is not configured.

**Current test results: 183 passed, 1 skipped, 0 failed.**

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check — confirms database connectivity |
| `POST` | `/projects/upload` | Upload a Python project as a `.zip` file |
| `GET` | `/projects` | List all uploaded projects |
| `GET` | `/projects/{id}` | Get project details |
| `POST` | `/projects/{id}/requirements` | Submit natural-language requirements |
| `GET` | `/projects/{id}/requirements` | Retrieve submitted requirements |
| `POST` | `/projects/{id}/analyze` | Trigger analysis (synchronous) |
| `GET` | `/projects/{id}/results` | Retrieve analysis results |

### Upload a project

```bash
curl -X POST http://localhost:8001/projects/upload \
  -F "file=@my_project.zip" \
  -F "project_name=My App"
```

### Submit requirements

```bash
curl -X POST http://localhost:8001/projects/project_<id>/requirements \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": [
      "Users should be able to register with an email address.",
      "Passwords must be hashed before storage.",
      "Users should be able to log in and receive a session token."
    ],
    "replace": false
  }'
```

### Trigger analysis

```bash
curl -X POST http://localhost:8001/projects/project_<id>/analyze
```

### Sample result response

```json
{
  "project_id": "project_3f9a1c2b7d10",
  "project_name": "My App",
  "project_status": "analyzed",
  "analyzed_at": "2026-10-31T10:16:02Z",
  "engine": "SpecTrace AST Engine v1",
  "is_mock": false,
  "analysis_mode": "gemini",
  "summary": {
    "total": 3,
    "implemented": 2,
    "partially_implemented": 1,
    "missing": 0,
    "not_verified": 0,
    "critical_risks": 0,
    "high_risks": 1,
    "medium_risks": 1,
    "low_risks": 1
  },
  "results": [
    {
      "id": "result_a1b2c3d4e5f6",
      "requirement_id": "requirement_0a1b2c3d4e5f",
      "requirement_description": "Passwords must be hashed before storage.",
      "status": "implemented",
      "confidence": 0.94,
      "risk_level": "low",
      "evidence": [
        {
          "file": "auth.py",
          "line": 42,
          "snippet": "password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())",
          "description": "bcrypt hash applied before user record is written"
        }
      ],
      "test_status": "not_run",
      "explanation": "auth.py line 42 applies bcrypt.hashpw before writing the user record.",
      "analysis_mode": "gemini",
      "engine": "SpecTrace AST Engine v1",
      "is_mock": false,
      "analyzed_at": "2026-10-31T10:16:02Z"
    }
  ]
}
```

### Error format

All errors use a consistent envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Project not found.",
    "details": []
  }
}
```

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `bad_request` | Invalid input or malformed ZIP |
| 404 | `not_found` | Unknown project or requirement ID |
| 409 | `conflict` | Analysis already running |
| 413 | `file_too_large` | ZIP exceeds `MAX_UPLOAD_MB` |
| 422 | `validation_error` | Schema validation failure |
| 502 | `engine_error` | AI engine returned bad output |
| 503 | `database_error` | MongoDB unreachable |

---

## How the AI Analysis Works

### Stage 1: AST Parsing

Every `.py` file in the uploaded project is parsed with Python's `ast` module — **no code is ever imported or executed**. The result is a structured index of:
- Function and class definitions (name, line, docstring, decorators)
- Import statements
- Call sites
- Assignment patterns

### Stage 2: Static Test Discovery

Test files are identified by naming convention (`test_*.py`, `*_test.py`). Each test function is scored for relevance to each requirement using keyword overlap. Relevance scores are stored separately and **never treated as semantic confidence**.

### Stage 3: Gemini Semantic Matching

Requirements are grouped into batches with a 50 000-character context budget. For each batch, a prompt containing the requirements and the most relevant source context is sent to `gemini-2.0-flash` using JSON mode with a strict `response_schema`. The model identifies implementing code with file paths, line ranges, and snippets.

- If Gemini is unavailable (no API key, timeout, rate limit), the batch falls back to static analysis.
- If some batches succeed and others fail, the run is marked `hybrid`. Per-requirement provenance is always recorded.
- The model is configurable via `GEMINI_MODEL`.

### Stage 4: Evidence Validation

Every piece of evidence from Gemini is validated against actual files on disk:
- File must exist in the extracted project
- Line range must be within the file
- Snippet must match the actual file content

Invalid evidence is rejected. If all evidence for a `missing` result is invalid, the status is downgraded to `not_verified`.

**Important policy:** `missing` status cannot be returned with an empty evidence list. Insufficient evidence → `not_verified`. This prevents false negatives from absent keywords.

### Stage 5: Risk Classification

A rule-based classifier assigns a risk level to each requirement:

| Status | Confidence | Risk Level |
|---|---|---|
| `missing` | any | `critical` |
| `partially_implemented` | < 0.5 | `high` |
| `partially_implemented` | ≥ 0.5 | `medium` |
| `implemented` | < 0.7 | `medium` |
| `implemented` | ≥ 0.7 | `low` |

`not_verified` requirements are **excluded** from all risk counts and reported separately.

---

## Configuration Reference

### Backend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | *required* | MongoDB Atlas connection string |
| `MONGODB_DB_NAME` | `spectrace` | Database name |
| `GEMINI_API_KEY` | *required for AI* | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `ANALYSIS_ENGINE` | `real` | `real` or `mock` |
| `MAX_UPLOAD_MB` | `50` | ZIP upload size limit |
| `PORT` | `8001` | Server port |

### Frontend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8001` | Backend base URL |

---

## Known Limitations

- **No authentication** — any user who can reach the API can list all projects. Add an auth layer before production use.
- **No analysis run history** — re-running analysis replaces previous results for that project.
- **`test_status` is always `not_run`** — executing uploaded test files requires a sandboxed environment (container + resource limits) not implemented in this version.
- **Python projects only** — the AST engine is Python-specific.
- **Synchronous analysis** — large projects may take several seconds; the API blocks until complete.
- **No rate limiting** — add a reverse proxy (nginx, Caddy) with rate limiting for public deployments.

---

## Security

- **ZIP bomb protection** — entry count cap, expanded size cap, entry-by-entry byte accounting.
- **Path traversal prevention** — every ZIP entry checked for `..` and absolute paths; symlinks and encrypted entries rejected; only whitelisted file types extracted.
- **No code execution** — uploaded code is read as text for AST parsing only.
- **Credentials via `.env`** — never committed (`.gitignore` covers `.env`). Server internal paths never returned by the API.
- **API key safety** — `GEMINI_API_KEY` is never logged or returned in any API response. Gemini error details are sanitized before reaching API consumers.

---

## Deployment

### Backend (Railway / Render / any PaaS)

1. Set all environment variables from the [Configuration Reference](#configuration-reference) in your platform's dashboard.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Point `MONGODB_URI` at your Atlas cluster with Network Access open to `0.0.0.0/0`.

### Frontend (Vercel / Netlify)

1. Set `VITE_API_BASE_URL` to your deployed backend URL.
2. Build command: `npm run build`
3. Output directory: `dist`

### Access instructions for judges

If login is required, see the submission form for test credentials. Never share personal passwords.

---

## Acknowledgements

Built for **Uncharted 2026** — NEXUS | SVNIT Surat, 30 October – 1 November 2026.

Track 3: Developer Tools for Production Use Cases.

---

## License

[MIT](LICENSE)
