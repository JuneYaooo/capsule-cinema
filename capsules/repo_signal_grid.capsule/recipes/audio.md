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

- Default audio is silent. Do not generate TTS, voiceover, burned subtitles, or subtitle timing for repo_signal_grid.
- Strip source clip audio before final export. This keeps the first-run route local and avoids AI speech or media-generation costs.
- Add BGM only when the user supplies a local track whose platform/distribution license has already been verified through `bgm_path`, `background_music_path`, or `CAPSULE_BGM_PATH`.
- When BGM is supplied, keep it low enough that the card rhythm feels fast without making the video feel like an ad bumper.
