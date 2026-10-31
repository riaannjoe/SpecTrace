import os
from pathlib import Path

from ai_engine.ast_visitor import extract_ast_index
from ai_engine.static_tests import discover_static_tests


# 1. pytest-style test functions
def test_pytest_style_functions(tmp_path):
    code = (
        "import pytest\n"
        "\n"
        "def test_simple_addition():\n"
        "    '''Verify addition.'''\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "def helper_not_a_test():\n"
        "    return 42\n"
    )
    (tmp_path / "test_math.py").write_text(code, encoding="utf-8")
    files = ["test_math.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    res = discover_static_tests(str(tmp_path), files, ast_idx, [])
    assert len(res["tests"]) == 1
    t = res["tests"][0]
    assert t["name"] == "test_simple_addition"
    assert t["framework"] == "pytest"
    assert t["is_async"] is False
    assert len(t["assertions"]) == 1
    assert "assert 1 + 1 == 2" in t["assertions"][0]


# 2. unittest-style test classes and methods
def test_unittest_style_classes_and_methods(tmp_path):
    code = (
        "import unittest\n"
        "\n"
        "class TestUserAuth(unittest.TestCase):\n"
        "    def test_login_success(self):\n"
        "        user = create_user('admin')\n"
        "        self.assertEqual(user.status, 'active')\n"
        "        self.assertTrue(user.is_authenticated)\n"
    )
    (tmp_path / "test_auth.py").write_text(code, encoding="utf-8")
    files = ["test_auth.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    res = discover_static_tests(str(tmp_path), files, ast_idx, [])
    assert len(res["tests"]) == 1
    t = res["tests"][0]
    assert t["name"] == "TestUserAuth.test_login_success"
    assert t["framework"] == "unittest"
    assert "create_user" in t["referenced_symbols"]
    assert len(t["assertions"]) == 2


# 3. Async test functions
def test_async_test_functions(tmp_path):
    code = (
        "import pytest\n"
        "\n"
        "async def test_async_fetch():\n"
        "    resp = await client.get('/api')\n"
        "    assert resp.status_code == 200\n"
    )
    (tmp_path / "test_api.py").write_text(code, encoding="utf-8")
    files = ["test_api.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    res = discover_static_tests(str(tmp_path), files, ast_idx, [])
    assert len(res["tests"]) == 1
    assert res["tests"][0]["is_async"] is True


# 4. Parametrized test decorators
def test_parametrized_test_decorators(tmp_path):
    code = (
        "import pytest\n"
        "\n"
        "@pytest.mark.parametrize('email,valid', [('a@b.com', True), ('bad', False)])\n"
        "def test_email_validation(email, valid):\n"
        "    assert validate_email(email) == valid\n"
    )
    (tmp_path / "test_validation.py").write_text(code, encoding="utf-8")
    files = ["test_validation.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    res = discover_static_tests(str(tmp_path), files, ast_idx, [])
    assert len(res["tests"]) == 1
    t = res["tests"][0]
    assert t["is_parametrized"] is True
    assert any("parametrize" in d for d in t["decorators"])


# 5. Assertions and referenced symbol extraction
def test_assertions_and_symbols_extraction(tmp_path):
    code = (
        "def test_order_checkout():\n"
        "    cart = Cart()\n"
        "    cart.add_item('book')\n"
        "    order = checkout_cart(cart)\n"
        "    assert order.total > 0\n"
        "    assert order.is_paid is True\n"
    )
    (tmp_path / "test_checkout.py").write_text(code, encoding="utf-8")
    files = ["test_checkout.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    res = discover_static_tests(str(tmp_path), files, ast_idx, [])
    t = res["tests"][0]
    assert "Cart" in t["referenced_symbols"]
    assert "checkout_cart" in t["referenced_symbols"]
    assert len(t["assertions"]) == 2


# 6. Meaningful requirement-to-test matches
def test_meaningful_requirement_matches(tmp_path):
    code = (
        "def test_user_login_with_password():\n"
        "    '''Check user authentication with credentials.'''\n"
        "    result = authenticate_user('user@example.com', 'secret')\n"
        "    assert result.is_valid is True\n"
    )
    (tmp_path / "test_auth.py").write_text(code, encoding="utf-8")
    files = ["test_auth.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_login_001", "description": "Users must be able to log in with email and password"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_login_001"]
    assert cov["test_covered"] is True
    assert len(cov["matches"]) == 1
    match = cov["matches"][0]
    assert match["score"] >= 0.4
    assert any("identifier" in r.lower() or "symbol" in r.lower() for r in match["reasons"])
    assert len(cov["test_evidence"]) == 1
    assert cov["test_evidence"][0]["file"] == "test_auth.py"


# 7. Unrelated tests not being associated
def test_unrelated_tests_not_associated(tmp_path):
    code = (
        "def test_export_data_to_csv():\n"
        "    result = export_csv(['a', 'b'])\n"
        "    assert len(result) > 0\n"
    )
    (tmp_path / "test_export.py").write_text(code, encoding="utf-8")
    files = ["test_export.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_pw_hash", "description": "Passwords must be hashed using bcrypt or argon2"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_pw_hash"]
    assert cov["test_covered"] is False
    assert cov["matches"] == []
    assert cov["test_evidence"] == []


# 8. Multiple requirements with different test associations
def test_multiple_requirements_distinct_associations(tmp_path):
    auth_code = (
        "def test_login():\n"
        "    assert verify_password('pass', 'hash') is True\n"
    )
    billing_code = (
        "def test_process_invoice_payment():\n"
        "    assert charge_credit_card(100) is True\n"
    )
    (tmp_path / "test_auth.py").write_text(auth_code, encoding="utf-8")
    (tmp_path / "test_billing.py").write_text(billing_code, encoding="utf-8")

    files = ["test_auth.py", "test_billing.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [
        {"id": "req_auth", "description": "Verify user password on login"},
        {"id": "req_billing", "description": "Process customer invoice payment via credit card"},
    ]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    auth_cov = res["requirement_coverage"]["req_auth"]
    billing_cov = res["requirement_coverage"]["req_billing"]

    assert auth_cov["test_covered"] is True
    assert billing_cov["test_covered"] is True
    assert auth_cov["test_evidence"][0]["file"] == "test_auth.py"
    assert billing_cov["test_evidence"][0]["file"] == "test_billing.py"


# 9. Requirements with no test candidates
def test_requirement_with_no_test_candidates(tmp_path):
    code = "def test_something_else(): assert 1 == 1\n"
    (tmp_path / "test_misc.py").write_text(code, encoding="utf-8")
    files = ["test_misc.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_empty", "description": "High performance real-time 3D physics rendering"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_empty"]
    assert cov["test_covered"] is False
    assert cov["matches"] == []
    assert cov["test_evidence"] == []


# 10. Exact preservation of requirement IDs
def test_exact_preservation_of_requirement_ids(tmp_path):
    req_ids = ["req_custom_1", "requirement_9f8e7d6c5b4a", "custom-id-xyz"]
    reqs = [{"id": rid, "description": "Sample description"} for rid in req_ids]

    res = discover_static_tests(str(tmp_path), [], {}, reqs)
    assert set(res["requirement_coverage"].keys()) == set(req_ids)


# 11. Evidence line and snippet validation
def test_evidence_validation_in_test_discovery(tmp_path):
    code = (
        "# Header\n"
        "def test_token_expiration():\n"
        "    token = generate_token()\n"
        "    assert is_expired(token) is False\n"
    )
    (tmp_path / "test_tokens.py").write_text(code, encoding="utf-8")
    files = ["test_tokens.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_token", "description": "Generate token with expiration check"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    evidence = res["requirement_coverage"]["req_token"]["test_evidence"]
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev["file"] == "test_tokens.py"
    assert ev["line"] == 2
    assert ev["line_end"] == 4
    assert "def test_token_expiration():" in ev["snippet"]


# 12. Malformed test files
def test_malformed_test_files_handled_gracefully(tmp_path):
    (tmp_path / "test_broken.py").write_text("def test_broken(:\n", encoding="utf-8")
    (tmp_path / "test_valid.py").write_text("def test_valid(): assert True\n", encoding="utf-8")

    files = ["test_broken.py", "test_valid.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    res = discover_static_tests(str(tmp_path), files, ast_idx, [])
    assert len(res["tests"]) == 1
    assert res["tests"][0]["name"] == "test_valid"
    assert "test_broken.py" in res["diagnostics"]["parse_errors"]


# 13. Missing files
def test_missing_files_handled_gracefully(tmp_path):
    files = ["test_ghost.py"]
    res = discover_static_tests(str(tmp_path), files, {}, [])
    assert len(res["tests"]) == 0
    assert "test_ghost.py" in res["diagnostics"]["parse_errors"]


# 14. Duplicate input paths
def test_duplicate_input_paths(tmp_path):
    (tmp_path / "test_sample.py").write_text("def test_sample(): assert 1 == 1\n", encoding="utf-8")
    files = ["test_sample.py", "test_sample.py", "test_sample.py"]

    res = discover_static_tests(str(tmp_path), files, {}, [])
    assert len(res["tests"]) == 1
    assert res["diagnostics"]["test_files_scanned"] == 1


# 15. Path traversal and absolute path rejection
def test_path_traversal_and_absolute_rejection(tmp_path):
    files = ["../escape_test.py", "C:/Windows/test.py", "/etc/test_foo.py"]
    res = discover_static_tests(str(tmp_path), files, {}, [])
    assert len(res["tests"]) == 0


# 16. Symlink escape protection
def test_symlink_escape_protection_static_tests(tmp_path):
    outside = tmp_path.parent / "test_secret_outside.py"
    outside.write_text("def test_outside(): assert True\n", encoding="utf-8")
    link = tmp_path / "test_symlink.py"

    try:
        os.symlink(outside, link)
        supported = True
    except (OSError, NotImplementedError):
        supported = False

    if supported:
        files = ["test_symlink.py"]
        res = discover_static_tests(str(tmp_path), files, {}, [])
        assert len(res["tests"]) == 0


# 17. Deterministic test IDs and output
def test_deterministic_output(tmp_path):
    code = (
        "def test_first(): assert 1 == 1\n"
        "def test_second(): assert 2 == 2\n"
    )
    (tmp_path / "test_det.py").write_text(code, encoding="utf-8")
    files = ["test_det.py"]

    res1 = discover_static_tests(str(tmp_path), files, {}, [])
    res2 = discover_static_tests(str(tmp_path), files, {}, [])

    assert res1["tests"] == res2["tests"]
    assert res1["tests"][0]["test_id"] == res2["tests"][0]["test_id"]


# 18. No execution or importing of analyzed code
def test_no_code_execution(tmp_path):
    code = (
        "import sys\n"
        "raise RuntimeError('CRITICAL: Uploaded code was executed!')\n"
        "def test_dummy(): pass\n"
    )
    (tmp_path / "test_dangerous.py").write_text(code, encoding="utf-8")
    files = ["test_dangerous.py"]

    res = discover_static_tests(str(tmp_path), files, {}, [])
    assert len(res["tests"]) == 1
    assert res["tests"][0]["name"] == "test_dummy"


# =========================================================================
# Phase 3.1 Targeted Calibration & Regression Tests
# =========================================================================

# 19. Generic HTTP/test vocabulary should not produce false positive matches
def test_generic_http_test_vocabulary_false_positives(tmp_path):
    # Test only uses generic HTTP/test harness vocabulary (resp, status_code, payload)
    code = (
        "def test_get_resource():\n"
        "    resp = client.get('/items')\n"
        "    assert resp.status_code == 200\n"
        "    payload = resp.json()\n"
        "    assert len(payload) > 0\n"
    )
    (tmp_path / "test_endpoint.py").write_text(code, encoding="utf-8")
    files = ["test_endpoint.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    # Requirement sharing only generic test/HTTP words without domain anchor
    reqs = [{"id": "req_status_payload", "description": "Services must return response payload with correct status code"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_status_payload"]
    assert cov["test_covered"] is False
    assert cov["matches"] == []
    assert cov["test_evidence"] == []


# 20. Domain word with generic token correctly matches
def test_domain_with_generic_token_preserves_match(tmp_path):
    # Payment is a domain anchor, combined with generic status
    code = (
        "def test_payment_status():\n"
        "    payment = create_payment()\n"
        "    assert payment.status == 'completed'\n"
    )
    (tmp_path / "test_payment.py").write_text(code, encoding="utf-8")
    files = ["test_payment.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_pay_status", "description": "Payment status must be updated on checkout"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_pay_status"]
    assert cov["test_covered"] is True
    assert len(cov["matches"]) == 1
    assert any("payment" in r.lower() for r in cov["matches"][0]["reasons"])


# 21. Synchronize matches with validated evidence (discarded evidence removes match)
def test_evidence_match_synchronization(tmp_path, monkeypatch):
    import ai_engine.static_tests as st_mod

    code = (
        "def test_invoice_one():\n"
        "    assert generate_invoice() is not None\n"
        "\n"
        "def test_invoice_two():\n"
        "    assert cancel_invoice() is True\n"
    )
    (tmp_path / "test_invoices.py").write_text(code, encoding="utf-8")
    files = ["test_invoices.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_inv", "description": "Generate and cancel invoice records"}]

    # Wrap validate_evidence_with_reasons to simulate rejection of test_invoice_two
    real_validate = st_mod.validate_evidence_with_reasons

    def mock_validate(evidence_list, project_path):
        valid, discarded = real_validate(evidence_list, project_path)
        # Discard any evidence corresponding to test_invoice_two
        surviving = [ev for ev in valid if ev["function"] != "test_invoice_two"]
        rejected = [ev for ev in valid if ev["function"] == "test_invoice_two"]
        return surviving, discarded + [{"evidence": ev, "reason": "Simulated rejection"} for ev in rejected]

    monkeypatch.setattr(st_mod, "validate_evidence_with_reasons", mock_validate)

    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)
    cov = res["requirement_coverage"]["req_inv"]

    # Only test_invoice_one should remain in both matches and test_evidence
    assert len(cov["test_evidence"]) == 1
    assert len(cov["matches"]) == 1
    assert cov["test_evidence"][0]["function"] == "test_invoice_one"
    assert cov["matches"][0]["test_id"] == [t["test_id"] for t in res["tests"] if t["name"] == "test_invoice_one"][0]
    assert cov["test_covered"] is True
    assert res["diagnostics"]["invalid_evidence_discarded"] == 1


# 22. Score calibration: distinct ordering and no premature saturation
def test_scoring_calibration_and_ordering(tmp_path):
    # Candidate 1: Weak match (name token only: 'refund')
    c1 = (
        "def test_refund():\n"
        "    pass\n"
    )
    # Candidate 2: Moderate match (name + symbol called)
    c2 = (
        "def test_refund_transaction():\n"
        "    process_refund(100)\n"
    )
    # Candidate 3: Strong match (name + symbol + assertion + docstring)
    c3 = (
        "def test_process_refund_flow():\n"
        "    '''Verify customer refund workflow.'''\n"
        "    result = process_refund(50)\n"
        "    assert result.refund_issued is True\n"
    )
    (tmp_path / "test_weak.py").write_text(c1, encoding="utf-8")
    (tmp_path / "test_mod.py").write_text(c2, encoding="utf-8")
    (tmp_path / "test_strong.py").write_text(c3, encoding="utf-8")
    files = ["test_weak.py", "test_mod.py", "test_strong.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_refund", "description": "Process customer refund transaction"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_refund"]
    matches_by_id = {m["test_id"]: m["score"] for m in cov["matches"]}

    tests_by_name = {t["name"]: t["test_id"] for t in res["tests"]}
    weak_score = matches_by_id[tests_by_name["test_refund"]]
    mod_score = matches_by_id[tests_by_name["test_refund_transaction"]]
    strong_score = matches_by_id[tests_by_name["test_process_refund_flow"]]

    # Assert strict ordering and no premature 1.0 saturation
    assert 0.30 <= weak_score < mod_score < strong_score < 1.0
    assert strong_score <= 0.90


# =========================================================================
# Phase 3.2 Deterministic Output Finalization Tests
# =========================================================================

# 23. Multiple valid candidates preserve original discovery order
def test_multiple_candidates_preserve_discovery_order(tmp_path):
    code = (
        "def test_order_alpha():\n"
        "    assert process_order() is True\n"
        "\n"
        "def test_order_beta():\n"
        "    assert process_order() is True\n"
        "\n"
        "def test_order_gamma():\n"
        "    assert process_order() is True\n"
    )
    (tmp_path / "test_orders.py").write_text(code, encoding="utf-8")
    files = ["test_orders.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)

    reqs = [{"id": "req_order", "description": "Process customer order transaction"}]
    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    cov = res["requirement_coverage"]["req_order"]
    assert len(cov["matches"]) == 3
    assert len(cov["test_evidence"]) == 3

    # Check that matches and evidence strictly preserve the discovery order (line 1, 4, 7)
    expected_order = ["test_order_alpha", "test_order_beta", "test_order_gamma"]
    observed_ev_order = [ev["function"] for ev in cov["test_evidence"]]
    assert observed_ev_order == expected_order

    # Check 1:1 correspondence between matches and evidence
    test_lookup = {t["name"]: t["test_id"] for t in res["tests"]}
    assert [m["test_id"] for m in cov["matches"]] == [test_lookup[name] for name in expected_order]


# 24. Repeated calls with identical inputs produce identical ordered outputs
def test_repeated_calls_produce_identical_ordered_outputs(tmp_path):
    code = (
        "def test_step_1(): assert run_step(1) is True\n"
        "def test_step_2(): assert run_step(2) is True\n"
        "def test_step_3(): assert run_step(3) is True\n"
    )
    (tmp_path / "test_steps.py").write_text(code, encoding="utf-8")
    files = ["test_steps.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)
    reqs = [{"id": "req_step", "description": "Execute run step pipeline"}]

    res1 = discover_static_tests(str(tmp_path), files, ast_idx, reqs)
    res2 = discover_static_tests(str(tmp_path), files, ast_idx, reqs)

    assert res1["tests"] == res2["tests"]
    assert res1["requirement_coverage"] == res2["requirement_coverage"]
    assert res1 == res2


# 25. Invalid evidence removes the candidate without disturbing remaining candidates' order
def test_invalid_evidence_removes_candidate_preserving_remaining_order(tmp_path, monkeypatch):
    import ai_engine.static_tests as st_mod

    code = (
        "def test_action_a(): assert do_action('a') is True\n"
        "def test_action_b(): assert do_action('b') is True\n"
        "def test_action_c(): assert do_action('c') is True\n"
    )
    (tmp_path / "test_actions.py").write_text(code, encoding="utf-8")
    files = ["test_actions.py"]
    ast_idx = extract_ast_index(str(tmp_path), files)
    reqs = [{"id": "req_action", "description": "Execute do action requests"}]

    real_validate = st_mod.validate_evidence_with_reasons

    # Simulate invalid evidence specifically for the middle candidate 'test_action_b'
    def mock_validate(evidence_list, project_path):
        valid, discarded = real_validate(evidence_list, project_path)
        surviving = [ev for ev in valid if ev["function"] != "test_action_b"]
        rejected = [ev for ev in valid if ev["function"] == "test_action_b"]
        return surviving, discarded + [{"evidence": ev, "reason": "Simulated rejection of B"} for ev in rejected]

    monkeypatch.setattr(st_mod, "validate_evidence_with_reasons", mock_validate)

    res = discover_static_tests(str(tmp_path), files, ast_idx, reqs)
    cov = res["requirement_coverage"]["req_action"]

    # Only A and C remain, in that exact original discovery order
    assert len(cov["test_evidence"]) == 2
    assert len(cov["matches"]) == 2
    assert cov["test_evidence"][0]["function"] == "test_action_a"
    assert cov["test_evidence"][1]["function"] == "test_action_c"

    test_lookup = {t["name"]: t["test_id"] for t in res["tests"]}
    assert cov["matches"][0]["test_id"] == test_lookup["test_action_a"]
    assert cov["matches"][1]["test_id"] == test_lookup["test_action_c"]
    assert res["diagnostics"]["invalid_evidence_discarded"] == 1


# 26. Test IDs remain strictly deterministic
def test_test_ids_strict_determinism(tmp_path):
    from ai_engine.static_tests import _generate_test_id

    id_1a = _generate_test_id("tests/test_x.py", "TestClass", "test_foo", 42)
    id_1b = _generate_test_id("tests/test_x.py", "TestClass", "test_foo", 42)
    assert id_1a == id_1b
    assert id_1a.startswith("test_")
    assert len(id_1a) == 17  # 'test_' (5) + 12 hex = 17 chars

