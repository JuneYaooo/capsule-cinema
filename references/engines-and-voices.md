# Public Engines and Voices

## Image and video

| Runtime name | Tool | Public provider | Purpose |
| --- | --- | --- | --- |
| `volcengine-seedream` | `VolcengineImageGeneratorTool` | official Volcengine Ark | Seedream 5.0 Pro text/single/multi-reference image generation |
| seedance2.0 | `Seedance20VideoGeneratorTool` | official Volcengine Ark | Seedance 2.0 text, first/last-frame, and multimodal video generation |

The built-in official model defaults are `doubao-seedream-5-0-pro-260628` and
`doubao-seedance-2-0-260128`. `ARK_SEEDREAM_MODEL` and
`ARK_SEEDANCE_MODEL` are optional overrides for an enabled Model ID or Endpoint
ID. Seedream 5.0 Pro produces one non-streaming image per request. Seedance 2.0
supports 4-15 seconds or automatic duration `-1`, synchronized audio,
first/last frames, and image/video/audio references; audio cannot be the only
reference input.

## TTS

`UniversalTTSTool` and `UniversalTTSBatchTool` accept `provider=minimax` or
`provider=doubao`. `DoubaoTTSTool` exposes the official API-Key-authenticated
bidirectional WebSocket route directly. Voices are selected from
`lib/config/voice_catalog.yaml`. Do not silently change provider or voice when
a capsule locks a voice identity.

## Local additions

Runtime names and tool classes for private adapters are loaded from the ignored
`local-channels/` overlay and are deliberately absent from this public file.
