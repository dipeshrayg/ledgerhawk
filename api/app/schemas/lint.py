from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class LintSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LintFinding(BaseModel):
    code: str
    severity: LintSeverity
    message: str
    rule_key: str | None = None
    explanation: str
