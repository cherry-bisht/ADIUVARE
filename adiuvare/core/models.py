from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class RequestContext:
    identity: str
    payload: str | None
    url: str
    method: str
    headers: dict[str, str]
    ip: str
    endpoint: str
    sensitivity: Literal["public", "internal", "critical"] = "internal"


@dataclass
class SignalResult:
    score: float
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)
    exception: Exception | None = None

