# Capsule Local Script Dispatch Design

## Goal

Make `local_script` capsules executable through one framework-owned path so mature capsules cannot be silently bypassed by one-off scripts under `output/`.

## Approved Behavior

- A capsule with `execution_mode: local_script` must run through `entrypoints.local_script`.
- `scripts/run_video.py --capsule <name>` must not route a `local_script` capsule into the generic `general_video` pipeline.
- A generic fallback may still be requested explicitly for exploration, but it must be marked as non-final preview work and must not be treated as a capsule release.
- Release and scoring checks must report a blocker when a manifest claims a `local_script` capsule but its execution script is outside the capsule package or an approved framework script.
- The fix is framework-level. `life_sim` is the motivating case, but the guard applies to every active local-script capsule.

## Current Context

Capsule packages already expose the needed metadata:

- `capsule.yaml` contains `execution_mode`.
- `capsule.yaml.entrypoints.local_script` points to the package-owned script.
- `scripts/capsule_runtime.py` can load package metadata and resolve `local_script_path`.
- `scripts/run_video.py --capsule` currently reads capsule defaults and injects the capsule prompt, then calls `run_general_video_flow`.

The gap is execution authority. A local-script capsule can declare a script and quality rule, but the public runtime wrapper does not force that script to own generation. This allowed `output/life_sim_rich_heiress_preview/render_preview.py` to act as an unregistered implementation and override the capsule defaults.

## Architecture

Add a small dispatcher script, `scripts/run_capsule.py`, as the canonical local-script entry point.

The dispatcher will:

1. Load the capsule package with `load_capsule()`.
2. Require `execution_mode: local_script`.
3. Resolve `local_script_path` from the package.
4. Merge user params with capsule defaults into a generated params file.
5. Call the package script with `--topic`, `--params`, and `--output-dir`.
6. Write a framework run record that includes the capsule name, local script path, return code, and whether this run is a final capsule execution.

`scripts/run_video.py` will become stricter:

- For `execution_mode: local_script`, it exits with a clear error unless the user passes `--allow_generic_capsule_fallback`.
- With `--allow_generic_capsule_fallback`, it may continue to generic video generation, but marks the delivery promise as `generic_preview` and adds a non-final fallback marker to the result and manifest.

Release and scoring checks will add a bypass detector:

- If a manifest has a capsule whose package is `local_script`, then the manifest must show a script path inside `capsules/<name>.capsule/scripts/` or an approved framework dispatcher path.
- If the manifest points to an `output/.../*.py` script or omits the execution path for a local-script capsule release, the check produces a delivery blocker.

## Data Flow

```text
user request
  -> scripts/run_capsule.py --capsule life_sim --topic ... --params ... --output-dir ...
  -> scripts/capsule_runtime.py loads package contract
  -> capsules/life_sim.capsule/scripts/life_sim_executor.py
  -> output run dir artifacts
  -> framework run record and artifact manifest
  -> QA/release checks verify execution path
```

Generic preview remains possible, but the data flow is explicit:

```text
scripts/run_video.py --capsule life_sim --allow_generic_capsule_fallback
  -> generic route
  -> result is marked non-final generic_preview
  -> release checks cannot promote it as a capsule final
```

## Error Handling

- Missing capsule package: fail before creating output.
- Capsule is not `local_script`: fail with guidance to use `scripts/run_video.py` for preset capsules.
- Missing `entrypoints.local_script`: fail with a package validation-style message.
- Local script returns non-zero: preserve its notes and return non-zero.
- Output manifest missing after a supposedly successful local-script run: fail the dispatcher.
- Generic fallback used for a local-script capsule: allow only when explicit and record it as non-final.

## Testing

Tests must cover behavior without paid media or network calls:

- A fake local-script capsule run proves `scripts/run_capsule.py` invokes the package script with the expected arguments and writes run metadata.
- `scripts/run_video.py --capsule life_sim` exits before `general_video` unless `--allow_generic_capsule_fallback` is present.
- Local-script capsule defaults, especially `aspect_ratio: 16:9` for `life_sim`, stay visible to the dispatcher params.
- A manifest claiming a local-script capsule with `output/.../render_preview.py` is scored or released as blocked.

## Out Of Scope

- Completing the full `life_sim` renderer backend.
- Regenerating the rejected rich-heiress preview.
- Changing provider credentials or writing secrets to files.
- Reworking all historical `output/` scripts.
