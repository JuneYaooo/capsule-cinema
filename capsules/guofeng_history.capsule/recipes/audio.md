---
type: Video Recipe
title: Audio Recipe
description: TTS, original audio, BGM, SFX, mix, timing, and sync rules.
stage: planning
domain: audio
profile: video.okf.capsule.v1
tags:
- audio
---

# Audio

## Rules

- Send the unified narration exactly once to MiniMax `Chinese (Mandarin)_Radio_Host`.
- Lock the provider-side speed to `0.8`; production evidence showed that `1.0` produced only 40.5 seconds for a 190-CJK script and violated the 45-55 second release gate.
- Treat the speed as part of the reviewed plan/run contract. Do not adjust it after a paid call, locally stretch the returned audio, insert silence to pass duration QA, retry TTS, or switch voice/provider.
- Measure the returned MP3 with `ffprobe` before any image or video request. Stop fail-closed unless it measures 45-55 seconds.
- Use only local original BGM under the narration; generated scene audio remains muted.
