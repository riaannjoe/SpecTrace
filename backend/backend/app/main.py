import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database.connection import check_connection, create_indexes, get_db
from app.routes import analysis, projects, requirements
from app.utils.errors import AppError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spectrace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        get_db()
        create_indexes()
        logger.info("Connected to MongoDB, indexes ready.")
    except Exception as exc:  # don't crash: / will report the DB problem and you can fix .env
        logger.error("Startup DB check failed: %s", exc)
    yield


app = FastAPI(
    title="SpecTrace API",
    description="Checks whether a Python project implements its stated requirements.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(requirements.router)
app.include_router(analysis.router)


# ---------- consistent error format: {"error": {"code": ..., "message": ...}} ----------
def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return _error(exc.status_code, HTTPStatus(exc.status_code).name.lower(), exc.message)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, HTTPStatus(exc.status_code).name.lower(), str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return _error(422, "validation_error", "The request is invalid.", details)


@app.exception_handler(PyMongoError)
async def mongo_error_handler(request: Request, exc: PyMongoError):
    logger.error("MongoDB error: %s", exc)
    return _error(503, "database_unavailable", "The database is temporarily unavailable.")


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return _error(500, "internal_server_error", "Something went wrong on the server.")


@app.get("/", tags=["Health"])
def health_check():
    db_ok = check_connection()
    return {
        "status": "ok",
        "service": "SpecTrace API",
        "database": "connected" if db_ok else "unavailable",
        "analysis_engine": settings.ANALYSIS_ENGINE,
    }
