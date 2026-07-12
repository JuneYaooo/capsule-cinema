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
    CapsuleReadOrder,
    CapsuleRunner,
)


def _manifest_string_list(
    manifest: dict[str, object], field: str, capsule_dir: Path
) -> list[str]:
    values = manifest.get(field, [])
    if not isinstance(values, list):
        raise CapsuleLoadError(
            "invalid_capsule_definition",
            f"Manifest field {field!r} must be a list",
            str(capsule_dir),
            {"field": field},
        )
    return [str(value) for value in values]


def _public_match_values(values: list[str]) -> list[str]:
    """Remove the exact v1 routing marker, preserving creator-owned vocabulary."""
    return [value for value in values if value != "local_script"]


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
            minimum=raw.get("minimum"),
            maximum=raw.get("maximum"),
        )
    capabilities = _manifest_string_list(manifest, "capabilities", capsule_dir)
    tags = _manifest_string_list(manifest, "tags", capsule_dir)
    when_to_use = _manifest_string_list(manifest, "when_to_use", capsule_dir)
    when_not_to_use = _manifest_string_list(manifest, "when_not_to_use", capsule_dir)
    raw_read_order = manifest.get("read_order", {})
    if not isinstance(raw_read_order, dict):
        raise CapsuleLoadError(
            "invalid_capsule_definition",
            "Manifest field 'read_order' must be an object",
            str(capsule_dir),
            {"field": "read_order"},
        )
    read_order = CapsuleReadOrder.model_validate(raw_read_order)
    mode = str(manifest.get("execution_mode") or "")
    entrypoints = (
        manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    )
    if mode == "local_script":
        relative = str(entrypoints.get("local_script") or "")
        try:
            entrypoint = (capsule_dir / relative).resolve()
            entrypoint_is_valid = (
                bool(relative)
                and entrypoint.is_relative_to(capsule_dir.resolve())
                and entrypoint.is_file()
            )
        except (OSError, RuntimeError):
            entrypoint_is_valid = False
        if not entrypoint_is_valid:
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
            capabilities=_public_match_values(capabilities),
            tags=_public_match_values(tags),
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
        ),
        interface=CapsuleInterface(inputs=inputs),
        implementation=CapsuleImplementation(runner=runner),
        read_order=read_order,
    )
