"""
SpecTrace AST Visitor & Indexer
================================
Safe AST parsing and static indexing of Python projects.
Uploaded code is NEVER imported, executed, or passed to subprocesses.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB per source file cap


class _CallVisitor(ast.NodeVisitor):
    """Collects function and method call names within an AST subtree."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = self._resolve_call_name(node.func)
        if name:
            self.calls.append({"name": name, "line": node.lineno})
        self.generic_visit(node)

    @staticmethod
    def _resolve_call_name(func_node: ast.AST) -> str | None:
        try:
            return ast.unparse(func_node)
        except Exception:
            if isinstance(func_node, ast.Name):
                return func_node.id
            if isinstance(func_node, ast.Attribute):
                val = _CallVisitor._resolve_call_name(func_node.value)
                return f"{val}.{func_node.attr}" if val else func_node.attr
            return None


def _format_args(args_node: ast.arguments) -> list[str]:
    """Formats argument names from an ast.arguments node."""
    arg_list: list[str] = []
    # Positional only
    for a in getattr(args_node, "posonlyargs", []):
        arg_list.append(a.arg)
    # Standard positional/keyword
    for a in args_node.args:
        arg_list.append(a.arg)
    # *args
    if args_node.vararg:
        arg_list.append(f"*{args_node.vararg.arg}")
    # Keyword only
    for a in args_node.kwonlyargs:
        arg_list.append(a.arg)
    # **kwargs
    if args_node.kwarg:
        arg_list.append(f"**{args_node.kwarg.arg}")
    return arg_list


def _extract_snippet(lines: list[str], start_line: int, end_line: int) -> str:
    """Extracts lines start_line..end_line (1-indexed, inclusive) as a clean snippet string."""
    if not lines or start_line < 1:
        return ""
    total = len(lines)
    clamped_start = max(1, start_line)
    clamped_end = min(total, max(clamped_start, end_line))
    return "".join(lines[clamped_start - 1 : clamped_end]).strip()


def _parse_single_file(
    rel_path: str,
    target: Path,
    content: str,
) -> dict[str, Any]:
    """Parses a single Python file AST and extracts structural symbols."""
    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    tree = ast.parse(content, filename=rel_path)

    module_doc = ast.get_docstring(tree) or ""
    imports: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    all_calls: list[dict[str, Any]] = []

    # Collect module-level imports
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "name": alias.name,
                    "asname": alias.asname,
                    "module": None,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append({
                    "name": alias.name,
                    "asname": alias.asname,
                    "module": mod,
                    "line": node.lineno,
                })

    # Collect classes and functions
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            bases: list[str] = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    bases.append(getattr(b, "id", "Unknown"))

            methods: list[dict[str, Any]] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_start = item.lineno
                    m_end = getattr(item, "end_lineno", m_start)
                    call_vis = _CallVisitor()
                    call_vis.visit(item)
                    all_calls.extend(call_vis.calls)

                    methods.append({
                        "name": item.name,
                        "args": _format_args(item.args),
                        "docstring": ast.get_docstring(item) or "",
                        "line": m_start,
                        "line_end": m_end,
                        "snippet": _extract_snippet(lines, m_start, m_end),
                        "calls": [c["name"] for c in call_vis.calls],
                        "is_async": isinstance(item, ast.AsyncFunctionDef),
                    })

            classes.append({
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "bases": bases,
                "line": start,
                "line_end": end,
                "snippet": _extract_snippet(lines, start, end),
                "methods": methods,
            })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            call_vis = _CallVisitor()
            call_vis.visit(node)
            all_calls.extend(call_vis.calls)

            functions.append({
                "name": node.name,
                "args": _format_args(node.args),
                "docstring": ast.get_docstring(node) or "",
                "line": start,
                "line_end": end,
                "snippet": _extract_snippet(lines, start, end),
                "calls": [c["name"] for c in call_vis.calls],
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })

    # Also capture top-level calls outside functions/classes if any
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            call_vis = _CallVisitor()
            call_vis.visit(node)
            all_calls.extend(call_vis.calls)

    return {
        "file_path": rel_path,
        "total_lines": total_lines,
        "docstring": module_doc,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "calls": all_calls,
    }


def extract_ast_index(
    project_path: str,
    python_files: list[str],
) -> dict[str, Any]:
    """
    Parses all designated Python files under project_path using Python's ast module.
    Enforces path traversal protection, symlink checks, file size caps, and error isolation.

    Returns:
        dict: {
            "files": { <rel_path>: file_index_dict, ... },
            "parse_errors": { <rel_path>: error_message, ... },
            "stats": {
                "total_requested": int,
                "parsed_count": int,
                "failed_count": int,
                "total_functions": int,
                "total_classes": int,
            }
        }
    """
    root = Path(project_path).resolve()
    if not root.is_dir():
        return {
            "files": {},
            "parse_errors": {"__project__": f"Project directory not found: {project_path}"},
            "stats": {
                "total_requested": len(python_files),
                "parsed_count": 0,
                "failed_count": 1,
                "total_functions": 0,
                "total_classes": 0,
            },
        }

    files_index: dict[str, Any] = {}
    parse_errors: dict[str, str] = {}
    seen_rel_paths: set[str] = set()

    for raw_path in python_files:
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue

        raw_clean = raw_path.strip().replace("\\", "/")

        # Security check: forbid absolute paths and '..' traversal BEFORE stripping
        if (
            raw_clean.startswith("/")
            or Path(raw_clean).is_absolute()
            or (len(raw_clean) > 1 and raw_clean[1] == ":")
            or any(part == ".." for part in Path(raw_clean).parts)
        ):
            parse_errors[raw_path] = "Security rejection: Path traversal or absolute path detected."
            continue

        norm_rel = raw_clean.lstrip("/")
        if not norm_rel:
            continue

        # Prevent duplicate parsing
        if norm_rel in seen_rel_paths:
            continue
        seen_rel_paths.add(norm_rel)

        p = Path(norm_rel)
        target = (root / p).resolve()

        # Security check: must remain inside project root
        if not target.is_relative_to(root):
            parse_errors[norm_rel] = "Security rejection: Resolved path escapes project root."
            continue

        # Check symlink target escapes
        unresolved_target = root / p
        if unresolved_target.is_symlink():
            real_target = unresolved_target.resolve()
            if not real_target.is_relative_to(root):
                parse_errors[norm_rel] = "Security rejection: Symlink points outside project root."
                continue

        if not target.exists():
            parse_errors[norm_rel] = "File not found on disk."
            continue

        if not target.is_file():
            parse_errors[norm_rel] = "Path is not a regular file."
            continue

        # Enforce max file size
        try:
            if target.stat().st_size > MAX_FILE_SIZE_BYTES:
                parse_errors[norm_rel] = f"File exceeds maximum allowed size ({MAX_FILE_SIZE_BYTES} bytes)."
                continue
        except OSError as exc:
            parse_errors[norm_rel] = f"Filesystem error checking file: {exc}"
            continue

        # Read content safely
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            parse_errors[norm_rel] = f"Read error: {exc}"
            continue

        # Parse AST with isolated error boundary
        try:
            file_meta = _parse_single_file(norm_rel, target, content)
            files_index[norm_rel] = file_meta
        except SyntaxError as exc:
            parse_errors[norm_rel] = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        except Exception as exc:
            parse_errors[norm_rel] = f"AST parse error: {exc}"

    # Compute aggregation stats
    total_funcs = sum(len(f["functions"]) + sum(len(c["methods"]) for c in f["classes"]) for f in files_index.values())
    total_cls = sum(len(f["classes"]) for f in files_index.values())

    return {
        "files": files_index,
        "parse_errors": parse_errors,
        "stats": {
            "total_requested": len(python_files),
            "parsed_count": len(files_index),
            "failed_count": len(parse_errors),
            "total_functions": total_funcs,
            "total_classes": total_cls,
        },
    }
