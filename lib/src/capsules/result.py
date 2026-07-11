from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "error"
    subject: str = ""
    remediation: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ResultEnvelope(BaseModel):
    ok: bool
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    issues: list[Issue] = Field(default_factory=list)


def success(
    status: str,
    data: dict[str, Any] | None = None,
    issues: list[Issue] | None = None,
) -> ResultEnvelope:
    return ResultEnvelope(ok=True, status=status, data=data or {}, issues=issues or [])


def failure(
    status: str,
    issues: list[Issue],
    data: dict[str, Any] | None = None,
) -> ResultEnvelope:
    return ResultEnvelope(ok=False, status=status, data=data or {}, issues=issues)
