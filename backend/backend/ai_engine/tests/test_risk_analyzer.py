"""
Tests for ai_engine.risk_analyzer
===================================
All tests are purely in-process — no I/O, no external dependencies.
"""

import pytest

from ai_engine.risk_analyzer import evaluate_risk, _has_security_keyword


# ---------------------------------------------------------------------------
# _has_security_keyword helper
# ---------------------------------------------------------------------------

class TestHasSecurityKeyword:
    def test_auth_keyword(self):
        assert _has_security_keyword("Users must authenticate before accessing the API") is True

    def test_password_keyword(self):
        assert _has_security_keyword("Passwords must be hashed using bcrypt") is True

    def test_token_keyword(self):
        assert _has_security_keyword("JWT token must expire after 24 hours") is True

    def test_encryption_keyword(self):
        assert _has_security_keyword("Data must be encrypted at rest") is True

    def test_access_control_phrase(self):
        assert _has_security_keyword("The system must enforce access control on all endpoints") is True

    def test_rbac_keyword(self):
        assert _has_security_keyword("Implement RBAC for the admin panel") is True

    def test_no_security_keyword(self):
        assert _has_security_keyword("Users can upload files up to 50 MB") is False

    def test_no_security_generic_requirement(self):
        assert _has_security_keyword("The system must respond within 200ms") is False

    def test_case_insensitive(self):
        assert _has_security_keyword("LOGIN must be rate-limited") is True

    def test_2fa_keyword(self):
        assert _has_security_keyword("Support 2FA for all admin accounts") is True

    def test_mfa_keyword(self):
        assert _has_security_keyword("MFA is required for payment operations") is True

    def test_xss_keyword(self):
        assert _has_security_keyword("Sanitize inputs to prevent XSS attacks") is True


# ---------------------------------------------------------------------------
# evaluate_risk — missing status
# ---------------------------------------------------------------------------

class TestMissingStatus:
    def test_missing_security_is_critical(self):
        risk, reason = evaluate_risk(
            "Users must authenticate with a valid token",
            status="missing",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "critical"
        assert "security" in reason.lower() or "missing" in reason.lower()

    def test_missing_non_security_is_high(self):
        risk, reason = evaluate_risk(
            "Users can upload files up to 50 MB",
            status="missing",
            confidence=0.9,
            evidence=[],
            test_covered=False,
        )
        assert risk == "high"
        assert "missing" in reason.lower() or "no implementation" in reason.lower()

    def test_missing_with_high_confidence_still_high(self):
        """Confidence is irrelevant for missing status (non-security)."""
        risk, _ = evaluate_risk(
            "System must log all errors",
            status="missing",
            confidence=0.95,
            evidence=[{"file": "app.py", "line": 1}],
            test_covered=True,
        )
        assert risk == "high"

    def test_missing_password_keyword_critical(self):
        risk, _ = evaluate_risk(
            "Passwords must be stored hashed",
            status="missing",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "critical"

    def test_missing_login_keyword_critical(self):
        risk, _ = evaluate_risk(
            "Login must be rate-limited to 5 attempts",
            status="missing",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "critical"


# ---------------------------------------------------------------------------
# evaluate_risk — partially_implemented status
# ---------------------------------------------------------------------------

class TestPartiallyImplementedStatus:
    def test_partial_low_confidence_is_high(self):
        risk, reason = evaluate_risk(
            "Users can filter search results",
            status="partially_implemented",
            confidence=0.3,
            evidence=[],
            test_covered=False,
        )
        assert risk == "high"
        assert "low confidence" in reason.lower() or "partial" in reason.lower()

    def test_partial_confidence_exactly_05_is_medium(self):
        """Boundary: confidence == 0.5 is NOT < 0.5, so medium."""
        risk, _ = evaluate_risk(
            "Users can filter search results",
            status="partially_implemented",
            confidence=0.5,
            evidence=[],
            test_covered=False,
        )
        assert risk == "medium"

    def test_partial_high_confidence_is_medium(self):
        risk, reason = evaluate_risk(
            "API must return paginated responses",
            status="partially_implemented",
            confidence=0.8,
            evidence=[{"file": "api.py", "line": 10}],
            test_covered=True,
        )
        assert risk == "medium"
        assert "partial" in reason.lower()

    def test_partial_none_confidence_is_high(self):
        """None confidence defaults to 0.0 which is < 0.5."""
        risk, _ = evaluate_risk(
            "System must send email notifications",
            status="partially_implemented",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "high"

    def test_partial_security_still_follows_partial_rules(self):
        """Security escalation only applies to 'missing', not 'partially_implemented'."""
        risk, _ = evaluate_risk(
            "Authentication must use bcrypt",
            status="partially_implemented",
            confidence=0.7,
            evidence=[],
            test_covered=False,
        )
        assert risk == "medium"


# ---------------------------------------------------------------------------
# evaluate_risk — implemented status
# ---------------------------------------------------------------------------

class TestImplementedStatus:
    def test_implemented_no_tests_is_medium(self):
        risk, reason = evaluate_risk(
            "Users can upload files",
            status="implemented",
            confidence=0.95,
            evidence=[{"file": "upload.py", "line": 5}],
            test_covered=False,
        )
        assert risk == "medium"
        assert "test" in reason.lower()

    def test_implemented_with_tests_is_low(self):
        risk, reason = evaluate_risk(
            "Users can upload files",
            status="implemented",
            confidence=0.95,
            evidence=[{"file": "upload.py", "line": 5}],
            test_covered=True,
        )
        assert risk == "low"
        assert "implemented" in reason.lower() or "test" in reason.lower()

    def test_implemented_confidence_irrelevant_for_level(self):
        """Once implemented+tests, confidence value doesn't change the risk level."""
        risk, _ = evaluate_risk(
            "System stores logs",
            status="implemented",
            confidence=0.1,
            evidence=[],
            test_covered=True,
        )
        assert risk == "low"

    def test_implemented_none_confidence_no_tests(self):
        risk, _ = evaluate_risk(
            "System stores logs",
            status="implemented",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "medium"


# ---------------------------------------------------------------------------
# evaluate_risk — not_verified status
# ---------------------------------------------------------------------------

class TestNotVerifiedStatus:
    def test_not_verified_is_medium(self):
        risk, reason = evaluate_risk(
            "System handles concurrent requests",
            status="not_verified",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "medium"
        assert "verif" in reason.lower()

    def test_not_verified_with_evidence_still_medium(self):
        risk, _ = evaluate_risk(
            "System handles concurrent requests",
            status="not_verified",
            confidence=0.9,
            evidence=[{"file": "app.py", "line": 1}],
            test_covered=True,
        )
        assert risk == "medium"

    def test_not_verified_security_still_medium(self):
        """not_verified does NOT escalate to critical even with security keywords."""
        risk, _ = evaluate_risk(
            "Authentication tokens must be verified",
            status="not_verified",
            confidence=None,
            evidence=[],
            test_covered=False,
        )
        assert risk == "medium"


# ---------------------------------------------------------------------------
# evaluate_risk — return type contract
# ---------------------------------------------------------------------------

class TestReturnContract:
    VALID_RISK_LEVELS = {"critical", "high", "medium", "low"}
    STATUSES = ["implemented", "partially_implemented", "missing", "not_verified"]

    @pytest.mark.parametrize("status", STATUSES)
    def test_always_returns_two_strings(self, status):
        risk, reason = evaluate_risk(
            "Some requirement",
            status=status,
            confidence=0.5,
            evidence=[],
            test_covered=False,
        )
        assert isinstance(risk, str)
        assert isinstance(reason, str)
        assert risk in self.VALID_RISK_LEVELS
        assert len(reason) > 0

    @pytest.mark.parametrize("status", STATUSES)
    def test_empty_evidence_does_not_raise(self, status):
        """evaluate_risk must not raise for any valid status with empty evidence."""
        evaluate_risk("Req", status=status, confidence=None, evidence=[], test_covered=False)

    def test_unknown_status_returns_medium(self):
        """Unrecognised status values fall through to the conservative medium default."""
        risk, _ = evaluate_risk(
            "Some requirement",
            status="unknown_future_status",
            confidence=0.9,
            evidence=[],
            test_covered=True,
        )
        assert risk == "medium"

