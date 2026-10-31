"""Safe upload saving and ZIP extraction. Uploaded code is NEVER executed here - only written to disk."""
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.utils.errors import AppError

# Only these file types are extracted; everything else in the ZIP is skipped.
ALLOWED_EXTENSIONS = {
    ".py", ".txt", ".md", ".rst", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".csv", ".html",
}
IGNORED_DIRS = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules", ".idea", ".vscode",
                ".pytest_cache", "__MACOSX"}


@dataclass
class ExtractionResult:
    python_files: list[str] = field(default_factory=list)  # relative, forward-slash paths
    extracted_count: int = 0
    skipped_count: int = 0


def save_upload_with_limit(upload, dest: Path, max_bytes: int) -> None:
    """Stream the upload to disk in 1 MB chunks and stop as soon as it exceeds the limit."""
    size = 0
    with open(dest, "wb") as out:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise AppError(413, f"File too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB.")
            out.write(chunk)
    if size == 0:
        raise AppError(400, "The uploaded file is empty.")


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> ExtractionResult:
    """Validate and extract a ZIP. Rejects the whole archive on any suspicious entry."""
    if not zipfile.is_zipfile(zip_path):
        raise AppError(400, "The file is not a valid ZIP archive.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()
    result = ExtractionResult()

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            if len(infos) > settings.MAX_FILES_IN_ZIP:
                raise AppError(400, f"ZIP contains too many files (max {settings.MAX_FILES_IN_ZIP}).")
            if sum(i.file_size for i in infos) > settings.MAX_UNCOMPRESSED_BYTES:
                raise AppError(400, "ZIP expands to too much data (possible zip bomb).")

            # Pass 1: security checks on EVERY entry before writing anything.
            for info in infos:
                name = info.filename.replace("\\", "/")
                target = (dest_root / name).resolve()
                if not target.is_relative_to(dest_root):  # catches '../x', '/abs/x', 'C:/x'
                    raise AppError(400, f"Unsafe path in ZIP rejected: {info.filename}")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:  # symlink
                    raise AppError(400, f"Symbolic links are not allowed in ZIP: {info.filename}")
                if info.flag_bits & 0x1:
                    raise AppError(400, "Password-protected ZIP files are not supported.")

            # Pass 2: extract allowed files only, counting REAL bytes written (headers can lie).
            written_total = 0
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                rel = Path(name)
                if any(part in IGNORED_DIRS for part in rel.parts) or rel.suffix.lower() not in ALLOWED_EXTENSIONS:
                    result.skipped_count += 1
                    continue
                target = (dest_root / name).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    while True:
                        chunk = src.read(64 * 1024)
                        if not chunk:
                            break
                        written_total += len(chunk)
                        if written_total > settings.MAX_UNCOMPRESSED_BYTES:
                            raise AppError(400, "ZIP expands to too much data (possible zip bomb).")
                        out.write(chunk)
                result.extracted_count += 1
                if rel.suffix.lower() == ".py":
                    result.python_files.append(rel.as_posix())
    except zipfile.BadZipFile as exc:
        raise AppError(400, "The ZIP file is corrupted.") from exc
    except (RuntimeError, NotImplementedError) as exc:  # encrypted / unsupported compression
        raise AppError(400, "The ZIP file uses unsupported features.") from exc

    result.python_files.sort()
    return result


def list_python_files(source_dir: Path) -> list[str]:
    """All .py files under source_dir as relative forward-slash paths."""
    return sorted(p.relative_to(source_dir).as_posix() for p in source_dir.rglob("*.py"))


def remove_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
