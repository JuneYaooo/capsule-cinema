from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.capsule_package_loader import CapsulePackageError, resolve_capsule_dir

from .model import CapsuleDefinition
from .result import Issue


class CapsuleLoadError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        subject: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.subject = subject
        self.details = details or {}


_PUBLIC_LOAD_MESSAGES = {
    "capsule_not_found": "The requested capsule was not found.",
    "invalid_capsule_document": "A required capsule document could not be read.",
    "unsupported_capsule_schema": "The capsule schema is not supported.",
    "invalid_capsule_definition": "The capsule definition is invalid.",
    "invalid_input_schema": "The capsule input schema is invalid.",
    "runner_entrypoint_missing": "The capsule's declared local entrypoint is unavailable.",
    "invalid_runner_kind": "The capsule execution configuration is invalid.",
}
_PUBLIC_LOAD_DETAIL_FIELDS = {
    "schema",
    "schema_version",
    "version",
    "field",
    "parameters",
    "return_code",
}


def _logical_capsule_subject(name_or_path: str | Path) -> str:
    name = Path(str(name_or_path)).name
    if name.endswith(".capsule"):
        return name.removesuffix(".capsule")
    return name or "capsule"


def public_issue_from_load_error(
    exc: CapsuleLoadError,
    name_or_path: str | Path,
    *,
    warning: bool = False,
    remediation: str = "Run the doctor command for package diagnostics.",
) -> Issue:
    """Map rich internal loader diagnostics to the stable public issue DTO."""
    return Issue(
        code=exc.code,
        message=_PUBLIC_LOAD_MESSAGES.get(
            exc.code, "The capsule package could not be loaded."
        ),
        severity="warning" if warning else "error",
        subject=_logical_capsule_subject(name_or_path),
        remediation=remediation,
        details={
            key: value
            for key, value in exc.details.items()
            if key in _PUBLIC_LOAD_DETAIL_FIELDS
        },
    )


def _read_object(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CapsuleLoadError(
            "invalid_capsule_document",
            f"Could not read capsule document: {path}",
            str(path),
            {"document": str(path)},
        ) from exc
    if not isinstance(document, dict):
        raise CapsuleLoadError(
            "invalid_capsule_document",
            f"Capsule document must be an object: {path}",
            str(path),
            {"document": str(path)},
        )
    return document


def detect_schema(capsule_dir: Path) -> str:
    manifest = _read_object(capsule_dir / "capsule.yaml")
    return str(manifest.get("schema_version") or "")


def load_definition(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> CapsuleDefinition:
    try:
        capsule_dir = resolve_capsule_dir(name_or_path, search_roots=search_roots)
    except CapsulePackageError as exc:
        raise CapsuleLoadError(
            "capsule_not_found",
            str(exc),
            str(name_or_path),
            {"search_roots": [str(root) for root in search_roots or []]},
        ) from exc

    schema = detect_schema(capsule_dir)
    if schema != "capsule.package.v1":
        raise CapsuleLoadError(
            "unsupported_capsule_schema",
            f"Unsupported capsule schema: {schema!r}",
            str(capsule_dir),
            {"schema_version": schema},
        )

    from .v1_adapter import adapt_v1

    try:
        return adapt_v1(capsule_dir)
    except ValidationError as exc:
        raise CapsuleLoadError(
            "invalid_capsule_definition",
            "Normalized capsule validation failed.",
            str(capsule_dir),
            {"errors": exc.errors(include_url=False)},
        ) from exc
    except (TypeError, ValueError) as exc:
        raise CapsuleLoadError(
            "invalid_capsule_definition",
            "Normalized capsule data has an invalid type.",
            str(capsule_dir),
            {"error_type": type(exc).__name__},
        ) from exc
