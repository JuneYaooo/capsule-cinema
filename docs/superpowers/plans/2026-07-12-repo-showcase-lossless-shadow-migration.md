# Repo Showcase Lossless Shadow Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a non-active native shadow candidate for the current dirty `repo_showcase` capsule, using `Agents365-ai/drawio-skill` to prove complete knowledge preservation, progressive stage compilation, and old-versus-new output parity without modifying the active package.

**Architecture:** Add reusable preservation, Instance, compiler, and parity modules under `src.capsules`, then compose them in a repo-showcase pilot orchestrator. The orchestrator freezes the current working-tree v1 package, generates an ignored shadow candidate, creates a locked Instance, compiles routing/planning/generation/QA contexts, renders the old and new routes with the same frozen browser assets, profile, BGM, renderer, and QA implementations, and emits a machine report plus a human comparison sheet. Candidate activation is explicitly excluded.

**Tech Stack:** Python 3.12, Pydantic 2, PyYAML 6, standard-library `unittest`, Pillow already used by the renderer, ffmpeg/ffprobe, existing repo-showcase renderer and batch source collector.

## Global Constraints

- The baseline is the current working-tree state of `capsules/repo_showcase.capsule/`, including uncommitted user changes.
- Implementation work may use an isolated Git worktree, but baseline and real-pilot commands must receive `--source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule` explicitly. They must never freeze the clean linked-worktree copy by accident.
- The current source collector is the user's untracked `/Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py`. Real-pilot commands receive it through `--source-collector`, freeze its digest, and never copy or commit it. Tests use a fixture collector.
- Never modify, stage, commit, replace, normalize in place, or auto-activate `capsules/repo_showcase.capsule/`.
- The only pilot subject is exactly `Agents365-ai/drawio-skill`.
- Source coverage must equal `100%`; `unclassified` must equal `0`; silent deletion must equal `0`.
- Progressive reading changes when knowledge is compiled, not whether effective reusable knowledge is preserved.
- The first candidate reuses the exact current renderer, BGM, source image bytes, normalized render profile, ffmpeg toolchain, QA implementation, and release-checker implementation.
- The old route captures browser source evidence once. The new route must reuse the frozen manifest and files and must not recapture remote pages.
- No paid model or production provider may be invoked without a new explicit user confirmation.
- The output contract remains 1080×1440, 3:4, ten seconds with tolerance `<= 0.05` seconds, no voiceover, no burned subtitles, and packaged BGM.
- Corresponding deterministic decoded frames require SSIM `>= 0.995` unless the report identifies an encoding-only difference and the human review accepts it.
- A worse human-review result blocks activation even if machine checks pass.
- All baseline, candidate, run, and parity artifacts live under ignored `output/capsule_migrations/`; no generated candidate or output is committed.
- `migration-workspace/` is not created; the ignored output tree is the concrete local shadow workspace for this implementation.
- The committed implementation contains reusable core code, focused tests, and documentation only. It contains no copied dirty capsule content, source screenshots, generated videos, or ignored local corpus.
- Existing user changes, staged deletions, ignored capsules, and untracked tests/scripts must remain untouched.
- Use `python3.12 -m unittest`, not pytest, and add no dependency.
- Every task uses TDD and path-limited commits. Never use `git add -A`, `git add .`, reset, clean, or checkout over user files.

---

## File Map

| Path | Responsibility |
| --- | --- |
| `lib/src/capsules/preservation.py` | Read-only package digest, section inventory, disposition rules, coverage validation, baseline freeze. |
| `lib/src/capsules/instance.py` | Generic configured Instance input/default/type/range/enum validation and digest locking. |
| `lib/src/capsules/compiler.py` | Deterministic stage-context compilation from a candidate, Instance, and preservation manifest. |
| `lib/src/capsules/parity.py` | Profile, contract, source, media, QA, and artifact parity calculations. |
| `lib/src/capsules/repo_showcase_shadow.py` | Pilot candidate builder and old/new controlled-run orchestration. |
| `scripts/repo_showcase_shadow_migration.py` | CLI for `freeze`, `build`, `compile`, `render-old`, `render-new`, `compare`, and `all`. |
| `tests/python/test_capsule_preservation.py` | Generic inventory/digest/coverage tests. |
| `tests/python/test_capsule_instance.py` | Generic Instance validation tests. |
| `tests/python/test_capsule_stage_compiler.py` | Generic progressive-context and coverage tests. |
| `tests/python/test_capsule_parity.py` | Generic deterministic parity tests. |
| `tests/python/test_repo_showcase_shadow_migration.py` | Pilot integration and active-package mutation-guard tests. |
| `references/repo-showcase-shadow-migration.md` | Local operator workflow, gates, output layout, and non-activation boundary. |
| `package.json` | Append only the six new Python source/CLI paths to existing `py_compile` coverage while preserving concurrent content. |

## Output Layout

Each invocation creates one ignored root:

```text
output/capsule_migrations/repo_showcase/<run-id>/
  baseline/
  candidate/
    capsule.yaml
    guidance/
    assets/
    runner/
    examples/
    build/
  instance.json
  compiled/
    routing.json
    planning.json
    generation.json
    qa.json
    compilation-report.json
    effective-rules.json
  frozen-source/
  old-run/
  new-run/
  parity/
    machine-parity.json
    frame-metrics.json
    comparison-contact-sheet.jpg
    human-review.json
    activation-recommendation.json
```

### Task 1: Read-Only Baseline Freeze And Mutation Guard

**Files:**
- Create: `lib/src/capsules/preservation.py`
- Create: `tests/python/test_capsule_preservation.py`

**Interfaces:**
- Produces: `FileRecord`, `SectionRecord`, `PackageSnapshot`, `sha256_file(path: Path) -> str`, `snapshot_package(package_dir: Path) -> PackageSnapshot`, `write_baseline(snapshot: PackageSnapshot, output_dir: Path, *, git_head: str, dirty_paths: list[str], python_version: str, ffmpeg_version: str) -> Path`, `assert_package_unchanged(before: PackageSnapshot, package_dir: Path) -> None`.
- Excludes only relative paths matching `**/__pycache__/**`, `**/*.pyc`, `.DS_Store`, and editor swap files; excluded files remain recorded with `classification="excluded_ephemeral"` but do not affect `package_digest`.
- All JSON writes use a temporary sibling followed by `Path.replace()` and never write below `package_dir`.

- [ ] **Step 1: Write failing snapshot tests**

Create a temporary package with YAML, Markdown, Python, binary asset, and `__pycache__/x.pyc`. Assert deterministic sorted records, SHA-256 changes when authored bytes change, `.pyc` does not change the authored digest, baseline JSON contains no environment values, attempting an output path inside the package raises `PreservationError(code="output_inside_source")`, and `assert_package_unchanged` raises `PreservationError(code="source_mutated")` after a source edit.

```python
class CapsulePreservationTests(unittest.TestCase):
    def test_snapshot_is_deterministic_and_excludes_only_ephemeral_bytes(self) -> None:
        before = snapshot_package(self.package)
        (self.package / "__pycache__" / "x.pyc").write_bytes(b"changed cache")
        after_cache = snapshot_package(self.package)
        self.assertEqual(before.package_digest, after_cache.package_digest)
        self.assertTrue(any(item.classification == "excluded_ephemeral" for item in after_cache.files))
        (self.package / "recipes" / "copy.md").write_text("# Copy\nchanged\n", encoding="utf-8")
        after_source = snapshot_package(self.package)
        self.assertNotEqual(before.package_digest, after_source.package_digest)

    def test_baseline_cannot_write_inside_source(self) -> None:
        with self.assertRaisesRegex(PreservationError, "output_inside_source"):
            write_baseline(
                snapshot_package(self.package),
                self.package / "baseline",
                git_head="abc",
                dirty_paths=[],
                python_version="3.12",
                ffmpeg_version="6.1",
            )
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_preservation -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.capsules.preservation'`.

- [ ] **Step 3: Implement deterministic snapshot and baseline writing**

Use Pydantic models with explicit `schema_version="capsule.preservation/v1"`. Hash each authored file as `relative POSIX path + NUL + bytes`; hash the package from sorted `relative path + NUL + file digest`. Record size, classification, and digest. `write_baseline` emits `baseline.json`, `package-digest.json`, and `source-inventory.json`; reject any output whose resolved path is equal to or below the resolved package directory. Do not serialize `os.environ`.

- [ ] **Step 4: Verify GREEN and existing core**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_preservation -v
PYTHONPATH=lib:scripts python3.12 -m unittest discover -s tests/python -p 'test_capsule_core_*.py' -v
```

Expected: preservation tests PASS; current Core suite PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/preservation.py tests/python/test_capsule_preservation.py
git commit --only lib/src/capsules/preservation.py tests/python/test_capsule_preservation.py -m "feat: freeze capsule migration baselines"
```

### Task 2: Section Inventory And Preservation Coverage

**Files:**
- Modify: `lib/src/capsules/preservation.py`
- Modify: `tests/python/test_capsule_preservation.py`

**Interfaces:**
- Produces: `inventory_sections(package_dir: Path) -> list[SectionRecord]`, `classify_repo_showcase_section(section: SectionRecord) -> PreservationDisposition`, `build_preservation_manifest(snapshot: PackageSnapshot, sections: list[SectionRecord]) -> PreservationManifest`, `validate_preservation_manifest(manifest: PreservationManifest) -> ResultEnvelope`.
- YAML inventory addresses every mapping key and list item with JSON Pointer syntax; Markdown inventory addresses frontmatter plus every heading-delimited section; Python inventory addresses module preamble plus every top-level function/class using AST line ranges; binary assets produce one whole-file section.

- [ ] **Step 1: Add failing complete-coverage tests**

Fixture assertions must prove that two YAML list entries with the same value remain distinct by index, Markdown text before the first heading is inventoried, Python module code and every top-level definition are inventoried, and deleting any disposition makes validation return `ok=False`, `status="incomplete"`, issue `preservation_unclassified`, and the missing section IDs.

Add a repo-showcase-shaped fixture and assert these deterministic routing rules:

```text
capsule.yaml identity/match/interface -> preserved_in_definition
contracts/input_schema.yaml -> preserved_in_definition
contracts/runtime.yaml -> preserved_in_definition
recipes/*.md -> moved_to_guidance
quality/rules.yaml object rules -> converted_to_rubric
quality/release_gates.yaml structured checker entries -> converted_to_checker
quality/release_gates.yaml string entries -> converted_to_rubric
learning/promoted_lessons.yaml -> moved_to_guidance
assets/index.yaml -> preserved_in_definition
assets/* binary -> moved_to_asset
examples/* -> moved_to_example
scripts/*.py -> moved_to_runner
CARD.md and index.md duplicated metadata/navigation -> generated_view
__pycache__/*.pyc -> excluded_ephemeral
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_preservation -v`

Expected: FAIL because section inventory and manifest interfaces do not exist.

- [ ] **Step 3: Implement section extraction and explicit dispositions**

Implement stable IDs as `<relative-path>#<kind>:<pointer-or-heading-or-symbol>`. Preserve source digest, byte/line range, stage set, promise-affecting boolean, target owner, and rationale. Do not mark any repo-showcase section obsolete. Manifest validation requires exact equality between inventoried section IDs and disposition section IDs, rejects duplicates, requires `100.0` coverage, and requires zero promise-affecting `obsolete_with_evidence` entries.

- [ ] **Step 4: Verify GREEN**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_preservation -v`

Expected: PASS with explicit assertions for `coverage_percent == 100.0`, `unclassified == []`, and `silent_deletions == []`.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/preservation.py tests/python/test_capsule_preservation.py
git commit --only lib/src/capsules/preservation.py tests/python/test_capsule_preservation.py -m "feat: inventory capsule preservation coverage"
```

### Task 3: Configured Capsule Instance And Input Binding

**Files:**
- Create: `lib/src/capsules/instance.py`
- Create: `tests/python/test_capsule_instance.py`

**Interfaces:**
- Consumes: Foundation `CapsuleDefinition`, candidate digest, renderer digest, and requested values.
- Produces: `CapsuleInstance`, `ResolvedInputs`, `configure_instance(definition: CapsuleDefinition, requested: dict[str, Any], *, candidate_digest: str, renderer_digest: str, topic: str = "") -> ResultEnvelope` and `write_instance(instance: CapsuleInstance, path: Path) -> Path`.
- `ResultEnvelope.data["instance"]` is the serialized Instance only when status is `ready`; missing fields return `needs_input`; invalid types/ranges/options/unknown keys return `invalid`.

- [ ] **Step 1: Write failing validation tests**

Tests must cover `repo_slug` missing, explicit value acceptance, default application for production mode/duration/platform, explicit value precedence, unknown input, integer-vs-boolean strictness, maximum 10 rejection, options rejection, source manifest path preservation, and Definition immutability.

```python
result = configure_instance(
    repo_definition,
    {"repo_slug": "Agents365-ai/drawio-skill"},
    candidate_digest="sha256:candidate",
    renderer_digest="sha256:renderer",
)
self.assertEqual(result.status, "ready")
instance = result.data["instance"]
self.assertEqual(instance["inputs"]["target_duration"], 10)
self.assertIn("target_duration", instance["resolved"]["defaults_applied"])
```

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_instance -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement strict generic binding**

Support v1 input types `string`, `integer`, `number`, `boolean`, `array`, `list`, `object`, and `enum`; apply `minimum`, `maximum`, and `enum/options` from normalized input metadata. Because the current normalized `CapsuleInput` does not yet retain minimum/maximum, extend it with optional `minimum: float | None` and `maximum: float | None`, map them in `v1_adapter.py`, and add adapter regression assertions. Do not infer `repo_slug` from topic in this pilot. Instance schema is exactly `capsule.instance/v1`; approvals contain `fallback_policy="no_promise_change"`.

- [ ] **Step 4: Verify GREEN and regressions**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_instance tests.python.test_capsule_core_model tests.python.test_capsule_core_v1_adapter -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/instance.py lib/src/capsules/model.py lib/src/capsules/v1_adapter.py tests/python/test_capsule_instance.py tests/python/test_capsule_core_model.py tests/python/test_capsule_core_v1_adapter.py
git commit --only lib/src/capsules/instance.py lib/src/capsules/model.py lib/src/capsules/v1_adapter.py tests/python/test_capsule_instance.py tests/python/test_capsule_core_model.py tests/python/test_capsule_core_v1_adapter.py -m "feat: configure locked capsule instances"
```

### Task 4: Shadow Candidate Builder

**Files:**
- Create: `lib/src/capsules/repo_showcase_shadow.py`
- Create: `tests/python/test_repo_showcase_shadow_migration.py`

**Interfaces:**
- Produces: `ShadowCandidate`, `build_repo_showcase_candidate(package_dir: Path, workspace: Path, snapshot: PackageSnapshot, manifest: PreservationManifest) -> ShadowCandidate`, `validate_candidate(candidate: ShadowCandidate, manifest: PreservationManifest) -> ResultEnvelope`.
- Candidate schema is `capsule.cinema/v2-shadow`; this is explicitly a pilot build shape, not an active installable release. The active loader must reject/disregard it because it is outside `capsules/*.capsule`.

- [ ] **Step 1: Write failing candidate tests**

Using a repo-showcase fixture, assert candidate output has `capsule.yaml`, guidance, assets, runner, examples, and build reports; copied bytes match their source digests; CARD/index are generated rather than copied; the candidate is below the requested workspace and never below the active package; candidate digest is stable; deleting a guidance or runner target fails validation with `candidate_target_missing`; and source package snapshot remains identical.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_repo_showcase_shadow_migration -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement lossless candidate materialization**

Generate `capsule.yaml` from normalized identity, promise, match, full published interface, output/runtime contracts, assets index, and exact runner reference. Copy recipe/lesson text without editing into stage-owned guidance files; copy assets, examples, and runner bytes; generate CARD/README views. Write `preservation-manifest.json`, `validation-report.json`, and `capsule.lock` with source package, candidate, renderer, asset, and BGM digests. Use atomic writes and reject workspace paths inside the active package.

- [ ] **Step 4: Verify GREEN and active mutation guard**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_repo_showcase_shadow_migration -v
```

Expected: PASS and source before/after snapshots equal.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/repo_showcase_shadow.py tests/python/test_repo_showcase_shadow_migration.py
git commit --only lib/src/capsules/repo_showcase_shadow.py tests/python/test_repo_showcase_shadow_migration.py -m "feat: build repo showcase shadow candidates"
```

### Task 5: Progressive Stage Context Compiler

**Files:**
- Create: `lib/src/capsules/compiler.py`
- Create: `tests/python/test_capsule_stage_compiler.py`

**Interfaces:**
- Produces: `StageContext`, `CompilationReport`, `compile_candidate(candidate: ShadowCandidate, instance: CapsuleInstance, manifest: PreservationManifest, output_dir: Path) -> ResultEnvelope`.
- Emits exact stages `routing`, `planning`, `generation`, `qa`; every non-ephemeral/non-generated-view preservation entry must be included in at least one declared stage.

- [ ] **Step 1: Write failing compiler tests**

Assert routing excludes guidance bodies, runner source, examples, and QA rules; planning contains interface, copy/structure/visual/audio guidance and source-evidence planning constraints; generation contains Instance, runtime, motion, runner digest, assets, audio, and deterministic pre-render blockers; QA contains all checker/rubric entries and artifact requirements. Assert missing asset, missing manifest mapping, unresolved duplicate conflict, candidate digest mismatch, or renderer digest mismatch returns a blocked envelope.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_stage_compiler -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement deterministic compilation**

Compile structured JSON, not a monolithic prompt. Each included item records preservation section ID, owner, digest, content or reference, and inclusion reason. Report byte/character counts, duplicates, conflicts, assets, included IDs, excluded IDs with reason, and unmapped IDs. Fail unless unmapped, unresolved conflicts, missing assets, promise-affecting exclusions, candidate digest mismatches, and renderer digest mismatches are all zero.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_stage_compiler tests.python.test_capsule_preservation tests.python.test_capsule_instance -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/compiler.py tests/python/test_capsule_stage_compiler.py
git commit --only lib/src/capsules/compiler.py tests/python/test_capsule_stage_compiler.py -m "feat: compile progressive capsule contexts"
```

### Task 6: Profile And Controlled-Run Orchestration

**Files:**
- Modify: `lib/src/capsules/repo_showcase_shadow.py`
- Modify: `tests/python/test_repo_showcase_shadow_migration.py`
- Create: `scripts/repo_showcase_shadow_migration.py`

**Interfaces:**
- Produces: `freeze_pilot(source_package: Path, source_collector: Path, run_root: Path) -> ResultEnvelope`, `prepare_old_route(source_package: Path, source_collector: Path, paths: PilotPaths) -> ResultEnvelope`, `prepare_new_route(source_package: Path, paths: PilotPaths) -> ResultEnvelope`, `render_route(route: Literal["old", "new"], source_package: Path, paths: PilotPaths) -> ResultEnvelope`, `PilotPaths`, and CLI commands `freeze`, `build`, `compile`, `render-old`, `render-new`, `compare`, `all`.
- Reuses `scripts/rerun_repo_showcase_real_batch.py` functions `parse_table`, `refresh_star_counts`, `collect_real_assets`, `has_required_visual_material`, `build_profile`, and `validate_profile_contract` only for the old route/source freeze. The new route reads frozen JSON and files and does not call collection or network functions.

- [ ] **Step 1: Write failing orchestration tests**

Mock network/source collection and subprocess only. Assert subject is rejected unless exactly `Agents365-ai/drawio-skill`; old preparation freezes a manifest/profile; new preparation produces a normalized profile semantically equal after replacing only output paths; new preparation never calls source collection; both renderer commands use the same renderer digest, BGM digest, manifest item digests, and profile semantics; a source/package/renderer digest change aborts before subprocess; no command path is inside the active package.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_repo_showcase_shadow_migration -v`

Expected: FAIL for missing orchestration interfaces.

- [ ] **Step 3: Implement orchestration and CLI**

`freeze` records current dirty path names without diffs or file contents outside the package and records the source-collector digest. `render-old` alone may import the explicitly supplied collector and collect source evidence. After successful material validation it copies exact selected files into `frozen-source/`, rewrites manifest paths to those frozen copies, builds one normalized profile, and renders old. `render-new` loads Instance/compiled generation context, reconstructs the same normalized profile, verifies equality, and invokes the copied candidate runner against the same frozen files. Use separate `old-run/` and `new-run/`. The CLI prints one JSON result envelope and never activates a capsule.

Every command requires `--source-package` and `--source-collector`; reject paths that are not the exact resolved current main-workspace package and collector for this pilot. Tests use temporary fixtures through an injected `allow_test_source=True` Python API only; the public CLI has no bypass flag.

- [ ] **Step 4: Verify GREEN, syntax, and dry-run CLI**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_repo_showcase_shadow_migration -v
python3.12 -m py_compile scripts/repo_showcase_shadow_migration.py lib/src/capsules/repo_showcase_shadow.py
python3.12 scripts/repo_showcase_shadow_migration.py --help
```

Expected: tests PASS, compile exits 0, help lists seven commands and the fixed subject.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/repo_showcase_shadow.py scripts/repo_showcase_shadow_migration.py tests/python/test_repo_showcase_shadow_migration.py
git commit --only lib/src/capsules/repo_showcase_shadow.py scripts/repo_showcase_shadow_migration.py tests/python/test_repo_showcase_shadow_migration.py -m "feat: orchestrate repo showcase shadow runs"
```

### Task 7: Machine Effect-Parity Analyzer

**Files:**
- Create: `lib/src/capsules/parity.py`
- Create: `tests/python/test_capsule_parity.py`
- Modify: `lib/src/capsules/repo_showcase_shadow.py`
- Modify: `scripts/repo_showcase_shadow_migration.py`

**Interfaces:**
- Produces: `compare_profiles`, `compare_source_manifests`, `probe_video`, `compare_frames`, `compare_artifacts`, `compare_qa`, `build_machine_parity_report`, and `write_contact_sheet`.
- `compare_frames` calls ffmpeg's `ssim` filter and samples frames at `0.5, 2.5, 4.5, 6.5, 8.5, 9.5` seconds; it never adds a Python image-comparison dependency.

- [ ] **Step 1: Write failing parity tests**

Generate tiny deterministic videos locally with ffmpeg color sources. Assert identical videos pass; a changed color fails SSIM; duration >0.05 seconds, wrong 1080×1440 metadata fixture, voice/subtitle stream, source digest mismatch, profile semantic mismatch, missing publishing artifact, newly failing QA gate, or missing manifest item fails the appropriate gate. Mock ffprobe/ffmpeg only for malformed-tool-output error cases. Assert contact sheet labels routes neutrally as A/B and does not reveal which is old/new.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_parity -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement machine comparison**

Normalize only explicit run-specific profile keys: absolute output paths, timestamps, run IDs, and output identifiers. Do not ignore copy, layout, source, motion, duration, audio, or QA fields. Probe video streams with ffprobe JSON. Run ffmpeg SSIM and parse `All:`; require every sampled comparison and aggregate score `>=0.995`. Compare required artifacts by logical category, not absolute path. Output each gate with old evidence, new evidence, threshold, pass boolean, and remediation.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_parity -v
```

Expected: PASS; tests skip with an explicit reason only if ffmpeg/ffprobe is genuinely unavailable.

- [ ] **Step 5: Commit**

```bash
git add lib/src/capsules/parity.py lib/src/capsules/repo_showcase_shadow.py scripts/repo_showcase_shadow_migration.py tests/python/test_capsule_parity.py
git commit --only lib/src/capsules/parity.py lib/src/capsules/repo_showcase_shadow.py scripts/repo_showcase_shadow_migration.py tests/python/test_capsule_parity.py -m "feat: compare capsule output parity"
```

### Task 8: Real Single-Subject Pilot And Human Review Package

**Files:**
- Create: `references/repo-showcase-shadow-migration.md`
- Modify: `package.json` only by appending new compile paths while preserving concurrent user edits.
- No generated output or candidate file is committed.

**Interfaces:**
- Consumes all preceding tasks and the current dirty active package.
- Produces ignored baseline/candidate/old/new/parity artifacts and a user-reviewed `human-review.json`.

- [ ] **Step 1: Add operator documentation contract test**

Add to `tests/python/test_repo_showcase_shadow_migration.py` an assertion that the reference contains: fixed subject, active-package mutation prohibition, seven commands, no-paid-provider rule, SSIM threshold, human review dimensions, failure rollback, and non-activation statement.

- [ ] **Step 2: Verify documentation RED**

Run: `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_repo_showcase_shadow_migration -v`

Expected: FAIL because the reference is absent.

- [ ] **Step 3: Write operator reference and append compile coverage**

Document exact commands:

```bash
python3.12 scripts/repo_showcase_shadow_migration.py freeze --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
python3.12 scripts/repo_showcase_shadow_migration.py build --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
python3.12 scripts/repo_showcase_shadow_migration.py compile --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
python3.12 scripts/repo_showcase_shadow_migration.py render-old --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
python3.12 scripts/repo_showcase_shadow_migration.py render-new --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
python3.12 scripts/repo_showcase_shadow_migration.py compare --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
python3.12 scripts/repo_showcase_shadow_migration.py all --source-package /Users/june2/code/github/capsule-cinema/capsules/repo_showcase.capsule --source-collector /Users/june2/code/github/capsule-cinema/scripts/rerun_repo_showcase_real_batch.py --run-id <id>
```

Append these paths to the existing `package.json` compile command without restoring removed video-distillation entries or changing any other concurrent content:

```text
lib/src/capsules/preservation.py
lib/src/capsules/instance.py
lib/src/capsules/compiler.py
lib/src/capsules/parity.py
lib/src/capsules/repo_showcase_shadow.py
scripts/repo_showcase_shadow_migration.py
```

- [ ] **Step 4: Run all automated verification before real rendering**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest \
  tests.python.test_capsule_preservation \
  tests.python.test_capsule_instance \
  tests.python.test_capsule_stage_compiler \
  tests.python.test_capsule_parity \
  tests.python.test_repo_showcase_shadow_migration -v
PYTHONPATH=lib:scripts python3.12 -m unittest discover -s tests/python -p 'test_capsule_core_*.py' -v
PYTHONPATH=lib:scripts python3.12 /Users/june2/code/github/capsule-cinema/tests/python/test_repo_showcase_capsule.py -v
npm test
git diff --check
```

Expected: all selected tests PASS. The repo-showcase test file has user-owned main-workspace modifications and is executed by absolute path; it is never copied or committed by this plan. If it exposes a pre-existing failure unrelated to the committed pilot, record the exact test and stop before rendering rather than modifying that file or the active package.

- [ ] **Step 5: Freeze and prove zero active-package mutation**

Choose `RUN_ID=drawio-$(date -u +%Y%m%dT%H%M%SZ)` and record `snapshot_package` before execution. Run `freeze`, `build`, and `compile`. Assert:

```text
coverage_percent = 100.0
unclassified = 0
unmapped = 0
unresolved_conflicts = 0
missing_assets = 0
active package digest unchanged
```

Expected: all gates PASS. If not, stop; do not render.

- [ ] **Step 6: Run the controlled old and new local renders**

Run `render-old` once, then `render-new` using the frozen source manifest. Before each subprocess, verify active package, renderer, candidate, BGM, manifest-item, and profile digests. No paid model call is allowed. If source collection cannot obtain four approved browser visuals, report `blocked_missing_material` and stop without weakening the approved-source contract.

Expected: both routes produce their required local output packages, or the pilot stops with a truthful blocker.

- [ ] **Step 7: Run machine parity and present human review**

Run `compare`. Require all machine gates and SSIM threshold to pass before presenting `comparison-contact-sheet.jpg`. Present the neutral A/B sheet to the user with the eight dimensions: one-glance value, source credibility, visual polish, readability, pacing/motion, usefulness, save/share potential, overall preference. Do not write a passing human result on the user's behalf.

Expected user outcomes:

```text
equal_or_better -> human gate pass
worse -> revise_candidate
cannot_judge -> human gate pending
```

- [ ] **Step 8: Write final recommendation without activation**

After user review, write `activation-recommendation.json` as `pass`, `revise_candidate`, or `reject`. Even `pass` must state `active_replaced=false` and require a separate explicit activation request.

- [ ] **Step 9: Commit only code-adjacent documentation/configuration**

Before committing, run `git status --short`, `git diff --cached --name-status`, and `git diff -- capsules/repo_showcase.capsule`. The active-package diff must contain only the user's pre-existing changes and must not contain pilot-authored modifications. Then commit only:

```bash
git add references/repo-showcase-shadow-migration.md package.json tests/python/test_repo_showcase_shadow_migration.py
git commit --only references/repo-showcase-shadow-migration.md package.json tests/python/test_repo_showcase_shadow_migration.py -m "docs: validate repo showcase shadow migration"
```

If `package.json` contains user-owned unstaged changes, create the task commit from a path-limited staged patch only when it can preserve their working-tree/index state exactly; otherwise leave `package.json` unstaged, run explicit `py_compile`, and document the omitted integration rather than overwriting or staging user content.

## Exit Criteria

- The active dirty `repo_showcase` package has the same authored package digest before and after the pilot.
- The committed branch contains no active-package content change, generated candidate, browser screenshot, source manifest, video, QA output, or local absolute path.
- The baseline inventory covers every meaningful source section and the preservation manifest has zero unclassified content.
- The candidate and compiler have zero missing targets, unmapped sections, unresolved conflicts, missing assets, or digest mismatches.
- Old and new routes use the same frozen `Agents365-ai/drawio-skill` inputs, browser assets, BGM, renderer, profile semantics, QA, and release implementations.
- Machine contract, profile, source, visual, content, artifact, and QA parity gates pass.
- Corresponding deterministic frames meet SSIM `>=0.995` or have a reviewed encoding-only exception.
- The user rates the new result equal or better; otherwise the candidate remains rejected or revision-only.
- No paid provider is invoked without a separate explicit confirmation.
- The active capsule is not replaced or activated by this plan.
