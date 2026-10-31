import os
from pathlib import Path

from ai_engine.ast_visitor import extract_ast_index
from ai_engine.source_validator import validate_evidence_bounds, validate_evidence_with_reasons


# 1. Function extraction
def test_function_extraction(tmp_path):
    code = (
        "def add(a, b=10, *args, **kwargs):\n"
        "    '''Adds numbers.'''\n"
        "    return a + b\n"
        "\n"
        "async def fetch_data(url: str):\n"
        "    return url\n"
    )
    (tmp_path / "math_ops.py").write_text(code, encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["math_ops.py"])

    assert "math_ops.py" in index["files"]
    funcs = index["files"]["math_ops.py"]["functions"]
    assert len(funcs) == 2

    f1 = funcs[0]
    assert f1["name"] == "add"
    assert "a" in f1["args"]
    assert "*args" in f1["args"]
    assert "**kwargs" in f1["args"]
    assert f1["docstring"] == "Adds numbers."
    assert f1["is_async"] is False
    assert f1["line"] == 1
    assert f1["line_end"] == 3

    f2 = funcs[1]
    assert f2["name"] == "fetch_data"
    assert f2["is_async"] is True


# 2. Class and method extraction
def test_class_and_method_extraction(tmp_path):
    code = (
        "class BaseController:\n"
        "    pass\n"
        "\n"
        "class UserController(BaseController):\n"
        "    '''User management.'''\n"
        "    def __init__(self, db):\n"
        "        self.db = db\n"
        "\n"
        "    def get_user(self, user_id):\n"
        "        return self.db.find(user_id)\n"
    )
    (tmp_path / "controllers.py").write_text(code, encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["controllers.py"])

    classes = index["files"]["controllers.py"]["classes"]
    assert len(classes) == 2

    c2 = classes[1]
    assert c2["name"] == "UserController"
    assert "BaseController" in c2["bases"]
    assert c2["docstring"] == "User management."
    assert len(c2["methods"]) == 2

    m2 = c2["methods"][1]
    assert m2["name"] == "get_user"
    assert m2["args"] == ["self", "user_id"]
    assert m2["line"] == 9
    assert m2["line_end"] == 10


# 3. Import extraction
def test_import_extraction(tmp_path):
    code = (
        "import os\n"
        "import sys as system\n"
        "from typing import Optional, List as MyList\n"
    )
    (tmp_path / "deps.py").write_text(code, encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["deps.py"])

    imports = index["files"]["deps.py"]["imports"]
    assert len(imports) == 4
    names = [i["name"] for i in imports]
    assert "os" in names
    assert "sys" in names
    assert "Optional" in names
    assert "List" in names


# 4. Function call extraction
def test_function_call_extraction(tmp_path):
    code = (
        "def run_job():\n"
        "    logger.info('starting')\n"
        "    calc(1, 2)\n"
        "    client.db.query('SELECT 1')\n"
    )
    (tmp_path / "job.py").write_text(code, encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["job.py"])

    func = index["files"]["job.py"]["functions"][0]
    call_names = func["calls"]
    assert "logger.info" in call_names
    assert "calc" in call_names
    assert "client.db.query" in call_names


# 5. Docstring extraction
def test_docstring_extraction(tmp_path):
    code = (
        "'''Module overview.'''\n"
        "class Model:\n"
        "    '''Class doc.'''\n"
        "    def save(self):\n"
        "        '''Method doc.'''\n"
        "        pass\n"
    )
    (tmp_path / "doc.py").write_text(code, encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["doc.py"])

    f = index["files"]["doc.py"]
    assert f["docstring"] == "Module overview."
    assert f["classes"][0]["docstring"] == "Class doc."
    assert f["classes"][0]["methods"][0]["docstring"] == "Method doc."


# 6. Correct line ranges
def test_correct_line_ranges(tmp_path):
    code = (
        "# line 1\n"
        "def compute():\n"  # line 2
        "    x = 10\n"       # line 3
        "    y = 20\n"       # line 4
        "    return x + y\n" # line 5
    )
    (tmp_path / "lines.py").write_text(code, encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["lines.py"])

    func = index["files"]["lines.py"]["functions"][0]
    assert func["line"] == 2
    assert func["line_end"] == 5
    assert func["snippet"].startswith("def compute():")
    assert func["snippet"].endswith("return x + y")


# 7. Syntax-error handling
def test_syntax_error_handling(tmp_path):
    (tmp_path / "valid.py").write_text("def ok(): pass\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    index = extract_ast_index(str(tmp_path), ["valid.py", "broken.py"])
    assert "valid.py" in index["files"]
    assert "broken.py" not in index["files"]
    assert "broken.py" in index["parse_errors"]
    assert "SyntaxError" in index["parse_errors"]["broken.py"]


# 8. Empty Python files
def test_empty_python_files(tmp_path):
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    (tmp_path / "comments.py").write_text("# only comments\n# here\n", encoding="utf-8")

    index = extract_ast_index(str(tmp_path), ["empty.py", "comments.py"])
    assert "empty.py" in index["files"]
    assert index["files"]["empty.py"]["total_lines"] == 0
    assert index["files"]["empty.py"]["functions"] == []
    assert index["files"]["comments.py"]["classes"] == []


# 9. Missing files
def test_missing_files(tmp_path):
    index = extract_ast_index(str(tmp_path), ["does_not_exist.py"])
    assert "does_not_exist.py" in index["parse_errors"]
    assert "not found" in index["parse_errors"]["does_not_exist.py"].lower()


# 10. Duplicate paths
def test_duplicate_paths(tmp_path):
    (tmp_path / "app.py").write_text("def start(): pass\n", encoding="utf-8")
    index = extract_ast_index(str(tmp_path), ["app.py", "app.py", "app.py"])
    assert len(index["files"]) == 1
    assert index["stats"]["parsed_count"] == 1


# 11. Path traversal rejection
def test_path_traversal_rejection(tmp_path):
    index = extract_ast_index(str(tmp_path), ["../outside.py", "sub/../../escape.py"])
    assert len(index["files"]) == 0
    assert len(index["parse_errors"]) == 2
    assert all("traversal" in err.lower() for err in index["parse_errors"].values())


# 12. Absolute path rejection
def test_absolute_path_rejection(tmp_path):
    index = extract_ast_index(str(tmp_path), ["/etc/passwd", "C:/Windows/system.py"])
    assert len(index["files"]) == 0
    assert len(index["parse_errors"]) >= 1
    assert all("absolute" in err.lower() or "traversal" in err.lower() for err in index["parse_errors"].values())


# 13. Symlink escape protection where supported
def test_symlink_escape_protection(tmp_path):
    outside = tmp_path.parent / "secret_outside.py"
    outside.write_text("SECRET = 123", encoding="utf-8")
    link = tmp_path / "sym_link.py"

    try:
        os.symlink(outside, link)
        symlink_supported = True
    except (OSError, NotImplementedError):
        symlink_supported = False

    if symlink_supported:
        index = extract_ast_index(str(tmp_path), ["sym_link.py"])
        assert "sym_link.py" not in index["files"]
        assert "sym_link.py" in index["parse_errors"]
        assert "symlink" in index["parse_errors"]["sym_link.py"].lower()


# 14. Evidence with valid line ranges
def test_evidence_with_valid_line_ranges(tmp_path):
    code = (
        "def authenticate(u, p):\n"
        "    return True\n"
    )
    (tmp_path / "auth.py").write_text(code, encoding="utf-8")

    evidence = [{
        "file": "auth.py",
        "line": 1,
        "line_end": 2,
        "function": "authenticate",
        "snippet": "def authenticate(u, p):\n    return True",
        "description": "auth function found",
    }]

    valid = validate_evidence_bounds(evidence, str(tmp_path))
    assert len(valid) == 1
    assert valid[0]["file"] == "auth.py"
    assert valid[0]["line"] == 1
    assert valid[0]["line_end"] == 2


# 15. Evidence with invalid line ranges
def test_evidence_with_invalid_line_ranges(tmp_path):
    (tmp_path / "short.py").write_text("x = 1\ny = 2\n", encoding="utf-8")

    evidence = [
        {"file": "short.py", "line": 10, "line_end": 20},  # line beyond file
        {"file": "short.py", "line": 2, "line_end": 1},   # line_end < line
        {"file": "short.py", "line": -1, "line_end": 1},  # negative line
    ]

    valid, discarded = validate_evidence_with_reasons(evidence, str(tmp_path))
    assert len(valid) == 0
    assert len(discarded) == 3


# 16. Evidence referencing nonexistent files
def test_evidence_referencing_nonexistent_files(tmp_path):
    evidence = [
        {"file": "ghost.py", "line": 1, "line_end": 1},
        {"file": "../escape.py", "line": 1, "line_end": 1},
    ]
    valid, discarded = validate_evidence_with_reasons(evidence, str(tmp_path))
    assert len(valid) == 0
    assert len(discarded) == 2


# 17. Evidence with incorrect snippets
def test_evidence_with_incorrect_snippets(tmp_path):
    code = (
        "def compute_total(items):\n"
        "    return sum(items)\n"
    )
    (tmp_path / "calc.py").write_text(code, encoding="utf-8")

    evidence = [{
        "file": "calc.py",
        "line": 1,
        "line_end": 2,
        "snippet": "def delete_database(): drop_all()",  # totally mismatching snippet
    }]

    valid, discarded = validate_evidence_with_reasons(evidence, str(tmp_path))
    assert len(valid) == 0
    assert len(discarded) == 1
    assert "snippet" in discarded[0]["reason"].lower()


# 18. Multiple files with cross-file symbols
def test_multiple_files_with_cross_file_symbols(tmp_path):
    (tmp_path / "models.py").write_text("class User:\n    pass\n", encoding="utf-8")
    (tmp_path / "services.py").write_text("from models import User\ndef create_user(): return User()\n", encoding="utf-8")

    index = extract_ast_index(str(tmp_path), ["models.py", "services.py"])
    assert index["stats"]["parsed_count"] == 2
    assert index["stats"]["failed_count"] == 0
    assert index["stats"]["total_classes"] == 1
    assert index["stats"]["total_functions"] == 1
    assert "models.py" in index["files"]
    assert "services.py" in index["files"]

