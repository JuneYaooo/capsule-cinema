# Capsule Production Core Implementation Plan

> **Execution:** Implement inline in this worktree with test-first changes and path-limited commits.

**Goal:** Make existing progressive reading first-class and add generic preservation, configured Instance, ProductionPlan, and EffectReport contracts without importing any capsule-specific production vocabulary into Core.

**Architecture:** Keep the Core thin. It normalizes lifecycle contracts, validates references, and derives fail-closed decisions; individual capsules continue to own domain payloads and effect checks.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML 6, standard-library `unittest`.

## Global Constraints

- Existing tracked v1 capsules remain read-only compatible.
- Existing `read_order` is authoritative; normal use does not require compiled stage artifacts.
- Core contains no repository, GitHub, scene, shot, BGM, subtitle, or other video-specific fields.
- No package-specific preservation classifier lives under `lib/src/capsules/`.
- No new dependency.
- Use `python3.12 -m unittest`, not pytest.
- Never stage or modify the dirty main worktree.

### Task 1: Generic preservation and configured Instance

**Files:**
- Create: `lib/src/capsules/preservation.py`
- Create: `lib/src/capsules/instance.py`
- Create: `tests/python/test_capsule_preservation.py`
- Create: `tests/python/test_capsule_instance.py`
- Modify: `lib/src/capsules/model.py`
- Modify: `lib/src/capsules/v1_adapter.py`
- Modify: `tests/python/test_capsule_core_model.py`
- Modify: `tests/python/test_capsule_core_v1_adapter.py`

**Interfaces:**
- `snapshot_package`, `inventory_sections`, `build_preservation_manifest(snapshot, sections, classifier)`, `validate_preservation_manifest`.
- `configure_instance(definition, requested, candidate_digest, renderer_digest, topic="")` and `write_instance`.

- [ ] Add/reuse focused tests that prove snapshots are read-only, coverage is exact, the classifier is caller-supplied, inputs are strictly bound, and serialization is deterministic.
- [ ] Run focused tests and confirm missing interfaces fail before adding production modules.
- [ ] Add the reviewed generic implementations, remove the repo-showcase classifier, and require an explicit classifier callable.
- [ ] Run preservation, Instance, model, and adapter tests.
- [ ] Commit only the listed paths.

### Task 2: First-class progressive reading

**Files:**
- Modify: `lib/src/capsules/model.py`
- Modify: `lib/src/capsules/v1_adapter.py`
- Create: `lib/src/capsules/reading.py`
- Create: `tests/python/test_capsule_reading.py`
- Modify: `tests/python/test_capsule_core_model.py`
- Modify: `tests/python/test_capsule_core_v1_adapter.py`

**Interfaces:**
- `CapsuleReadOrder` with `routing`, `planning`, `generation`, `qa`, and `learning` ordered lists.
- `load_stage_resources(definition, stage) -> ResultEnvelope` returning logical relative paths, SHA-256 digests, and UTF-8 content.

- [ ] Write tests for v1 preservation, missing `read_order`, author order, empty stages, duplicate rejection, traversal/absolute/symlink/missing/non-UTF-8 resources, and source immutability.
- [ ] Run tests and confirm the normalized field/module is missing.
- [ ] Implement strict adapter parsing and fail-closed stage loading.
- [ ] Run focused tests and all Capsule Core regressions.
- [ ] Commit only the listed paths.

### Task 3: ProductionPlan and EffectReport

**Files:**
- Create: `lib/src/capsules/production.py`
- Create: `lib/src/capsules/effect.py`
- Create: `tests/python/test_capsule_production_plan.py`
- Create: `tests/python/test_capsule_effect_report.py`

**Interfaces:**
- `ProductionPlan`, `ProductionStep`, `EvidenceRequirement`, `QualityRequirement`, `build_production_plan`, `production_plan_digest`.
- `EffectCheck`, `EffectReport`, `build_effect_report`.

- [ ] Write tests for deterministic plan digests, unique IDs, known references, ordered stages, JSON-safe domain payloads, and source-object immutability.
- [ ] Run tests and confirm the modules are missing.
- [ ] Implement the minimal generic contracts without domain vocabulary.
- [ ] Write and run tests proving failed blockers derive `blocked`, pending required human review derives `review_required`, and clean reports derive `ready`.
- [ ] Commit only the four listed paths.

### Task 4: Compatibility, documentation, and delivery

**Files:**
- Modify: `lib/src/capsules/__init__.py`
- Modify: `package.json`
- Create: `references/capsule-production-core.md`
- Create or modify focused real-package compatibility tests under `tests/python/`.

- [ ] Add tests loading at least two structurally different tracked v1 capsules and asserting normalized `read_order` without byte mutation.
- [ ] Add the new source modules to `npm test` py_compile coverage and document thin-Core boundaries.
- [ ] Run all focused Capsule Core tests, preservation/Instance/reading/production/effect tests, tracked-package validation, `npm test`, and `git diff --check`.
- [ ] Perform a whole-branch code review and fix all Critical/Important findings.
- [ ] Merge into local `main`, repeat merged-state verification, and push `main` to `origin/main`.
