# SpecTrace – Backend (FastAPI + MongoDB Atlas)

Upload a Python project (ZIP) → add requirements → analyse → get a requirement-by-requirement report.

```
React  ──HTTP/JSON──►  FastAPI routes ─► services ─► database/operations ─► MongoDB Atlas
                                            │
                                            └─► analysis/adapter ─► (mock | real AST engine)
```
Routes only parse HTTP. Services hold the logic. `database/operations.py` is the only file that talks to MongoDB.

## 1. Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
```

### Connect MongoDB Atlas
1. atlas → create a free **M0** cluster.
2. **Database Access** → Add user (username + password; avoid special characters like `@ : /` in the password, or URL-encode them).
3. **Network Access** → Add IP → "Allow access from anywhere" (`0.0.0.0/0`) is fine for a hackathon.
4. **Connect → Drivers → Python** → copy the string into `.env` as `MONGODB_URI`, replacing `<username>` / `<password>`.
5. Collections (`projects`, `requirements`, `analysis_results`) and indexes are created automatically. The DB name is `MONGODB_DB_NAME=spectrace`.

## 2. Run

```bash
uvicorn app.main:app --reload --port 8000
```
- Health check: http://localhost:8000/  → should say `"database": "connected"`
- Swagger UI: http://localhost:8000/docs

## 3. Test

```bash
pytest -v
```
Tests use an in-memory fake MongoDB (`mongomock`), so they run without Atlas. `tests/test_db_connection.py` tests your real Atlas connection and skips itself if `.env` isn't set.

## 4. API

| Method | Endpoint | Body | Success |
|---|---|---|---|
| GET | `/` | – | 200 |
| POST | `/projects/upload` | multipart: `file` (.zip), optional `project_name` | 201 Project |
| GET | `/projects` | – | 200 `{count, projects}` |
| GET | `/projects/{id}` | – | 200 Project |
| POST | `/projects/{id}/requirements` | `{"requirements": ["..."], "replace": false}` | 201 `{project_id, count, requirements}` |
| GET | `/projects/{id}/requirements` | – | 200 same shape |
| POST | `/projects/{id}/analyze` | – | 200 Results |
| GET | `/projects/{id}/results` | – | 200 Results |

**Errors** always look like `{"error": {"code": "not_found", "message": "...", "details": [...]}}`.
Codes used: 400 bad input/ZIP · 404 unknown id · 409 analysis already running · 413 file too large · 422 validation · 502 engine returned bad output · 503 database down.

### Sample flow (curl)
```bash
curl -X POST localhost:8000/projects/upload -F "file=@student_app.zip" -F "project_name=Student App"
# -> {"id":"project_3f9a1c2b7d10","project_name":"Student App","filename":"student_app.zip","language":"Python",
#     "status":"uploaded","python_file_count":4,"total_file_count":6,"created_at":"2026-10-31T10:15:00Z","last_analyzed_at":null}

curl -X POST localhost:8000/projects/project_3f9a1c2b7d10/requirements -H "Content-Type: application/json" \
  -d '{"requirements":["Users must be able to register","Users must be able to log in","Passwords must be validated"]}'

curl -X POST localhost:8000/projects/project_3f9a1c2b7d10/analyze
curl localhost:8000/projects/project_3f9a1c2b7d10/results
```
Results response (shown here with a real engine; with the mock every status is `not_verified` and `is_mock` is `true`):
```json
{
  "project_id": "project_3f9a1c2b7d10",
  "project_name": "Student App",
  "project_status": "analyzed",
  "analyzed_at": "2026-10-31T10:16:02Z",
  "engine": "SpecTrace AST Engine v1",
  "is_mock": false,
  "summary": {"total": 3, "implemented": 1, "partially_implemented": 1, "missing": 1, "not_verified": 0},
  "results": [{
    "id": "result_a1b2c3d4e5f6", "project_id": "project_3f9a1c2b7d10",
    "requirement_id": "requirement_0a1b2c3d4e5f",
    "requirement_description": "Users must be able to log in",
    "status": "implemented",
    "evidence": [{"file": "auth.py", "line": 25, "description": "login() function identified"}],
    "file_name": "auth.py", "line_number": 25,
    "test_status": "not_run",
    "explanation": "...", "engine": "SpecTrace AST Engine v1", "is_mock": false,
    "analyzed_at": "2026-10-31T10:16:02Z"
  }]
}
```
React examples: `docs/frontend_api_example.js`.

## 5. MongoDB design

| Collection | Key fields |
|---|---|
| `projects` | `_id` (`project_…`), `project_name`, `filename`, `language`, `status`, `python_file_count`, `total_file_count`, `storage_path` (internal), `created_at`, `last_analyzed_at` |
| `requirements` | `_id` (`requirement_…`), `project_id`, `description`, `status` (`pending` → result status), `created_at` |
| `analysis_results` | `_id` (`result_…`), `project_id`, `requirement_id`, `requirement_description`, `status`, `evidence[]`, `file_name`, `line_number`, `test_status`, `explanation`, `engine`, `is_mock`, `order`, `analyzed_at` |

Indexes: `projects.created_at`, `requirements(project_id, created_at)`, `analysis_results(project_id, order)` and `(project_id, requirement_id)`. Timestamps are real BSON dates (UTC). Re-running analysis replaces that project's old results.

Added vs. your draft: `evidence` embedded in the result (one read gets everything), `is_mock`/`engine` flags, `order` to keep results in requirement order, file counts on the project.

## 6. Plugging in the real analysis engine (for the AST teammate)

The contract is documented at the top of `app/analysis/contract.py`. Short version:

1. Create a package in `backend/`, e.g. `backend/analysis_engine/__init__.py`, exposing `def analyze(request: dict) -> dict`.
2. Input: `project_id`, `project_path` (folder with extracted files), `python_files` (relative paths), `requirements` (`[{id, description}]`).
3. Output: `{"engine_name": "...", "is_mock": false, "results": [{requirement_id, status, evidence[{file,line,description}], test_status, explanation}]}`.
4. In `.env` set `ANALYSIS_ENGINE=real` and restart. **No backend code changes.**

The backend validates the output: bad structure or unknown requirement IDs → 502 and the project is marked `analysis_failed`; requirements the engine skips are stored as `not_verified`.
The mock (`app/analysis/mock_adapter.py`) never invents results: everything is `not_verified`, `is_mock: true`, explanation says "MOCK RESULT". The frontend should show a visible "demo data" banner when `is_mock` is true.

## 7. Security notes
- ZIP: extension check, streamed size limit (`MAX_UPLOAD_MB`), `zipfile` validity check, every entry checked for path traversal (`..`, absolute paths), symlinks and encryption rejected, file-count and expanded-size caps (zip-bomb protection), actual bytes counted while writing, only whitelisted file types extracted, one isolated folder per project.
- Uploaded code is **never imported or executed**. **Test execution (pytest on uploaded code) is intentionally NOT implemented**: it needs a sandbox (container, timeouts, resource limits) that isn't realistic in 7 hours, so `test_status` is `not_run` unless your engine supplies it.
- Credentials only via `.env` (git-ignored). Server file paths are never returned by the API.
- Not included (by design for the MVP): authentication, rate limiting, per-user project ownership. Anyone who can reach the API can list all projects.

## 8. Project layout
```
backend/
├── app/
│   ├── main.py                 # app, CORS, error handlers, health check
│   ├── config.py               # env settings
│   ├── routes/                 # projects.py, requirements.py, analysis.py
│   ├── services/               # project_service.py, requirement_service.py, analysis_service.py
│   ├── database/               # connection.py, operations.py
│   ├── schemas/                # project.py, requirement.py, result.py
│   ├── analysis/               # contract.py, adapter.py, mock_adapter.py   (NEW)
│   └── utils/                  # file_handler.py, errors.py, ids.py
├── tests/  docs/  uploads/
├── .env.example  .gitignore  requirements.txt  pytest.ini  README.md
```
