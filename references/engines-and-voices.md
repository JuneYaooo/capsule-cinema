# Public Engines and Voices

## Image and video

| Runtime name | Tool | Public provider | Purpose |
| --- | --- | --- | --- |
| `volcengine-seedream` | `VolcengineImageGeneratorTool` | official Volcengine Ark | Seedream 5.0 Pro text/single/multi-reference image generation |
| `agnes-image-2.1-flash` | `AgnesImageGeneratorTool` | official Agnes API | optional free-tier text-to-image; user-owned key required |
| seedance2.0 | `Seedance20VideoGeneratorTool` | official Volcengine Ark | Seedance 2.0 text, first/last-frame, and multimodal video generation |
| `minimax-h3` | `MiniMaxH3VideoGeneratorTool` | official MiniMax | H3/Hailuo-03 text, first/last-frame, and multimodal 2K video generation |
| direct tool only | `AgnesVideoGeneratorTool` | official Agnes API | optional free-tier short text-to-video; not a full `run_video.py` image-to-video engine |

The built-in official model defaults are `doubao-seedream-5-0-pro-260628` and
`doubao-seedance-2-0-260128`. `ARK_SEEDREAM_MODEL` and
`ARK_SEEDANCE_MODEL` are optional overrides for an enabled Model ID or Endpoint
ID. Seedream 5.0 Pro produces one non-streaming image per request. Seedance 2.0
supports 4-15 seconds or automatic duration `-1`, synchronized audio,
first/last frames, and image/video/audio references; audio cannot be the only
reference input.

The complete-video default stays on `seedance2.0` at 720p. `minimax-h3` is
selected only for an explicit H3, Hailuo-03, 2K, or high-resolution request.
The H3 V2 API currently has one resolution value, `2K`; lower-resolution H3
requests are rejected instead of being silently rewritten. H3 supports 4-15
seconds, up to 9 reference images, 3 videos, and 3 audio clips. Reference audio
requires at least one reference image or video.

The Agnes adapters default to `agnes-image-2.1-flash` and
`agnes-video-v2.0`. The verified public surface is text-to-image and short
text-to-video only. The provider may normalize dimensions, and its video output
may contain native audio; the tool removes that audio by default unless
`preserve_native_audio=true` is explicitly requested. Free-tier quotas and
rate limits remain provider-controlled.

## TTS

`UniversalTTSTool` and `UniversalTTSBatchTool` accept `provider=minimax` or
`provider=doubao`. `DoubaoTTSTool` exposes the official API-Key-authenticated
bidirectional WebSocket route directly. Voices are selected from
`lib/config/voice_catalog.yaml`. Do not silently change provider or voice when
a capsule locks a voice identity.

## Local additions

Runtime names and tool classes for private adapters are loaded from the ignored
`local-channels/` overlay and are deliberately absent from this public file.
