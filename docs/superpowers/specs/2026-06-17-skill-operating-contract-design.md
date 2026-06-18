# Skill Operating Contract Design

## Goal

Make the Capsule Cinema skills easier for future agents to discover and follow by converting the current capability-heavy documentation into a clearer operating contract with explicit gates, red flags, and testable pressure scenarios.

The runtime already has strong artifact, QA, channel, and capsule contracts. This design improves the agent-facing skill layer so those contracts are triggered earlier and followed more consistently.

## Scope

This change covers four documentation and validation surfaces:

- Root `skill.md`: add a short agent operating contract near the start of the body.
- `references/production-guide.md`: tighten the route, policy, production, and release gates into superpower-style mandatory flow.
- Skill/capsule tests: add static pressure tests that preserve the operating contract and prevent future regressions.

This change does not add new video generation workflows, new providers, new capsule schemas, or new runtime behavior. It makes existing rules harder to miss.

## Context

Capsule Cinema already has strong execution contracts:

- Workflows and maintenance rules are centralized in `skill.md`.
- Route and channel policy are documented in `references/production-guide.md`.
- Artifact, EditPlan, repair plan, and release checkpoint rules are documented in `references/workflow-state-artifacts.md`.
- `tests/skill.test.js` already verifies metadata, env allowlists, runtime boundaries, prompt snapshots, QA artifacts, and release traceability.
- Ignored private local skills are intentionally out of scope for remote commits and tests.

The gap is that the skill reads more like a capability catalog than an operating discipline. Superpower skills are effective because they front-load the behavior contract: iron law, mandatory phases, red flags, and verification evidence. Capsule Cinema should adopt that shape without duplicating all runtime details in the root skill.

## Approaches Considered

### Recommended: Thin Operating Contract

Add a compact contract to `skill.md`, preserve detailed references, and add static tests for key phrases and boundaries.

Trade-off: This is low risk and fits the existing structure, but it relies on static tests rather than running real agent simulations.

### Stronger: Pressure Scenario Harness

Create a small scenario runner that prompts a subagent or model with unsafe requests and checks whether it refuses, routes, or asks for evidence correctly.

Trade-off: This would test behavior more directly, but it is heavier, slower, and depends on agent/tool availability. It is better as a later phase.

### Broad Refactor: Split Video Production into Multiple Skills

Split generic video production, runtime maintenance, capsule management, account distillation, and release QA into separate skills.

Trade-off: This may improve discovery in the long term, but it risks breaking current OpenClaw packaging and forces a larger migration. It is outside the first implementation.

## Design

### Root Skill Operating Contract

Add a short section near the top of `skill.md` body, before the current boundary and workflow tables. It should state the rules future agents must follow before using the runtime:

- Classify the request route before planning or running tools.
- For capsule tasks, inspect the local SQLite capsule contract before planning.
- Choose only channels approved by the active channel policy and tool registry.
- For new AI video, prototype and inspect one representative hard scene before batching.
- For final delivery, require local artifacts under `output/`, manifest, QA, repair plan when needed, and release checkpoint.
- If a blocker exists, fix it or report it; do not describe the run as complete.

This section should avoid long examples. It should point to `references/production-guide.md` for details.

### Production Guide Gate Shape

Keep the existing Route/Policy/Craft/State model, but make the mandatory gate language easier to scan:

- Add an "Iron Laws" subsection after the design overview.
- Convert the first decision into a route gate with failure behavior.
- Make unapproved channel fallback a named blocker.
- Make reference-remake-without-analysis a named blocker.
- Make release without checkpoint a named blocker.

The guide should keep detailed commands in linked references and wrappers. The goal is not to lengthen the guide; it is to make the mandatory flow harder to bypass.

### Ignored Private Skills Boundary
Ignored private local skills remain local-only and are not rewritten, tested, or committed as part of this remote branch.

### Static Pressure Tests

Extend `tests/skill.test.js` or add a focused JS test file for skill-document contracts. The tests should fail if the operating contract is removed or weakened.

Minimum assertions:

- Root `skill.md` contains an "Agent Operating Contract" section.
- Root `skill.md` points video production tasks to `references/production-guide.md`.
- Root `skill.md` explicitly requires capsule contract inspection before capsule planning.
- `references/production-guide.md` contains named iron laws for approved channels, reference analysis, and release checkpoints.
- Ignored private local skills remain out of scope for remote commits and tests.

These tests are not a substitute for future behavioral pressure scenarios. They protect the first implementation from accidental documentation drift.

## Data Flow

The implementation does not change runtime data flow.

Agent-facing flow after the change:

1. Skill activation loads `skill.md`.
2. The agent reads the operating contract before choosing a workflow.
3. Production tasks route into `references/production-guide.md`.
4. Production guide routes to only the relevant supporting reference files.
5. Runtime wrappers write artifacts under `output/` and existing QA scripts validate them.
6. Tests preserve the documentation contract and existing runtime traceability.

## Error Handling

The documentation should define blocker behavior in operational terms:

- If the route is specialized and no registered wrapper or local-script capsule exists, report the missing route instead of using generic `run_video.py` as final output.
- If a capsule is disabled, archived, inconsistent, missing local assets, or references an unapproved channel, report a blocker or migrate it explicitly.
- If channel policy rejects a provider, retry approved channels or report the blocker; do not silently switch.
- If QA, EditPlan validation, visible copy lint, or release checkpoint fails, repair or report the blocker; do not record success.

## Testing

Implementation should follow test-first discipline for documentation contracts:

1. Add static tests that fail against the current docs.
2. Run the targeted JS test and confirm the expected failure.
3. Update the docs minimally.
4. Run the targeted JS test again and confirm it passes.
5. Run `npm test` for the full repository test contract.

If the implementation later adds a real pressure scenario harness, it should follow the writing-skills pattern: document a baseline failure, add the skill instruction, then verify the agent response changes.

## Out of Scope

- Splitting `capsule-cinema` into multiple installed skills.
- Changing OpenClaw metadata or package format.
- Adding model-provider integrations.
- Reworking SQLite capsule schema.
- Running real video generation as part of this documentation change.
- Adding subagent/model-based pressure tests in the first implementation.
- Changing ignored private local skills in remote commits or tests.

## Acceptance Criteria

- The new root operating contract is short enough to read before action and strong enough to stop unsafe routing.
- Production guide gates make the most common mistakes explicit blockers.
- Ignored private local skills remain out of scope for remote commits and tests.
- Tests lock in the new documentation contract.
- Existing `npm test` continues to pass.
