---
okf_version: '0.1'
type: Video Capsule Bundle Index
title: 艺术图像参考帧动态短片
description: 把用户文字和参考图做成艺术化参考帧动态短片，带高级字幕、生成视频原生音效和淡BGM；运行时按本地能力选择渠道。
profile: video.okf.capsule.v1
primary_workflow: art_reference_frame_video
tags:
- art
- capability-matched-video
- reference-frames
- bgm
- captions
- local-script
---

# 艺术图像参考帧动态短片

把用户文字和参考图做成艺术化参考帧动态短片，带高级字幕、生成视频原生音效和淡BGM；运行时按本地能力选择渠道。

# Entry

* [Capsule Card](CARD.md) - Routing summary, purpose, and usage boundary.

# Contracts

* [Input Schema](contracts/input_schema.yaml) - User input requirements and intake fields.
* [Runtime Contract](contracts/runtime.yaml) - Tool roles, execution constraints, and output contract.

# Recipes

* [Structure](recipes/structure.md) - Story beats, pacing, and scene architecture.
* [Copy](recipes/copy.md) - Voiceover, subtitles, titles, cover copy, lyrics, and CTA rules.
* [Visual](recipes/visual.md) - Visual style, references, characters, scenes, and continuity.
* [Audio](recipes/audio.md) - TTS, original audio, BGM, SFX, mix, and sync rules.
* [Motion](recipes/motion.md) - Camera motion, action, transitions, dynamic generation, and editing rhythm.

# Assets

* [Asset Index](assets/index.yaml) - Reusable packaged assets and references. Asset files are not loaded unless needed.

# Quality

* [Rules](quality/rules.yaml) - Machine-readable QA rules.
* [Release Gates](quality/release_gates.yaml) - Required checks before release.

# Learning

* [Promoted Lessons](learning/promoted_lessons.yaml) - Generalized lessons only; raw evidence remains local or archived.

# Examples

* [Illustrative Examples](examples/illustrative.yaml) - Examples for orientation only, not default final content.
