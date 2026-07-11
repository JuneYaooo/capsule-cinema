# Capsule Core Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first compatibility foundation that reads every current v1 capsule into one normalized model and gives creators one stable CLI for discovery, inspection, diagnosis, planning, and execution without exposing preset-versus-local-runner routing.

**Architecture:** Add a focused `src.capsules` package in front of the existing v1 loader and two existing runners. The package owns stable result contracts, a normalized read model, a read-only v1 adapter, catalog and doctor services, and an internal dispatch plan; `scripts/capsule.py` is a thin JSON CLI over those services. This slice deliberately delegates production to `run_video.py` and `run_capsule.py`, so it improves the creator surface without rewriting packages or production behavior.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML 6, `argparse`, `subprocess`, and standard-library `unittest`.

## Global Constraints

- The open-source repository remains a self-contained, local-first production core; do not add accounts, hosted registries, markets, ratings, payment, cloud sync, or remote runners.
- `capsule.yaml` remains the v1 package identity source; Foundation reads existing auxiliary v1 files but never rewrites a package.
- Loading and running a v1 package must not modify `capsule.yaml`, `CARD.md`, contracts, recipes, assets, examples, quality files, or learning files.
- The normalized model is schema-neutral and must not leak SQLite fallback behavior.
- The public `list`, `show`, `doctor`, `plan`, and `run` surfaces must not require the creator to choose `preset` or `local_script`; runner kind may appear only in diagnostic/internal data.
- Foundation supports only existing v1 packages and delegation to existing runners. Native v2 definitions, Releases, Instances, Macro Controls, Production Blocks, compiled stage contexts, evidence-bound gates, and Lesson Proposals belong to later plans.
- Use Python 3.12 and the already-declared `pydantic>=2.0.0` and `PyYAML>=6.0.0`; add no dependency.
- Use `python3.12 -m unittest`, not pytest.
- The worktree contains unrelated user changes, staged deletions, and untracked tests. Never reset, clean, stage all files, or overwrite them; every commit in this plan must use explicit paths and `git commit --only`.
- New tests use the unique `tests/python/test_capsule_core_*` prefix.

---

## Delivery Roadmap

This specification is intentionally split into four independently usable implementation plans. Only the first plan is detailed below.

1. **Foundation — this plan:** normalized model, read-only v1 adapter, catalog/show/doctor, internal unified dispatch, and one creator CLI. Exit criterion: all eight current capsules can be listed and shown, both runner families can be planned through the same command, and real execution still delegates unchanged.
2. **Native definition and instance:** define the native `capsule.yaml` schema, native loader, generated card, release digest/lock, Capsule Release and Capsule Instance models, macro-control validation, and v1/native loader coexistence. Exit criterion: a native package has one authored metadata source and a reproducible configured instance.
3. **Blocks, compiler, quality, and learning:** add shallow `Capsule -> Block` dependencies, locked/vendored Block snapshots, per-stage compilation and reports, executable checkers/evidence-bound rubrics, run evidence, and reviewed Lesson Proposals. Exit criterion: stage context and blockers are measurable and a lesson can only become a versioned diff.
4. **Authoring and migration:** add author validation/pack/install commands, deterministic offline archives, migrate `art_motion` then the remaining pilots in the approved order, and retire duplicated canonical documentation only after parity. Exit criterion: all active capsules use the native format without destructive v1 conversion.

The later plans must depend only on the interfaces documented in this plan. They may extend `CapsuleDefinition` with native release/instance composition, but they must not change the `Issue`, `ResultEnvelope`, `load_definition`, catalog, or dispatch call shapes without an explicit compatibility migration.

## File Map

| Path | Responsibility |
| --- | --- |
| `lib/src/capsules/__init__.py` | Stable public imports for the foundation package. |
| `lib/src/capsules/result.py` | Machine-readable issue and operation-result envelope. |
| `lib/src/capsules/model.py` | Schema-neutral normalized capsule read model. |
| `lib/src/capsules/v1_adapter.py` | Pure, read-only conversion from one resolved v1 directory. |
| `lib/src/capsules/loader.py` | Package resolution, schema detection, and adapter routing. |
| `lib/src/capsules/catalog.py` | Deterministic local discovery and detail lookup. |
| `lib/src/capsules/doctor.py` | Package integrity and local runner-readiness checks. |
| `lib/src/capsules/dispatch.py` | Internal construction and execution of legacy runner commands. |
| `scripts/capsule.py` | Unified creator CLI: `list`, `show`, `doctor`, `plan`, `run`. |
| `tests/python/test_capsule_core_*.py` | Isolated unit/contract tests for each responsibility. |
| `references/capsule-core-cli.md` | Foundation user contract and migration-safe examples. |

### Task 1: Stable operation result contract

**Files:**
- Create: `lib/src/capsules/__init__.py`
- Create: `lib/src/capsules/result.py`
- Create: `tests/python/test_capsule_core_result.py`

**Interfaces:**
- Consumes: Pydantic 2 `BaseModel`, `Field`; standard `typing.Any`, `Literal`.
- Produces: `Issue(code: str, message: str, severity: Literal["info", "warning", "error"] = "error", subject: str = "", remediation: str = "", details: dict[str, Any] = {})`; `ResultEnvelope(ok: bool, status: str, data: dict[str, Any] = {}, issues: list[Issue] = [])`; `success(status: str, data: dict[str, Any] | None = None, issues: list[Issue] | None = None) -> ResultEnvelope`; `failure(status: str, issues: list[Issue], data: dict[str, Any] | None = None) -> ResultEnvelope`.

- [ ] **Step 1: Write the failing contract test**

```python
import json
import unittest

from src.capsules.result import Issue, ResultEnvelope, failure, success


class CapsuleCoreResultTests(unittest.TestCase):
    def test_success_serializes_stable_defaults(self) -> None:
        result = success("catalog_ready", {"count": 2})
        self.assertEqual(
            json.loads(result.model_dump_json()),
            {
                "ok": True,
                "status": "catalog_ready",
                "data": {"count": 2},
                "issues": [],
            },
        )

    def test_failure_preserves_structured_remediation(self) -> None:
        issue = Issue(
            code="capsule_not_found",
            message="Capsule 'missing' was not found.",
            subject="missing",
            remediation="Run `capsule.py list` to inspect local capsules.",
            details={"search_roots": ["/tmp/capsules"]},
        )
        result = failure("not_found", [issue])
        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].code, "capsule_not_found")
        self.assertEqual(result.issues[0].severity, "error")

    def test_mutable_defaults_are_not_shared(self) -> None:
        first = ResultEnvelope(ok=True, status="one")
        second = ResultEnvelope(ok=True, status="two")
        first.data["changed"] = True
        first.issues.append(Issue(code="x", message="x"))
        self.assertEqual(second.data, {})
        self.assertEqual(second.issues, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and confirm the missing package failure**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules'`.

- [ ] **Step 3: Implement the minimal result models and public package file**

```python
# lib/src/capsules/result.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "error"
    subject: str = ""
    remediation: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ResultEnvelope(BaseModel):
    ok: bool
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    issues: list[Issue] = Field(default_factory=list)


def success(
    status: str,
    data: dict[str, Any] | None = None,
    issues: list[Issue] | None = None,
) -> ResultEnvelope:
    return ResultEnvelope(ok=True, status=status, data=data or {}, issues=issues or [])


def failure(
    status: str,
    issues: list[Issue],
    data: dict[str, Any] | None = None,
) -> ResultEnvelope:
    return ResultEnvelope(ok=False, status=status, data=data or {}, issues=issues)
```

```python
# lib/src/capsules/__init__.py
"""Local-first capsule core public contracts."""

from src.capsules.result import Issue, ResultEnvelope, failure, success

__all__ = ["Issue", "ResultEnvelope", "failure", "success"]
```

- [ ] **Step 4: Run the focused test**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit only this task's files**

```bash
git add -f lib/src/capsules/__init__.py lib/src/capsules/result.py tests/python/test_capsule_core_result.py
git commit --only lib/src/capsules/__init__.py lib/src/capsules/result.py tests/python/test_capsule_core_result.py -m "feat: add capsule core result contract"
```

### Task 2: Schema-neutral normalized capsule model

**Files:**
- Create: `lib/src/capsules/model.py`
- Modify: `lib/src/capsules/__init__.py`
- Create: `tests/python/test_capsule_core_model.py`

**Interfaces:**
- Consumes: `Issue` only at service boundaries, not inside definition data.
- Produces: `CapsuleMetadata`, `CapsulePromise`, `CapsuleMatch`, `CapsuleInput`, `CapsuleInterface`, `CapsuleRunner`, `CapsuleImplementation`, `CapsuleDefinition`; `CapsuleDefinition.public_summary() -> dict[str, Any]`.
- Contract: normalized `version` is always a non-empty string; `source_schema` is `capsule.package.v1` for this slice; `runner.kind` is internal diagnostic state and `public_summary()` excludes it.

- [ ] **Step 1: Write the failing model test**

```python
import unittest

from pydantic import ValidationError

from src.capsules.model import (
    CapsuleDefinition,
    CapsuleImplementation,
    CapsuleInput,
    CapsuleInterface,
    CapsuleMatch,
    CapsuleMetadata,
    CapsulePromise,
    CapsuleRunner,
)


def definition() -> CapsuleDefinition:
    return CapsuleDefinition(
        metadata=CapsuleMetadata(
            name="art_motion",
            display_name="Art Motion",
            version="1",
            status="active",
            source_schema="capsule.package.v1",
            source_path="/tmp/art_motion.capsule",
        ),
        promise=CapsulePromise(summary="Turn a prompt into an art-motion short."),
        match=CapsuleMatch(
            category="art_transition",
            workflow="art_first_last_frame_video",
            capabilities=["image_to_video"],
            tags=["art"],
            when_to_use=["art"],
            when_not_to_use=[],
        ),
        interface=CapsuleInterface(
            inputs={
                "prompt": CapsuleInput(type="string", required=True),
                "mood": CapsuleInput(type="string", default="auto", options=["auto", "novel"]),
            }
        ),
        implementation=CapsuleImplementation(
            runner=CapsuleRunner(kind="local_script", entrypoint="scripts/run.py")
        ),
    )


class CapsuleCoreModelTests(unittest.TestCase):
    def test_public_summary_hides_runner_kind_and_entrypoint(self) -> None:
        summary = definition().public_summary()
        self.assertEqual(summary["name"], "art_motion")
        self.assertEqual(summary["required_inputs"], ["prompt"])
        self.assertNotIn("implementation", summary)
        self.assertNotIn("runner", summary)
        self.assertNotIn("entrypoint", str(summary))

    def test_input_options_are_preserved(self) -> None:
        self.assertEqual(definition().interface.inputs["mood"].options, ["auto", "novel"])

    def test_blank_identity_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CapsuleMetadata(
                name=" ",
                display_name="Broken",
                version="1",
                status="draft",
                source_schema="capsule.package.v1",
                source_path="/tmp/broken",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and confirm the module failure**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_model -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules.model'`.

- [ ] **Step 3: Implement the normalized model**

```python
# lib/src/capsules/model.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CapsuleMetadata(BaseModel):
    name: str
    display_name: str
    version: str
    status: str
    source_schema: str
    source_path: str

    @field_validator("name", "display_name", "version", "source_schema", "source_path")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class CapsulePromise(BaseModel):
    summary: str


class CapsuleMatch(BaseModel):
    category: str = ""
    workflow: str = ""
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    when_to_use: list[str] = Field(default_factory=list)
    when_not_to_use: list[str] = Field(default_factory=list)


class CapsuleInput(BaseModel):
    type: str
    required: bool = False
    description: str = ""
    default: Any = None
    options: list[Any] = Field(default_factory=list)


class CapsuleInterface(BaseModel):
    inputs: dict[str, CapsuleInput] = Field(default_factory=dict)


class CapsuleRunner(BaseModel):
    kind: Literal["preset", "local_script"]
    entrypoint: str


class CapsuleImplementation(BaseModel):
    runner: CapsuleRunner


class CapsuleDefinition(BaseModel):
    metadata: CapsuleMetadata
    promise: CapsulePromise
    match: CapsuleMatch
    interface: CapsuleInterface
    implementation: CapsuleImplementation

    def public_summary(self) -> dict[str, Any]:
        required = sorted(name for name, field in self.interface.inputs.items() if field.required)
        return {
            "name": self.metadata.name,
            "display_name": self.metadata.display_name,
            "version": self.metadata.version,
            "status": self.metadata.status,
            "summary": self.promise.summary,
            "category": self.match.category,
            "workflow": self.match.workflow,
            "capabilities": self.match.capabilities,
            "tags": self.match.tags,
            "when_to_use": self.match.when_to_use,
            "when_not_to_use": self.match.when_not_to_use,
            "required_inputs": required,
            "inputs": {
                name: field.model_dump(exclude_none=True)
                for name, field in sorted(self.interface.inputs.items())
            },
            "source_schema": self.metadata.source_schema,
        }
```

Update `lib/src/capsules/__init__.py` to export all eight model classes in addition to Task 1's exports.

- [ ] **Step 4: Run model and result tests**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result tests.python.test_capsule_core_model -v`

Expected: 6 tests PASS.

- [ ] **Step 5: Commit only the model task**

```bash
git add -f lib/src/capsules/__init__.py lib/src/capsules/model.py tests/python/test_capsule_core_model.py
git commit --only lib/src/capsules/__init__.py lib/src/capsules/model.py tests/python/test_capsule_core_model.py -m "feat: define normalized capsule model"
```

### Task 3: Read-only v1 adapter and schema-detecting loader

**Files:**
- Create: `lib/src/capsules/v1_adapter.py`
- Create: `lib/src/capsules/loader.py`
- Create: `tests/python/test_capsule_core_v1_adapter.py`

**Interfaces:**
- Consumes: Task 2 model classes; existing `src.capsule_package_loader.resolve_capsule_dir`; PyYAML.
- Produces: `adapt_v1(capsule_dir: Path) -> CapsuleDefinition`; `detect_schema(capsule_dir: Path) -> str`; `load_definition(name_or_path: str | Path, search_roots: list[str | Path] | None = None) -> CapsuleDefinition`.
- Failure contract: malformed YAML, a non-object manifest, unsupported schema, missing/invalid input schema, invalid execution mode, and missing declared entrypoint raise `CapsuleLoadError(code: str, message: str, subject: str, details: dict[str, Any])`.
- Read-only contract: no function opens package paths for writing and no load path calls `load_capsule()` because that function can invoke the retired SQLite compatibility path.

- [ ] **Step 1: Write adapter tests with a disposable v1 package**

```python
import tempfile
import unittest
from pathlib import Path

from src.capsules.loader import CapsuleLoadError, load_definition


MANIFEST = """schema_version: capsule.package.v1
profile: video.okf.capsule.v1
name: demo
display_name: Demo Capsule
version: 7
status: active
execution_mode: local_script
category: demo_video
primary_workflow: demo_workflow
summary: Produce a deterministic demo video.
capabilities: [image_to_video]
tags: [demo]
when_to_use: [demo, tutorial]
when_not_to_use: [live_stream]
entrypoints:
  preset: general_video
  local_script: scripts/run_demo.py
"""

INPUTS = """fields:
  prompt:
    type: string
    required: true
  mood:
    type: string
    required: false
    default: calm
    enum: [calm, vivid]
"""


class CapsuleCoreV1AdapterTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        package = root / "demo.capsule"
        (package / "contracts").mkdir(parents=True)
        (package / "scripts").mkdir()
        (package / "capsule.yaml").write_text(MANIFEST, encoding="utf-8")
        (package / "contracts" / "input_schema.yaml").write_text(INPUTS, encoding="utf-8")
        (package / "scripts" / "run_demo.py").write_text("print('demo')\n", encoding="utf-8")
        return package

    def test_adapts_v1_without_changing_package_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            before = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}
            capsule = load_definition("demo", search_roots=[Path(tmp)])
            after = {path: path.read_bytes() for path in package.rglob("*") if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(capsule.metadata.version, "7")
            self.assertEqual(capsule.interface.inputs["mood"].options, ["calm", "vivid"])
            self.assertEqual(capsule.implementation.runner.kind, "local_script")
            self.assertTrue(Path(capsule.implementation.runner.entrypoint).is_absolute())

    def test_rejects_unknown_schema_with_stable_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "capsule.yaml").write_text(
                MANIFEST.replace("capsule.package.v1", "capsule.package.v99"),
                encoding="utf-8",
            )
            with self.assertRaises(CapsuleLoadError) as raised:
                load_definition(package)
            self.assertEqual(raised.exception.code, "unsupported_capsule_schema")

    def test_rejects_missing_local_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self.make_package(Path(tmp))
            (package / "scripts" / "run_demo.py").unlink()
            with self.assertRaises(CapsuleLoadError) as raised:
                load_definition(package)
            self.assertEqual(raised.exception.code, "runner_entrypoint_missing")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and confirm the loader module is missing**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_v1_adapter -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules.loader'`.

- [ ] **Step 3: Implement the adapter and loader**

Implement `CapsuleLoadError` with public attributes `code`, `subject`, and `details`. Add private `_read_object(path: Path) -> dict[str, Any]` that uses `yaml.safe_load`, translates file/YAML/type errors to `invalid_capsule_document`, and never writes.

Implement `adapt_v1` exactly as follows:

```python
def adapt_v1(capsule_dir: Path) -> CapsuleDefinition:
    manifest = _read_object(capsule_dir / "capsule.yaml")
    input_document = _read_object(capsule_dir / "contracts" / "input_schema.yaml")
    fields = input_document.get("fields", {})
    if not isinstance(fields, dict):
        raise CapsuleLoadError("invalid_input_schema", "fields must be an object", str(capsule_dir))
    inputs: dict[str, CapsuleInput] = {}
    for name, raw in fields.items():
        if not isinstance(raw, dict):
            raise CapsuleLoadError("invalid_input_schema", f"field {name!r} must be an object", str(capsule_dir))
        options = raw.get("enum", [])
        if not isinstance(options, list):
            raise CapsuleLoadError("invalid_input_schema", f"field {name!r} enum must be a list", str(capsule_dir))
        inputs[str(name)] = CapsuleInput(
            type=str(raw.get("type") or "string"),
            required=bool(raw.get("required", False)),
            description=str(raw.get("description") or ""),
            default=raw.get("default"),
            options=options,
        )
    mode = str(manifest.get("execution_mode") or "")
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    if mode == "local_script":
        relative = str(entrypoints.get("local_script") or "")
        entrypoint = (capsule_dir / relative).resolve()
        if not relative or not entrypoint.is_relative_to(capsule_dir.resolve()) or not entrypoint.is_file():
            raise CapsuleLoadError("runner_entrypoint_missing", "Declared local runner does not exist", str(capsule_dir))
        runner = CapsuleRunner(kind="local_script", entrypoint=str(entrypoint))
    elif mode == "preset":
        preset = str(entrypoints.get("preset") or "general_video")
        runner = CapsuleRunner(kind="preset", entrypoint=preset)
    else:
        raise CapsuleLoadError("invalid_runner_kind", f"Unsupported execution_mode: {mode!r}", str(capsule_dir))
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
```

In `loader.py`, define `CapsuleLoadError.__init__(self, code: str, message: str, subject: str = "", details: dict[str, Any] | None = None)`, resolve with the existing `resolve_capsule_dir`, and translate `CapsulePackageError` to `CapsuleLoadError("capsule_not_found", str(exc), str(name_or_path), {"search_roots": [str(root) for root in search_roots or []]})`. Make `detect_schema()` read only `capsule.yaml` and route only `capsule.package.v1` to `adapt_v1`. Wrap Pydantic `ValidationError` as `CapsuleLoadError("invalid_capsule_definition", "Normalized capsule validation failed.", str(capsule_dir), {"errors": exc.errors(include_url=False)})`.

- [ ] **Step 4: Run focused and cumulative tests**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result tests.python.test_capsule_core_model tests.python.test_capsule_core_v1_adapter -v`

Expected: 9 tests PASS.

- [ ] **Step 5: Commit only adapter files**

```bash
git add -f lib/src/capsules/v1_adapter.py lib/src/capsules/loader.py tests/python/test_capsule_core_v1_adapter.py
git commit --only lib/src/capsules/v1_adapter.py lib/src/capsules/loader.py tests/python/test_capsule_core_v1_adapter.py -m "feat: adapt v1 capsules into core model"
```

### Task 4: Deterministic local catalog and public detail service

**Files:**
- Create: `lib/src/capsules/catalog.py`
- Create: `tests/python/test_capsule_core_catalog.py`

**Interfaces:**
- Consumes: `load_definition`, `CapsuleLoadError`, `ResultEnvelope`, `Issue`, `success`, `failure`.
- Produces: `discover_capsules(search_roots: list[str | Path] | None = None) -> ResultEnvelope`; `show_capsule(name_or_path: str | Path, search_roots: list[str | Path] | None = None) -> ResultEnvelope`.
- Contract: discovery scans immediate `*.capsule` child directories only, sorts by normalized capsule name, reports invalid packages as issues without hiding valid packages, and never exposes implementation in catalog entries.

- [ ] **Step 1: Write catalog tests**

```python
import tempfile
import unittest
from pathlib import Path

from src.capsules.catalog import discover_capsules, show_capsule


def write_preset(root: Path, name: str, schema: str = "capsule.package.v1") -> None:
    package = root / f"{name}.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "capsule.yaml").write_text(
        f"""schema_version: {schema}
name: {name}
display_name: {name.title()}
version: 1
status: active
execution_mode: preset
summary: {name} summary
category: demo
primary_workflow: demo
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints: {{preset: general_video}}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text("fields: {}\n", encoding="utf-8")


class CapsuleCoreCatalogTests(unittest.TestCase):
    def test_discovery_is_sorted_and_keeps_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_preset(root, "zeta")
            write_preset(root, "alpha")
            write_preset(root, "broken", "capsule.package.v99")
            result = discover_capsules([root])
            self.assertTrue(result.ok)
            self.assertEqual([item["name"] for item in result.data["capsules"]], ["alpha", "zeta"])
            self.assertEqual(result.data["count"], 2)
            self.assertEqual(result.issues[0].code, "unsupported_capsule_schema")
            self.assertNotIn("implementation", result.data["capsules"][0])

    def test_show_returns_stable_not_found_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = show_capsule("missing", [Path(tmp)])
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "not_found")
            self.assertEqual(result.issues[0].code, "capsule_not_found")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and confirm catalog import failure**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_catalog -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules.catalog'`.

- [ ] **Step 3: Implement catalog services**

Use `DEFAULT_SEARCH_ROOTS` from the existing package loader when roots are absent. Deduplicate resolved package paths across roots. For each load error, append:

```python
Issue(
    code=exc.code,
    message=str(exc),
    severity="warning",
    subject=exc.subject,
    remediation="Run the doctor command for package diagnostics.",
    details=exc.details,
)
```

Return `success("catalog_ready", {"count": len(items), "capsules": items}, issues)` after sorting `items` by `item["name"]`. `show_capsule` returns `success("capsule_ready", {"capsule": definition.public_summary()})`; translate a loader error to `failure("not_found" if exc.code == "capsule_not_found" else "invalid_capsule", [Issue(code=exc.code, message=str(exc), subject=exc.subject, remediation="Run the doctor command for package diagnostics.", details=exc.details)])`.

- [ ] **Step 4: Run catalog and prior tests**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result tests.python.test_capsule_core_model tests.python.test_capsule_core_v1_adapter tests.python.test_capsule_core_catalog -v`

Expected: 11 tests PASS.

- [ ] **Step 5: Commit only catalog files**

```bash
git add -f lib/src/capsules/catalog.py tests/python/test_capsule_core_catalog.py
git commit --only lib/src/capsules/catalog.py tests/python/test_capsule_core_catalog.py -m "feat: add local capsule catalog"
```

### Task 5: Package and local-readiness doctor

**Files:**
- Create: `lib/src/capsules/doctor.py`
- Create: `tests/python/test_capsule_core_doctor.py`

**Interfaces:**
- Consumes: `load_definition`; existing `src.capsule_package_loader.load_runtime_contract`; existing `src.capsule_preflight.run_preflight`, `src.capsule_preflight.to_report`; existing `src.capsule_resolver.load_all_tools`; standard environment mapping.
- Produces: `doctor_capsule(name_or_path: str | Path, search_roots: list[str | Path] | None = None, environ: dict[str, str] | None = None, tools: dict[str, Any] | None = None) -> ResultEnvelope`.
- Contract: doctor distinguishes `ready`, `needs_confirmation`, `blocked`, and `invalid_capsule`. It checks v1 structure and runner entrypoint through the loader, then performs capability preflight only when `contracts/runtime.yaml` declares a non-empty `roles` object. A package with no roles is structurally ready with an informational `preflight_not_declared` issue, never falsely “verified.”

- [ ] **Step 1: Write doctor tests**

```python
import tempfile
import unittest
from pathlib import Path

from src.capsules.doctor import doctor_capsule


def write_package(root: Path, runtime: str) -> Path:
    package = root / "demo.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "capsule.yaml").write_text(
        """schema_version: capsule.package.v1
name: demo
display_name: Demo
version: 1
status: active
execution_mode: preset
summary: Demo
category: demo
primary_workflow: demo
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints: {preset: general_video}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text("fields: {}\n", encoding="utf-8")
    (package / "contracts" / "runtime.yaml").write_text(runtime, encoding="utf-8")
    return package


class CapsuleCoreDoctorTests(unittest.TestCase):
    def test_no_declared_roles_is_structurally_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "roles: {}\noutput_contract: {}\n")
            result = doctor_capsule(package, environ={}, tools={})
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "ready")
            self.assertEqual(result.issues[0].code, "preflight_not_declared")

    def test_missing_capability_blocks_with_preflight_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(
                Path(tmp),
                """roles:
  image:
    modality: image
    requires: [transparent_background]
output_contract: {}
""",
            )
            result = doctor_capsule(package, environ={}, tools={})
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.issues[0].code, "local_capability_blocked")
            self.assertEqual(result.data["preflight"]["blocked"], ["image"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and confirm doctor module failure**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_doctor -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules.doctor'`.

- [ ] **Step 3: Implement doctor translation**

After `load_definition`, read the v1 runtime contract. If `roles` is empty, return:

```python
success(
    "ready",
    {"capsule": definition.public_summary(), "preflight": None},
    [Issue(
        code="preflight_not_declared",
        message="Capsule declares no capability roles; only package structure was checked.",
        severity="info",
        subject=definition.metadata.name,
    )],
)
```

Otherwise set `selected_tools = tools if tools is not None else load_all_tools()` and `selected_environ = environ if environ is not None else dict(os.environ)`. Call `run_preflight({"name": definition.metadata.name, "roles": roles, "output_contract": runtime.get("output_contract") if isinstance(runtime.get("output_contract"), dict) else {}}, selected_tools, scan_available_env(selected_environ))`, convert it with `to_report`, and map status:

- `ok` -> envelope `ok=True`, status `ready`, no issues;
- `needs_confirmation` -> envelope `ok=True`, status `needs_confirmation`, one warning `local_substitution_requires_confirmation`;
- `blocked` -> envelope `ok=False`, status `blocked`, one error `local_capability_blocked`, remediation `Configure one of the required local tools or environment keys, then run doctor again.`.

Translate loader/runtime document errors to `invalid_capsule` and preserve their stable issue codes.

- [ ] **Step 4: Run doctor plus cumulative suite**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result tests.python.test_capsule_core_model tests.python.test_capsule_core_v1_adapter tests.python.test_capsule_core_catalog tests.python.test_capsule_core_doctor -v`

Expected: 13 tests PASS.

- [ ] **Step 5: Commit only doctor files**

```bash
git add -f lib/src/capsules/doctor.py tests/python/test_capsule_core_doctor.py
git commit --only lib/src/capsules/doctor.py tests/python/test_capsule_core_doctor.py -m "feat: diagnose local capsule readiness"
```

### Task 6: Internal unified dispatch plan and executor

**Files:**
- Create: `lib/src/capsules/dispatch.py`
- Create: `tests/python/test_capsule_core_dispatch.py`

**Interfaces:**
- Consumes: `load_definition`; `ResultEnvelope`; standard `subprocess.run`, `os.environ`, `sys.executable`.
- Produces: `DispatchPlan(capsule: str, action: Literal["plan", "run"], command: list[str], cwd: str, environment: dict[str, str], output_dir: str)`; `build_dispatch_plan(name_or_path: str | Path, topic: str, params: dict[str, Any], output_dir: str | Path, action: Literal["plan", "run"], search_roots: list[str | Path] | None = None) -> DispatchPlan`; `execute_dispatch_plan(plan: DispatchPlan) -> ResultEnvelope`.
- Public contract: callers always supply capsule, topic, params, output directory, and action. They never supply runner kind.
- Internal contract: local runners delegate to `scripts/run_capsule.py`; preset runners delegate to `scripts/run_video.py`; action `plan` adds `--dry-run` or `--storyboard_only` respectively.

- [ ] **Step 1: Write command-planning tests**

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.capsules.dispatch import build_dispatch_plan, execute_dispatch_plan


def write_package(root: Path, name: str, mode: str) -> Path:
    package = root / f"{name}.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "scripts").mkdir()
    local = "\n  local_script: scripts/run.py" if mode == "local_script" else ""
    (package / "capsule.yaml").write_text(
        f"""schema_version: capsule.package.v1
name: {name}
display_name: {name}
version: 1
status: active
execution_mode: {mode}
summary: demo
category: demo
primary_workflow: demo
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints:
  preset: general_video{local}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text("fields: {}\n", encoding="utf-8")
    (package / "scripts" / "run.py").write_text("print('run')\n", encoding="utf-8")
    return package


class CapsuleCoreDispatchTests(unittest.TestCase):
    def test_plan_hides_local_runner_behind_common_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_package(root, "local", "local_script")
            output = root / "out"
            plan = build_dispatch_plan(package, "topic", {"mood": "calm"}, output, "plan")
            self.assertTrue(plan.command[1].endswith("scripts/run_capsule.py"))
            self.assertIn("--dry-run", plan.command)
            self.assertIn("--params", plan.command)
            self.assertTrue((output / "inputs" / "params.requested.json").is_file())

    def test_plan_maps_preset_params_and_output_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_package(root, "preset", "preset")
            output = root / "out"
            plan = build_dispatch_plan(
                package,
                "topic",
                {"target_duration": 18, "aspect_ratio": "9:16", "add_subtitles": False},
                output,
                "plan",
            )
            self.assertTrue(plan.command[1].endswith("scripts/run_video.py"))
            self.assertIn("--storyboard_only", plan.command)
            self.assertEqual(plan.environment["OPENCLAW_OUTPUT_DIR"], str(output.resolve()))
            self.assertIn("18", plan.command)
            self.assertIn("false", plan.command)

    @patch("src.capsules.dispatch.subprocess.run")
    def test_executor_returns_child_exit_evidence(self, run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_package(Path(tmp), "preset", "preset")
            plan = build_dispatch_plan(package, "topic", {}, Path(tmp) / "out", "run")
            run.return_value.returncode = 7
            result = execute_dispatch_plan(plan)
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "run_failed")
            self.assertEqual(result.data["return_code"], 7)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and confirm dispatch module failure**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_dispatch -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules.dispatch'`.

- [ ] **Step 3: Implement dispatch planning and execution**

Define the Pydantic `DispatchPlan`; locate repository root with `Path(__file__).resolve().parents[3]`. Always create `<output>/inputs/params.requested.json` by writing pretty JSON plus a trailing newline before constructing either command. This request snapshot is run input, not a capsule-package mutation.

For local runner, build:

```python
[
    sys.executable,
    str(root / "scripts" / "run_capsule.py"),
    "--capsule", definition.metadata.source_path,
    "--topic", topic,
    "--params", str(params_path),
    "--output-dir", str(output.resolve()),
] + (["--dry-run"] if action == "plan" else [])
```

For preset, build the base command:

```python
[
    sys.executable,
    str(root / "scripts" / "run_video.py"),
    "--capsule", definition.metadata.source_path,
    "--user_requirements", topic,
] + (["--storyboard_only"] if action == "plan" else [])
```

Append only these supported mappings when present: `target_duration -> --target_duration int`, `aspect_ratio -> --aspect_ratio str`, `platform -> --platform str`, `add_subtitles -> --add_subtitles true|false`, `add_background_music -> --add_background_music true|false`, `background_music_path -> --background_music_path str`, `bgm_volume -> --bgm_volume float`, `voice_volume -> --voice_volume float`, `image_engine -> --image_engine str`, `video_engine -> --video_engine str`, `user_reference_images -> --user_reference_images` compact JSON, and `accept_preflight_changes=True -> --accept_preflight_changes`. If any other key exists, raise `DispatchError(code="unsupported_preset_parameter", details={"parameters": sorted(unknown)})` instead of silently dropping it.

Set `environment` to `{"OPENCLAW_OUTPUT_DIR": str(output.resolve())}` for preset and `{}` for local. `execute_dispatch_plan` merges `os.environ` with `plan.environment`, calls `subprocess.run(plan.command, cwd=plan.cwd, env=merged_env)`, and returns:

```python
success(
    "planned" if plan.action == "plan" else "completed",
    {"capsule": plan.capsule, "action": plan.action, "output_dir": plan.output_dir, "return_code": 0},
)
```

on zero. Execute the child with `text=True, capture_output=True`; after completion, forward both captured streams to the parent process's stderr so stdout remains a single machine-readable envelope. On nonzero return exactly:

```python
failure(
    "run_failed",
    [Issue(
        code="runner_failed",
        message=f"Capsule runner exited with code {completed.returncode}.",
        subject=plan.capsule,
        remediation="Inspect the runner logs emitted on stderr and the output directory, then retry.",
        details={"return_code": completed.returncode},
    )],
    {
        "capsule": plan.capsule,
        "action": plan.action,
        "output_dir": plan.output_dir,
        "return_code": completed.returncode,
    },
)
```

This preserves existing log text and progress events for a human terminal while reserving stdout for the stable CLI result contract; Foundation does not reinterpret those legacy logs.

- [ ] **Step 4: Run dispatch plus cumulative suite**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result tests.python.test_capsule_core_model tests.python.test_capsule_core_v1_adapter tests.python.test_capsule_core_catalog tests.python.test_capsule_core_doctor tests.python.test_capsule_core_dispatch -v`

Expected: 16 tests PASS.

- [ ] **Step 5: Commit only dispatch files**

```bash
git add -f lib/src/capsules/dispatch.py tests/python/test_capsule_core_dispatch.py
git commit --only lib/src/capsules/dispatch.py tests/python/test_capsule_core_dispatch.py -m "feat: unify capsule dispatch planning"
```

### Task 7: One creator CLI for discovery through execution

**Files:**
- Create: `scripts/capsule.py`
- Create: `tests/python/test_capsule_core_cli.py`

**Interfaces:**
- Consumes: `discover_capsules`, `show_capsule`, `doctor_capsule`, `build_dispatch_plan`, `execute_dispatch_plan`, `ResultEnvelope`.
- Produces: `build_parser() -> argparse.ArgumentParser`; `main(argv: list[str] | None = None) -> int`; CLI subcommands `list`, `show NAME`, `doctor NAME`, `plan NAME`, `run NAME`.
- Contract: every command prints exactly one final JSON `ResultEnvelope` to stdout; validation/operation failure exits 1; argument parse errors remain argparse exit 2. `plan` reports a redacted logical dispatch preview, not internal runner kind or entrypoint.

- [ ] **Step 1: Write CLI subprocess contract tests**

```python
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "capsule.py"


class CapsuleCoreCliTests(unittest.TestCase):
    def invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "lib"), str(ROOT / "scripts")])
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_list_discovers_real_capsules(self) -> None:
        result = self.invoke("list")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        names = {item["name"] for item in payload["data"]["capsules"]}
        self.assertIn("art_motion", names)
        self.assertIn("felt_asmr", names)

    def test_show_does_not_expose_runner_choice(self) -> None:
        result = self.invoke("show", "art_motion")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("local_script", serialized)
        self.assertNotIn("entrypoint", serialized)

    def test_plan_uses_same_surface_for_both_runner_families(self) -> None:
        for capsule in ("art_motion", "felt_asmr"):
            with self.subTest(capsule=capsule):
                result = self.invoke(
                    "plan", capsule,
                    "--topic", "A small test",
                    "--params-json", "{}",
                    "--output-dir", str(ROOT / "output" / "capsule-core-cli-test" / capsule),
                )
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(payload["status"], "dispatch_ready")
                self.assertEqual(payload["data"]["action"], "plan")
                self.assertNotIn("runner", payload["data"])
                self.assertNotIn("command", payload["data"])

    def test_missing_capsule_returns_json_failure(self) -> None:
        result = self.invoke("show", "does-not-exist")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["issues"][0]["code"], "capsule_not_found")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and confirm the CLI file is absent**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_cli -v`

Expected: FAIL because `scripts/capsule.py` does not exist or produces no JSON.

- [ ] **Step 3: Implement the CLI parser and service translation**

Use one shared helper for `plan` and `run` arguments:

```python
def add_execution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--params-json", default="{}")
    parser.add_argument("--output-dir", required=True)
```

Add `--root` with `action="append"` to `list`, `show`, and `doctor` only. Decode `--params-json` with `json.loads`; reject invalid or non-object JSON with `failure("invalid_request", [Issue(code="invalid_params_json", message="--params-json must be a JSON object.", subject=args.name, remediation="Pass an object such as --params-json '{}'.")])`.

Command behavior:

- `list`: call `discover_capsules(args.root)`;
- `show`: call `show_capsule(args.name, args.root)`;
- `doctor`: call `doctor_capsule(args.name, args.root)`;
- `plan`: call `build_dispatch_plan(args.name, args.topic, params, args.output_dir, "plan")` but do not execute it; return `success("dispatch_ready", {"capsule": plan.capsule, "action": "plan", "output_dir": plan.output_dir})`;
- `run`: call `build_dispatch_plan(args.name, args.topic, params, args.output_dir, "run")`, then `execute_dispatch_plan(plan)`.

Translate `CapsuleLoadError` and `DispatchError` into stable `Issue` values. Print with:

```python
print(result.model_dump_json(indent=2))
return 0 if result.ok else 1
```

Keep imports after inserting `<repo>/lib` and `<repo>/scripts` into `sys.path`, matching existing script conventions.

- [ ] **Step 4: Run all Foundation unit tests**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_result tests.python.test_capsule_core_model tests.python.test_capsule_core_v1_adapter tests.python.test_capsule_core_catalog tests.python.test_capsule_core_doctor tests.python.test_capsule_core_dispatch tests.python.test_capsule_core_cli -v`

Expected: 20 tests PASS.

- [ ] **Step 5: Commit only CLI files**

```bash
git add -f scripts/capsule.py tests/python/test_capsule_core_cli.py
git commit --only scripts/capsule.py tests/python/test_capsule_core_cli.py -m "feat: add unified capsule creator cli"
```

### Task 8: Real-package compatibility, documentation, and final verification

**Files:**
- Create: `tests/python/test_capsule_core_real_packages.py`
- Create: `references/capsule-core-cli.md`
- Modify: `package.json` only if its current `test` script has a Python `py_compile` file list; preserve all concurrent user changes and append only the eight new Python source paths.

**Interfaces:**
- Consumes: all Foundation public APIs and the eight checked-in v1 packages.
- Produces: a compatibility guard proving all current packages normalize read-only; user documentation for the common command surface.

- [ ] **Step 1: Add the real-package regression test**

```python
import hashlib
import unittest
from pathlib import Path

from src.capsules.catalog import discover_capsules
from src.capsules.loader import load_definition


ROOT = Path(__file__).resolve().parents[2]
CAPSULES = ROOT / "capsules"
EXPECTED = {
    "ai_open_source_tool_radar",
    "art_motion",
    "ecommerce_product_showcase",
    "felt_asmr",
    "guofeng_history",
    "high_abstraction_growth_card",
    "life_sim",
    "repo_showcase",
}


def digest_package(package: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class CapsuleCoreRealPackageTests(unittest.TestCase):
    def test_all_current_packages_load_without_mutation(self) -> None:
        packages = {path.stem: path for path in CAPSULES.glob("*.capsule")}
        self.assertEqual(set(packages), EXPECTED)
        before = {name: digest_package(path) for name, path in packages.items()}
        definitions = {name: load_definition(path) for name, path in packages.items()}
        after = {name: digest_package(path) for name, path in packages.items()}
        self.assertEqual(before, after)
        self.assertEqual(set(definitions), EXPECTED)
        self.assertEqual(
            {item.implementation.runner.kind for item in definitions.values()},
            {"preset", "local_script"},
        )

    def test_catalog_returns_every_current_package(self) -> None:
        result = discover_capsules([CAPSULES])
        self.assertTrue(result.ok)
        self.assertEqual({item["name"] for item in result.data["capsules"]}, EXPECTED)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the real-package tests before documenting**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_core_real_packages -v`

Expected: 2 tests PASS. If a checked-in package fails, fix only the adapter's normalization of a valid v1 shape and add the exact failing shape as a unit test; do not edit the package to satisfy the adapter.

- [ ] **Step 3: Write the Foundation CLI reference**

Create `references/capsule-core-cli.md` with these exact sections and commands:

````markdown
# Capsule Core CLI

`scripts/capsule.py` is the local creator surface for current capsule packages. It discovers, explains, diagnoses, plans, and runs a capsule without asking whether the package uses a preset or a local runner.

## Discover and inspect

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py list
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py show art_motion
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py doctor art_motion
```

All commands return a JSON result envelope with `ok`, `status`, `data`, and `issues`. An issue contains a stable `code`, human message, subject, remediation, severity, and optional details.

## Plan through one interface

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py plan art_motion \
  --topic "Ink flowers opening into a summer landscape" \
  --params-json '{"aspect_ratio":"9:16"}' \
  --output-dir output/art-motion-plan
```

`plan` validates and prepares dispatch but does not claim that a deliverable video exists. The same command works for every runner family.

## Run through one interface

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py run felt_asmr \
  --topic "A wool-felt strawberry mille-feuille" \
  --params-json '{"target_duration":20,"aspect_ratio":"9:16"}' \
  --output-dir output/felt-asmr-run
```

The command delegates to the existing production runner. The unified CLI forwards legacy runner logs to stderr and reserves stdout for the final JSON envelope; produced artifacts retain their current contracts.

## Foundation boundary

This compatibility layer does not rewrite v1 packages. Native definitions, configured instances, macro controls, Production Blocks, compiled stage contexts, release locks, run evidence, and lesson proposals are introduced by subsequent core plans.
````

- [ ] **Step 4: Add compile coverage without overwriting concurrent package changes**

First inspect: `git diff -- package.json && rg -n 'py_compile|"test"' package.json`.

If `package.json` contains an existing `py_compile` list, use `apply_patch` to append these paths to that same command while preserving every other current edit:

```text
lib/src/capsules/__init__.py
lib/src/capsules/result.py
lib/src/capsules/model.py
lib/src/capsules/v1_adapter.py
lib/src/capsules/loader.py
lib/src/capsules/catalog.py
lib/src/capsules/doctor.py
lib/src/capsules/dispatch.py
scripts/capsule.py
```

If no such list exists, do not modify `package.json`; use the explicit compile command in Step 5.

- [ ] **Step 5: Run syntax, Foundation, and existing capsule regression verification**

Run:

```bash
python3.12 -m py_compile \
  lib/src/capsules/__init__.py \
  lib/src/capsules/result.py \
  lib/src/capsules/model.py \
  lib/src/capsules/v1_adapter.py \
  lib/src/capsules/loader.py \
  lib/src/capsules/catalog.py \
  lib/src/capsules/doctor.py \
  lib/src/capsules/dispatch.py \
  scripts/capsule.py
PYTHONPATH=lib:scripts python3.12 -m unittest discover -s tests/python -p 'test_capsule_core_*.py' -v
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_package_real_packages tests.python.test_run_video_preflight -v
```

Expected: `py_compile` exits 0; all Foundation tests PASS; the two named existing regression modules PASS. If either named module is absent because it remains an untracked user file, record that fact in the handoff and run every present `test_capsule_package_*` and `test_run_video_preflight` module without adding or deleting user files.

- [ ] **Step 6: Smoke-test the public local commands**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py list
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py show art_motion
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py doctor art_motion
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py plan art_motion --topic "Foundation smoke test" --params-json '{}' --output-dir output/capsule-core-foundation-smoke/art_motion
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py plan felt_asmr --topic "Foundation smoke test" --params-json '{}' --output-dir output/capsule-core-foundation-smoke/felt_asmr
```

Expected: every command emits a valid JSON envelope; `list` includes eight capsules; `show` excludes runner data; `doctor` reports evidence-backed readiness; both `plan` calls return `status: dispatch_ready` through identical public syntax. Do not invoke a paid/full production run as part of Foundation smoke verification.

- [ ] **Step 7: Review scope and commit the final compatibility slice**

Run `git diff --check`, `git status --short`, and `git diff --cached --name-status` first. Confirm unrelated staged deletions and user modifications are unchanged. Then commit only files created or deliberately amended by this task:

```bash
git add -f tests/python/test_capsule_core_real_packages.py references/capsule-core-cli.md
git commit --only tests/python/test_capsule_core_real_packages.py references/capsule-core-cli.md -m "docs: verify capsule core foundation"
```

If and only if Step 4 deliberately changed `package.json`, include it explicitly in both commands:

```bash
git add package.json
git commit --only tests/python/test_capsule_core_real_packages.py references/capsule-core-cli.md package.json -m "docs: verify capsule core foundation"
```

## Foundation Exit Criteria

- Every current v1 capsule normalizes into `CapsuleDefinition` without changing a package byte.
- Catalog and show expose creator-relevant promise, match, and input data without exposing runner selection.
- Doctor never equates structural validity with production verification and reports local blockers with evidence.
- Preset and local-runner capsules use identical public `plan` and `run` syntax.
- Unknown preset parameters fail explicitly instead of being ignored.
- Production remains delegated to the existing runners; their artifact and progress behavior is not rewritten.
- The result envelope and service signatures are stable enough for the native-definition plan to build on.
- No platform, hosted-service, account, market, rating, payment, sync, or remote-execution concept appears in source, CLI, tests, or documentation.
