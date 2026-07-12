from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic_core import PydanticSerializationError

from .reading import STAGES, StageName
from .result import Issue, ResultEnvelope, failure, success


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _require_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized


def _require_refs(values: list[str]) -> list[str]:
    normalized = [_require_text(value) for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError("logical references must be unique")
    return normalized


def _require_json(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("value must be deterministic JSON data") from exc
    return value


class Objective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    statement: str

    _id = field_validator("id")(_require_text)
    _statement = field_validator("statement")(_require_text)


class EvidenceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    description: str
    required: bool = True

    _id = field_validator("id")(_require_text)
    _description = field_validator("description")(_require_text)


class QualityRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    description: str
    blocker: bool = True

    _id = field_validator("id")(_require_text)
    _description = field_validator("description")(_require_text)


class ProductionStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    stage: StageName
    objective_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    quality_refs: list[str] = Field(default_factory=list)
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)

    _id = field_validator("id")(_require_text)
    _refs = field_validator(
        "objective_refs",
        "evidence_refs",
        "quality_refs",
        "input_refs",
        "output_refs",
        "rule_refs",
    )(_require_refs)


class ProductionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["capsule.production-plan/v1"] = "capsule.production-plan/v1"
    capsule: str
    instance_digest: str
    objectives: list[Objective] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    quality_requirements: list[QualityRequirement] = Field(default_factory=list)
    steps: list[ProductionStep] = Field(default_factory=list)
    fallback_policy: str = "no_promise_change"
    human_approval_points: list[str] = Field(default_factory=list)
    domain_payload: dict[str, Any] = Field(default_factory=dict)

    _capsule = field_validator("capsule")(_require_text)
    _fallback = field_validator("fallback_policy")(_require_text)
    _approvals = field_validator("human_approval_points")(_require_refs)
    _domain = field_validator("domain_payload", mode="before")(_require_json)

    @field_validator("instance_digest")
    @classmethod
    def require_digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("instance_digest must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> ProductionPlan:
        groups = {
            "objective": [item.id for item in self.objectives],
            "evidence": [item.id for item in self.evidence_requirements],
            "quality": [item.id for item in self.quality_requirements],
            "step": [item.id for item in self.steps],
        }
        for kind, identifiers in groups.items():
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{kind} identifiers must be unique")
        known_objectives = set(groups["objective"])
        known_evidence = set(groups["evidence"])
        known_quality = set(groups["quality"])
        order = {stage: index for index, stage in enumerate(STAGES)}
        previous = -1
        for step in self.steps:
            current = order[step.stage]
            if current < previous:
                raise ValueError("production step stages must not regress")
            previous = current
            if not set(step.objective_refs) <= known_objectives:
                raise ValueError("production step references an unknown objective")
            if not set(step.evidence_refs) <= known_evidence:
                raise ValueError("production step references unknown evidence")
            if not set(step.quality_refs) <= known_quality:
                raise ValueError("production step references an unknown quality requirement")
        return self


def production_plan_digest(plan: ProductionPlan | dict[str, Any]) -> str:
    payload = plan.model_dump(mode="python") if isinstance(plan, ProductionPlan) else plan
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_production_plan(payload: dict[str, Any]) -> ResultEnvelope:
    try:
        plan = ProductionPlan.model_validate(payload)
        serialized = plan.model_dump(mode="json")
        digest = production_plan_digest(plan)
    except (
        ValidationError,
        PydanticSerializationError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        return failure(
            "invalid",
            [
                Issue(
                    code="production_plan_invalid",
                    message="The production plan is structurally invalid.",
                    subject="production-plan",
                    remediation="Repair identifiers, references, stage order, or domain data.",
                )
            ],
        )
    return success("ready", {"plan": serialized, "digest": digest})
