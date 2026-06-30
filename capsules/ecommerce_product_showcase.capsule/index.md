---
okf_version: '0.1'
type: Video Capsule Bundle Index
title: Ecommerce Product Showcase
description: 电商商品种草/带货短视频胶囊：用商品名、主图、卖点、人群和平台生成 15-30 秒竖屏短视频，强调商品可见、卖点清晰、TTS+字幕、低音量 BGM 和合规话术。
profile: video.okf.capsule.v1
primary_workflow: ecommerce_product_video
tags:
- ecommerce
- product
- showcase
- tiktok-shop
- douyin
- voiceover
- subtitles
- '9:16'
---

# Ecommerce Product Showcase

电商商品种草/带货短视频胶囊：用商品名、主图、卖点、人群和平台生成 15-30 秒竖屏短视频，强调商品可见、卖点清晰、TTS+字幕、低音量 BGM 和合规话术。

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
