"""
*** MOCK ANALYSIS ADAPTER - NOT A REAL ANALYSIS ***

Exists only so the whole upload -> requirements -> analyze -> results flow (and the React
dashboard) can be tested before the real AST engine is ready.

It deliberately does NOT guess implemented/missing. Every requirement is "not_verified",
every result is flagged is_mock=true, and the explanation says so.
"""


def analyze(request: dict) -> dict:
    file_count = len(request["python_files"])
    return {
        "engine_name": "MOCK ADAPTER (placeholder - no real analysis performed)",
        "is_mock": True,
        "results": [
            {
                "requirement_id": req["id"],
                "status": "not_verified",
                "evidence": [],
                "test_status": "not_run",
                "explanation": (
                    f"MOCK RESULT: the real analysis engine is not connected. "
                    f"{file_count} Python file(s) were received but NOT analysed."
                ),
            }
            for req in request["requirements"]
        ],
    }
