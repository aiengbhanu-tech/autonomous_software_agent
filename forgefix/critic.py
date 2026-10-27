from .types import TestResult


def review(public: TestResult, hidden: TestResult | None = None) -> dict:
    if not public.green:
        return {"decision": "revise", "reason": "Public tests failed or collected no passes.",
                "feedback": public.output[:16_000]}
    if hidden is not None and not hidden.green:
        return {"decision": "revise", "reason": "Independent hidden contract failed.",
                "feedback": "Hidden contract failed; reconsider boundaries and preserve stated behavior."}
    return {"decision": "accept", "reason": "All configured checks passed.", "feedback": ""}

