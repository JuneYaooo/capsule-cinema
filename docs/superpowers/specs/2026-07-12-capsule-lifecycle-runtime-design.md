# Capsule Lifecycle Runtime Integration Design

## Goal

Connect the new capsule Core contracts to the real `plan` and `run` dispatch path
without rewriting existing preset or local-script runners. Existing capsule content
and runner commands remain authoritative.

## Chosen approach

Use a compatibility lifecycle adapter at the dispatch boundary. The adapter creates
standard lifecycle artifacts and passes their paths to child runners through
environment variables. Existing runners may ignore those variables and continue to
work; upgraded runners can consume them immediately.

This is preferred over either leaving the contracts test-only or forcing every
capsule and runner to migrate at once.

## Request binding

The adapter binds request data to `CapsuleInstance` deterministically:

1. Parameters whose names are declared by `input_schema.yaml` are explicit inputs.
2. If the schema declares `topic`, `--topic` fills it when it was not explicit.
3. Otherwise, `--topic` fills the only unresolved required string input.
4. If more than one unresolved required input remains, no guess is made and dispatch
   returns a stable `needs_input` result listing logical input names.
5. Transport parameters that are valid for an existing runner but are not declared
   capsule inputs remain in `params.requested.json`; they are not silently inserted
   into the strict Instance.

Defaults, bounds, enums, strict types, and JSON-safety continue to be enforced by
`configure_instance`. Definition and runner digests are deterministic and contain no
environment values or secrets.

## Progressive stage flow

Lifecycle stages are loaded only at their transition:

- dispatch preparation: `routing`, then `planning`;
- run preparation: `generation`;
- after runner completion: `qa`;
- `learning` is never loaded automatically.

Each loaded stage is written as a JSON context artifact containing logical relative
paths, digests, and authored UTF-8 content in author order. Any unsafe, missing, or
unreadable declared resource blocks dispatch with the existing stable stage issue.

## Production plan

Before returning a plan or starting a run, the adapter builds a generic
`ProductionPlan` with:

- one objective representing the user request;
- evidence and quality requirements for runner completion;
- ordered steps for each stage actually entered;
- logical stage-resource references and digests in `domain_payload`;
- a deterministic plan digest.

The adapter does not add video, repository, scene, subtitle, BGM, or other
domain-specific fields to Core.

## Runner integration

`DispatchPlan` carries lifecycle artifact paths and adds these child environment
variables:

- `CAPSULE_INSTANCE_PATH`
- `CAPSULE_PRODUCTION_PLAN_PATH`
- `CAPSULE_ROUTING_CONTEXT_PATH`
- `CAPSULE_PLANNING_CONTEXT_PATH`
- `CAPSULE_GENERATION_CONTEXT_PATH` for `run`

Existing command construction and preset/local-script behavior stay unchanged.
Public CLI envelopes do not expose commands, local runner paths, environment values,
or capsule source paths.

## Effect report and release decision

After a run attempt, dispatch loads the `qa` stage and writes an `EffectReport`:

- runner exit code zero produces a passing blocker check;
- nonzero exit, start failure, or communication failure produces a failed blocker;
- the Core-derived recommendation is therefore `ready` or `blocked`;
- no caller-provided release recommendation is trusted.

The existing public success and failure statuses remain compatible. Lifecycle data
adds only logical artifact references, plan digest, and release recommendation.

## Artifact layout

All generated files remain inside the requested output directory:

```text
inputs/params.requested.json
lifecycle/capsule.instance.json
lifecycle/capsule.production-plan.json
lifecycle/stages/routing.json
lifecycle/stages/planning.json
lifecycle/stages/generation.json   # run only
lifecycle/stages/qa.json           # after run attempt
lifecycle/capsule.effect-report.json
```

Writes use temporary sibling files followed by replacement so a partial write does
not publish a malformed lifecycle artifact.

## Failure behavior

- Binding failures return stable logical issues and never start the runner.
- Stage-loading failures preserve their stable issue code and never expose absolute
  paths.
- Artifact-write failures return `lifecycle_artifact_write_failed` without exposing
  exception text.
- A runner failure still returns the existing `run_failed` result and additionally
  records a blocked EffectReport when the output boundary is writable.

## Compatibility and testing

Tests cover both preset and local-script runners, topic mapping, ambiguous required
inputs, stage ordering, artifact contents, environment forwarding, effect decisions,
write failures, safe public envelopes, and source-package immutability. Existing
Capsule Core and CLI tests must remain green.

No capsule manifests are rewritten, no generated candidate is activated, and no
commercial or hosted-system design is introduced.
