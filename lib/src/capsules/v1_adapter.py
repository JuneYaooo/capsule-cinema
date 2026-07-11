from __future__ import annotations

from pathlib import Path

from .loader import CapsuleLoadError, _read_object
from .model import (
    CapsuleDefinition,
    CapsuleImplementation,
    CapsuleInput,
    CapsuleInterface,
    CapsuleMatch,
    CapsuleMetadata,
    CapsulePromise,
    CapsuleRunner,
)


def adapt_v1(capsule_dir: Path) -> CapsuleDefinition:
    manifest = _read_object(capsule_dir / "capsule.yaml")
    input_document = _read_object(capsule_dir / "contracts" / "input_schema.yaml")
    fields = input_document.get("fields", {})
    if not isinstance(fields, dict):
        raise CapsuleLoadError(
            "invalid_input_schema", "fields must be an object", str(capsule_dir)
        )
    inputs: dict[str, CapsuleInput] = {}
    for name, raw in fields.items():
        if not isinstance(raw, dict):
            raise CapsuleLoadError(
                "invalid_input_schema",
                f"field {name!r} must be an object",
                str(capsule_dir),
            )
        options = raw.get("enum", [])
        if not isinstance(options, list):
            raise CapsuleLoadError(
                "invalid_input_schema",
                f"field {name!r} enum must be a list",
                str(capsule_dir),
            )
        inputs[str(name)] = CapsuleInput(
            type=str(raw.get("type") or "string"),
            required=bool(raw.get("required", False)),
            description=str(raw.get("description") or ""),
            default=raw.get("default"),
            options=options,
        )
    mode = str(manifest.get("execution_mode") or "")
    entrypoints = (
        manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    )
    if mode == "local_script":
        relative = str(entrypoints.get("local_script") or "")
        entrypoint = (capsule_dir / relative).resolve()
        if (
            not relative
            or not entrypoint.is_relative_to(capsule_dir.resolve())
            or not entrypoint.is_file()
        ):
            raise CapsuleLoadError(
                "runner_entrypoint_missing",
                "Declared local runner does not exist",
                str(capsule_dir),
            )
        runner = CapsuleRunner(kind="local_script", entrypoint=str(entrypoint))
    elif mode == "preset":
        preset = str(entrypoints.get("preset") or "general_video")
        runner = CapsuleRunner(kind="preset", entrypoint=preset)
    else:
        raise CapsuleLoadError(
            "invalid_runner_kind",
            f"Unsupported execution_mode: {mode!r}",
            str(capsule_dir),
        )
    return CapsuleDefinition(
        metadata=CapsuleMetadata(
            name=str(manifest.get("name") or ""),
            display_name=str(manifest.get("display_name") or manifest.get("name") or ""),
            version=str(manifest.get("version") or "1"),
            status=str(manifest.get("status") or "draft"),
            source_schema="capsule.package.v1",
            source_path=str(capsule_dir.resolve()),
        ),
        promise=CapsulePromise(summary=str(manifest.get("summary") or "")),
        match=CapsuleMatch(
            category=str(manifest.get("category") or ""),
            workflow=str(manifest.get("primary_workflow") or ""),
            capabilities=[str(value) for value in manifest.get("capabilities", [])],
            tags=[str(value) for value in manifest.get("tags", [])],
            when_to_use=[str(value) for value in manifest.get("when_to_use", [])],
            when_not_to_use=[str(value) for value in manifest.get("when_not_to_use", [])],
        ),
        interface=CapsuleInterface(inputs=inputs),
        implementation=CapsuleImplementation(runner=runner),
    )
