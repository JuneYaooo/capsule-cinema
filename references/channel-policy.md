# Channel Policy

The current default production recommendation is narrow: Juling for image/video generation, RunningHub for workflow-style video operations, MiniMax/Doubao for TTS, licensed URL/Jamendo/Internet Archive for searchable BGM, and Suno for generated music/BGM.

This file is an editable policy, not a forever whitelist. To add, remove, replace, or deprecate channels, follow [channel-customization.md](channel-customization.md). That customization guide mirrors the original `tool_registry.json` design: `tools` records, `engine_decision`, `tool_chain_patterns`, capsule overrides, and pitfalls. A newer explicit user/project channel policy overrides this default.

Unless noted otherwise, tools listed under Approved sections are `status: approved`. Tools listed under Do Not Select are `status: disabled`. `Veo31VideoGeneratorTool` is `status: suspended` until registration and a smoke test confirm it works through the wrapper.

`Env:` entries below are variable names only. Never write secret values into this file, recipes, scripts, plans, capsules, manifests, or logs. See [env-secrets.md](env-secrets.md).

## Approved Image Tools

### `GptImage2Tool` - Juling

Use as the default image engine for realistic, high-quality scene frames.

- Channel: Juling
- Env: `JULING_GPT_IMAGE2_BASE_URL` or `JULING_BASE_URL`; `JULING_GPT_IMAGE2_API_KEY`
- Strengths: realistic photography, scene frames, clean high-quality images
- Limits: single reference image; supports `9:16`, `16:9`, `1:1`
- Gotcha: aspect ratio can drift; the implementation retries with stricter size prompts.

### `Seedream5ImageGeneratorTool` - Juling

Use for Chinese prompts, stylized scenes, quick character/reference iteration, and single-reference workflows.

- Channel: Juling
- Env: `JULING_BASE_URL`, `JULING_API_KEY`
- Strengths: Chinese prompt understanding, reference-image support, good creative scene generation
- Gotcha: large reference images are compressed; avoid asking it to render text.

## Approved Video Tools

### `GrokVideoGeneratorTool` - Juling

Default video tool for realistic or flexible scene motion.

- Channel: Juling
- Env: `GROK_VIDEO_API_KEY` or `JULING_API_KEY`; `GROK_VIDEO_BASE_URL` or `JULING_BASE_URL`
- Modes: `text_to_video`, `image_to_video`
- Durations: `5s`, `10s`, `15s`
- Current legacy models: `grok-3-video`, `grok-3-video-10s`, `grok-3-video-15s` through `/v1/videos`.
- Optional unified route: `/v1/video/create` with `grok-video-3`; set `api_style=unified` only when the configured provider supports that route. Unified image-to-video requires a provider-accessible image URL, not a local-only file.
- Strengths: timeline prompts, motion direction, 15s single clips
- Gotcha: may include English audio. Mute before TTS assembly or lip sync.
- Current regression note: the legacy `10s` route passed in the active Juling account, but `15s` returned provider-side `model_not_found` / no distributor and the unified route returned route-not-found. Smoke test `15s` before selecting it; if unavailable, compose from `10s` clips.

### `Jimeng35ProVideoGeneratorTool` - Juling Seedance 1.5 Pro

Use when native Chinese speech or Seedance 1.5 Pro is explicitly useful.

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`
- Modes: `text_to_video`, `image_to_video`
- Durations: `5s`, `10s`, `12s`
- Strengths: Chinese short-video style, native speech cases
- Gotcha: can randomly output English speech. Keep `auto_language_check=true` for image-to-video and run language checks.

### `SeedanceFastVideoGeneratorTool` - Juling Seedance 1.0 Fast

Use as a simpler Juling fallback when a 10s clip is acceptable and will be trimmed in assembly.

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`
- Model: `seedance-1.0-fast-10s`
- Modes: `text_to_video`, `image_to_video`
- Gotcha: fixed 10s model; trim to narration in assembly.

### `Veo31VideoGeneratorTool` - Juling, explicit registration required

The codebase contains a Juling `veo3.1_fast` wrapper, but it may not be registered in `custom_tools/tool_registry.py` in every checkout. Do not use through `run_tool.py` unless it is registered and tested.

## Approved RunningHub Tools

Use RunningHub for workflow-style operations, not as a generic replacement for Juling scene generation.

- `ActionImitateTool`: single-person action transfer; internally tries Wan animate engines.
- `WanMultiPersonActionImitateTool`: multi-person action transfer, RunningHub workflow `2014675474420604929`.
- `InfiniteTalkV2VAPI`: video + audio -> lip-sync video, RunningHub app `1961415775317856257`.
- `LTX23LipSyncTool`: image + audio -> digital human/lip-sync style video when available.
- `VideoSuperResTool`: RunningHub super-resolution, app `1996062530516795394`.

RunningHub gotchas:

- Upload local files; do not pass social-platform URLs directly.
- Single-action old `.cn` app uploads can have 30MB limits; newer `.ai` v2 workflows have different limits. Compress first if uploads fail.
- For lip sync, the source face must be clear and large enough; close-up or medium shot works best.
- For vertical output, check width/height order: `576x1024`, not `1024x576`.
- `VideoSuperResTool` `max_resolution` is a long-edge cap. It must be at least the source video's long edge; using a smaller value configures the job as downscaling, not super-resolution.
- Super-resolution can still change duration and dimensions even when the API task succeeds. Always `ffprobe` the returned file; for narrated videos, treat duration drift from the original narration as a blocker and reattach the original audio or rerender before delivery.
- Do not log RunningHub upload/result URLs. They can be signed or private; logs, manifests, capsule notes, and reports should store only local artifact paths, task status, dimensions, duration, and secret-free error summaries.

## Approved TTS

### `TextToSpeechTool` - MiniMax

- Params: `text`, `voice_id`, `output_path`, `speed`, `vol`, `pitch`
- Good default for narration and cloned/preconfigured voice IDs.
- MiniMax can be quiet; use API `vol` around `2.0-2.5` when needed, then keep ffmpeg `voice_volume` sane.

### `DoubaoTTSTool` - Doubao

- Params: `text`, `output_path`, `voice_type`, `speed_ratio`, `encoding`
- Use for expressive Chinese narration.
- Only use opened `_mars_bigtts` voices. `_moon_bigtts` voices can fail with resource mismatch.

## Approved Music / BGM

### Online Music Search / Download - Jamendo / Internet Archive

Use when the video needs an existing licensed instrumental track instead of generated BGM.

- Channel: Jamendo API when `JAMENDO_CLIENT_ID` is configured; Internet Archive Creative Commons/public-domain search otherwise.
- Env: optional `JAMENDO_CLIENT_ID`, `JAMENDO_API_BASE`, `ONLINE_MUSIC_ENABLE_ARCHIVE`, `INTERNET_ARCHIVE_SEARCH_API`, `INTERNET_ARCHIVE_METADATA_BASE`, `INTERNET_ARCHIVE_DOWNLOAD_BASE`, `ONLINE_MUSIC_MAX_MB`, `ONLINE_MUSIC_SEARCH_LIMIT`, `ONLINE_MUSIC_REQUEST_TIMEOUT`
- Inputs: `music_query`, optional `tags`, or explicit `music_url` / `audio_url`.
- Strengths: searchable licensed tracks with local download for repeatable assembly.
- Gotcha: do not scrape arbitrary web pages or download copyright songs. Only use explicit user-supplied audio URLs or approved music-provider search results.

### `UniversalMusicGenerationTool` / `SunoMusicTool` - Suno

Use when the video needs generated BGM, an instrumental mood bed, or a music-led montage track.

- Channel: Suno
- Env: `SUNO_BASE_URL`, `SUNO_API_KEY`
- Modes: `inspiration`, `custom`; direct wrappers also expose lyrics generation.
- Strengths: fast mood/BGM ideation, instrumental tracks, music-led montage support.
- Gotcha: request `output_dir` so the wrapper downloads audio locally. Do not store or report Suno remote audio/image/video URLs; keep local paths plus duration/audio metadata.
- QA: inspect with `ffprobe`; for narrated videos, mix BGM below narration and confirm voice intelligibility.

## Do Not Select

Do not actively choose these for current default video production:

- `GptImage2ProTool` - ZeakAI channel
- `Gemini3ProImageGeneratorTool`
- `MidjourneyImageGeneratorTool`
- `Sdance2VideoGeneratorTool` - XGAPI/SDANCE channel
- Hailuo, Kling, Sora, Replicate variants
- `VoiceCloneTool` as a default TTS route; only use voice cloning when the user explicitly requests voice cloning.

If an old capsule specifies a disabled tool, treat it as stale and ask for or apply a migration to the current approved tool set rather than executing it blindly.
