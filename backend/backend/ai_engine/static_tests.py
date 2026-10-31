"""
SpecTrace Static Test Discovery
===============================
Deterministic, offline static test discovery engine that identifies existing Python
tests and correlates them with software requirements using conservative static signals.
Uploaded code is NEVER imported, executed, or passed to test runners (pytest/unittest).

Scoring Methodology
-------------------
Test relevance is calculated using an independent multi-signal probabilistic combination
formula that avoids linear saturation at 1.0 while preserving strict ranking granularity:

    Score = 1.0 - (1.0 - S_name) * (1.0 - S_symbol) * (1.0 - S_assertion) * (1.0 - S_doc)

Signal Weights:
  - S_name: Primary anchor based on function and class name tokens (0.35 - 0.60).
  - S_symbol: Referenced domain functions/classes called in body (0.30 - 0.55).
  - S_assertion: Relevant assertions testing the requirement context (0.15 - 0.30).
  - S_doc: Contextual docstring matches (0.10 - 0.20).

Generic Identifier Pruning:
  Generic test-harness variables ('response', 'status', 'code', 'result', etc.)
  cannot establish an association on their own. At least one domain-specific token
  is strictly required to trigger relevance scoring.
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any

from ai_engine.source_validator import validate_evidence_with_reasons

# Stop words to ignore during requirement & identifier tokenization
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "app", "application", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "check", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "must", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over",
    "own", "s", "same", "shall", "she", "should", "so", "some", "such", "system",
    "t", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours",
    "yourself", "yourselves", "able",
    # Test-generic words
    "test", "tests", "testing", "tested", "assert", "assertion", "assertions", "case", "cases",
}

# Generic test-variable identifiers that should not be treated as domain symbols
GENERIC_TEST_VARS = {
    "result", "results", "response", "res", "resp", "data", "val", "vals",
    "status", "code", "payload", "item", "items", "obj", "output", "client",
}

# Python built-in symbols to ignore in symbol reference matching
IGNORED_SYMBOLS = {
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict", "set",
    "tuple", "type", "isinstance", "issubclass", "super", "getattr", "setattr",
    "hasattr", "open", "enumerate", "zip", "map", "filter", "any", "all", "min",
    "max", "sum", "sorted", "reversed", "repr", "id", "hash", "input", "format",
    "self", "cls", "True", "False", "None", "Exception", "ValueError", "TypeError",
    *GENERIC_TEST_VARS,
}


def _stem(w: str) -> str:
    """Deterministic light suffix stemming for software terms."""
    w = w.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        return w[:-1]
    if w.endswith("ing") and len(w) > 4:
        return w[:-3]
    if w.endswith("ed") and len(w) > 3:
        return w[:-2]
    return w


def _split_identifier(name: str) -> list[str]:
    """Splits snake_case and camelCase identifiers into lower-cased subwords and stems."""
    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+", name)
    tokens: list[str] = []
    for p in parts:
        lower_p = p.lower()
        if len(lower_p) > 1 and lower_p not in STOP_WORDS:
            tokens.append(lower_p)
            stemmed = _stem(lower_p)
            if stemmed != lower_p and stemmed not in STOP_WORDS:
                tokens.append(stemmed)
    return tokens


def _tokenize_text(text: str) -> tuple[set[str], set[str]]:
    """
    Extracts tokens from text, returning:
        (domain_tokens, generic_tokens)
    """
    raw_words = re.findall(r"\b[A-Za-z0-9_]+\b", text)
    domain_tokens: list[str] = []
    generic_tokens: list[str] = []
    lower_words: list[str] = []

    for w in raw_words:
        lw = w.lower()
        lower_words.append(lw)
        stemmed = _stem(lw)

        if lw in GENERIC_TEST_VARS or stemmed in GENERIC_TEST_VARS:
            generic_tokens.append(lw)
            generic_tokens.append(stemmed)
            continue

        parts = _split_identifier(w)
        if parts:
            for p in parts:
                p_stem = _stem(p)
                if p in GENERIC_TEST_VARS or p_stem in GENERIC_TEST_VARS:
                    generic_tokens.append(p)
                else:
                    domain_tokens.append(p)
                    domain_tokens.append(p_stem)
        elif len(lw) > 1 and lw not in STOP_WORDS:
            domain_tokens.append(lw)
            if stemmed != lw and stemmed not in STOP_WORDS:
                domain_tokens.append(stemmed)

    # Detect common compound phrases (e.g. "log in" -> "login", "sign in" -> "signin")
    for i in range(len(lower_words) - 1):
        pair = f"{lower_words[i]}{lower_words[i+1]}"
        if pair in {"login", "signin", "signup", "logout", "signout", "passcode", "password"}:
            domain_tokens.append(pair)

    return (
        set(t for t in domain_tokens if t not in STOP_WORDS and t not in GENERIC_TEST_VARS),
        set(t for t in generic_tokens if t not in STOP_WORDS),
    )


def _is_test_file(rel_path: str) -> bool:
    """Checks if a relative path corresponds to a standard Python test file convention."""
    p = Path(rel_path)
    stem = p.stem.lower()
    return stem.startswith("test_") or stem.endswith("_test") or stem == "test"


def _generate_test_id(file_path: str, class_name: str | None, func_name: str, line: int) -> str:
    """Generates a stable, deterministic test identifier."""
    raw = f"{file_path}:{class_name or ''}:{func_name}:{line}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"test_{digest}"


class _TestFileVisitor(ast.NodeVisitor):
    """Safely extracts test candidates from a test file's AST."""

    def __init__(self, rel_path: str, lines: list[str]) -> None:
        self.rel_path = rel_path
        self.lines = lines
        self.candidates: list[dict[str, Any]] = []
        self.current_class: str | None = None
        self.current_class_bases: list[str] = []
        self.has_pytest_import = False
        self.has_unittest_import = False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "pytest":
                self.has_pytest_import = True
            elif alias.name == "unittest":
                self.has_unittest_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "pytest" or (node.module and node.module.startswith("pytest.")):
            self.has_pytest_import = True
        elif node.module == "unittest" or (node.module and node.module.startswith("unittest.")):
            self.has_unittest_import = True
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        old_class = self.current_class
        old_bases = self.current_class_bases

        self.current_class = node.name
        self.current_class_bases = []
        for b in node.bases:
            try:
                self.current_class_bases.append(ast.unparse(b))
            except Exception:
                if isinstance(b, ast.Name):
                    self.current_class_bases.append(b.id)

        self.generic_visit(node)

        self.current_class = old_class
        self.current_class_bases = old_bases

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._inspect_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._inspect_function(node, is_async=True)

    def _inspect_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        is_test_name = node.name.startswith("test_") or node.name.startswith("test")
        in_test_class = False
        if self.current_class:
            c_name = self.current_class.lower()
            in_test_class = (
                c_name.startswith("test")
                or c_name.endswith("test")
                or c_name.endswith("tests")
                or any("TestCase" in b for b in self.current_class_bases)
            )

        if not (is_test_name or (in_test_class and node.name.startswith("test"))):
            return

        assertions: list[str] = []
        referenced_symbols: list[str] = []
        has_unittest_asserts = False

        for sub in ast.walk(node):
            if isinstance(sub, ast.Assert):
                try:
                    expr = ast.unparse(sub).strip()
                    if expr:
                        assertions.append(expr)
                except Exception:
                    assertions.append("assert <expression>")
            elif isinstance(sub, ast.Call):
                name = self._resolve_call_name(sub.func)
                if name:
                    # Prune trivial HTTP test calls unless qualified with domain models
                    if name not in {"client.get", "client.post", "client.put", "client.delete", "self.client.get"}:
                        referenced_symbols.append(name)
                    if name.startswith("self.assert") or name.startswith("self.assertRaises"):
                        has_unittest_asserts = True
                        try:
                            assertions.append(ast.unparse(sub).strip())
                        except Exception:
                            assertions.append(f"{name}(...)")
            elif isinstance(sub, ast.Name):
                lower_id = sub.id.lower()
                # Exclude built-ins AND generic local test variables from bare symbol matching
                if (
                    sub.id not in IGNORED_SYMBOLS
                    and lower_id not in GENERIC_TEST_VARS
                    and not sub.id.startswith("__")
                ):
                    referenced_symbols.append(sub.id)

        decorators: list[str] = []
        is_parametrized = False
        for dec in node.decorator_list:
            try:
                dec_str = ast.unparse(dec).strip()
                decorators.append(dec_str)
                if "parametrize" in dec_str:
                    is_parametrized = True
            except Exception:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                    if "parametrize" in dec.id:
                        is_parametrized = True

        is_unittest_class = any("TestCase" in b for b in self.current_class_bases)
        if is_unittest_class or has_unittest_asserts or (self.has_unittest_import and not self.has_pytest_import):
            framework = "unittest"
        elif self.has_pytest_import or any("pytest" in d for d in decorators) or bool(assertions):
            framework = "pytest"
        else:
            framework = "unknown"

        start = node.lineno
        end = getattr(node, "end_lineno", start)
        snippet = "".join(self.lines[start - 1 : end]).strip() if self.lines else ""

        full_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
        test_id = _generate_test_id(self.rel_path, self.current_class, node.name, start)

        candidate = {
            "test_id": test_id,
            "name": full_name,
            "raw_name": node.name,
            "class_name": self.current_class,
            "file": self.rel_path,
            "line": start,
            "line_end": end,
            "snippet": snippet,
            "docstring": ast.get_docstring(node) or "",
            "framework": framework,
            "is_async": is_async,
            "assertions": assertions,
            "referenced_symbols": list(dict.fromkeys(referenced_symbols)),
            "decorators": decorators,
            "is_parametrized": is_parametrized,
        }
        self.candidates.append(candidate)

    @staticmethod
    def _resolve_call_name(func_node: ast.AST) -> str | None:
        try:
            return ast.unparse(func_node)
        except Exception:
            if isinstance(func_node, ast.Name):
                return func_node.id
            if isinstance(func_node, ast.Attribute):
                val = _TestFileVisitor._resolve_call_name(func_node.value)
                return f"{val}.{func_node.attr}" if val else func_node.attr
            return None


def _calculate_test_relevance(
    domain_tokens: set[str],
    generic_tokens: set[str],
    candidate: dict[str, Any],
) -> tuple[float, list[str]]:
    """
    Computes a non-saturating relevance score [0.0, 1.0] between requirement tokens
    and candidate test symbols/assertions.

    Rule: Matches require at least ONE domain token. Generic HTTP/test tokens alone
    cannot establish an association.
    """
    if not domain_tokens:
        return 0.0, []

    reasons: list[str] = []
    has_domain_anchor = False

    # 1. Identifier Tokens from test function name and class name
    name_tokens = set(_split_identifier(candidate["raw_name"]))
    if candidate.get("class_name"):
        name_tokens.update(_split_identifier(candidate["class_name"]))

    domain_name_matches = domain_tokens & name_tokens
    s_name = 0.0
    if domain_name_matches:
        has_domain_anchor = True
        reasons.append(f"Meaningful identifier match in test name: {', '.join(sorted(domain_name_matches))}")
        s_name = min(0.60, 0.35 + 0.15 * (len(domain_name_matches) - 1))

    # 2. Referenced Symbols Match (functions or classes called/instantiated)
    symbol_tokens: set[str] = set()
    for sym in candidate["referenced_symbols"]:
        symbol_tokens.update(_split_identifier(sym))

    domain_symbol_matches = domain_tokens & symbol_tokens
    s_symbol = 0.0
    if domain_symbol_matches:
        has_domain_anchor = True
        reasons.append(f"Referenced symbol match in test body: {', '.join(sorted(domain_symbol_matches))}")
        s_symbol = min(0.55, 0.30 + 0.15 * (len(domain_symbol_matches) - 1))

    # 3. Assertion Context Match
    assertion_text = " ".join(candidate["assertions"]).lower()
    ass_domain, _ = _tokenize_text(assertion_text)
    domain_assertion_matches = domain_tokens & ass_domain
    s_assertion = 0.0
    if domain_assertion_matches:
        has_domain_anchor = True
        reasons.append(f"Assertion context match: {', '.join(sorted(domain_assertion_matches))}")
        s_assertion = min(0.30, 0.15 + 0.10 * (len(domain_assertion_matches) - 1))

    # 4. Docstring Match
    s_doc = 0.0
    if candidate.get("docstring"):
        doc_domain, _ = _tokenize_text(candidate["docstring"])
        domain_doc_matches = domain_tokens & doc_domain
        if domain_doc_matches:
            has_domain_anchor = True
            reasons.append(f"Test docstring match: {', '.join(sorted(domain_doc_matches))}")
            s_doc = min(0.20, 0.10 + 0.05 * (len(domain_doc_matches) - 1))

    # Strict domain anchor requirement: generic words alone never qualify
    if not has_domain_anchor:
        return 0.0, []

    # Non-saturating probabilistic combination formula:
    # 1.0 - (1.0 - S_name) * (1.0 - S_symbol) * (1.0 - S_assertion) * (1.0 - S_doc)
    uncombined_prob = (1.0 - s_name) * (1.0 - s_symbol) * (1.0 - s_assertion) * (1.0 - s_doc)
    combined_score = round(1.0 - uncombined_prob, 2)

    return combined_score, reasons


def discover_static_tests(
    project_path: str,
    python_files: list[str],
    ast_index: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Discovers static Python tests and associates them with software requirements.
    Uploaded code is NEVER executed or imported.

    Args:
        project_path: Absolute or relative root of extracted project files.
        python_files: List of Python files relative to project_path.
        ast_index: Structural AST index produced by extract_ast_index().
        requirements: List of requirement dictionaries with 'id' and 'description'.

    Returns:
        Structured dictionary matching the required static test discovery contract.
    """
    root = Path(project_path).resolve()
    if not root.is_dir():
        return {
            "tests": [],
            "requirement_coverage": {
                r["id"]: {"test_covered": False, "test_evidence": [], "matches": []}
                for r in requirements
                if isinstance(r, dict) and "id" in r
            },
            "diagnostics": {
                "test_files_scanned": 0,
                "tests_discovered": 0,
                "requirements_with_test_candidates": 0,
                "invalid_evidence_discarded": 0,
                "parse_errors": {"__project__": f"Project directory not found: {project_path}"},
            },
        }

    # 1. Identify test files
    test_files_to_scan: list[str] = []
    seen_files: set[str] = set()

    for raw_f in python_files:
        if not isinstance(raw_f, str) or not raw_f.strip():
            continue

        raw_clean = raw_f.strip().replace("\\", "/")

        # Security check: forbid absolute paths and '..' traversal
        if (
            raw_clean.startswith("/")
            or Path(raw_clean).is_absolute()
            or (len(raw_clean) > 1 and raw_clean[1] == ":")
            or any(part == ".." for part in Path(raw_clean).parts)
        ):
            continue

        clean_f = raw_clean.lstrip("/")
        if clean_f in seen_files:
            continue
        seen_files.add(clean_f)

        if _is_test_file(clean_f):
            test_files_to_scan.append(clean_f)

    # 2. Extract test candidates
    discovered_tests: list[dict[str, Any]] = []
    parse_errors: dict[str, str] = {}

    for rel_file in test_files_to_scan:
        p = Path(rel_file)
        target = (root / p).resolve()

        if not target.is_relative_to(root):
            parse_errors[rel_file] = "Security rejection: Path escapes project root."
            continue

        unresolved_target = root / p
        if unresolved_target.is_symlink():
            real_target = unresolved_target.resolve()
            if not real_target.is_relative_to(root):
                parse_errors[rel_file] = "Security rejection: Symlink points outside project root."
                continue

        if not target.exists():
            parse_errors[rel_file] = "Test file not found on disk."
            continue

        if not target.is_file():
            parse_errors[rel_file] = "Path is not a regular file."
            continue

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)
            tree = ast.parse(content, filename=rel_file)
            visitor = _TestFileVisitor(rel_file, lines)
            visitor.visit(tree)
            discovered_tests.extend(visitor.candidates)
        except SyntaxError as exc:
            parse_errors[rel_file] = f"SyntaxError in test file: {exc.msg} (line {exc.lineno})"
        except Exception as exc:
            parse_errors[rel_file] = f"Error reading/parsing test file: {exc}"

    # Sort discovered tests deterministically
    discovered_tests.sort(key=lambda t: (t["file"], t["line"], t["name"]))

    # Public representation of tests
    public_tests: list[dict[str, Any]] = []
    for t in discovered_tests:
        public_tests.append({
            "test_id": t["test_id"],
            "name": t["name"],
            "file": t["file"],
            "line": t["line"],
            "line_end": t["line_end"],
            "snippet": t["snippet"],
            "docstring": t["docstring"],
            "framework": t["framework"],
            "is_async": t["is_async"],
            "assertions": t["assertions"],
            "referenced_symbols": t["referenced_symbols"],
            "decorators": t["decorators"],
            "is_parametrized": t["is_parametrized"],
        })

    # 3. Associate requirements to test candidates with strict evidence synchronization
    requirement_coverage: dict[str, Any] = {}
    invalid_evidence_count = 0
    requirements_with_candidates = 0

    MATCH_SCORE_THRESHOLD = 0.30

    for req in requirements:
        if not isinstance(req, dict) or "id" not in req:
            continue

        req_id = req["id"]
        req_desc = req.get("description", "")
        domain_tokens, generic_tokens = _tokenize_text(req_desc)

        candidate_matches: dict[str, dict[str, Any]] = {}
        raw_evidence_items: list[dict[str, Any]] = []

        for candidate in discovered_tests:
            score, reasons = _calculate_test_relevance(domain_tokens, generic_tokens, candidate)
            if score >= MATCH_SCORE_THRESHOLD and reasons:
                candidate_matches[candidate["test_id"]] = {
                    "test_id": candidate["test_id"],
                    "score": score,
                    "reasons": reasons,
                }
                raw_evidence_items.append({
                    "file": candidate["file"],
                    "line": candidate["line"],
                    "line_end": candidate["line_end"],
                    "function": candidate["name"],
                    "snippet": candidate["snippet"],
                    "description": f"Test '{candidate['name']}' ({candidate['framework']}) verifies requirement: {reasons[0]}.",
                    "_test_id": candidate["test_id"],  # Internal correlation token for validation sync
                })

        # Validate evidence bounds strictly through source_validator
        valid_evidence_raw, discarded = validate_evidence_with_reasons(raw_evidence_items, str(root))
        invalid_evidence_count += len(discarded)

        # Synchronize matches and evidence in deterministic candidate discovery order:
        # valid_evidence_raw preserves the input candidate discovery order.
        # Iterating directly over valid_evidence_raw guarantees 1:1 index alignment,
        # preserves candidate discovery order, and avoids relying on set iteration order.
        clean_valid_evidence: list[dict[str, Any]] = []
        synchronized_matches: list[dict[str, Any]] = []

        for ev in valid_evidence_raw:
            c_id = ev.pop("_test_id", None)
            if c_id and c_id in candidate_matches:
                clean_valid_evidence.append(ev)
                synchronized_matches.append(candidate_matches[c_id])

        has_coverage = len(clean_valid_evidence) > 0 and len(synchronized_matches) > 0
        if has_coverage:
            requirements_with_candidates += 1

        requirement_coverage[req_id] = {
            "test_covered": has_coverage,
            "test_evidence": clean_valid_evidence,
            "matches": synchronized_matches,
        }

    return {
        "tests": public_tests,
        "requirement_coverage": requirement_coverage,
        "diagnostics": {
            "test_files_scanned": len(test_files_to_scan),
            "tests_discovered": len(public_tests),
            "requirements_with_test_candidates": requirements_with_candidates,
            "invalid_evidence_discarded": invalid_evidence_count,
            "parse_errors": parse_errors,
        },
    }
