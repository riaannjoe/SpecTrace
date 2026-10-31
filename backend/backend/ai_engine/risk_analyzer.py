"""
SpecTrace Risk Analyser
=======================
Pure rule-based, offline risk classification for software requirements.
No external dependencies, no network calls.

Rules (first match wins):
  1. status == "missing"  AND  security keyword in description  => critical
  2. status == "missing"                                         => high
  3. status == "partially_implemented" AND confidence < 0.5     => high
  4. status == "partially_implemented"                           => medium
  5. status == "implemented" AND NOT test_covered                => medium
  6. status == "implemented" AND test_covered                    => low
  7. status == "not_verified"                                    => medium

Constraint: "missing" requires positive evidence of absence supplied by the caller.
This module does NOT infer "missing" from absent keywords; it only classifies a
status value that was already determined by the semantic/static pipeline.
"""

from __future__ import annotations

# Conservative set of security-domain anchors.
# A requirement is only escalated to "critical" when its status is already
# "missing" AND the description contains at least one of these terms.
_SECURITY_KEYWORDS: frozenset[str] = frozenset({
    "auth",
    "authentication",
    "authorisation",
    "authorization",
    "login",
    "logout",
    "password",
    "credential",
    "credentials",
    "token",
    "jwt",
    "oauth",
    "session",
    "encrypt",
    "encryption",
    "decrypt",
    "decryption",
    "hash",
    "hashing",
    "secret",
    "api key",
    "apikey",
    "permission",
    "permissions",
    "role",
    "roles",
    "access control",
    "rbac",
    "acl",
    "privilege",
    "privileges",
    "sanitise",
    "sanitize",
    "injection",
    "xss",
    "csrf",
    "tls",
    "ssl",
    "https",
    "certificate",
    "signature",
    "signing",
    "verify",
    "verification",
    "two-factor",
    "2fa",
    "mfa",
    "multi-factor",
})


def _has_security_keyword(description: str) -> bool:
    """Return True if the description contains at least one security anchor term."""
    lower = description.lower()
    return any(kw in lower for kw in _SECURITY_KEYWORDS)


def evaluate_risk(
    req_description: str,
    status: str,
    confidence: float | None,
    evidence: list[dict],
    test_covered: bool,
) -> tuple[str, str]:
    """
    Classify the risk level for a single requirement result.

    Parameters
    ----------
    req_description : str
        The original requirement description (used for security keyword check).
    status : str
        One of: "implemented" | "partially_implemented" | "missing" | "not_verified"
    confidence : float | None
        Semantic confidence score [0.0, 1.0], or None when unavailable.
    evidence : list[dict]
        Implementation evidence items (used only for context; classification is
        by status + confidence).
    test_covered : bool
        Whether a static test candidate was discovered for this requirement.

    Returns
    -------
    (risk_level, risk_reason) : tuple[str, str]
        risk_level: "critical" | "high" | "medium" | "low"
        risk_reason: human-readable rationale string
    """
    conf = confidence if confidence is not None else 0.0

    if status == "missing":
        if _has_security_keyword(req_description):
            return (
                "critical",
                "Requirement is missing and involves a security-sensitive concern.",
            )
        return "high", "Requirement has no implementation evidence."

    if status == "partially_implemented":
        if conf < 0.5:
            return (
                "high",
                "Requirement is only partially implemented with low confidence.",
            )
        return "medium", "Requirement is only partially implemented."

    if status == "implemented":
        if not test_covered:
            return (
                "medium",
                "Requirement is implemented but no test coverage was discovered.",
            )
        return "low", "Requirement is implemented and test coverage was found."

    # status == "not_verified" (or any unexpected value — be conservative)
    return "medium", "Requirement implementation could not be verified."

