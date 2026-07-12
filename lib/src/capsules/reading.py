from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from .model import CapsuleDefinition
from .result import Issue, ResultEnvelope, failure, success


StageName = Literal["routing", "planning", "generation", "qa", "learning"]
STAGES: tuple[StageName, ...] = (
    "routing",
    "planning",
    "generation",
    "qa",
    "learning",
)


def _blocked(code: str, message: str, subject: str) -> ResultEnvelope:
    return failure(
        "blocked",
        [
            Issue(
                code=code,
                message=message,
                subject=subject,
                remediation="Repair the capsule read_order resource before continuing.",
            )
        ],
    )


def load_stage_resources(definition: CapsuleDefinition, stage: str) -> ResultEnvelope:
    """Load only the author-declared UTF-8 resources for one capsule stage."""

    if stage not in STAGES:
        return failure(
            "invalid",
            [
                Issue(
                    code="stage_unknown",
                    message="The requested capsule reading stage is not supported.",
                    subject=stage if type(stage) is str else "stage",
                    remediation=f"Use one of: {', '.join(STAGES)}.",
                )
            ],
        )
    try:
        package = Path(definition.metadata.source_path).resolve(strict=True)
    except (OSError, RuntimeError):
        return _blocked(
            "stage_source_unavailable",
            "The capsule source package is unavailable.",
            definition.metadata.name,
        )
    if not package.is_dir():
        return _blocked(
            "stage_source_unavailable",
            "The capsule source package is unavailable.",
            definition.metadata.name,
        )

    resources: list[dict[str, str]] = []
    for relative_value in getattr(definition.read_order, stage):
        relative = Path(relative_value)
        subject = relative.as_posix()
        if relative.is_absolute() or ".." in relative.parts:
            return _blocked(
                "stage_resource_outside_package",
                "A stage resource must remain inside the capsule package.",
                subject,
            )
        candidate = package / relative
        cursor = package
        try:
            for part in relative.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    return _blocked(
                        "stage_resource_symlink_refused",
                        "Stage resources cannot traverse symbolic links.",
                        subject,
                    )
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, NotADirectoryError):
            return _blocked(
                "stage_resource_missing",
                "A declared stage resource is missing.",
                subject,
            )
        except (OSError, RuntimeError):
            return _blocked(
                "stage_resource_unavailable",
                "A declared stage resource could not be resolved.",
                subject,
            )
        if not resolved.is_relative_to(package):
            return _blocked(
                "stage_resource_outside_package",
                "A stage resource must remain inside the capsule package.",
                subject,
            )
        if not resolved.is_file():
            return _blocked(
                "stage_resource_missing",
                "A declared stage resource is not a file.",
                subject,
            )
        try:
            raw = resolved.read_bytes()
        except OSError:
            return _blocked(
                "stage_resource_unavailable",
                "A declared stage resource could not be read.",
                subject,
            )
        try:
            content = raw.decode("utf-8")
        except UnicodeError:
            return _blocked(
                "stage_resource_not_utf8",
                "A declared stage resource is not UTF-8 text.",
                subject,
            )
        resources.append(
            {
                "relative_path": subject,
                "digest": hashlib.sha256(raw).hexdigest(),
                "content": content,
            }
        )
    return success(
        "ready",
        {
            "capsule": definition.metadata.name,
            "stage": stage,
            "resources": resources,
        },
    )
