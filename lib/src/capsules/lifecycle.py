from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .effect import build_effect_report
from .instance import CapsuleInstance, configure_instance
from .model import CapsuleDefinition
from .production import build_production_plan
from .reading import StageName, load_stage_resources
from .result import Issue, ResultEnvelope, failure, success


class LifecycleBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    capsule: str
    action: Literal["plan", "run"]
    output_dir: str
    instance_path: str
    plan_path: str
    plan_digest: str
    stage_paths: dict[StageName, str] = Field(default_factory=dict)
    entered_stages: list[StageName] = Field(default_factory=list)


def _stable_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _definition_digest(definition: CapsuleDefinition) -> str:
    payload = definition.model_dump(mode="json")
    payload["metadata"].pop("source_path", None)
    payload.pop("implementation", None)
    return _stable_digest(payload)


def _runner_digest(definition: CapsuleDefinition) -> str:
    runner = definition.implementation.runner
    digest = hashlib.sha256()
    digest.update(runner.kind.encode("utf-8"))
    digest.update(b"\0")
    if runner.kind == "local_script":
        try:
            digest.update(Path(runner.entrypoint).read_bytes())
        except OSError:
            digest.update(b"unavailable")
    else:
        digest.update(runner.entrypoint.encode("utf-8"))
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_failure(capsule: str) -> ResultEnvelope:
    return failure(
        "blocked",
        [
            Issue(
                code="lifecycle_artifact_write_failed",
                message="A capsule lifecycle artifact could not be written.",
                subject=capsule,
                remediation="Check the output directory and retry.",
            )
        ],
    )


def _bound_inputs(
    definition: CapsuleDefinition,
    topic: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    declared = definition.interface.inputs
    requested = {
        name: value
        for name, value in params.items()
        if type(name) is str and name in declared
    }
    inferred: list[str] = []
    if "topic" in declared and "topic" not in requested:
        requested["topic"] = topic
        inferred.append("topic")
    else:
        unresolved = [
            name
            for name, field in declared.items()
            if field.required
            and field.default is None
            and name not in requested
            and field.type.casefold() == "string"
        ]
        if len(unresolved) == 1:
            requested[unresolved[0]] = topic
            inferred.append(unresolved[0])
    return requested, inferred


def _load_stages(
    definition: CapsuleDefinition,
    stages: list[StageName],
) -> tuple[dict[StageName, dict[str, Any]] | None, ResultEnvelope | None]:
    loaded: dict[StageName, dict[str, Any]] = {}
    for stage in stages:
        result = load_stage_resources(definition, stage)
        if not result.ok:
            return None, result
        loaded[stage] = result.data
    return loaded, None


def prepare_lifecycle(
    definition: CapsuleDefinition,
    topic: str,
    params: dict[str, Any],
    output_dir: str | Path,
    action: Literal["plan", "run"],
) -> ResultEnvelope:
    requested, inferred = _bound_inputs(definition, topic, params)
    configured = configure_instance(
        definition,
        requested,
        candidate_digest=_definition_digest(definition),
        renderer_digest=_runner_digest(definition),
    )
    if not configured.ok:
        return configured

    instance_payload = configured.data["instance"]
    instance_payload["resolved"]["inferred_values"] = inferred
    instance = CapsuleInstance.model_validate(instance_payload)
    serialized_instance = instance.model_dump(mode="json")
    instance_digest = _stable_digest(serialized_instance)

    entered_stages: list[StageName] = ["routing", "planning"]
    if action == "run":
        entered_stages.append("generation")
    loaded, stage_failure = _load_stages(definition, entered_stages)
    if stage_failure is not None:
        return stage_failure
    assert loaded is not None

    stage_resources = {
        stage: [
            {
                "relative_path": resource["relative_path"],
                "digest": resource["digest"],
            }
            for resource in loaded[stage]["resources"]
        ]
        for stage in entered_stages
    }
    plan_result = build_production_plan(
        {
            "capsule": definition.metadata.name,
            "instance_digest": instance_digest,
            "objectives": [{"id": "request", "statement": topic}],
            "evidence_requirements": [
                {
                    "id": "runner-completion",
                    "description": "The configured capsule runner completes.",
                }
            ],
            "quality_requirements": [
                {
                    "id": "runner-success",
                    "description": "The configured capsule runner succeeds.",
                    "blocker": True,
                }
            ],
            "steps": [
                {
                    "id": f"enter-{stage}",
                    "stage": stage,
                    "objective_refs": ["request"],
                    "evidence_refs": ["runner-completion"],
                    "quality_refs": ["runner-success"],
                    "input_refs": [
                        resource["relative_path"] for resource in stage_resources[stage]
                    ],
                }
                for stage in entered_stages
            ],
            "domain_payload": {"stage_resources": stage_resources},
        }
    )
    if not plan_result.ok:
        return plan_result

    output = Path(output_dir).resolve()
    lifecycle_dir = output / "lifecycle"
    instance_path = lifecycle_dir / "capsule.instance.json"
    plan_path = lifecycle_dir / "capsule.production-plan.json"
    stage_paths = {
        stage: lifecycle_dir / "stages" / f"{stage}.json"
        for stage in entered_stages
    }
    try:
        _write_json_atomic(instance_path, serialized_instance)
        for stage in entered_stages:
            _write_json_atomic(stage_paths[stage], loaded[stage])
        _write_json_atomic(plan_path, plan_result.data)
    except (OSError, TypeError, ValueError, OverflowError, RecursionError):
        return _write_failure(definition.metadata.name)

    bundle = LifecycleBundle(
        capsule=definition.metadata.name,
        action=action,
        output_dir=str(output),
        instance_path=str(instance_path),
        plan_path=str(plan_path),
        plan_digest=plan_result.data["digest"],
        stage_paths={stage: str(path) for stage, path in stage_paths.items()},
        entered_stages=entered_stages,
    )
    return success("ready", {"bundle": bundle.model_dump(mode="json")})


def lifecycle_environment(bundle: LifecycleBundle) -> dict[str, str]:
    environment = {
        "CAPSULE_INSTANCE_PATH": bundle.instance_path,
        "CAPSULE_PRODUCTION_PLAN_PATH": bundle.plan_path,
    }
    for stage, path in bundle.stage_paths.items():
        environment[f"CAPSULE_{stage.upper()}_CONTEXT_PATH"] = path
    return environment


def finalize_lifecycle(
    definition: CapsuleDefinition,
    bundle: LifecycleBundle,
    runner_result: ResultEnvelope,
) -> ResultEnvelope:
    loaded, stage_failure = _load_stages(definition, ["qa"])
    if stage_failure is not None:
        return stage_failure
    assert loaded is not None

    passed = runner_result.ok and runner_result.data.get("return_code") == 0
    report_result = build_effect_report(
        {
            "capsule": definition.metadata.name,
            "production_plan_digest": bundle.plan_digest,
            "artifacts": [
                {
                    "id": "runner-result",
                    "reference": "runner-result",
                    "description": "The result returned by the configured runner.",
                }
            ],
            "checks": [
                {
                    "id": "runner-success",
                    "passed": passed,
                    "severity": "blocker",
                    "message": (
                        "The configured runner completed successfully."
                        if passed
                        else "The configured runner did not complete successfully."
                    ),
                    "evidence_refs": ["runner-result"],
                }
            ],
            "human_review_required": False,
            "human_review_status": "not_required",
        }
    )
    if not report_result.ok:
        return report_result

    lifecycle_dir = Path(bundle.output_dir) / "lifecycle"
    qa_path = lifecycle_dir / "stages" / "qa.json"
    report_path = lifecycle_dir / "capsule.effect-report.json"
    report = report_result.data["report"]
    try:
        _write_json_atomic(qa_path, loaded["qa"])
        _write_json_atomic(report_path, report)
    except (OSError, TypeError, ValueError, OverflowError, RecursionError):
        return _write_failure(definition.metadata.name)
    return success(
        "complete",
        {
            "effect_report_path": str(report_path),
            "qa_context_path": str(qa_path),
            "release_recommendation": report["release_recommendation"],
        },
    )
