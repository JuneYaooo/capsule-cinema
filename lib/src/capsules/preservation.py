from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from .result import Issue, ResultEnvelope, failure, success


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
    yaml_value_type: Literal["mapping", "sequence", "scalar"] | None = None


DispositionName = Literal[
    "preserved_in_definition",
    "moved_to_guidance",
    "converted_to_rubric",
    "converted_to_checker",
    "moved_to_asset",
    "moved_to_example",
    "moved_to_runner",
    "generated_view",
    "excluded_ephemeral",
    "obsolete_with_evidence",
]


class PreservationDisposition(BaseModel):
    schema_version: Literal["capsule.preservation/v1"] = SCHEMA_VERSION
    section_id: str
    disposition: DispositionName
    target_owner: str
    rationale: str


class PreservationManifest(BaseModel):
    schema_version: Literal["capsule.preservation/v1"] = SCHEMA_VERSION
    package_digest: str
    sections: list[SectionRecord] = Field(default_factory=list)
    dispositions: list[PreservationDisposition] = Field(default_factory=list)
    coverage_percent: float = 0.0
    unclassified: list[str] = Field(default_factory=list)
    silent_deletions: list[str] = Field(default_factory=list)


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


def _json_pointer_token(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(match.end() for match in re.finditer("\n", text))
    return starts


def _char_to_byte(text: str, index: int) -> int:
    return len(text[:index].encode("utf-8"))


def _text_section(
    relative_path: str,
    kind: str,
    label: str,
    digest: str,
    text: str,
    start: int,
    end: int,
    *,
    stages: list[str],
    promise_affecting: bool,
) -> SectionRecord:
    return SectionRecord(
        section_id=f"{relative_path}#{kind}:{label}",
        relative_path=relative_path,
        kind=kind,
        source_digest=digest,
        byte_start=_char_to_byte(text, start),
        byte_end=_char_to_byte(text, end),
        line_start=text.count("\n", 0, start) + 1,
        line_end=text.count("\n", 0, max(start, end - 1)) + 1,
        stages=stages,
        promise_affecting=promise_affecting,
    )


def _section_metadata(relative_path: str) -> tuple[list[str], bool]:
    if relative_path == "capsule.yaml" or relative_path.startswith("contracts/"):
        return ["definition"], True
    if relative_path.startswith("quality/"):
        return ["quality"], True
    if relative_path.startswith(("recipes/", "learning/")):
        return ["guidance"], False
    if relative_path.startswith("assets/"):
        return ["assets"], False
    if relative_path.startswith("examples/"):
        return ["examples"], False
    if relative_path.startswith("scripts/"):
        return ["runner"], True
    if relative_path in {"CARD.md", "index.md"}:
        return ["generated_view"], False
    if _is_excluded_ephemeral(Path(relative_path)):
        return ["ephemeral"], False
    return ["source"], False


def _yaml_sections(relative_path: str, text: str, digest: str) -> list[SectionRecord]:
    root = yaml.compose(text)
    if root is None:
        stages, promise_affecting = _section_metadata(relative_path)
        return [
            _text_section(
                relative_path,
                "yaml",
                "/",
                digest,
                text,
                0,
                0,
                stages=stages,
                promise_affecting=promise_affecting,
            )
        ]
    stages, promise_affecting = _section_metadata(relative_path)
    sections: list[SectionRecord] = []

    def append(node: Node, pointer: str, start: int | None = None) -> None:
        section = _text_section(
            relative_path,
            "yaml",
            pointer or "/",
            digest,
            text,
            node.start_mark.index if start is None else start,
            node.end_mark.index,
            stages=stages,
            promise_affecting=promise_affecting,
        )
        section.yaml_value_type = (
            "mapping"
            if isinstance(node, MappingNode)
            else "sequence"
            if isinstance(node, SequenceNode)
            else "scalar"
        )
        sections.append(section)

    def visit(node: Node, pointer: str) -> None:
        if isinstance(node, MappingNode):
            for key, value in node.value:
                token = _json_pointer_token(key.value if isinstance(key, ScalarNode) else key.start_mark.index)
                child_pointer = f"{pointer}/{token}"
                append(value, child_pointer, key.start_mark.index)
                visit(value, child_pointer)
        elif isinstance(node, SequenceNode):
            for index, value in enumerate(node.value):
                child_pointer = f"{pointer}/{index}"
                append(value, child_pointer)
                visit(value, child_pointer)

    if isinstance(root, (MappingNode, SequenceNode)):
        visit(root, "")
    else:
        append(root, "/")
    return sections


_HEADING = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*(?:\n|$)")


def _markdown_sections(relative_path: str, text: str, digest: str) -> list[SectionRecord]:
    stages, promise_affecting = _section_metadata(relative_path)
    sections: list[SectionRecord] = []
    content_start = 0
    if text.startswith("---\n"):
        closing = re.search(r"(?m)^---[ \t]*(?:\n|$)", text[4:])
        if closing:
            end = 4 + closing.end()
            sections.append(
                _text_section(
                    relative_path, "markdown_frontmatter", "frontmatter", digest, text, 0, end,
                    stages=stages, promise_affecting=promise_affecting,
                )
            )
            content_start = end

    headings = list(_HEADING.finditer(text, content_start))
    preamble_end = headings[0].start() if headings else len(text)
    if preamble_end > content_start and text[content_start:preamble_end].strip():
        sections.append(
            _text_section(
                relative_path, "markdown_preamble", "preamble", digest, text,
                content_start, preamble_end, stages=stages, promise_affecting=promise_affecting,
            )
        )
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        line = text.count("\n", 0, heading.start()) + 1
        label = f"{heading.group(2).strip()}@L{line}"
        sections.append(
            _text_section(
                relative_path, "markdown_heading", label, digest, text, heading.start(), end,
                stages=stages, promise_affecting=promise_affecting,
            )
        )
    if not sections and text:
        sections.append(
            _text_section(
                relative_path, "markdown_preamble", "preamble", digest, text, 0, len(text),
                stages=stages, promise_affecting=promise_affecting,
            )
        )
    return sections


def _python_sections(relative_path: str, text: str, digest: str) -> list[SectionRecord]:
    tree = ast.parse(text)
    stages, promise_affecting = _section_metadata(relative_path)
    starts = _line_starts(text)
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    first_line = min(
        (
            min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
            for node in definitions
        ),
        default=len(starts) + 1,
    )
    preamble_end = starts[first_line - 1] if first_line <= len(starts) else len(text)
    sections: list[SectionRecord] = []
    sections.append(
        _text_section(
            relative_path, "python", "module-preamble", digest, text, 0,
            preamble_end if definitions else len(text), stages=stages,
            promise_affecting=promise_affecting,
        )
    )
    for node in definitions:
        start_line = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
        start = starts[start_line - 1]
        end = starts[node.end_lineno] if node.end_lineno < len(starts) else len(text)
        symbol_kind = "class" if isinstance(node, ast.ClassDef) else "function"
        sections.append(
            _text_section(
                relative_path, "python", f"{symbol_kind}:{node.name}", digest, text, start, end,
                stages=stages, promise_affecting=promise_affecting,
            )
        )
    return sections


def inventory_sections(package_dir: Path) -> list[SectionRecord]:
    snapshot = snapshot_package(package_dir)
    root = Path(snapshot.package_dir)
    sections: list[SectionRecord] = []
    for file_record in snapshot.files:
        path = root / file_record.relative_path
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            sections.extend(_yaml_sections(file_record.relative_path, path.read_text(encoding="utf-8"), file_record.digest))
        elif suffix in {".md", ".markdown"}:
            sections.extend(_markdown_sections(file_record.relative_path, path.read_text(encoding="utf-8"), file_record.digest))
        elif suffix == ".py":
            sections.extend(_python_sections(file_record.relative_path, path.read_text(encoding="utf-8"), file_record.digest))
        else:
            stages, promise_affecting = _section_metadata(file_record.relative_path)
            sections.append(
                SectionRecord(
                    section_id=f"{file_record.relative_path}#binary:whole-file",
                    relative_path=file_record.relative_path,
                    kind="binary",
                    source_digest=file_record.digest,
                    byte_start=0,
                    byte_end=file_record.size,
                    line_start=1,
                    line_end=1,
                    stages=stages,
                    promise_affecting=promise_affecting,
                )
            )
    return sections


def classify_repo_showcase_section(section: SectionRecord) -> PreservationDisposition:
    path = section.relative_path
    if _is_excluded_ephemeral(Path(path)):
        route = ("excluded_ephemeral", "none", "Generated cache is explicitly excluded.")
    elif path == "capsule.yaml" or path in {
        "contracts/input_schema.yaml", "contracts/runtime.yaml", "assets/index.yaml"
    }:
        route = ("preserved_in_definition", "capsule definition", "Declarative contract remains in the definition.")
    elif path.startswith("recipes/") or path == "learning/promoted_lessons.yaml":
        route = ("moved_to_guidance", "guidance", "Authored guidance moves to the guidance owner.")
    elif path == "quality/rules.yaml":
        route = ("converted_to_rubric", "quality rubric", "Object quality rules become rubric criteria.")
    elif path == "quality/release_gates.yaml":
        pointer = section.section_id.split("#yaml:", 1)[-1]
        direct_list_item = bool(re.search(r"/\d+$", pointer))
        if direct_list_item and section.yaml_value_type == "scalar":
            route = ("converted_to_rubric", "quality rubric", "String gate entries become rubric criteria.")
        else:
            route = ("converted_to_checker", "release checker", "Structured gate entries become executable checkers.")
    elif path.startswith("assets/"):
        route = ("moved_to_asset", "asset store", "Binary asset moves to the asset owner.")
    elif path.startswith("examples/"):
        route = ("moved_to_example", "examples", "Example content moves to the examples owner.")
    elif path.startswith("scripts/"):
        route = ("moved_to_runner", "runner", "Executable source moves to the runner owner.")
    elif path in {"CARD.md", "index.md"}:
        route = ("generated_view", "generated views", "Duplicated metadata and navigation become generated views.")
    else:
        route = ("preserved_in_definition", "capsule definition", "Authored source remains explicitly preserved.")
    return PreservationDisposition(
        section_id=section.section_id,
        disposition=route[0],
        target_owner=route[1],
        rationale=route[2],
    )


def build_preservation_manifest(
    snapshot: PackageSnapshot, sections: list[SectionRecord]
) -> PreservationManifest:
    dispositions = [classify_repo_showcase_section(section) for section in sections]
    return PreservationManifest(
        package_digest=snapshot.package_digest,
        sections=sections,
        dispositions=dispositions,
        coverage_percent=100.0 if sections else 100.0,
        unclassified=[],
        silent_deletions=[],
    )


def validate_preservation_manifest(manifest: PreservationManifest) -> ResultEnvelope:
    section_ids = [section.section_id for section in manifest.sections]
    disposition_ids = [item.section_id for item in manifest.dispositions]
    section_set = set(section_ids)
    disposition_set = set(disposition_ids)
    missing = sorted(section_set - disposition_set)
    extra = sorted(disposition_set - section_set)
    duplicate_sections = sorted(item for item, count in Counter(section_ids).items() if count > 1)
    duplicate_dispositions = sorted(
        item for item, count in Counter(disposition_ids).items() if count > 1
    )
    silent_deletions = sorted(
        item.section_id
        for item in manifest.dispositions
        if item.disposition == "obsolete_with_evidence"
        and next((section.promise_affecting for section in manifest.sections if section.section_id == item.section_id), False)
    )
    classified = len(section_set & disposition_set)
    coverage = 100.0 if not section_set else round(classified / len(section_set) * 100.0, 10)
    data = {
        "coverage_percent": coverage,
        "unclassified": missing,
        "silent_deletions": silent_deletions,
    }
    issues: list[Issue] = []
    if missing:
        issues.append(
            Issue(
                code="preservation_unclassified",
                message="Inventoried sections are missing preservation dispositions.",
                subject="preservation_manifest",
                details={"section_ids": missing},
            )
        )
    if extra:
        issues.append(
            Issue(
                code="preservation_unknown_section",
                message="Preservation dispositions reference sections outside the inventory.",
                subject="preservation_manifest",
                details={"section_ids": extra},
            )
        )
    if duplicate_sections or duplicate_dispositions:
        issues.append(
            Issue(
                code="preservation_duplicate_section",
                message="Preservation inventory and dispositions must not contain duplicate section IDs.",
                subject="preservation_manifest",
                details={
                    "inventory_section_ids": duplicate_sections,
                    "disposition_section_ids": duplicate_dispositions,
                },
            )
        )
    if silent_deletions:
        issues.append(
            Issue(
                code="preservation_silent_deletion",
                message="Promise-affecting sections cannot be marked obsolete.",
                subject="preservation_manifest",
                details={"section_ids": silent_deletions},
            )
        )
    if issues or coverage != 100.0:
        return failure("incomplete", issues, data)
    return success("complete", data)


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
