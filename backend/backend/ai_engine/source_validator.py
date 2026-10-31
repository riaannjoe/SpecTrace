"""
SpecTrace Source Evidence Validator
====================================
Validates that generated evidence references real files, valid line bounds,
and matching source snippets within the extracted project.
Invalid evidence is strictly discarded rather than clamped or fabricated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _normalize_snippet(text: str) -> str:
    """Normalizes whitespace across lines to allow minor formatting tolerance."""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def validate_evidence_with_reasons(
    evidence_list: list[dict[str, Any]],
    project_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validates evidence items against actual files on disk.

    Returns:
        tuple: (valid_evidence_list, discarded_with_reasons_list)
    """
    root = Path(project_path).resolve()
    if not root.is_dir():
        discarded = [
            {"evidence": ev, "reason": f"Project root directory does not exist: {project_path}"}
            for ev in evidence_list
        ]
        return [], discarded

    valid_results: list[dict[str, Any]] = []
    discarded_results: list[dict[str, Any]] = []

    # Cache file line reads to avoid repeatedly reading the same file
    file_cache: dict[str, list[str]] = {}

    for raw_item in evidence_list:
        if not isinstance(raw_item, dict):
            discarded_results.append({
                "evidence": raw_item,
                "reason": "Malformed evidence: item is not a dictionary.",
            })
            continue

        item = dict(raw_item)
        file_field = item.get("file")
        if not isinstance(file_field, str) or not file_field.strip():
            discarded_results.append({
                "evidence": item,
                "reason": "Malformed evidence: 'file' path must be a non-empty string.",
            })
            continue

        raw_clean = file_field.strip().replace("\\", "/")

        # Security check: forbid absolute paths and path traversal BEFORE stripping
        if (
            raw_clean.startswith("/")
            or Path(raw_clean).is_absolute()
            or (len(raw_clean) > 1 and raw_clean[1] == ":")
            or any(part == ".." for part in Path(raw_clean).parts)
        ):
            discarded_results.append({
                "evidence": item,
                "reason": f"Path traversal or absolute path rejected: '{file_field}'.",
            })
            continue

        norm_rel = raw_clean.lstrip("/")
        rel_p = Path(norm_rel)

        target = (root / rel_p).resolve()
        if not target.is_relative_to(root):
            discarded_results.append({
                "evidence": item,
                "reason": f"File escapes project root: '{file_field}'.",
            })
            continue

        if not target.exists():
            discarded_results.append({
                "evidence": item,
                "reason": f"Referenced file does not exist on disk: '{norm_rel}'.",
            })
            continue

        if not target.is_file():
            discarded_results.append({
                "evidence": item,
                "reason": f"Referenced path is not a regular file: '{norm_rel}'.",
            })
            continue

        # Cache file lines
        if norm_rel not in file_cache:
            try:
                file_cache[norm_rel] = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            except Exception as exc:
                discarded_results.append({
                    "evidence": item,
                    "reason": f"Failed reading file content: {exc}",
                })
                continue

        lines = file_cache[norm_rel]
        total_lines = len(lines)

        # Line number checks
        line = item.get("line")
        line_end = item.get("line_end")

        if line is not None:
            if not isinstance(line, int) or line < 1:
                discarded_results.append({
                    "evidence": item,
                    "reason": f"Invalid start line: {line}. Must be integer >= 1.",
                })
                continue

            # Default line_end to line if omitted
            if line_end is None:
                line_end = line
            elif not isinstance(line_end, int):
                discarded_results.append({
                    "evidence": item,
                    "reason": f"Invalid line_end: {line_end}. Must be an integer.",
                })
                continue

            if line_end < line:
                discarded_results.append({
                    "evidence": item,
                    "reason": f"Invalid range: line_end ({line_end}) < line ({line}).",
                })
                continue

            if line > total_lines or line_end > total_lines:
                discarded_results.append({
                    "evidence": item,
                    "reason": f"Line range {line}-{line_end} exceeds file length ({total_lines} lines).",
                })
                continue

            # Update sanitized line_end on output item
            item["line"] = line
            item["line_end"] = line_end

            # Verify snippet if provided
            snippet = item.get("snippet")
            if snippet and isinstance(snippet, str) and snippet.strip():
                actual_slice = "".join(lines[line - 1 : line_end])
                norm_actual = _normalize_snippet(actual_slice)
                norm_snip = _normalize_snippet(snippet)

                # Check if normalized snippet matches actual lines
                if norm_snip not in norm_actual and norm_actual not in norm_snip:
                    discarded_results.append({
                        "evidence": item,
                        "reason": f"Snippet does not correspond to source lines {line}-{line_end} in '{norm_rel}'.",
                    })
                    continue

        item["file"] = norm_rel
        valid_results.append(item)

    return valid_results, discarded_results


def validate_evidence_bounds(
    evidence_list: list[dict[str, Any]],
    project_path: str,
) -> list[dict[str, Any]]:
    """
    Validates evidence items against disk files and returns only valid evidence items.
    Discards invalid items rather than clamping.
    """
    valid, _ = validate_evidence_with_reasons(evidence_list, project_path)
    return valid
