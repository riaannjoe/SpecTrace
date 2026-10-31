"""Central place for all settings. Everything comes from environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # the "backend/" folder
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.MONGODB_URI: str = os.getenv("MONGODB_URI", "")
        self.MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "spectrace")

        origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
        self.CORS_ORIGINS: list[str] = [o.strip() for o in origins.split(",") if o.strip()]

        upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
        self.UPLOAD_DIR: Path = upload_dir if upload_dir.is_absolute() else BASE_DIR / upload_dir

        self.MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
        # Zip-bomb protection: limits on what a ZIP may expand to.
        self.MAX_UNCOMPRESSED_BYTES: int = 200 * 1024 * 1024
        self.MAX_FILES_IN_ZIP: int = 2000

        self.ANALYSIS_ENGINE: str = os.getenv("ANALYSIS_ENGINE", "mock").lower()  # mock | real
        self.ANALYSIS_ENGINE_MODULE: str = os.getenv("ANALYSIS_ENGINE_MODULE", "analysis_engine")


settings = Settings()
