# Capsule Local Script Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a framework-owned dispatcher and release guard so `local_script` capsules cannot be silently bypassed by one-off scripts.

**Architecture:** Introduce `scripts/run_capsule.py` for canonical local-script execution. Tighten `scripts/run_video.py` so local-script capsules do not enter `general_video` unless explicitly marked as generic preview. Add manifest scoring checks that block unregistered `output/*.py` scripts from claiming local-script capsule final status.

**Tech Stack:** Python 3.12, existing capsule package loader in `scripts/capsule_runtime.py`, existing release and scoring scripts, unittest tests under `tests/python`.

## Global Constraints

- A capsule with `execution_mode: local_script` must run through `entrypoints.local_script`.
- Generic fallback for local-script capsules must be explicit and non-final.
- Do not write API keys, tokens, cookies, signed URLs, or provider private endpoints to params, manifests, docs, logs, or tests.
- Keep existing preset capsule behavior unchanged.
- Use TDD: each behavior gets a failing test before production code.

---

## Task 1: Canonical `run_capsule.py`

**Files:**
- Create: `tests/python/test_run_capsule_dispatch.py`
- Create: `scripts/run_capsule.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: `scripts.capsule_runtime.load_capsule(name)`.
- Produces: CLI `scripts/run_capsule.py --capsule NAME --topic TEXT --params PATH --output-dir DIR`.

- [ ] Write failing tests that create a temporary local-script capsule package, run `scripts/run_capsule.py`, and assert that the package script received `--topic`, `--params`, and `--output-dir`.
- [ ] Run the focused test and confirm it fails because `scripts/run_capsule.py` does not exist.
- [ ] Implement the dispatcher with subprocess execution, merged params, and `reports/capsule_dispatch.json`.
- [ ] Add `scripts/run_capsule.py` to the `npm test` py_compile list.
- [ ] Re-run the focused test and `npm test`.

## Task 2: `run_video.py` Local-Script Guard

**Files:**
- Create: `tests/python/test_run_video_local_script_guard.py`
- Modify: `scripts/run_video.py`

**Interfaces:**
- Consumes: `capsule["execution_mode"]`, `capsule["local_script_path"]`, and existing `--allow_generic_capsule_fallback`.
- Produces: hard failure for local-script capsules without explicit generic fallback.

- [ ] Write a failing subprocess test for `scripts/run_video.py --capsule life_sim --storyboard_only`, asserting it exits non-zero before importing/running `general_video`.
- [ ] Write a second test proving `--allow_generic_capsule_fallback` preserves the route as explicitly non-final generic preview.
- [ ] Run the focused test and confirm current behavior fails the new expectation.
- [ ] Implement the guard immediately after capsule load.
- [ ] Re-run the focused test and relevant existing run-video tests.

## Task 3: Release And Scoring Bypass Detection

**Files:**
- Create: `tests/python/test_capsule_local_script_bypass_guard.py`
- Modify: `scripts/score_video_quality.py`
- Modify: `scripts/release_checkpoint.py`

**Interfaces:**
- Consumes: manifest fields `capsule`, `capsule_name`, `execution_mode`, `execution_script`, `toolchain.execution_script`, and loaded capsule metadata.
- Produces: blocker issue id `local_script_capsule_bypassed` when a local-script capsule release points outside the package script or dispatcher.

- [ ] Write failing tests with a manifest that claims `life_sim` and points to `output/life_sim_rich_heiress_preview/render_preview.py`.
- [ ] Add a passing control test where execution path is `capsules/life_sim.capsule/scripts/life_sim_executor.py`.
- [ ] Run focused tests and confirm they fail.
- [ ] Implement shared helper logic in the existing scoring/release scripts without broad refactors.
- [ ] Re-run focused tests and `npm test`.

## Task 4: Documentation And Verification

**Files:**
- Verify: no output scripts are added to git.

**Interfaces:**
- Produces: a pushed branch with tests passing and a clear commit.

- [ ] Run `python3.12 -m unittest` on new focused tests.
- [ ] Run `npm test`.
- [ ] Run any existing Python tests touched by this change.
- [ ] Check `git status --short` for unrelated files.
- [ ] Commit with message `fix: enforce local script capsule dispatch`.
- [ ] Push branch `fix/capsule-local-script-dispatch` to `origin`.
