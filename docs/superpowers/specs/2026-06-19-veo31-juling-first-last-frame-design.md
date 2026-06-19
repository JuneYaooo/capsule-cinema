# Veo 3.1 Juling First/Last Frame Design

## Goal

Add a new full-flow video engine, `veo3.1`, backed by Juling's `/v1/videos`
API. The engine must support first/last-frame video generation and be available
through the normal runtime surfaces, not only direct tool calls.

## Scope

- Add `Veo31VideoGeneratorTool` as a separate tool. Do not change the existing
  `Veo3VideoGeneratorTool`.
- Register `veo3.1` in the runtime engine list, tool registry, engine config,
  OpenClaw metadata, docs, and tests.
- Support the Juling payload shape:
  - `model`: default `veo3.1_fast`, overridable with `JULING_VEO31_MODEL`
  - `type`: `2` for first/last-frame video
  - `aspect_ratio`: runtime aspect ratio, default `9:16`
  - `images`: `[start_image, end_image]`
- Support direct params `start_image_path` and `end_image_path`, plus a
  compatible `images` list for callers that already have provider-accessible
  URLs.
- Add a simple user-facing README example for generating the vase transition.

## Architecture

The new implementation lives under `lib/custom_tools/video_generation/`:

- `veo31_video_generator_tool.py`
  - Pydantic schema for direct tool calls.
  - Juling client for create, poll, content/download, and output path handling.
  - Local image conversion helper matching existing Juling tools: HTTP(S) URLs
    pass through; local files are converted to data URIs.
- `video_generation_tool.py`
  - Adds `veo3.1` as a supported engine.
  - Adds `generation_type="first_last_frame"` routing for direct and universal
    tool usage.
  - Keeps ordinary full-video scene generation as single-image `image_to_video`
    unless a scene or caller provides both start and end frames.

Configuration and docs stay aligned:

- `lib/config/tool_registry.yaml`
- `lib/config/video_engines.yaml`
- `lib/src/video_generation_config.py`
- `skill.md`, `index.js`, `lib/config/env_registry.json`
- `references/channel-policy.md`, `references/tools-api.md`,
  `references/engines-and-voices.md`, `references/video-recipes.md`
- `README.md`

## Data Flow

Direct first/last-frame call:

1. `scripts/run_tool.py` loads `Veo31VideoGeneratorTool`.
2. The tool validates `prompt`, `start_image_path`, `end_image_path`,
   `aspect_ratio`, and output parameters.
3. The client POSTs to `{JULING_BASE_URL}/v1/videos` with the Juling JSON
   payload.
4. The client polls `GET /v1/videos/{task_id}` until success or failure.
5. The client downloads from either the task response video URL or
   `GET /v1/videos/{task_id}/content`, then writes the local output path.

Full-flow engine call:

1. `run_video.py` or `run_scene.py` accepts `--video_engine veo3.1`.
2. Runtime normalization maps aliases such as `veo31`, `veo3_1`, and
   `veo3.1_fast` to `veo3.1`.
3. Ordinary storyboard scenes use `image_to_video`.
4. If a caller passes both start and end frame fields, the universal wrapper
   routes to `first_last_frame`.

## Error Handling

- Missing `JULING_API_KEY` or `JULING_BASE_URL` fails fast with env var names
  only.
- Missing second frame for `first_last_frame` returns a clear failed result.
- Unsupported `generation_type` returns a failed result without falling back to
  another provider.
- Polling recognizes common success states (`success`, `completed`, `done`) and
  failure states (`failed`, `error`).
- API errors redact auth headers and do not write keys or signed URLs into docs.

## Testing

Add tests before implementation:

- Registry/docs alignment includes `Veo31VideoGeneratorTool` and `veo3.1`.
- Runtime normalization maps aliases to `veo3.1`.
- `UniversalVideoGenerationTool` exposes and routes `first_last_frame`.
- `Veo31VideoClient` builds the exact Juling first/last-frame payload.
- OpenClaw env allowlist and `skill.md` env declarations stay aligned.

Verification:

- Run the focused JS and Python tests touched by the change.
- Run `npm test` if dependencies and local Python environment are available.

## README Example

Keep the example short. It should show:

1. Generate two `gpt-image-2` frames: an empty antique vase scroll scene, then
   the same vase full of Dragon Boat Festival mugwort and calamus.
2. Call `Veo31VideoGeneratorTool` with `generation_type="first_last_frame"`,
   `start_image_path`, `end_image_path`, `aspect_ratio="9:16"`, and a concise
   growth/bloom prompt.

The example must use env var names only, not secret values.

## Out Of Scope

- Do not redesign the storyboard contract to automatically generate paired
  start/end frames for every scene.
- Do not remove or repoint the existing `Veo3VideoGeneratorTool`.
- Do not add a new provider outside Juling.
