from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TestResult:
    status: str
    passed: int = 0
    failed: int = 0
    output: str = ""
    duration_s: float = 0.0
    backend: str = ""

    @property
    def green(self) -> bool:
        return self.status == "passed" and self.passed > 0 and self.failed == 0


@dataclass
class Edit:
    path: str
    before_sha256: str
    content: str


@dataclass
class Proposal:
    hypothesis: str
    explanation: str
    edits: list[Edit]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    complete: bool = True
    input_rate: float | None = None
    output_rate: float | None = None

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost(self) -> float | None:
        if not self.complete or self.input_rate is None or self.output_rate is None:
            return None
        return (self.input_tokens * self.input_rate + self.output_tokens * self.output_rate) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "total_tokens": self.tokens, "cost_usd": self.cost}

