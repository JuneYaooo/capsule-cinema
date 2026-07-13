# Skill Lifecycle Consumption Implementation Plan

> **For agentic workers:** Execute inline in this isolated worktree. Do not use subagents.

**Goal:** Make OpenClaw capsule runs consume staged lifecycle context and produce QA-aware EffectReports.

**Architecture:** Extend generic lifecycle evidence handling, then bridge it into preset and local-script runtime paths without changing the non-capsule route.

**Tech Stack:** Python 3.12, JavaScript ES modules, Pydantic 2, standard-library unittest.

## Global Constraints

- Use tests before production changes.
- Preserve existing OpenClaw and CLI result fields.
- Never infer multiple ambiguous capsule inputs.
- Never treat process exit zero as deliverable when richer QA says otherwise.
- Do not load learning automatically or rewrite capsule sources.

### Task 1: QA-aware lifecycle evidence

**Files:** `lib/src/capsules/lifecycle.py`, `lib/src/capsules/dispatch.py`, `tests/python/test_capsule_lifecycle.py`, `tests/python/test_capsule_core_dispatch.py`.

- [ ] Add failing tests for structured runner payload extraction and QA-driven blocked/review-required decisions.
- [ ] Implement safe payload extraction and evidence checks.
- [ ] Run focused tests and commit.

### Task 2: Runtime context consumption

**Files:** `scripts/run_video.py`, `scripts/run_capsule.py`, `scripts/capsule_runtime.py`, related runtime tests.

- [ ] Add failing tests for staged prompt injection, environment-context reuse, local-script delegation, and lifecycle params forwarding.
- [ ] Implement the minimal preset and local-script bridge.
- [ ] Run focused tests and commit.

### Task 3: OpenClaw Skill surface and delivery

**Files:** `skill.md`, `index.js`, `references/capsule-core-cli.md`, JavaScript/Python tests.

- [ ] Add `capsule_params_json` routing and lifecycle output fields.
- [ ] Update concise Skill instructions and references.
- [ ] Run Core, runtime, package, npm, and real-capsule smoke tests.
- [ ] Review, merge into dirty local main with the authorized safe autostash workflow, verify, and push `origin/main`.
