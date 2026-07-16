# Public Engines and Voices

## Image and video

| Runtime name | Tool | Public provider | Purpose |
| --- | --- | --- | --- |
| `volcengine-seedream` | `VolcengineImageGeneratorTool` | official Volcengine Ark | text/reference image generation |
| seedance2.0 | `Seedance20VideoGeneratorTool` | official Volcengine Ark | text-to-video and image-to-video |

Model values are official Ark endpoint IDs supplied through
`ARK_SEEDREAM_MODEL` and `ARK_SEEDANCE_MODEL`; they are configuration, not
hard-coded defaults.

## TTS

`UniversalTTSTool` and `UniversalTTSBatchTool` accept `provider=minimax` or
`provider=doubao`. `DoubaoTTSTool` exposes the official API-Key-authenticated
bidirectional WebSocket route directly. Voices are selected from
`lib/config/voice_catalog.yaml`. Do not silently change provider or voice when
a capsule locks a voice identity.

## Local additions

Runtime names and tool classes for private adapters are loaded from the ignored
`local-channels/` overlay and are deliberately absent from this public file.
