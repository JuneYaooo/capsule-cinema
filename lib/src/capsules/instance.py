from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .model import CapsuleDefinition, CapsuleInput
from .result import Issue, ResultEnvelope, failure, success


INSTANCE_SCHEMA = "capsule.instance/v1"


class CapsuleLock(BaseModel):
    name: str
    candidate_digest: str
    renderer_digest: str


class ResolvedInputs(BaseModel):
    defaults_applied: list[str] = Field(default_factory=list)
    inferred_values: list[str] = Field(default_factory=list)


class InstanceApprovals(BaseModel):
    fallback_policy: Literal["no_promise_change"] = "no_promise_change"


class CapsuleInstance(BaseModel):
    schema_version: Literal["capsule.instance/v1"] = INSTANCE_SCHEMA
    capsule: CapsuleLock
    inputs: dict[str, Any] = Field(default_factory=dict)
    resolved: ResolvedInputs = Field(default_factory=ResolvedInputs)
    approvals: InstanceApprovals = Field(default_factory=InstanceApprovals)


def _issue(
    code: str,
    message: str,
    name: str,
    *,
    details: dict[str, Any] | None = None,
) -> Issue:
    return Issue(code=code, message=message, subject=name, details=details or {})


def _has_strict_type(field: CapsuleInput, value: Any) -> bool:
    expected = field.type.casefold()
    if expected == "string":
        return type(value) is str
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return type(value) is int or (
            type(value) is float and math.isfinite(value)
        )
    if expected == "boolean":
        return type(value) is bool
    if expected in {"array", "list"}:
        return type(value) is list
    if expected == "object":
        return type(value) is dict
    if expected == "enum":
        return bool(field.options) and any(
            type(value) is type(option) and value == option for option in field.options
        )
    return False


def _validate_value(name: str, field: CapsuleInput, value: Any) -> list[Issue]:
    expected = field.type.casefold()
    supported = {
        "string",
        "integer",
        "number",
        "boolean",
        "array",
        "list",
        "object",
        "enum",
    }
    if expected not in supported:
        return [
            _issue(
                "unsupported_input_type",
                f"Input {name!r} declares unsupported type {field.type!r}.",
                name,
                details={"type": field.type},
            )
        ]
    if not _has_strict_type(field, value):
        code = "input_not_allowed" if expected == "enum" else "invalid_input_type"
        return [
            _issue(
                code,
                (
                    f"Input {name!r} must be one of its allowed options."
                    if expected == "enum"
                    else f"Input {name!r} must have type {field.type!r}."
                ),
                name,
                details={"expected": field.type},
            )
        ]

    if field.options and expected != "enum" and not any(
        type(value) is type(option) and value == option for option in field.options
    ):
        return [
            _issue(
                "input_not_allowed",
                f"Input {name!r} must be one of its allowed options.",
                name,
                details={"options": field.options},
            )
        ]

    if expected in {"integer", "number"}:
        if field.minimum is not None and value < field.minimum:
            return [
                _issue(
                    "input_below_minimum",
                    f"Input {name!r} is below its minimum.",
                    name,
                    details={"minimum": field.minimum, "actual": value},
                )
            ]
        if field.maximum is not None and value > field.maximum:
            return [
                _issue(
                    "input_above_maximum",
                    f"Input {name!r} is above its maximum.",
                    name,
                    details={"maximum": field.maximum, "actual": value},
                )
            ]
    return []


def configure_instance(
    definition: CapsuleDefinition,
    requested: dict[str, Any],
    *,
    candidate_digest: str,
    renderer_digest: str,
    topic: str = "",
) -> ResultEnvelope:
    del topic  # The v1 pilot has no approved topic-to-input inference rules.
    declared = definition.interface.inputs
    issues = [
        _issue(
            "unknown_input",
            f"Input {name!r} is not declared by the capsule.",
            name,
        )
        for name in sorted(set(requested) - set(declared))
    ]
    bound: dict[str, Any] = {}
    defaults_applied: list[str] = []
    missing: list[Issue] = []

    for name in sorted(declared):
        field = declared[name]
        if name in requested:
            value = requested[name]
        elif field.default is not None:
            value = field.default
            defaults_applied.append(name)
        elif field.required:
            missing.append(
                _issue(
                    "missing_required_input",
                    f"Required input {name!r} is missing.",
                    name,
                )
            )
            continue
        else:
            continue

        value_issues = _validate_value(name, field, value)
        if value_issues:
            issues.extend(value_issues)
        else:
            bound[name] = value

    if issues:
        return failure("invalid", issues)
    if missing:
        return failure("needs_input", missing)

    instance = CapsuleInstance(
        capsule=CapsuleLock(
            name=definition.metadata.name,
            candidate_digest=candidate_digest,
            renderer_digest=renderer_digest,
        ),
        inputs=bound,
        resolved=ResolvedInputs(
            defaults_applied=defaults_applied,
            inferred_values=[],
        ),
    )
    return success("ready", {"instance": instance.model_dump(mode="json")})


def write_instance(instance: CapsuleInstance, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                instance.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
