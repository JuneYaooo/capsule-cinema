# Video To Capsule Workflow Design

## Goal

Add a first-class `video-to-capsule` workflow that analyzes a local source video with a user-selected video analysis tool, produces reviewable capsule evidence and a capsule draft, and optionally writes a valid active OKF capsule package.

## User Decisions

The approved behavior is:

- The workflow is two-step by default: generate analysis and a draft first, write a package only when explicitly requested.
- Video analysis models are selected through the existing tool registry and capability layer, not hard-coded into the workflow.
- The analysis keeps both levels of output: scene/beat-level evidence plus capsule-level reusable rules.
- The source video is not packaged by default. If `include_source_video=true`, it is copied into the capsule as a `reference_only` asset.

## Current Context

The repo already has the necessary building blocks:

- `Gemini3VideoAnalyzerTool` can call a Gemini-compatible video analysis endpoint.
- `scripts/run_tool.py` can invoke registered tools by name.
- `lib/config/tool_registry.yaml` maps tool names to Python modules.
- `lib/config/tool_capabilities.yaml` is the capability/preflight layer used by capsules and tools.
- `scripts/capsule_package_create.py` creates valid `video.okf.capsule.v1` packages.
- `index.js` routes OpenClaw workflow inputs to Python scripts.

The missing piece is an orchestration workflow that turns a source video into structured evidence, derives a capsule draft, and writes a capsule package only after explicit user intent.

## Architecture

Add an independent workflow named `video-to-capsule`.

It should not alter the existing generation workflows:

- `full-video`
- `storyboard-only`
- `concat`
- `feedback`

The new workflow is analysis-first. It reads a local video, calls the selected analyzer tool, normalizes the response into stable contracts, writes analysis artifacts to a workspace, and optionally creates a capsule package.

The workflow has three layers:

1. Entry adapter: `index.js` accepts OpenClaw inputs and routes `workflow=video-to-capsule` to a new Python script.
2. CLI orchestration: `scripts/analyze_video_to_capsule.py` validates inputs, resolves the analyzer tool, runs analysis, writes artifacts, and optionally writes a package.
3. Pure Python helpers: a new small module handles response normalization, draft building, and package materialization so tests can cover behavior without network calls.

## Inputs

Add OpenClaw and CLI inputs:

- `source_video_path`: required for `video-to-capsule`; local source video path.
- `video_analysis_tool`: optional tool name; default `Gemini3VideoAnalyzerTool` if available.
- `capsule_name`: required when `write_capsule=true`; optional for draft-only runs, where it can be inferred from the video filename.
- `capsule_display_name`: optional display name; defaults to a title derived from `capsule_name`.
- `capsule_summary`: optional human summary; defaults to the analyzer-derived summary.
- `write_capsule`: boolean, default `false`; creates `capsules/<name>.capsule/` only when true.
- `include_source_video`: boolean, default `false`; when true and `write_capsule=true`, copies the source video into package assets as `reference_only`.
- `overwrite_capsule`: boolean, default `false`; controls whether an existing package may be replaced.
- `analysis_prompt`: optional custom prompt appended to the workflow's required JSON schema prompt.
- `target_platform`: optional platform hint, default empty.

## Outputs

Return and expose:

- `workspace_dir`
- `video_analysis_path`
- `capsule_draft_path`
- `capsule_dir`
- `capsule_name`
- `analysis_tool_used`
- `write_capsule`
- `include_source_video`
- `warnings`

Draft-only runs return `capsule_dir=null`.

## Workspace Artifacts

The workflow writes:

```text
output/<run_id>/
  analysis/
    source_video_metadata.json
    video_breakdown.json
    capsule_draft.json
    analyzer_raw_response.json
  artifact_manifest.json
```

`video_breakdown.json` is evidence for this one source video. It may include scene-by-scene observations, timestamps, visible text, narration, edit rhythm, visual style, audio notes, pacing notes, and analyzer confidence.

`capsule_draft.json` is the reusable recipe proposal. It should map cleanly to active capsule surfaces:

- identity and routing metadata
- when-to-use and when-not-to-use
- input fields
- runtime defaults
- structure recipe rules
- copy recipe rules
- visual recipe rules
- audio recipe rules
- motion recipe rules
- quality rules
- promoted lessons
- optional source asset metadata

The active capsule package must not store `video_breakdown.json` or `analyzer_raw_response.json`. Those stay in the workspace as evidence.

## Analyzer Tool Capability

Register video analysis tools in both registry layers.

`lib/config/tool_registry.yaml` should keep the callable mapping, with `Gemini3VideoAnalyzerTool` categorized as `video_analysis` or `quality_check`.

`lib/config/tool_capabilities.yaml` should add a tool entry for `Gemini3VideoAnalyzerTool` with:

- `modality: video_analysis`
- `provides.flags.source_video_analysis: true`
- `provides.flags.scene_breakdown: true`
- `provides.flags.capsule_recipe_inference: true`
- `requires_env: [GEMINI3_API_KEY, GEMINI3_BASE_URL]`

`lib/config/capabilities.yaml` should define the `video_analysis` modality vocabulary used above.

The first implementation may rely on `Gemini3VideoAnalyzerTool`, but the workflow must resolve tools by name so later providers can be added without changing the orchestration API.

## Analyzer Prompt Contract

The workflow should pass a strict prompt that asks the analyzer for JSON with this shape:

```json
{
  "summary": "short source video summary",
  "source_profile": {
    "likely_format": "short_video|explainer|product_showcase|story|music_mv|other",
    "aspect_ratio": "9:16|16:9|1:1|unknown",
    "target_platform": "optional platform inference",
    "primary_audience": "optional audience inference"
  },
  "segments": [
    {
      "start_time": "00:00.000",
      "end_time": "00:03.000",
      "beat": "what happens in this segment",
      "visuals": "subject, scene, composition, style",
      "motion": "action, camera, transition, edit rhythm",
      "copy": "visible text, subtitles, hook, narration meaning",
      "audio": "speech, music, sfx, mix notes",
      "reuse_lesson": "what can be reused as a recipe rule"
    }
  ],
  "capsule_recipe": {
    "when_to_use": [],
    "when_not_to_use": [],
    "structure_rules": [],
    "copy_rules": [],
    "visual_rules": [],
    "audio_rules": [],
    "motion_rules": [],
    "quality_rules": [],
    "default_runtime": {}
  },
  "warnings": []
}
```

The normalizer must tolerate partial model output. Missing arrays become empty arrays, missing strings become empty strings, and invalid JSON becomes a blocked analysis result rather than a successful capsule draft.

## Package Materialization

When `write_capsule=true`, the workflow creates a package through the existing capsule package creation path rather than hand-writing an ad hoc directory.

The package should use:

- `profile: video.okf.capsule.v1`
- `execution_mode: preset`
- `entrypoints.preset: general_video`
- `primary_workflow` inferred from analysis, defaulting to `generic_ai_video`
- capabilities inferred from the draft, defaulting to `image_to_video`, `tts`, `bgm`
- tags inferred from source profile and recipe, with stable fallback tags `video-analysis` and `ai-video`

After scaffolding, controlled surfaces are updated from `capsule_draft.json`:

- `CARD.md` routing summary and usage boundaries
- `contracts/input_schema.yaml` input fields
- `contracts/runtime.yaml` defaults and output contract hints
- `recipes/structure.md`
- `recipes/copy.md`
- `recipes/visual.md`
- `recipes/audio.md`
- `recipes/motion.md`
- `quality/rules.yaml`
- `learning/promoted_lessons.yaml`
- `assets/index.yaml` only when `include_source_video=true`

Then `validate_capsule_dir()` must run. If validation fails, the workflow reports failure and does not claim the package is usable.

## Source Video Asset Rule

Default behavior:

- Do not copy the source video into the active capsule.
- Record the original source path only in workspace evidence.

When `include_source_video=true` and `write_capsule=true`:

- Copy the source video under `capsules/<name>.capsule/assets/source_video<ext>`.
- Add an `assets/index.yaml` entry:
  - `role: source_video_reference`
  - `reuse: reference_only`
  - `description: Source video used to infer this capsule; reference only, not reused as final media.`
- Never mark the source video as `reuse=always`.

When `include_source_video=true` but `write_capsule=false`, return a warning that no package asset was written.

## Error Handling

Block with clear errors when:

- `source_video_path` is missing or not a file.
- `video_analysis_tool` is not registered.
- the selected tool cannot be imported.
- the selected tool does not expose `_run`.
- `write_capsule=true` and `capsule_name` is missing or unsafe.
- a target capsule exists and `overwrite_capsule=false`.
- analyzer output cannot produce valid evidence.
- capsule validation fails after materialization.

Analysis API failures should be recorded as unsuccessful analysis artifacts when possible, but must not generate a capsule draft that looks valid.

## Testing

Use test-first development for implementation.

Required tests:

- Tool registry/capability tests show `Gemini3VideoAnalyzerTool` is registered as video analysis.
- Normalizer tests convert a complete analyzer response into `video_breakdown.json` and `capsule_draft.json`.
- Normalizer tests block invalid JSON or analyzer failure without producing a valid draft.
- CLI tests use a fake analyzer tool to run draft-only mode and verify workspace artifacts.
- CLI tests with `write_capsule=true` create a valid capsule package and return `capsule_dir`.
- CLI tests verify the source video is not copied by default.
- CLI tests verify `include_source_video=true` writes a `reference_only` asset.
- OpenClaw adapter tests verify `workflow=video-to-capsule` routes to the new script and exposes the new outputs.

## Non-Goals

This change does not:

- generate a new video from the analyzed source;
- train or fine-tune a model;
- perform copyright clearance;
- guarantee perfect timestamp segmentation from every analyzer model;
- store raw source-video evidence inside active capsule recipe files;
- rewrite existing generation workflows.

## Success Criteria

A user can run the new workflow with a local video and a registered analyzer tool, review `analysis/video_breakdown.json` and `analysis/capsule_draft.json`, then explicitly create a valid active capsule package. The formal capsule contains reusable rules, not one-off evidence, and source video packaging is opt-in only.
