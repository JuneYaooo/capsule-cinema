from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .lifecycle import (
    LifecycleBundle,
    finalize_lifecycle,
    lifecycle_environment,
    prepare_lifecycle,
)
from .loader import load_definition
from .model import CapsuleDefinition
from .result import Issue, ResultEnvelope, failure, success


class DispatchError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class DispatchLifecycleError(Exception):
    def __init__(self, result: ResultEnvelope) -> None:
        super().__init__("Capsule lifecycle preparation failed.")
        self.result = result


class DispatchPlan(BaseModel):
    capsule: str
    action: Literal["plan", "run"]
    command: list[str]
    cwd: str
    environment: dict[str, str]
    output_dir: str
    definition: CapsuleDefinition | None = Field(default=None, exclude=True, repr=False)
    lifecycle: LifecycleBundle | None = None


_PRESET_PARAMETER_ORDER = (
    "target_duration",
    "aspect_ratio",
    "platform",
    "add_subtitles",
    "add_background_music",
    "background_music_path",
    "bgm_volume",
    "voice_volume",
    "image_engine",
    "video_engine",
    "user_reference_images",
    "accept_preflight_changes",
)
_PRESET_FLAGS = {name: f"--{name}" for name in _PRESET_PARAMETER_ORDER}
_STRING_PARAMETERS = {
    "aspect_ratio",
    "platform",
    "background_music_path",
    "image_engine",
    "video_engine",
}
_BOOLEAN_PARAMETERS = {"add_subtitles", "add_background_music"}
_FLOAT_PARAMETERS = {"bgm_volume", "voice_volume"}


def _invalid_parameter(name: str, expected: str) -> DispatchError:
    return DispatchError(
        "invalid_preset_parameter",
        f"Preset parameter {name!r} must be {expected}.",
        {"parameter": name, "expected": expected},
    )


def _serialize_preset_parameter(name: str, value: Any) -> str | None:
    if name == "target_duration":
        if type(value) is not int:
            raise _invalid_parameter(name, "an integer")
        return str(value)
    if name in _STRING_PARAMETERS:
        if type(value) is not str:
            raise _invalid_parameter(name, "a string")
        return value
    if name in _BOOLEAN_PARAMETERS:
        if type(value) is not bool:
            raise _invalid_parameter(name, "a boolean")
        return "true" if value else "false"
    if name in _FLOAT_PARAMETERS:
        if type(value) not in (int, float):
            raise _invalid_parameter(name, "a number")
        return str(float(value))
    if name == "user_reference_images":
        if not isinstance(value, list) or not all(
            type(item) is str for item in value
        ):
            raise _invalid_parameter(name, "a list of strings")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if name == "accept_preflight_changes":
        if type(value) is not bool:
            raise _invalid_parameter(name, "a boolean")
        return None
    raise AssertionError(f"Unsupported preset parameter serializer: {name}")


def _write_params_snapshot(output: Path, params: dict[str, Any]) -> Path:
    params_path = output / "inputs" / "params.requested.json"
    boundary_error: DispatchError | None = None
    try:
        serialized = json.dumps(params, ensure_ascii=False, indent=2) + "\n"
        params_path.parent.mkdir(parents=True, exist_ok=True)
        params_path.write_text(serialized, encoding="utf-8")
    except (OSError, TypeError, UnicodeError, ValueError):
        boundary_error = DispatchError(
            "output_snapshot_failed",
            "Could not write the requested parameter snapshot.",
            {"output_dir": str(output)},
        )
    if boundary_error is not None:
        raise boundary_error from None
    return params_path


def build_dispatch_plan(
    name_or_path: str | Path,
    topic: str,
    params: dict[str, Any],
    output_dir: str | Path,
    action: Literal["plan", "run"],
    search_roots: list[str | Path] | None = None,
) -> DispatchPlan:
    definition = load_definition(name_or_path, search_roots=search_roots)
    root = Path(__file__).resolve().parents[3]
    output = Path(output_dir).resolve()
    params_path = _write_params_snapshot(output, params)

    if definition.implementation.runner.kind == "local_script":
        command = [
            sys.executable,
            str(root / "scripts" / "run_capsule.py"),
            "--capsule",
            definition.metadata.source_path,
            "--topic",
            topic,
            "--params",
            str(params_path),
            "--output-dir",
            str(output),
        ]
        if action == "plan":
            command.append("--dry-run")
        environment: dict[str, str] = {}
    else:
        unknown = set(params) - (
            set(_PRESET_PARAMETER_ORDER) | set(definition.interface.inputs)
        )
        if unknown:
            raise DispatchError(
                "unsupported_preset_parameter",
                "One or more preset parameters are not supported.",
                {"parameters": sorted(unknown)},
            )
        command = [
            sys.executable,
            str(root / "scripts" / "run_video.py"),
            "--capsule",
            definition.metadata.source_path,
            "--user_requirements",
            topic,
        ]
        if action == "plan":
            command.append("--storyboard_only")
        for name in _PRESET_PARAMETER_ORDER:
            if name not in params:
                continue
            serialized = _serialize_preset_parameter(name, params[name])
            if name == "accept_preflight_changes":
                if params[name]:
                    command.append(_PRESET_FLAGS[name])
                continue
            command.extend([_PRESET_FLAGS[name], serialized])
        environment = {"OPENCLAW_OUTPUT_DIR": str(output)}

    lifecycle_result = prepare_lifecycle(
        definition,
        topic,
        params,
        output,
        action,
    )
    if not lifecycle_result.ok:
        raise DispatchLifecycleError(lifecycle_result)
    lifecycle = LifecycleBundle.model_validate(lifecycle_result.data["bundle"])
    environment.update(lifecycle_environment(lifecycle))

    return DispatchPlan(
        capsule=definition.metadata.name,
        action=action,
        command=command,
        cwd=str(root),
        environment=environment,
        output_dir=str(output),
        definition=definition,
        lifecycle=lifecycle,
    )


def _execute_runner(plan: DispatchPlan) -> ResultEnvelope:
    merged_env = dict(os.environ)
    merged_env.update(plan.environment)
    try:
        completed = subprocess.run(
            plan.command,
            cwd=plan.cwd,
            env=merged_env,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except UnicodeError:
        return _runner_boundary_failure(
            plan,
            "runner_communication_failed",
            "Capsule runner communication failed.",
        )
    except (OSError, ValueError):
        return _runner_boundary_failure(
            plan,
            "runner_start_failed",
            "Capsule runner could not be started.",
        )
    except subprocess.SubprocessError:
        return _runner_boundary_failure(
            plan,
            "runner_communication_failed",
            "Capsule runner communication failed.",
        )
    try:
        if completed.stdout:
            sys.stderr.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
    except (OSError, UnicodeError):
        return _runner_boundary_failure(
            plan,
            "runner_communication_failed",
            "Capsule runner communication failed.",
        )

    data = {
        "capsule": plan.capsule,
        "action": plan.action,
        "output_dir": plan.output_dir,
        "return_code": completed.returncode,
    }
    runner_payload = _extract_runner_payload(completed.stdout or "")
    if runner_payload:
        data["_runner_payload"] = runner_payload
    if completed.returncode == 0:
        return success("planned" if plan.action == "plan" else "completed", data)
    return failure(
        "run_failed",
        [
            Issue(
                code="runner_failed",
                message=f"Capsule runner exited with code {completed.returncode}.",
                subject=plan.capsule,
                remediation=(
                    "Inspect the runner logs emitted on stderr and the output "
                    "directory, then retry."
                ),
                details={"return_code": completed.returncode},
            )
        ],
        data,
    )


def execute_dispatch_plan(plan: DispatchPlan) -> ResultEnvelope:
    runner_result = _execute_runner(plan)
    if plan.definition is None or plan.lifecycle is None:
        return _without_private_runner_data(runner_result)

    finalized = finalize_lifecycle(plan.definition, plan.lifecycle, runner_result)
    data = {
        key: value
        for key, value in runner_result.data.items()
        if not key.startswith("_")
    }
    data["lifecycle"] = {
        "production_plan": "lifecycle/capsule.production-plan.json",
        "plan_digest": plan.lifecycle.plan_digest,
    }
    if not finalized.ok:
        return failure(
            "run_failed",
            [*runner_result.issues, *finalized.issues],
            data,
        )
    data["lifecycle"].update(
        {
            "effect_report": "lifecycle/capsule.effect-report.json",
            "qa_context": "lifecycle/stages/qa.json",
            "release_recommendation": finalized.data["release_recommendation"],
        }
    )
    if runner_result.ok:
        return success(runner_result.status, data, runner_result.issues)
    return failure(runner_result.status, runner_result.issues, data)


def _extract_runner_payload(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    cursor = 0
    last_payload: dict[str, Any] = {}
    while cursor < len(stdout):
        start = stdout.find("{", cursor)
        if start < 0:
            break
        try:
            value, length = decoder.raw_decode(stdout[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        cursor = start + max(length, 1)
        if isinstance(value, dict) and not value.get("event"):
            last_payload = value
    return last_payload


def _without_private_runner_data(result: ResultEnvelope) -> ResultEnvelope:
    data = {
        key: value for key, value in result.data.items() if not key.startswith("_")
    }
    if result.ok:
        return success(result.status, data, result.issues)
    return failure(result.status, result.issues, data)


def _runner_boundary_failure(
    plan: DispatchPlan,
    code: str,
    message: str,
) -> ResultEnvelope:
    return failure(
        "run_failed",
        [
            Issue(
                code=code,
                message=message,
                subject=plan.capsule,
                remediation="Check the local runner installation and retry.",
            )
        ],
        {
            "capsule": plan.capsule,
            "action": plan.action,
            "output_dir": plan.output_dir,
        },
    )
