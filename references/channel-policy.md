# Public Channel Policy

The public repository uses an explicit allowlist. Public media-generation
integrations are limited to:

- official Volcengine Ark for image and video generation;
- official Agnes API for optional free-tier text-to-image and short text-to-video;
- official MiniMax for TTS;
- official Doubao for TTS;
- RunningHub workflow adapters as public, inspectable examples.

Local ffmpeg/Pillow processing, user-provided media, and capsule-packaged assets
are not cloud channels and remain available.

## Selection table

| Need | Public route | Required env |
| --- | --- | --- |
| Image generation | `VolcengineImageGeneratorTool` (Seedream 5.0 Pro) | `ARK_API_KEY` |
| Video generation | `Seedance20VideoGeneratorTool` (Seedance 2.0) | `ARK_API_KEY` |
| Optional free-tier text-to-image | `AgnesImageGeneratorTool` (Agnes Image 2.1 Flash) | `AGNES_API_KEY` |
| Optional free-tier short text-to-video | `AgnesVideoGeneratorTool` (Agnes Video v2.0) | `AGNES_API_KEY` |
| MiniMax narration | `UniversalTTSTool` with `provider=minimax` | `MINIMAX_API_KEY` |
| Doubao narration | `DoubaoTTSTool` or `UniversalTTSTool` with `provider=doubao` | `DOUBAO_TTS_API_KEY` |
| Action transfer | RunningHub example tools | `RUNNINGHUB_API_KEY` and workflow-specific values when required |
| Lip sync | RunningHub example tools | `RUNNINGHUB_API_KEY` and workflow-specific values when required |
| BGM | user-provided local file or capsule asset | none |
| Subtitles, concat, QA | local tools | none |

## Public/runtime boundary

Public registries are `lib/config/tool_registry.yaml`,
`lib/config/tool_capabilities.yaml`, and `lib/config/env_registry.json`. A clean
clone must work without importing any unlisted adapter.

Additional providers are local-only. Put their registry records in
`local-channels/tool_registry.yaml` and
`local-channels/tool_capabilities.yaml`. The directory is ignored by Git and is
merged only at runtime. Credentials stay in `.env`; never put secret values or
private endpoints in a registry, capsule, manifest, log, or document.

Fallbacks are allowlist-bound. Failure may fall back to another listed public
tool, a user-provided/local-media edit, an explicitly configured local overlay,
or an honest blocker. Never select an unlisted cloud route silently.

The official defaults are `doubao-seedream-5-0-pro-260628` and
`doubao-seedance-2-0-260128`. Model environment variables are optional
overrides. Seedance 2.0 must be enabled on the account before use; lack of
balance, resource package, or model permission is a blocker rather than a
reason to switch providers silently.

The optional Agnes defaults are `agnes-image-2.1-flash` and
`agnes-video-v2.0`. Each user supplies their own key. The provider's free-tier
FAQ currently says core models are free indefinitely and without a time limit,
but this means no end date is published, not unlimited requests. The current
free/default effective limits are about 20 RPM for 1K images, 10 RPM for 2K,
1 RPM for 3K/4K, and 1 RPM for video. The free daily video-seconds quota is not
publicly specified; the documented 500 seconds per day belongs to paid Token
Plans. Free access has no production SLA, and the provider may change limits or
model policy. Agnes image and video results must be downloaded and inspected
because the provider may normalize pixel dimensions. The video route is
text-to-video only, and provider audio is removed by default unless the caller
explicitly sets `preserve_native_audio=true`. Official references:
[API platform](https://platform.agnes-ai.com/),
[FAQ](https://wiki.agnes-ai.com/en/docs/faqs.md), and
[limits](https://wiki.agnes-ai.com/en/docs/tokenplan.md).

## RunningHub example rules

- Workflow IDs may be committed when the workflow itself is intended as a
  public example.
- API keys, cookies, signed URLs, upload URLs, and result URLs must not be
  committed or logged.
- Download results to a local artifact path and keep only task status, task ID,
  dimensions, duration, and local paths in manifests.
- Verify face framing for lip sync, input size limits for uploads, and the
  actual duration/dimensions of every returned video.
