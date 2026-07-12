from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


SCHEMA_VERSION = "capsule.preservation/v1"


class PreservationError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(f"{code}: {message}")


class FileRecord(BaseModel):
    schema_version: Literal["capsule.preservation/v1"] = SCHEMA_VERSION
    relative_path: str
    size: int
    classification: Literal["authored", "excluded_ephemeral"]
    digest: str


class SectionRecord(BaseModel):
    schema_version: Literal["capsule.preservation/v1"] = SCHEMA_VERSION
    section_id: str
    relative_path: str
    kind: str
    source_digest: str
    byte_start: int | None = None
    byte_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    stages: list[str] = Field(default_factory=list)
    promise_affecting: bool = False


class PackageSnapshot(BaseModel):
    schema_version: Literal["capsule.preservation/v1"] = SCHEMA_VERSION
    package_dir: str
    package_digest: str
    files: list[FileRecord] = Field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_excluded_ephemeral(relative_path: Path) -> bool:
    name = relative_path.name
    return (
        "__pycache__" in relative_path.parts
        or name.endswith(".pyc")
        or name == ".DS_Store"
        or name.endswith((".swp", ".swo", ".swn"))
    )


def _file_digest(relative_path: str, path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(relative_path.encode("utf-8"))
    digest.update(b"\0")
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_package(package_dir: Path) -> PackageSnapshot:
    resolved_package = package_dir.resolve()
    if not resolved_package.is_dir():
        raise PreservationError(
            "source_not_directory",
            f"capsule package is not a directory: {resolved_package}",
        )

    records: list[FileRecord] = []
    for path in sorted(
        (candidate for candidate in resolved_package.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(resolved_package).as_posix(),
    ):
        relative = path.relative_to(resolved_package)
        relative_path = relative.as_posix()
        resolved_path = path.resolve()
        if resolved_package not in resolved_path.parents:
            raise PreservationError(
                "source_path_outside_package",
                f"source file resolves outside the capsule package: {relative_path}",
                details={
                    "source_package": str(resolved_package),
                    "relative_path": relative_path,
                    "resolved_path": str(resolved_path),
                },
            )
        records.append(
            FileRecord(
                relative_path=relative_path,
                size=resolved_path.stat().st_size,
                classification=(
                    "excluded_ephemeral" if _is_excluded_ephemeral(relative) else "authored"
                ),
                digest=_file_digest(relative_path, resolved_path),
            )
        )

    package_hasher = hashlib.sha256()
    for record in records:
        if record.classification == "excluded_ephemeral":
            continue
        package_hasher.update(record.relative_path.encode("utf-8"))
        package_hasher.update(b"\0")
        package_hasher.update(record.digest.encode("ascii"))

    return PackageSnapshot(
        package_dir=str(resolved_package),
        package_digest=package_hasher.hexdigest(),
        files=records,
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_baseline(
    snapshot: PackageSnapshot,
    output_dir: Path,
    *,
    git_head: str,
    dirty_paths: list[str],
    python_version: str,
    ffmpeg_version: str,
) -> Path:
    source = Path(snapshot.package_dir).resolve()
    resolved_output = output_dir.resolve()
    if resolved_output == source or source in resolved_output.parents:
        raise PreservationError(
            "output_inside_source",
            f"baseline output must be outside the source package: {resolved_output}",
            details={"source_package": str(source), "output_dir": str(resolved_output)},
        )

    output = output_dir
    output.mkdir(parents=True, exist_ok=True)
    baseline_path = output / "baseline.json"
    _write_json_atomic(
        baseline_path,
        {
            "schema_version": SCHEMA_VERSION,
            "source_package": str(source),
            "package_digest": snapshot.package_digest,
            "git_head": git_head,
            "dirty_paths": sorted(dirty_paths),
            "python_version": python_version,
            "ffmpeg_version": ffmpeg_version,
        },
    )
    _write_json_atomic(
        output / "package-digest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "algorithm": "sha256",
            "package_digest": snapshot.package_digest,
        },
    )
    _write_json_atomic(
        output / "source-inventory.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source_package": str(source),
            "files": [record.model_dump(mode="json") for record in snapshot.files],
        },
    )
    return baseline_path


def assert_package_unchanged(before: PackageSnapshot, package_dir: Path) -> None:
    after = snapshot_package(package_dir)
    if after.package_digest != before.package_digest:
        raise PreservationError(
            "source_mutated",
            "authored capsule package bytes changed after the baseline snapshot",
            details={
                "before_digest": before.package_digest,
                "after_digest": after.package_digest,
                "source_package": str(package_dir.resolve()),
            },
        )
