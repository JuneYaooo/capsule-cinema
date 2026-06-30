# Capsule Canonical Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `capsules/<name>.capsule/` the canonical active capsule format, archive legacy zip packages, remove user-facing "v3" naming, and keep SQLite as legacy fallback.

**Architecture:** Introduce neutral package modules while keeping short compatibility wrappers for old imports. Move active packages into `capsules/`, move legacy zip packages into `archive/legacy_capsule_zips/`, and enforce canonical stage-readable package rules through validation and runtime tests. `run_video.py --capsule` should prefer directory packages and fall back to SQLite only when no package exists.

**Tech Stack:** Python 3.12, `unittest`, YAML via `pyyaml`, existing `scripts/run_video.py`, existing local SQLite capsule runtime.

## Global Constraints

- Active checked-in capsules live under `capsules/<name>.capsule/`.
- Legacy zip packages live under `archive/legacy_capsule_zips/`.
- SQLite remains supported as legacy/local evidence storage and explicit fallback.
- Public/current names avoid `v3`; use `capsule_package_*` names for current format code and docs.
- The canonical read stages are exactly `routing`, `planning`, `generation`, `qa`, and `learning`.
- The loader reads only files declared for the requested stage.
- Active packages reject migration metadata: `source`, `legacy_version`, and `converted_at`.
- Active packages reject unreferenced `recipes/*.md`.
- Active package recipe and config surfaces reject raw evidence, local paths, output paths, secrets, and remote URLs.
- Keep edits scoped to capsule canonical/archive work; do not remove SQLite features.

---

## File Structure

- `lib/src/capsule_package_loader.py`: current package loader API.
- `lib/src/capsule_v3_loader.py`: compatibility wrapper importing from `capsule_package_loader.py`.
- `scripts/capsule_package_validate.py`: current package validator CLI/API.
- `scripts/capsule_v3_validate.py`: compatibility wrapper importing from `capsule_package_validate.py`.
- `scripts/capsule_package_convert.py`: current package converter CLI/API.
- `scripts/capsule_v3_convert.py`: compatibility wrapper importing from `capsule_package_convert.py`.
- `scripts/capsule_runtime.py`: add package-to-runtime adapter and make package loading reusable.
- `scripts/run_video.py`: prefer package capsule loading before SQLite loading.
- `capsules/`: active directory-style packages.
- `archive/legacy_capsule_zips/`: old `.capsule.zip` packages.
- `references/capsule-package-format.md`: current format docs.
- `references/capsule-v3-format.md`: compatibility pointer or removed if all references update cleanly.
- `references/local-capsule-sqlite.md`, `references/production-guide.md`, `skill.md`: describe canonical packages and SQLite legacy status.
- `tests/python/test_capsule_package_loader.py`: current loader tests.
- `tests/python/test_capsule_package_validate.py`: current validator tests.
- `tests/python/test_capsule_package_real_packages.py`: real active package tests.
- `tests/python/test_capsule_runtime.py`: package preference and SQLite fallback tests.
- Existing `test_capsule_v3_*.py` files: either renamed or kept as compatibility smoke tests.

---

### Task 1: Neutral Loader Module And Canonical Search Root

**Files:**
- Create: `lib/src/capsule_package_loader.py`
- Modify: `lib/src/capsule_v3_loader.py`
- Create: `tests/python/test_capsule_package_loader.py`
- Modify or keep: `tests/python/test_capsule_v3_loader.py`

**Interfaces:**
- Consumes: existing functions from `lib/src/capsule_v3_loader.py`.
- Produces:
  - `resolve_capsule_dir(name_or_path: str | Path, search_roots: list[str | Path] | None = None) -> Path`
  - `load_capsule_card(...) -> dict[str, Any]`
  - `load_runtime_contract(...) -> dict[str, Any]`
  - `load_stage_context(...) -> dict[str, Any]`
  - `load_quality_rules(...) -> list[dict[str, Any]]`
  - `load_assets_index(...) -> list[dict[str, Any]]`

- [ ] **Step 1: Write failing canonical-root loader test**

Add this test to `tests/python/test_capsule_package_loader.py`:

```python
def test_default_search_root_is_capsules(self):
    from src import capsule_package_loader

    roots = [path.name for path in capsule_package_loader.DEFAULT_SEARCH_ROOTS]

    self.assertEqual(roots, ["capsules"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_package_loader.CapsulePackageLoaderTest.test_default_search_root_is_capsules
```

Expected: FAIL or import error because `src.capsule_package_loader` does not exist yet.

- [ ] **Step 3: Create neutral loader implementation**

Copy the current implementation from `lib/src/capsule_v3_loader.py` into `lib/src/capsule_package_loader.py`, then change:

```python
DEFAULT_SEARCH_ROOTS = [ROOT / "capsules"]
```

Keep the same exception class name for now:

```python
class CapsulePackageError(Exception):
    """Raised when a capsule package cannot be resolved or loaded."""
```

Use `CapsulePackageError` internally. In the compatibility wrapper, alias it back as `CapsuleV3Error`.

- [ ] **Step 4: Add compatibility wrapper**

Replace `lib/src/capsule_v3_loader.py` with:

```python
from __future__ import annotations

from src.capsule_package_loader import (  # noqa: F401
    CapsulePackageError as CapsuleV3Error,
    DEFAULT_SEARCH_ROOTS,
    load_assets_index,
    load_capsule_card,
    load_quality_rules,
    load_runtime_contract,
    load_stage_context,
    resolve_capsule_dir,
)
```

- [ ] **Step 5: Run focused loader tests**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_package_loader tests.python.test_capsule_v3_loader
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/src/capsule_package_loader.py lib/src/capsule_v3_loader.py tests/python/test_capsule_package_loader.py tests/python/test_capsule_v3_loader.py
git commit -m "feat: add canonical capsule package loader"
```

---

### Task 2: Archive Legacy Zips And Move Active Packages

**Files:**
- Move: `capsules_v3/*` -> `capsules/`
- Move: `capsules/*.zip` -> `archive/legacy_capsule_zips/`
- Modify: `.gitignore` if needed
- Modify: tests that reference `capsules_v3`

**Interfaces:**
- Consumes: `DEFAULT_SEARCH_ROOTS = [ROOT / "capsules"]`.
- Produces: active package directories at `capsules/<name>.capsule/`.

- [ ] **Step 1: Write failing real-package path test**

In `tests/python/test_capsule_package_real_packages.py`, add:

```python
def test_active_capsules_live_under_capsules_not_capsules_v3(self):
    self.assertTrue((ROOT / "capsules" / "repo_showcase.capsule" / "capsule.yaml").is_file())
    self.assertFalse((ROOT / "capsules_v3").exists())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_package_real_packages.CapsulePackageRealPackagesTest.test_active_capsules_live_under_capsules_not_capsules_v3
```

Expected: FAIL because active packages still live under `capsules_v3/`.

- [ ] **Step 3: Move files**

Use git moves:

```bash
mkdir -p archive/legacy_capsule_zips
git mv capsules/*.zip archive/legacy_capsule_zips/
git mv capsules_v3/*.capsule capsules/
rmdir capsules_v3
```

- [ ] **Step 4: Update tests from `capsules_v3` to `capsules`**

Replace references in tests:

```bash
rg -n "capsules_v3" tests/python lib scripts references skill.md
```

Update current-format references to `capsules`. Keep compatibility wrapper tests only where they deliberately test old imports.

- [ ] **Step 5: Run focused package tests**

```bash
PYTHONPATH=lib python3.12 -m unittest discover -s tests/python -p 'test_capsule_package_*.py'
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add capsules archive tests/python
git commit -m "data: make directory capsules canonical"
```

---

### Task 3: Neutral Converter And Validator Commands

**Files:**
- Create: `scripts/capsule_package_convert.py`
- Create: `scripts/capsule_package_validate.py`
- Modify: `scripts/capsule_v3_convert.py`
- Modify: `scripts/capsule_v3_validate.py`
- Rename/update tests.

**Interfaces:**
- Produces:
  - `validate_capsule_dir(capsule_dir: str | Path, warnings_ok: bool = False) -> dict[str, Any]`
  - `convert_capsule(payload: dict, out_root: str | Path, include_evidence: bool = False, overwrite: bool = False) -> Path`

- [ ] **Step 1: Write failing neutral import tests**

Create or update tests:

```python
from capsule_package_validate import validate_capsule_dir
from capsule_package_convert import convert_capsule

def test_neutral_modules_import():
    self.assertTrue(callable(validate_capsule_dir))
    self.assertTrue(callable(convert_capsule))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_package_validate tests.python.test_capsule_package_convert
```

Expected: FAIL or import error because neutral modules do not exist yet.

- [ ] **Step 3: Create neutral modules**

Copy current script bodies:

```bash
cp scripts/capsule_v3_validate.py scripts/capsule_package_validate.py
cp scripts/capsule_v3_convert.py scripts/capsule_package_convert.py
```

Then edit defaults:

```python
# capsule_package_convert.py
parser = argparse.ArgumentParser(description="Convert legacy SQLite/zip capsules to package directories.")
parser.add_argument("--from-zip-dir", default="archive/legacy_capsule_zips")
parser.add_argument("--out", default="capsules")
```

```python
# capsule_package_validate.py
parser = argparse.ArgumentParser(description="Validate a capsule package directory.")
print("capsule package validation:", "ok" if report["ok"] else "failed")
```

- [ ] **Step 4: Replace old scripts with wrappers**

`scripts/capsule_v3_validate.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from capsule_package_validate import *  # noqa: F401,F403
from capsule_package_validate import main

if __name__ == "__main__":
    main()
```

`scripts/capsule_v3_convert.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

from capsule_package_convert import *  # noqa: F401,F403
from capsule_package_convert import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run converter/validator tests**

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_package_validate tests.python.test_capsule_package_convert tests.python.test_capsule_v3_validate tests.python.test_capsule_v3_convert
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts tests/python
git commit -m "feat: add neutral capsule package commands"
```

---

### Task 4: Enforce Canonical Active Package Shape

**Files:**
- Modify: `scripts/capsule_package_validate.py`
- Modify: `capsules/*.capsule/capsule.yaml`
- Remove or move: `capsules/*.capsule/recipes/legacy_notes.md`, `repair_playbook.md`, `subtitle.md` if not promoted.
- Modify: `tests/python/test_capsule_package_validate.py`
- Modify: `tests/python/test_capsule_package_real_packages.py`

**Interfaces:**
- Consumes: `validate_capsule_dir`.
- Produces: active package validation that rejects hidden recipes and migration metadata.

- [ ] **Step 1: Write failing validator test for migration metadata**

Add:

```python
def test_active_package_rejects_migration_metadata(self):
    with tempfile.TemporaryDirectory() as tmp:
        cap = make_valid_capsule(Path(tmp))
        data = yaml.safe_load((cap / "capsule.yaml").read_text(encoding="utf-8"))
        data["source"] = {"type": "sqlite", "legacy_version": 1, "converted_at": "2026-06-30T00:00:00Z"}
        write(cap / "capsule.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

        report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("migration metadata" in item for item in report["errors"]))
```

- [ ] **Step 2: Write failing validator test for unreferenced recipe**

Add:

```python
def test_active_package_rejects_unreferenced_recipe_file(self):
    with tempfile.TemporaryDirectory() as tmp:
        cap = make_valid_capsule(Path(tmp))
        write(cap / "recipes" / "legacy_notes.md", "# Legacy Notes\n\nOld notes.\n")

        report = validate_capsule_dir(cap, warnings_ok=True)

        self.assertFalse(report["ok"])
        self.assertTrue(any("unreferenced recipe file" in item for item in report["errors"]))
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_package_validate
```

Expected: FAIL because validator still allows these cases.

- [ ] **Step 4: Implement validator checks**

In `validate_capsule_dir`, after reading `capsule.yaml`, add:

```python
for key in ("source", "legacy_version", "converted_at"):
    if key in capsule:
        errors.append(f"migration metadata is not allowed in active package: capsule.yaml {key}")
```

After read-order validation, add:

```python
declared = set()
if isinstance(read_order, dict):
    for paths in read_order.values():
        if isinstance(paths, list):
            declared.update(str(path) for path in paths)
for recipe in sorted((root / "recipes").glob("*.md")):
    rel = recipe.relative_to(root).as_posix()
    if rel not in declared:
        errors.append(f"unreferenced recipe file: {rel}")
```

- [ ] **Step 5: Clean active capsule package metadata and hidden files**

For each active `capsules/*.capsule/capsule.yaml`, remove:

```yaml
source:
  type: sqlite
  legacy_version: ...
  converted_at: ...
```

For each active capsule, remove these files unless their content is promoted into canonical read-order files:

```text
recipes/legacy_notes.md
recipes/repair_playbook.md
recipes/subtitle.md
```

Promote only concise reusable rules into existing canonical files, not raw historical dumps.

- [ ] **Step 6: Run real package validation**

```bash
for cap in capsules/*.capsule; do python3.12 scripts/capsule_package_validate.py "$cap" --warnings-ok; done
```

Expected: each prints `capsule package validation: ok`.

- [ ] **Step 7: Commit**

```bash
git add scripts/capsules tests/python
git commit -m "fix: enforce canonical capsule package shape"
```

---

### Task 5: Runtime Package Preference With SQLite Fallback

**Files:**
- Modify: `scripts/capsule_runtime.py`
- Modify: `scripts/run_video.py`
- Modify: `tests/python/test_capsule_runtime.py`
- Modify or add: `tests/python/test_run_video_preflight.py`

**Interfaces:**
- Produces:
  - `load_capsule_package(name: str, search_roots: list[str | Path] | None = None) -> dict | None`
  - `load_capsule(name: str, db_path: str = "", prefer_package: bool = True) -> dict`

- [ ] **Step 1: Write failing runtime package-preference test**

Add to `tests/python/test_capsule_runtime.py`:

```python
def test_load_capsule_prefers_package_over_sqlite_when_package_exists(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "capsules" / "sample.capsule"
        write_minimal_package(package, name="sample", summary="package wins")
        db_path = root / "capsules.sqlite"
        write_capsule_row(db_path, "sample", description="sqlite loses")

        capsule = runtime.load_capsule("sample", str(db_path), package_roots=[root / "capsules"])

        self.assertEqual(capsule["description"], "package wins")
        self.assertEqual(capsule["source_format"], "package")
```

- [ ] **Step 2: Write failing SQLite fallback test**

```python
def test_load_capsule_falls_back_to_sqlite_when_package_missing(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "capsules.sqlite"
        write_capsule_row(db_path, "sample", description="sqlite fallback")

        capsule = runtime.load_capsule("sample", str(db_path), package_roots=[root / "capsules"])

        self.assertEqual(capsule["description"], "sqlite fallback")
        self.assertEqual(capsule["source_format"], "sqlite")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_runtime
```

Expected: FAIL because `load_capsule` has no package preference yet.

- [ ] **Step 4: Implement package-to-runtime adapter**

In `scripts/capsule_runtime.py`, import neutral loader:

```python
from src.capsule_package_loader import CapsulePackageError, load_assets_index, load_capsule_card, load_quality_rules, load_runtime_contract
```

Add:

```python
def load_capsule_package(name: str, package_roots: list[str | Path] | None = None) -> dict | None:
    try:
        card = load_capsule_card(name, search_roots=package_roots)
        runtime_contract = load_runtime_contract(card["capsule_dir"])
        quality_rules = load_quality_rules(card["capsule_dir"])
        assets = load_assets_index(card["capsule_dir"])
    except CapsulePackageError:
        return None
    defaults = runtime_contract.get("defaults") if isinstance(runtime_contract.get("defaults"), dict) else {}
    return {
        "name": card.get("name"),
        "display_name": card.get("display_name"),
        "status": card.get("status"),
        "execution_mode": card.get("execution_mode"),
        "description": card.get("summary") or card.get("card_markdown", ""),
        "category": card.get("category"),
        "tags": card.get("when_to_use") or [],
        "config": {**defaults, "roles": runtime_contract.get("roles", {}), "output_contract": runtime_contract.get("output_contract", {})},
        "method": {},
        "input_schema": {},
        "quality_rules": quality_rules,
        "local_assets": assets,
        "examples": [],
        "local_script_path": (card.get("entrypoints") or {}).get("local_script", ""),
        "version": int(card.get("version") or 1),
        "capsule_dir": card["capsule_dir"],
        "source_format": "package",
    }
```

Change `load_capsule` signature:

```python
def load_capsule(name: str, db_path: str = "", prefer_package: bool = True, package_roots: list[str | Path] | None = None) -> dict:
    if prefer_package:
        packaged = load_capsule_package(name, package_roots=package_roots)
        if packaged is not None:
            return packaged
    ...
    payload["source_format"] = "sqlite"
    return payload
```

- [ ] **Step 5: Update `run_video.py` call**

Keep existing CLI stable. Change:

```python
capsule = load_capsule(args.capsule, args.capsule_db)
```

to:

```python
capsule = load_capsule(args.capsule, args.capsule_db, prefer_package=True)
```

- [ ] **Step 6: Run runtime tests**

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_capsule_runtime tests.python.test_run_video_preflight
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts tests/python
git commit -m "feat: prefer package capsules at runtime"
```

---

### Task 6: Documentation And Compatibility Cleanup

**Files:**
- Create: `references/capsule-package-format.md`
- Modify: `references/capsule-v3-format.md`
- Modify: `references/local-capsule-sqlite.md`
- Modify: `references/production-guide.md`
- Modify: `references/video-recipes.md`
- Modify: `skill.md`
- Modify: `README.md`
- Modify: `tests/skill.test.js`

**Interfaces:**
- Consumes: canonical paths and neutral commands.
- Produces: docs that explain `capsules/` as active and SQLite/zip as legacy archive.

- [ ] **Step 1: Write failing docs test**

In `tests/skill.test.js`, update expectations so current docs mention:

```javascript
assert(localCapsuleDocs.includes('capsules/<name>.capsule/'));
assert(localCapsuleDocs.includes('archive/legacy_capsule_zips/'));
assert(!localCapsuleDocs.includes('capsules_v3/<name>.capsule/'));
```

- [ ] **Step 2: Run docs test to verify it fails**

```bash
node tests/skill.test.js
```

Expected: FAIL because docs still mention `capsules_v3`.

- [ ] **Step 3: Update docs**

Create `references/capsule-package-format.md` from the spec summary. It must include:

```text
capsules/<name>.capsule/
python3.12 scripts/capsule_package_validate.py capsules/felt_asmr.capsule
python3.12 scripts/capsule_package_convert.py --out capsules
```

Update SQLite docs to say:

```text
SQLite is legacy/local evidence storage and explicit fallback. Active checked-in capsules live under capsules/<name>.capsule/. Legacy zip packages live under archive/legacy_capsule_zips/.
```

Make `references/capsule-v3-format.md` a short compatibility pointer to `capsule-package-format.md`, or remove it only if all references are updated.

- [ ] **Step 4: Run docs tests**

```bash
node tests/skill.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add references skill.md README.md tests/skill.test.js
git commit -m "docs: document canonical capsule packages"
```

---

### Task 7: Whole-Branch Verification And Review

**Files:**
- No new production files unless tests reveal a defect.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: final verified branch ready for PR or merge.

- [ ] **Step 1: Run full package validation**

```bash
for cap in capsules/*.capsule; do python3.12 scripts/capsule_package_validate.py "$cap" --warnings-ok; done
```

Expected: six `capsule package validation: ok` lines.

- [ ] **Step 2: Run Python capsule tests**

```bash
PYTHONPATH=lib python3.12 -m unittest discover -s tests/python -p 'test_capsule_*.py'
```

Expected: all tests pass.

- [ ] **Step 3: Run JS skill tests**

```bash
node tests/skill.test.js
```

Expected: all tests pass.

- [ ] **Step 4: Run compile and path scans**

```bash
python3.12 -m py_compile scripts/capsule_package_convert.py scripts/capsule_package_validate.py lib/src/capsule_package_loader.py scripts/capsule_runtime.py scripts/run_video.py
rg -n "capsules_v3|capsule-v3|Capsule v3|capsule_v3" capsules references skill.md README.md scripts lib/src tests/python tests/skill.test.js
rg -n "feedback|run_history|feedback_json|artifact_manifest\\.json|/output/|/Users|/home|/tmp|\\.codex|capsules\\.sqlite" capsules/*/recipes || true
git diff --check
```

Expected: compile exits 0, no current-format `v3` references except compatibility wrappers/tests if deliberately retained, no forbidden recipe tokens, and `git diff --check` exits 0.

- [ ] **Step 5: Commit any verification fixes**

```bash
git add .
git commit -m "test: verify canonical capsule packages"
```

Only commit if Step 1-4 required fixes. Otherwise do not create an empty commit.

---

## Self-Review

- Spec coverage: directory canonicalization, archive move, neutral naming, validation hardening, package runtime preference, docs, and verification are covered by Tasks 1-7.
- Placeholder scan: no task uses unresolved placeholder tokens or open-ended "add tests" language without concrete commands.
- Type consistency: loader, validator, converter, and runtime function names are defined before later tasks consume them.
