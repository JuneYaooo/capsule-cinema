# Capsule Cinema Local Core Redesign

Date: 2026-07-11
Status: proposed for final user review
Scope: Capsule Cinema open-source repository only

## 1. Decision

Capsule Cinema will adopt a blueprint-and-instance capsule model:

- A capsule is a versioned, verifiable, configurable video-production promise.
- A capsule definition is separate from a configured instance and from an actual run.
- Capsule authors publish a small interface and reusable production composition.
- Video creators provide episode-specific inputs and adjust a small set of published controls.
- Runs produce evidence and lesson proposals; they never mutate an active capsule automatically.
- The repository remains a local-first, open-source video-production core.

All core operations are local and require no service-side identity, hosted state, or remote execution dependency. Portability comes from a stable package format, CLI JSON contracts, Python APIs, and run artifacts. These interfaces remain domain-neutral and contain no assumptions about downstream products.

## 2. Relationship To Earlier Designs

This design supersedes the implementation direction in:

- `2026-06-25-capsule-v2-video-recipe-design.md`;
- `2026-06-30-capsule-v3-design.md`;
- `2026-06-30-capsule-canonical-archive-design.md`.

Those documents remain historical records. This design preserves their successful decisions:

- reusable recipe data must be separated from raw run evidence;
- fixed assets and reference-only assets must have different semantics;
- active capsules are directory packages under `capsules/<name>.capsule/`;
- contracts and release requirements must be machine-readable;
- shareable packages must be local, portable, hashed, and safe to install;
- planning, generation, QA, and learning must receive different context;
- secrets, run outputs, private material, and ephemeral paths must not leak into a capsule release.

This design replaces these earlier decisions:

- a capsule no longer requires a fixed set of 15 or more files;
- `CARD.md`, `index.md`, and repeated Markdown frontmatter are not hand-maintained sources of truth;
- authors do not hand-maintain `read_order`;
- empty recipe, asset, example, and learning files are not required;
- SQLite is not an active-capsule fallback or evidence store in the new model;
- `preset` and `local_script` do not require different user-facing run commands;
- natural-language string IDs are not considered executable release gates;
- promoted lessons are not appended directly to an active capsule without a reviewed diff and new version.

## 3. Current-System Findings

The current format is structurally valid but product-heavy:

- the eight active capsules contain 15–20 files each;
- capsule text ranges from roughly 328 to 2,242 lines;
- generated capsule prompts range from roughly 6,780 to 86,139 characters;
- package loading eagerly reads runtime, assets, examples, quality rules, and all planning and generation recipe files;
- metadata is duplicated across `capsule.yaml`, `CARD.md`, `index.md`, and `when_to_use`;
- the eight capsules declare 317 release-gate entries, but the dedicated gate runner executes only object-form checker bindings;
- users must choose different commands for `preset` and `local_script` capsules;
- there is no unified first-class flow for local discovery, recommendation, configuration, preview, execution, and review.

The root problem is not missing capability. The root problem is that the distribution package, authoring model, runtime contract, knowledge base, and user interface are treated as one object.

## 4. Product Principles

### 4.1 One production promise

A capsule owns one dominant viewer outcome and one dominant production route. A capsule may support variations, but it must not become a general video-production framework.

### 4.2 One source of truth

`capsule.yaml` is the only required authored file and the only metadata source. Cards, README content, indexes, compiled contexts, dependency locks, and effective-rule reports are generated.

### 4.3 Explicit interface, hidden implementation

Creators see required inputs, published controls, constraints, readiness, proposal, sample, and delivery status. They do not need to know the internal runner kind, Python entrypoint, tool class names, file read order, or rule file locations.

### 4.4 Definition, instance, and run are separate

- Definition: reusable, authored, versioned production knowledge.
- Instance: episode-specific inputs, controls, and approved overrides.
- Run: tools, artifacts, approvals, QA, repairs, and final delivery.

No object silently mutates another object.

### 4.5 Reuse through shallow blocks

Generic production behavior belongs in reusable Production Blocks. The first implementation supports only `Capsule -> Block`. Blocks do not depend on blocks, and capsules do not inherit from capsules.

### 4.6 Evidence before promotion

Runs may produce lesson proposals. A proposal must cite evidence, state its scope, describe the proposed diff, and identify regression risk. Applying a proposal requires validation, a representative sample, QA, and a new capsule or block version.

### 4.7 Progressive disclosure is measured

Stage loading is controlled by a compiler, not directory convention. Compilation reports context size, duplicates, conflicts, unused guidance, effective rules, and referenced assets.

### 4.8 Local-first and portable

All core authoring, discovery, compilation, validation, execution, review, packing, and installation work locally. Share packages vendor their locked block dependencies and require no remote dependency resolution.

## 5. Core Object Model

### 5.1 Production Brief

A short normalized interpretation of the creator's request:

- intent and subject;
- audience and platform when known;
- duration and aspect ratio;
- source mode and available assets;
- audio and voice mode;
- desired viewer outcome;
- explicit constraints and forbidden outcomes.

The brief contains no provider selection, prompt, block, QA, or package implementation detail.

### 5.2 Capsule Definition

The authored reusable definition contains:

- identity and version;
- production promise;
- matching boundaries;
- required and optional inputs;
- four to seven published controls in the normal case;
- exact Production Block dependencies;
- capsule-specific guidance and invariants;
- implementation requirements and local runner entrypoint;
- capsule-specific release gates and review rubrics;
- reusable assets and curated examples.

It contains no per-run values, output paths, credentials, raw feedback, or run evidence.

### 5.3 Capsule Release

A release is an immutable, validated capsule version with:

- exact semantic version;
- content digest;
- locked block versions and digests;
- validation and compilation reports;
- declared verification level;
- representative sample references;
- change summary and compatibility statement.

Release verification levels are:

- `draft`: definition only; no representative sample;
- `sampled`: at least one representative sample exists;
- `verified`: declared release gates passed for a representative sample;
- `proven`: multiple materially different instances passed the defined gates.

`active` may remain an internal availability flag during migration, but it is not a quality claim.

### 5.4 Capsule Instance

An instance records one use of a capsule release:

```yaml
schema_version: capsule.instance/v1
capsule:
  id: felt-asmr
  version: 2.1.0
  digest: sha256:...
inputs:
  food_subject: 巴斯克芝士蛋糕
controls:
  pace: balanced
  tactile_intensity: 70
overrides:
  aspect_ratio: "9:16"
  duration: 36
approvals:
  fallback_policy: same_promise_only
```

Instances live in a workspace, lock an exact capsule release, and never modify the definition. An instance may be saved as a local variation. A variation is an instance preset, not a new capsule.

### 5.5 Production Block

A block is a small reusable production capability that may provide one or more of:

- input or output contract fragments;
- defaults and control mappings;
- stage-specific guidance;
- capability requirements;
- deterministic execution steps;
- checkers or review rubrics.

Blocks must be versioned. They may not contain per-run evidence. The initial dependency model is one level deep.

### 5.6 Run

A run records execution facts:

- exact capsule and block digests;
- instance values;
- production proposal and delivery promise;
- selected tools and approved fallbacks;
- prompts and decision log;
- generated media and EditPlan;
- QA, repairs, and release checkpoint;
- final delivery artifacts;
- lesson proposals.

### 5.7 Lesson Proposal

A proposal records:

- observation;
- evidence from one or more runs;
- applicable conditions;
- target capsule or block;
- operation such as add, replace, remove, or remap;
- before and after values;
- confidence;
- regression risk.

Proposals live under run or workspace output, not in a capsule release.

## 6. Creator Experience

### 6.1 Natural-language entry

Creators describe the desired video without knowing a capsule ID. The system derives a Production Brief and avoids asking for facts already present in the request.

### 6.2 Local matching

Matching occurs only against locally installed capsules.

Hard filtering removes capsules that conflict with:

- intent or source mode;
- required inputs;
- aspect or duration constraints;
- delivery promise;
- local capability availability;
- package, block, asset, or runner validity.

Soft ranking uses:

- intent and format fit;
- audience, platform, aspect, and audio fit;
- available-input fit;
- desired viewer-outcome fit;
- verification level;
- local readiness;
- number of missing inputs.

At most three candidates are shown. Each result explains why it fits, what is missing, what is imperfect, and whether it can run locally. If no capsule can honor the request, the system offers the general production route or a draft-and-sample exploration instead of forcing a poor match.

An explicitly named capsule bypasses ranking but not validation, suitability checks, or preflight.

### 6.3 Generated capsule card

The creator-facing card contains:

- one-sentence promise;
- suitable and unsuitable use cases;
- required and optional inputs;
- published controls;
- representative sample references;
- verification level;
- dynamic local readiness;
- material limitations.

It does not expose package read order, implementation mode, entrypoint, or internal rule locations.

### 6.4 Progressive configuration

Configuration is shown in three layers:

1. blocking required inputs;
2. four to seven published controls;
3. collapsed advanced overrides.

Supported initial control types are `choice`, `range`, `boolean`, `text`, and `asset`. Controls may map to several internal parameters. Arbitrary user-defined expressions are out of scope.

### 6.5 Preflight and proposal

Static local checks run before or during matching. Full preflight runs after instance creation. Checks that do not require a decision remain quiet.

The creator sees a concise proposal containing:

- viewer experience and delivery promise;
- duration, aspect, and audio strategy;
- selected production route;
- important tool choices;
- representative hard sample;
- material risks and blockers;
- release bar.

Approval is required for promise-changing fallback, meaningful quality downgrade, unavailable required input, unapproved channel, high-cost route change, or relaxed blocker. Same-role, same-promise retries may be pre-approved.

### 6.6 Representative hard sample

The sample is selected by risk, not always scene order. Risk signals include identity consistency, material consistency, motion complexity, native audio, lip sync, text, first/last-frame transition, and capsule-specific viewer outcome.

Batch generation cannot begin until the sample is accepted or the user explicitly skips the sample gate.

### 6.7 Run and delivery

Creator-visible run states are:

- `retrying`;
- `needs_input`;
- `needs_approval`;
- `repairable`;
- `blocked`;
- `failed`;
- `complete`.

Final user-level delivery is summarized as:

- `ready`: promise honored and required gates passed;
- `needs_review`: technically usable but named human or model review remains;
- `blocked`: promise, artifact, or blocker failure prevents final delivery.

The delivery summary identifies the final artifacts, promise result, passed checks, remaining review, and smallest repair unit.

## 7. Author Experience

Authors can start from:

- a successful run;
- a reference-video analysis;
- an empty draft;
- a copied snapshot of an existing capsule.

Copying an existing capsule creates an independent definition. It does not create inheritance.

The author flow is:

```text
draft -> promise -> match boundary -> interface -> blocks -> delta guidance
      -> compile -> representative sample -> QA -> immutable release
```

Deriving from a run proposes reusable and non-reusable content separately. It must not copy absolute paths, private material, raw prompts, run IDs, QA reports, or final media into the draft.

Authors work with a summary of promise, inputs, controls, composition, capsule-specific blockers, samples, context size, conflicts, and release readiness. They do not need to inspect every internal file to understand capsule state.

## 8. Capsule V2 Source And Build Layout

### 8.1 Authored source

```text
capsules/<name>.capsule/
  capsule.yaml              # required; sole source of truth
  guidance/                 # optional; capsule-specific prose only
    planning.md
    generation.md
  assets/                   # optional reusable local assets
  runner/                   # optional specialized local implementation
  examples/                 # optional curated, non-authoritative examples
```

No empty optional directory is required.

### 8.2 Generated build artifacts

```text
.build/capsules/<name>/
  CARD.md
  README.md
  capsule.lock.json
  validation_report.json
  effective_rules.json
  compiled/
    routing.json
    planning.json
    generation.json
    qa.json
```

Generated files are reproducible and are not hand-maintained sources of truth.

### 8.3 Share package

The existing `.video-capsule.zip` extension remains. A packed release contains:

```text
manifest.json
<name>.capsule/
  capsule.yaml
  capsule.lock.json
  README.md
  guidance/
  assets/
  runner/
  examples/
  vendor/blocks/
```

Only present directories are included. `vendor/blocks/` contains locked local snapshots so installation and execution require no remote block resolution.

## 9. Capsule V2 Manifest Shape

The authoritative manifest uses these top-level sections:

```yaml
schema_version: capsule.cinema/v2
kind: Capsule
metadata: {}
promise: {}
match: {}
interface:
  inputs: {}
  controls: {}
composition:
  blocks: []
guidance: {}
implementation:
  runner: {}
  requirements: {}
quality:
  release_gates: []
  review_rubrics: []
assets: []
examples: []
```

`metadata` contains only package identity such as ID, version, title, summary, and license.

`promise` describes viewer outcome, delivery medium, dominant route, audio role, and capsule-specific invariants.

`match` declares positive and negative routing boundaries. It is structured data, not a duplicate list of free-form tags.

`interface` declares episode inputs and published controls. Internal control mappings may be inline for simple cases or supplied by a referenced block or local runner.

`composition` references exact local block versions.

`implementation` is internal. Its runner kind does not alter the public run command.

`quality` separates executable or evidence-bound release gates from non-blocking rubrics.

## 10. Production Blocks

Built-in blocks live under:

```text
blocks/<domain>/<name>/block.yaml
```

Initial domains may include `hook`, `structure`, `copy`, `visual`, `motion`, `audio`, and `qa`. Domains are organization only and do not affect dependency resolution.

A block must provide a stable contract, execution behavior, checker, rubric, control mapping, or material stage guidance. A generic paragraph is not sufficient reason to create a block.

Block constraints:

- exact semantic version and digest;
- no nested block dependencies in the first version;
- no capsule dependency;
- no run evidence or local output paths;
- declared applicable stages;
- declared capabilities and conflicts;
- one owner for every rule ID.

## 11. Context Compiler

The compiler replaces authored `read_order`.

### Routing context

Contains identity, promise summary, match, required-input summary, verification, and dynamic readiness. It never loads long guidance, examples, or full QA rules.

### Planning context

Contains promise, current instance, planning blocks, planning guidance, required planning outputs, and planning-stage rules.

### Generation context

Contains the current scene or unit of work, generation blocks, relevant assets, selected runner/tool directives, and generation-stage rules. The entire capsule is not repeated for every scene.

### QA context

Contains actual artifacts, effective release gates, review rubrics, and required evidence.

### Learning context

Contains selected run evidence, current effective rules, and a proposed structured diff. It is not part of ordinary generation.

Compilation reports:

- character or token size by stage;
- duplicate and conflicting rules;
- unused guidance and unreferenced assets;
- unbound blockers;
- effective defaults and control mappings;
- resolved block versions and digests.

Initial context budgets are warnings, not release blockers:

- routing target: no more than 4,000 characters;
- capsule-specific planning delta target: no more than 16,000 characters;
- compiled planning target: no more than 32,000 characters;
- stage context growth from one release to the next: warning above 25 percent without an explicit explanation.

Duplicate owners, conflicts, unreferenced required files, and unbound blockers are release blockers.

## 12. Quality And Learning

Rules are divided into:

- machine invariants;
- release gates;
- review rubrics;
- craft guidance;
- lesson proposals.

A release gate must bind to an executable checker or to a named human/multimodal rubric with required evidence. An unbound natural-language string cannot be a blocker.

Capsule-specific blockers should normally be seven or fewer. More than seven requires an explicit validation explanation. Generic blockers belong to the core or a shared block.

Applying a lesson proposal performs an explicit add, replace, remove, or remap operation. It generates a diff. Publication after applying a lesson requires a representative sample and the affected QA. The new result receives a new version.

## 13. Versioning

Instances lock exact capsule version and digest. No automatic upgrade is allowed.

Version semantics:

- major: promise change, required-input removal or rename, control semantic change, output-type change, incompatible runner route, or old-instance incompatibility;
- minor: optional input or control, new variation, new block, new release gate, expanded aspect/platform support, or meaningful backward-compatible effect enhancement;
- patch: copy correction, prompt or runner bug fix, checker fix, security fix, or internal tuning that adds no required input or blocker and preserves the public promise.

Instance upgrade is explicit and reports input, control, block, gate, and expected-output changes before writing.

## 14. Unified Local CLI And API

All capsule operations are exposed through one local command surface. Existing scripts may remain as compatibility wrappers during migration.

Creator-oriented commands:

```text
capsule list
capsule recommend
capsule show
capsule configure
capsule plan
capsule sample
capsule run
capsule status
capsule inspect-run
```

Author-oriented commands:

```text
capsule init
capsule derive
capsule validate
capsule compile
capsule diff
capsule release
capsule pack
capsule install
capsule lesson
```

The same `capsule run` dispatcher handles generic preset and specialized local-runner capsules. Runner kind is an internal implementation detail.

Every command supports a stable `--json` envelope:

```json
{
  "ok": false,
  "status": "needs_input",
  "data": {},
  "issues": [
    {
      "code": "capsule.input.missing",
      "message": "A product image is required.",
      "subject": "inputs.product_image",
      "remediation": "Provide a local image path."
    }
  ]
}
```

Human-readable output is rendered from the same result object. OpenClaw and other Agent adapters consume the JSON contract rather than parsing terminal prose.

## 15. Error And Approval Model

Core pre-run statuses are:

- `ok`;
- `needs_input`;
- `needs_approval`;
- `blocked`;
- `invalid`.

Run statuses are those defined in the creator experience. Every issue has a stable code, human message, structured subject, and remediation. Technical details are optional and must not contain secret values.

The system fails closed for:

- unsafe package paths;
- secret or private-data leakage;
- missing or invalid locked dependency;
- promise-changing unapproved fallback;
- unbound blocker;
- missing required evidence for a declared gate;
- specialized route represented by a generic final output;
- digest mismatch or tampered installed package.

## 16. V1 Compatibility And Migration

Migration is incremental and non-destructive.

### 16.1 Normalized internal model first

The runtime first gains a single normalized internal object model. Both package formats load into it:

- `capsule.package.v1` through a read-only compatibility adapter;
- `capsule.cinema/v2` through the native loader.

Consumer matching, preflight, proposal, unified dispatch, and QA operate on the normalized model. This allows usability work before rewriting every package.

### 16.2 No SQLite active fallback

The v2 runtime does not restore SQLite as an active-capsule source. Historical SQLite code and tests may inform migration, but active packages resolve from `capsules/<name>.capsule/` or an explicit local package path.

### 16.3 Per-capsule migration

Migration writes a candidate under a migration workspace, compiles and validates it, compares its effective promise and behavior, and only then replaces the active source through a reviewed commit. Git history preserves the old package.

Pilot order:

1. `art_motion`: local-runner route with small textual contract;
2. `felt_asmr`: complex preset route with large visual guidance and QA;
3. `guofeng_history` and `ecommerce_product_showcase`;
4. `high_abstraction_growth_card` and `ai_open_source_tool_radar`;
5. `life_sim`;
6. `repo_showcase` last because it is the largest and most actively changing package.

For each capsule, migration must:

- preserve the production promise and required outputs;
- classify every old field as core policy, block, capsule delta, instance value, run evidence, generated view, or obsolete content;
- extract repeated generic rules into blocks instead of copying them;
- convert input schema into the published interface;
- propose, not silently invent, Macro Controls;
- bind or downgrade old string blockers appropriately;
- remove duplicated metadata and authored read order;
- keep reusable assets and runner code;
- exclude raw evidence and ephemeral paths;
- compile a context-size and effective-rule comparison;
- pass a representative dry run or sample appropriate to the capsule.

### 16.4 Compatibility window

During migration, v1 and v2 packages may coexist under the same `capsules/` root and are detected by schema. Existing `run_video.py`, `run_capsule.py`, and package commands become wrappers over the unified service or remain operational until all active packages have migrated.

No v1 package is rewritten automatically when merely loaded or run.

## 17. Security And Portability

The current safe-pack and safe-install behavior is retained and extended to block locks and generated source views.

Validation rejects:

- absolute paths in portable definitions;
- path traversal and symlink escape;
- `output/`, cache, temp, or editor-state content;
- API keys, authorization data, cookies, tokens, or private environment values;
- raw run evidence in definition, guidance, examples, or assets metadata;
- undeclared executable entrypoints;
- missing asset or block digests in a release;
- remote dependency requirements.

Local runner execution remains an explicit capability and approval boundary. Installing a package validates hashes and paths; it does not execute its runner.

## 18. Testing Strategy

Implementation follows test-driven development.

### Unit tests

- v2 schema normalization and validation;
- v1 adapter normalization;
- semantic version and digest logic;
- match hard filters and deterministic ranking;
- input and control validation;
- control mapping;
- block resolution and conflict detection;
- stage compiler inclusion/exclusion;
- context budget reporting;
- gate binding and effective-rule compilation;
- lesson proposal add/replace/remove/remap behavior;
- safe path, secret, evidence, and digest checks.

### Contract tests

- stable JSON envelopes and issue codes for every CLI command;
- generated card and README derive from `capsule.yaml`;
- source changes deterministically alter lock and digest;
- human output and JSON output represent the same result;
- `preset` and local runner use the same public dispatch contract.

### Real-package tests

- all eight current active capsules load through v1 adapter during migration;
- all migrated capsules load natively;
- compiled stages do not receive unrelated files or evidence;
- current delivery promises and key defaults survive normalization;
- fixed and reference-only asset semantics remain intact;
- v1 packages are not modified by loading, validation, or running.

### Integration tests

- natural-language brief to local recommendation;
- explicit capsule to instance and proposal;
- missing input and blocked capability flows;
- same-promise fallback and promise-changing approval flows;
- representative sample gate;
- unified dispatch dry runs for preset and local runner;
- QA to ready, needs-review, and blocked delivery summaries;
- lesson proposal to validated new release;
- pack, install, digest verification, and offline block resolution.

### Migration tests

- golden normalized output for each pilot capsule;
- field-classification report with no unclassified data;
- no secret, output path, raw evidence, or duplicated metadata in migrated source;
- old and new compiled promise/default comparisons;
- context-size reduction report;
- effective blocker binding report.

## 19. Rollout Slices

The implementation plan should decompose this design into independently reviewable slices:

1. normalized model, stable result envelope, and v1 adapter;
2. unified local catalog, show, doctor, and dispatch facade;
3. v2 schema, native loader, generated card, and lock/digest;
4. Capsule Instance, controls, proposal, and preflight flow;
5. Production Blocks and stage context compiler;
6. executable gate/rubric model and lesson proposals;
7. authoring commands and deterministic share package;
8. `art_motion` and `felt_asmr` pilot migrations;
9. remaining capsule migrations;
10. removal of obsolete v1-only internals after the compatibility exit criteria pass.

Each slice must leave the repository runnable. Existing unrelated worktree changes must not be reset or overwritten.

## 20. Acceptance Criteria

### Creator usability

- A creator can start from a natural-language request without knowing a capsule ID.
- Recommendation returns no more than three locally runnable candidates with explanations.
- Required questions are limited to missing blocking inputs.
- Normal configuration exposes four to seven controls per capsule where appropriate.
- One public run flow works for preset and local-runner capsules.
- Promise-changing fallbacks always require approval.
- Final delivery reports ready, needs review, or blocked with remediation.

### Author usability

- A new capsule requires only `capsule.yaml`.
- Cards, README, lock, compiled contexts, and effective-rule reports are generated.
- Deriving from a run creates a draft without evidence or path leakage.
- Authors can see effective rules, block ownership, context size, conflicts, samples, and release readiness in one summary.
- Applying a lesson creates a diff and cannot mutate an existing release.

### Correctness

- Every release blocker has a checker or evidence-bound rubric.
- Stage compilation excludes unrelated context and raw evidence.
- Instances lock an exact version and digest.
- Installed releases and vendored blocks are hash-verified and work offline.
- The eight current capsules remain runnable throughout migration.

### Complexity reduction

- No duplicate hand-authored metadata across card, index, and manifest.
- No required empty recipe, asset, example, or learning files.
- Routing context remains at or below the target budget for all migrated capsules.
- Compiled planning context for each migrated capsule is materially smaller than the current eager prompt or has an explicit reviewed exception.
- No capsule-specific release blocker is a bare string ID.

### Scope integrity

- Core authoring, discovery, compilation, validation, execution, review, packing, and installation work locally.
- Core operation requires no service-side identity, hosted state, or remote execution dependency.
- Core schemas contain only video-production, package, compatibility, execution, and evidence concepts.
- README and public documentation describe a local open-source production core.

## 21. Documentation Changes Required By Implementation

When implementation begins, the following current documentation must be reconciled rather than supplemented with another competing model:

- `README.md` and `README.en.md`;
- `skill.md`;
- `references/capsule-package-format.md`;
- `references/production-guide.md`;
- `references/workflow-state-artifacts.md`;
- `references/architecture.md`;
- command examples and package lifecycle descriptions.

Historical design documents remain historical. Current public and runtime documentation must point to one canonical capsule model.

## 22. Final Design Summary

Capsule Cinema becomes a local production core with six explicit objects:

```text
Production Brief
      -> Capsule Definition / Release
      -> Capsule Instance
      -> Production Blocks + local Runner
      -> Run and delivery artifacts
      -> Lesson Proposal
      -> reviewed new Release
```

The capsule is small because it owns only its production promise, public interface, composition, unique delta, and evidence-bound release bar. The runtime is powerful because shared policy, blocks, compilation, execution, QA, packaging, and migration live in the core. The user experience is simple because internal implementation choices are hidden behind one local interface. The project remains open-source, self-contained, and local-first.
