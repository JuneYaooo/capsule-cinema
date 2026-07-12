from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .result import Issue, ResultEnvelope, failure, success


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized


class ArtifactEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    reference: str
    description: str = ""

    _id = field_validator("id")(_text)
    _reference = field_validator("reference")(_text)


class EffectCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    passed: bool
    severity: Literal["blocker", "warning", "info"]
    message: str
    evidence_refs: list[str] = Field(default_factory=list)

    _id = field_validator("id")(_text)
    _message = field_validator("message")(_text)

    @field_validator("evidence_refs")
    @classmethod
    def validate_refs(cls, values: list[str]) -> list[str]:
        normalized = [_text(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("evidence references must be unique")
        return normalized


class EffectReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["capsule.effect-report/v1"] = "capsule.effect-report/v1"
    capsule: str
    production_plan_digest: str
    checks: list[EffectCheck] = Field(default_factory=list)
    artifacts: list[ArtifactEvidence] = Field(default_factory=list)
    human_review_required: bool = False
    human_review_status: Literal["not_required", "pending", "accepted", "rejected"] = (
        "not_required"
    )
    release_recommendation: Literal["blocked", "review_required", "ready"]

    _capsule = field_validator("capsule")(_text)

    @field_validator("production_plan_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("production_plan_digest must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_report(self) -> EffectReport:
        check_ids = [item.id for item in self.checks]
        artifact_ids = [item.id for item in self.artifacts]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("effect check identifiers must be unique")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact evidence identifiers must be unique")
        known = set(artifact_ids)
        if any(not set(check.evidence_refs) <= known for check in self.checks):
            raise ValueError("effect check references unknown artifact evidence")
        if self.human_review_required and self.human_review_status == "not_required":
            raise ValueError("required human review needs an explicit status")
        if not self.human_review_required and self.human_review_status != "not_required":
            raise ValueError("optional human review must use not_required status")
        blocker_failed = any(
            not check.passed and check.severity == "blocker" for check in self.checks
        )
        if blocker_failed or self.human_review_status == "rejected":
            expected_recommendation = "blocked"
        elif self.human_review_required and self.human_review_status == "pending":
            expected_recommendation = "review_required"
        else:
            expected_recommendation = "ready"
        if self.release_recommendation != expected_recommendation:
            raise ValueError(
                "release_recommendation must be derived from checks and human review"
            )
        return self


def _recommendation(payload: dict) -> str:
    checks = payload.get("checks") or []
    blocker_failed = any(
        isinstance(item, dict)
        and item.get("severity") == "blocker"
        and item.get("passed") is False
        for item in checks
    )
    if blocker_failed or payload.get("human_review_status") == "rejected":
        return "blocked"
    if payload.get("human_review_required") and payload.get("human_review_status") == "pending":
        return "review_required"
    return "ready"


def build_effect_report(payload: dict) -> ResultEnvelope:
    try:
        prepared = dict(payload)
        prepared["release_recommendation"] = _recommendation(prepared)
        report = EffectReport.model_validate(prepared)
        serialized = report.model_dump(mode="json")
    except (ValidationError, TypeError, ValueError, RecursionError):
        return failure(
            "invalid",
            [
                Issue(
                    code="effect_report_invalid",
                    message="The effect report is structurally invalid.",
                    subject="effect-report",
                    remediation="Repair checks, evidence references, or human-review state.",
                )
            ],
        )
    return success("complete", {"report": serialized})
