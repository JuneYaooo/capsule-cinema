# Repo Showcase Lossless Shadow Migration Design

Date: 2026-07-11
Status: approved direction; written-spec review pending
Pilot subject: `Agents365-ai/drawio-skill`
Scope: local open-source Capsule Cinema core only

## 1. Decision

`repo_showcase` will be the first effect-parity stress test for the native capsule direction. Migration will use a shadow candidate and will not rewrite, replace, stage, or commit the current active v1 package while the candidate is being built and evaluated.

The baseline is the current working-tree state of:

```text
capsules/repo_showcase.capsule/
```

including the user's uncommitted changes. The baseline is frozen by content digest and inventory before candidate work begins.

The only representative subject for this pilot is:

```text
Agents365-ai/drawio-skill
```

This pilot proves one controlled migration path. It does not claim that one sample proves parity for every repository or every future capsule.

## 2. Non-Negotiable Principle

Simplification may remove duplicate maintenance, empty structure, generated views, and reviewed obsolete content. It may not remove or weaken anything that affects:

- the production promise;
- creator inputs or defaults;
- user-value extraction;
- title, hook, copy, or publishing logic;
- visual layout and motion;
- source-evidence integrity;
- reusable assets;
- the specialized renderer;
- release blockers or review rubrics;
- local QA, compliance, or delivery artifacts;
- representative output quality.

Progressive reading changes when effective knowledge is compiled into a stage context. It does not change what effective reusable knowledge the release owns.

The candidate cannot replace the active capsule unless all preservation and effect-parity gates pass.

## 3. Why Repo Showcase Is a Valid Stress Test

The current package combines:

- a specialized local renderer;
- fixed 3:4, 1080×1440, ten-second silent-video behavior;
- packaged BGM;
- browser-only approved source evidence;
- source provenance and manifest requirements;
- four or more rich middle visuals;
- adaptive middle-image motion;
- user-value, hook, title, copy, and publishing rules;
- a large quality-rule and release-gate surface;
- local QA, compliance, publishing-package, and artifact-manifest outputs.

A migration that preserves this capsule's controlled sample is stronger evidence than migrating a small text-only recipe. It is deliberately not the easiest pilot.

## 4. Controlled Variables

The parity experiment changes only:

- package representation;
- Definition normalization;
- Instance creation and input binding;
- stage-context compilation;
- generated build reports.

The first parity run must keep these identical between old and new routes:

- `repo_slug` and all episode inputs;
- frozen actual-browser source asset manifest;
- exact source image bytes;
- exact packaged BGM bytes;
- renderer source bytes;
- render profile values;
- ffmpeg and local rendering toolchain when available;
- output duration, dimensions, page count, and production mode;
- QA and release-checker implementations.

The candidate initially reuses the current specialized renderer. Rewriting or generalizing the renderer is outside this pilot because it would confound package migration with visual-engine changes.

No paid model or production provider may be invoked by this pilot without a new explicit user confirmation. Local browser capture, local rendering, ffmpeg, and deterministic analysis are allowed.

## 5. Baseline Freeze

Before creating the candidate, write an ignored run artifact under:

```text
output/capsule_migrations/repo_showcase/<timestamp>/baseline/
```

It contains:

```text
baseline.json
package-digest.json
source-inventory.json
section-inventory.json
input-contract.json
runtime-contract.json
effective-rules.json
gate-inventory.json
runner-contract.json
asset-inventory.json
example-inventory.json
sample-input.json
sample-source-manifest.json
```

The package digest covers authored and reusable package files. `__pycache__`, `.pyc`, system metadata, run outputs, and temporary files are inventoried as excluded ephemeral data and do not count as production knowledge.

The baseline record includes Git HEAD, dirty-path list, per-file digest, whole-package digest, Python version, ffmpeg version, and renderer digest. It contains no secret values.

Freezing is read-only with respect to the active package.

## 6. Preservation Manifest

Every meaningful source section receives one disposition:

```text
preserved_in_definition
moved_to_guidance
moved_to_runner
moved_to_asset
moved_to_example
extracted_to_block
converted_to_checker
converted_to_rubric
generated_view
archived_run_evidence
obsolete_with_evidence
excluded_ephemeral
```

The manifest records:

- source file and stable section identifier;
- source digest;
- disposition;
- target owner and target path or field;
- whether it affects the production promise;
- whether it is loaded for routing, planning, generation, QA, or learning;
- validation evidence;
- reviewer note when content is merged, downgraded, or declared obsolete.

Hard gates:

```text
source coverage = 100%
unclassified = 0
promise-affecting obsolete items = 0
silent deletion = 0
```

String release gates are not discarded. Each becomes a checker, an evidence-bound rubric, capsule guidance, or a reviewed advisory. A blocker cannot be downgraded silently.

Production Blocks may be identified in the manifest, but creating a general Block library is outside this pilot. Candidate-local extraction is allowed only when the locked content is vendored and parity remains measurable.

## 7. Shadow Candidate Layout

The candidate lives outside the active capsule root:

```text
migration-workspace/repo_showcase-v2.candidate/
  capsule.yaml
  guidance/
  assets/
  runner/
  examples/
  build/
    CARD.md
    README.md
    capsule.lock
    preservation-manifest.json
    validation-report.json
    compilation-report.json
    effective-rules.json
    contexts/
      routing.json
      planning.json
      generation.json
      qa.json
```

The candidate is never discovered as an active capsule. It becomes eligible for activation only after parity passes and the user explicitly approves replacement in a later reviewed change.

The source may remain large. File-count reduction and token reduction are not acceptance criteria for the lossless pass.

## 8. Instance And Input Binding

The pilot creates a local Instance for `Agents365-ai/drawio-skill`:

```yaml
schema_version: capsule.instance/v1
capsule:
  name: repo_showcase
  candidate_digest: sha256:...
inputs:
  repo_slug: Agents365-ai/drawio-skill
  production_mode: short_silent_repo_showcase
  target_duration: 10
  target_platform: wechat_channels
  source_asset_manifest_path: ...
resolved:
  defaults_applied: [...]
  inferred_values: [...]
approvals:
  fallback_policy: no_promise_change
```

Rules:

- explicit input beats an inferred value;
- defaults are recorded, not silently hidden;
- missing required inputs produce `needs_input`;
- invalid types, ranges, or enums produce `invalid`;
- instance values never mutate the Definition;
- capsule inputs are not confused with legacy runner CLI flags;
- the Instance locks the candidate digest and renderer digest used by the parity run.

## 9. Progressive Stage Compiler

The pilot compiler emits four contexts.

### Routing

Contains only promise, suitability, input summary, output summary, verification state, and local readiness. It excludes craft guidance, renderer internals, full examples, and QA implementation detail.

### Planning

Contains the effective input contract, user-value method, subject/value extraction, title and hook rules, copy rules, source-evidence planning constraints, page structure, and applicable planning rubrics.

### Generation

Contains the resolved Instance, exact source manifest, layout and motion rules, renderer contract, fixed assets, audio contract, and deterministic generation blockers.

### QA

Contains effective release checkers, evidence-bound rubrics, output contract, source provenance requirements, publishing-package requirements, and artifact requirements.

Each compilation report contains:

```text
included source sections
excluded source sections and reason
effective rules
duplicate merges
conflicts
referenced assets and digests
context characters and bytes
unmapped sections
```

Hard gates:

```text
unmapped sections = 0
unresolved conflicts = 0
missing required assets = 0
promise-affecting excluded sections = 0
```

Context size is reported but has no maximum in this lossless pilot. Later optimization may reduce it only while parity continues to pass.

## 10. Single-Sample Dual Run

The old and new routes consume the same frozen sample inputs and exact source assets.

### Old route

Uses the frozen current working-tree v1 package and current specialized renderer.

### New route

Uses the shadow candidate, Instance, compiled stage contexts, and the same specialized renderer.

Both routes write to separate ignored output directories. Neither route changes the active package.

The browser source manifest is frozen before the dual run. The parity comparison does not recapture remote pages between old and new runs, because changed remote content would invalidate the controlled experiment.

## 11. Effect-Parity Gates

### Contract parity

- required inputs and accepted values are preserved;
- fixed 3:4 output is preserved;
- resolution is 1080×1440;
- target duration is 10 seconds with tolerance no greater than 0.05 seconds;
- production mode remains `short_silent_repo_showcase`;
- no voiceover or burned subtitles appear;
- packaged BGM identity and configured mix value are preserved;
- required artifacts and publishing package are present.

### Profile parity

The normalized renderer profile must be semantically identical after removing only run-specific absolute paths, timestamps, and output identifiers. Any other difference requires review and blocks automatic parity.

### Source-evidence parity

- exact source asset digests match;
- each scene uses an approved actual-browser manifest item;
- no generated or reconstructed card is represented as real source evidence;
- rich middle visual count is not reduced;
- source priority and fallback behavior are unchanged.

### Visual parity

Sample decoded frames at fixed timestamps across the ten-second output. Requirements:

- canvas, title area, middle panel, bottom cards, identity badge, and page count match the established composition;
- no new overlap, clipping, illegible copy, blank frame, frozen tail, or unexpected safe-space bar;
- motion type and direction remain appropriate to the same source image geometry;
- perceptual similarity for deterministic corresponding frames is SSIM ≥ 0.995 unless a documented encoding-only difference explains the result;
- exact frame or final-file digest equality is recorded when achieved but is not required across nondeterministic encoders.

### Content parity

- same subject identity;
- same user-value promise;
- same or stronger first-screen hook;
- no README-only feature dump;
- no visible production jargon or internal strategy terms;
- bottom-card fact chain remains complete;
- title, cover, first screen, publishing copy, and pinned comment remain aligned;
- no unsupported factual claim is introduced.

### QA parity

- every executable old blocker applicable to the sample still executes;
- every old evidence-bound requirement remains represented;
- old passing gates must not newly fail;
- new candidate may add stricter findings, but they cannot be hidden to claim parity;
- local video QA, compliance review, release checkpoint, and artifact-manifest checks must pass at least as strongly as the baseline.

### Human review

A side-by-side review compares old and new outputs without using package origin as a quality signal. Review dimensions are:

- one-glance value clarity;
- source credibility;
- visual polish;
- readability;
- pacing and motion;
- usefulness to the target viewer;
- save/share potential;
- overall preference.

The new candidate must be rated equal or better overall. A worse result blocks activation even if structural tests pass.

## 12. Failure And Rollback

Any preservation, compilation, contract, visual, content, QA, or human-review failure leaves the active v1 package unchanged.

The failure report records:

- failed gate;
- old and new evidence;
- implicated source sections;
- proposed candidate-only correction;
- whether the candidate must be rebuilt and rerun.

Corrections apply only to the candidate. The active v1 package is never rewritten as a side effect of comparison.

## 13. Deliverables

The pilot produces:

- immutable baseline metadata and digests;
- complete source and section inventory;
- preservation manifest with zero unclassified content;
- shadow native candidate;
- locked Instance for `Agents365-ai/drawio-skill`;
- routing, planning, generation, and QA contexts;
- compilation and effective-rule reports;
- old and new output packages;
- machine parity report;
- side-by-side frame/contact-sheet comparison;
- human review scorecard;
- activation recommendation: `pass`, `revise_candidate`, or `reject`.

It does not replace the active capsule in this pilot.

## 14. Acceptance Criteria

The pilot is complete only when:

- the current dirty v1 baseline is frozen without mutation;
- source coverage is 100% and unclassified content is zero;
- no promise-affecting knowledge is silently removed or downgraded;
- the candidate compiles with zero unmapped sections or unresolved conflicts;
- the same frozen source assets and renderer are used by both routes;
- all contract, profile, source-evidence, visual, content, QA, and human-review parity gates pass;
- no paid provider was invoked without explicit confirmation;
- the active v1 package remains unchanged;
- candidate activation remains a separate explicit user decision.
