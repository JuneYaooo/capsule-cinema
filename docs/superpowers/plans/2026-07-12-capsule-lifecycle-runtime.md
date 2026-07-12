# Capsule Lifecycle Runtime Implementation Plan

> **For agentic workers:** Execute inline in this isolated worktree. Do not use subagents.

**Goal:** Connect CapsuleInstance, progressive stage reading, ProductionPlan, and EffectReport to real capsule `plan` and `run` dispatch.

**Architecture:** Add one generic lifecycle adapter that prepares and finalizes artifacts. Dispatch calls it at lifecycle transitions while retaining existing runner commands and public status compatibility.

**Tech Stack:** Python 3.12, Pydantic 2, standard-library `unittest`.

## Global Constraints

- Existing capsule packages remain read-only.
- Existing preset and local-script commands remain compatible.
- Topic inference is deterministic and never fills multiple ambiguous inputs.
- Learning resources are never loaded automatically.
- Public issues do not expose absolute paths, commands, environments, or exception text.
- No domain-specific production vocabulary enters Core.

---

### Task 1: Lifecycle preparation and finalization

**Files:**
- Create: `lib/src/capsules/lifecycle.py`
- Create: `tests/python/test_capsule_lifecycle.py`
- Modify: `lib/src/capsules/__init__.py`
- Modify: `package.json`

**Interfaces:**
- `prepare_lifecycle(definition, topic, params, output_dir, action) -> ResultEnvelope`
- `finalize_lifecycle(bundle, runner_result) -> ResultEnvelope`
- `LifecycleBundle` contains only logical identity, output artifact paths, plan digest, and stages entered.

- [ ] Write failing tests proving topic mapping, ambiguous-input refusal, stage order, deterministic artifacts, environment paths, learning omission, safe write failures, and source immutability.
- [ ] Run `PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_capsule_lifecycle -v` and confirm the missing module/API fails.
- [ ] Implement strict binding through `configure_instance`, stage loading through `load_stage_resources`, deterministic Definition/runner digests, atomic JSON writes, ProductionPlan construction, and EffectReport finalization.
- [ ] Re-run the focused tests and commit the task paths.

### Task 2: Dispatch and CLI integration

**Files:**
- Modify: `lib/src/capsules/dispatch.py`
- Modify: `scripts/capsule.py`
- Modify: `tests/python/test_capsule_core_dispatch.py`
- Modify: `tests/python/test_capsule_core_cli.py`

**Interfaces:**
- `DispatchPlan.lifecycle` stores the prepared bundle.
- `build_dispatch_plan()` prepares lifecycle artifacts and adds `CAPSULE_*_PATH` environment variables.
- `execute_dispatch_plan()` finalizes an EffectReport for every runner attempt.

- [ ] Write failing dispatch tests for both runner families, child environment forwarding, blocked preparation, QA finalization, and release recommendations.
- [ ] Write failing CLI tests proving plan responses include safe lifecycle evidence and ambiguous required inputs return `needs_input` without starting a runner.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement minimal dispatch and CLI wiring while preserving existing public statuses and safe envelopes.
- [ ] Run focused lifecycle, dispatch, and CLI tests.
- [ ] Run all Capsule Core regressions, `npm test`, `git diff --check`, and a real-package plan smoke test.
- [ ] Commit, review the whole branch, merge to local `main` without overwriting its dirty changes, verify merged state, and push `origin/main` after user-authorized integration.
