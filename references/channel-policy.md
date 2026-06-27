# Channel Policy

The current default production recommendation is narrow: registered Juling/Veo wrappers for full-video image/video generation, registered RunningHub wrappers for specialized manual operations, Universal TTS with MiniMax/Doubao providers, licensed URL/Jamendo/Internet Archive for searchable BGM, and Suno for generated music/BGM.

This file is an editable policy, not a forever whitelist. To add, remove, replace, or deprecate channels, follow [channel-customization.md](channel-customization.md). That customization guide mirrors the original `tool_registry.json` design: `tools` records, `engine_decision`, `tool_chain_patterns`, capsule overrides, and pitfalls. A newer explicit user/project channel policy overrides this default.

Unless noted otherwise, tools listed under Approved sections are `status: approved` and must exist in `lib/config/tool_registry.yaml`. Tools listed under Do Not Select are `status: disabled` even if implementation files are present.

`Env:` entries below are variable names only. Never write secret values into this file, recipes, scripts, plans, capsules, manifests, or logs. See [env-secrets.md](env-secrets.md).

## Approved Image Tools

### `GptImage2Tool` - OpenAI Images

Use when realistic, high-quality scene frames are more important than maximum compatibility with the default full-video planner.

- Channel: OpenAI Images API
- Env: `GPT_IMAGE2_API_KEY`; optional `GPT_IMAGE2_BASE_URL`, `GPT_IMAGE2_EDIT_BASE_URL`
- Strengths: realistic photography, scene frames, clean high-quality images
- Limits: single reference image; supports `9:16`, `16:9`, `1:1`
- Gotcha: aspect ratio can drift; the implementation retries with stricter size prompts.

### `Seedream5ImageGeneratorTool` - Juling

Use for Chinese prompts, stylized scenes, quick character/reference iteration, and single-reference workflows.

- Channel: Juling
- Env: `JULING_BASE_URL`, `JULING_API_KEY`
- Strengths: Chinese prompt understanding, reference-image support, good creative scene generation
- Gotcha: large reference images are compressed; avoid asking it to render text.

### `Gemini3ProImageGeneratorTool` - registered, manual only

The tool is registered for compatibility and direct experiments, but it is not a default production fallback. Use it only when the user explicitly approves Gemini image generation or a project policy enables it.

## Approved Video Tools

### `SeedanceFastVideoGeneratorTool` - Juling Seedance 1.0 Fast

Use as the default video tool for ordinary full-video image-to-video scenes when a 5s or 10s clip is acceptable and will be trimmed in assembly.

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`
- Modes: `text_to_video`, `image_to_video`
- Durations: `5s`, `10s`
- Gotcha: trim to narration in assembly.

### `SeedanceVideoGeneratorTool` - Juling Seedance 1.0 Pro

Use when the project needs the Seedance Pro tier and the active account supports it.

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`
- Modes: `text_to_video`, `image_to_video`
- Durations: `5s`, `10s`

### `Jimeng35ProVideoGeneratorTool` - Juling Seedance 1.5 Pro

Use when native Chinese speech or Seedance 1.5 Pro is explicitly useful.

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`
- Modes: `text_to_video`, `image_to_video`
- Durations: `5s`, `10s`, `12s`
- Strengths: Chinese short-video style, native speech cases
- Gotcha: can randomly output English speech. Keep `auto_language_check=true` for image-to-video and run language checks.

### `Veo3VideoGeneratorTool` - Veo

Use when the user asks for higher-quality or cinematic output and accepts slower generation and stricter moderation.

- Channel: Veo
- Env: `VEO3_BASE_URL`, `VEO3_API_KEY`, optional `VEO_ACCESS_TOKEN`
- Modes: `text_to_video`, `image_to_video`
- Durations: `8s`

### `Veo31VideoGeneratorTool` - Juling Veo 3.1 Fast

Use when the user asks for Juling Veo 3.1 or needs a start/end-frame transition.

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`, optional `JULING_VEO31_MODEL`
- Modes: `text_to_video`, `image_to_video`, `first_last_frame`
- Durations: about `8s`
- Strengths: high-quality transitions controlled by start and end frames
- Gotcha: for `first_last_frame`, provide two stable frames with matching subject, framing, and aspect ratio.

## Approved RunningHub Tools

Use RunningHub for workflow-style operations, not as a generic replacement for Juling scene generation.

- `ActionImitateTool`: single-person action transfer; internally tries Wan animate engines.
- `WanMultiPersonActionImitateTool`: multi-person action transfer, RunningHub workflow `2014675474420604929`.
- `InfiniteTalkV2VTool`: video + audio -> lip-sync video, RunningHub app `1961415775317856257`.
- `LTX23LipSyncTool`: image + audio -> digital human/lip-sync style video when available.
- `Wan22LipSyncTool`: image + audio -> lip-sync backup route.

RunningHub gotchas:

- Upload local files; do not pass social-platform URLs directly.
- Single-action old `.cn` app uploads can have 30MB limits; newer `.ai` v2 workflows have different limits. Compress first if uploads fail.
- For lip sync, the source face must be clear and large enough; close-up or medium shot works best.
- For vertical output, check width/height order: `576x1024`, not `1024x576`.
- Super-resolution is not an approved default unless a concrete wrapper is registered and smoke-tested. If added later, its long-edge cap must be at least the source video's long edge, and narrated videos must preserve audio timing.
- Do not log RunningHub upload/result URLs. They can be signed or private; logs, manifests, capsule notes, and reports should store only local artifact paths, task status, dimensions, duration, and secret-free error summaries.

## Approved TTS

### `UniversalTTSTool` / `UniversalTTSBatchTool` - MiniMax or Doubao

- Params: `text`, `output_path`, `provider`, `voice_type`, `speed`, `encoding`.
- `provider=minimax` uses MiniMax T2A v2 and needs `MINIMAX_API_KEY`.
- `provider=doubao` uses Doubao TTS and needs `DOUBAO_TTS_APPID` / `DOUBAO_TTS_ACCESS_TOKEN`.
- Use opened `_mars_bigtts` Doubao voices where possible. `_moon_bigtts` voices can fail with resource mismatch.

## Approved Music / BGM

### Online Music Search / Download - Jamendo / Internet Archive

Use when the video needs an existing licensed instrumental track instead of generated BGM.

- Channel: Jamendo API when `JAMENDO_CLIENT_ID` is configured; Internet Archive Creative Commons/public-domain search otherwise.
- Env: optional `JAMENDO_CLIENT_ID`, `JAMENDO_API_BASE`, `ONLINE_MUSIC_ENABLE_ARCHIVE`, `INTERNET_ARCHIVE_SEARCH_API`, `INTERNET_ARCHIVE_METADATA_BASE`, `INTERNET_ARCHIVE_DOWNLOAD_BASE`, `ONLINE_MUSIC_MAX_MB`, `ONLINE_MUSIC_SEARCH_LIMIT`, `ONLINE_MUSIC_REQUEST_TIMEOUT`
- Inputs: `music_query`, optional `tags`, or explicit `music_url` / `audio_url`.
- Strengths: searchable licensed tracks with local download for repeatable assembly.
- Gotcha: do not scrape arbitrary web pages or download copyright songs. Only use explicit user-supplied audio URLs or approved music-provider search results.

### `UniversalMusicGenerationTool` - Suno

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
- Gemini image generation as an automatic fallback
- Grok video wrappers until registered and smoke-tested
- super-resolution wrappers until registered and smoke-tested
- `MidjourneyImageGeneratorTool`
- `Sdance2VideoGeneratorTool` - XGAPI/SDANCE channel
- Hailuo, Kling, Sora, Replicate variants
- `VoiceCloneTool` as a default TTS route; only use voice cloning when the user explicitly requests voice cloning.

If an old capsule specifies a disabled tool, treat it as stale and ask for or apply a migration to the current approved tool set rather than executing it blindly.
