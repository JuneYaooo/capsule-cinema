# Runtime Behavior Logic Optimization Design

Date: 2026-07-01

## Goal

Fix the first behavior-logic optimization slice for Capsule Cinema without broad structural refactors. This slice targets three runtime correctness issues:

- Delivery promise inference should not classify ordinary subtitled or default-volume videos as `tts_led_explainer`.
- Video generation fallback should continue filling missing scenes instead of stopping at 70% success and then failing QA for incomplete scenes.
- Full-video runs should expose the workspace early enough for OpenClaw progress monitoring.

Out of scope:

- Unifying all workspace creation helpers.
- Introducing a full `RuntimePlan` abstraction.
- Reworking active capsule package structure.
- Changing public skill inputs/outputs except for richer internal progress parsing.

## Current Problems

`scripts/run_video.py` currently passes `needs_audio=bool(add_subtitles) or bool(kwargs.get("voice_volume"))` into `build_delivery_promise`. Because subtitles default to enabled and `voice_volume` defaults to `1.5`, normal general-video runs can be inferred as `tts_led_explainer` even when the user did not ask for narration-led delivery.

`VideoGenerator.generate_videos` stops trying fallback engines when a batch reaches `success_rate >= 0.7`. The flow later treats any missing scene videos as `scene_videos_incomplete`, so a partial success can still become a blocker even though later fallback engines were never tried.

`index.js` starts workspace monitoring before full-video runs, but full-video runs do not have a workspace path yet because `run_video.py` creates it inside the Python flow. The adapter therefore cannot reliably emit meaningful milestone progress for full-video runs.

## Design

### Delivery Promise Inference

Add a small helper in `scripts/run_video.py` to infer narration intent from explicit semantics instead of output mechanics.

Inputs considered true narration intent:

- Explicit user text markers such as `旁白`, `讲解`, `配音`, `voiceover`, or `narration`.
- Capsule config `has_narration is True`.
- Capsule output contract `voice == "unified_tts"`.

Inputs that must not imply narration intent by themselves:

- `add_subtitles`.
- `voice_volume`.
- `add_background_music`.
- Default runtime TTS capability.

Keep the public `build_delivery_promise(... needs_audio=...)` parameter stable for compatibility. The caller will now pass the narrower narration-intent value.

### Video Fallback Completion

Change `VideoGenerator.generate_videos` from all-or-nothing batch fallback to missing-scene completion:

1. Track successful outputs by original scene index.
2. For each available video engine, call `_generate_video_batch` only for scenes not yet completed.
3. Run quality regeneration for that engine's attempted subset.
4. Continue until all scenes have valid outputs or all engines are exhausted.
5. If scenes are still missing, use image fallback only for the missing scenes when capsule/static fallback rules allow it.
6. Return `scene_videos_incomplete` only when missing scenes remain after all allowed recovery paths.

This preserves already successful outputs and avoids wasting provider calls.

### Full-Video Progress Monitoring

Emit one machine-readable workspace marker from Python as soon as the flow creates a workspace:

```json
{"event":"workspace_created","workspace_dir":"..."}
```

`run_video.py` will provide a progress callback to `run_general_video_flow`; `AgnoGeneralVideoFlow` will pass it into `AgnoGeneralVideoCrew.kickoff`; the crew will call it immediately after workspace setup.

`index.js` will parse stdout incrementally. When it sees `event == "workspace_created"`, it starts `startWorkspaceMonitor(workspace_dir, context)` if no monitor has started yet. Final JSON parsing remains compatible with existing script output.

The progress marker must be ignored by `parseOutput` final result parsing except as a fallback source for `workspace_dir`.

## Error Handling

- If progress marker parsing fails, the run continues and final JSON parsing still controls output.
- If fallback engines all fail and static fallback is disallowed, existing blocker behavior remains.
- If only some scenes are missing and static fallback is allowed, fallback should create outputs only for those missing scenes.
- If narration intent is ambiguous, default to not `tts_led_explainer` unless the text or capsule contract explicitly says narration.

## Tests

Add focused regression tests:

- Delivery promise: a plain general-video request with subtitles/default voice volume does not infer `tts_led_explainer`.
- Delivery promise: explicit narration markers still infer `tts_led_explainer`.
- Video fallback: first engine returns partial scene outputs, second engine fills missing scenes, final summary has all scenes generated.
- Video fallback: static fallback only fills missing scenes when engines fail partially.
- OpenClaw adapter parsing: stdout workspace marker starts or records workspace monitoring data without breaking final JSON parsing.

Existing `npm test` must continue to pass.

## Files Expected To Change

- `scripts/run_video.py`
- `lib/video_workflows/general_video/flow.py`
- `lib/video_workflows/general_video/crew.py`
- `lib/src/runtime/general_video_crew/video_generator.py`
- `index.js`
- focused tests under `tests/`

No capsule package content should be modified by this slice.
