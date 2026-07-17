---
okf_version: '0.1'
type: Video Capsule Bundle Index
title: 高抽象成长卡片
description: 可复用的高抽象成长类图文卡片讲解胶囊：按四条题材路线完成现实场景、机制、证明、行动和身份收束，再生成动态语义卡片视频；不包含参考账号身份或原素材。
profile: video.okf.capsule.v1
primary_workflow: high_abstraction_growth_card_explainer
tags:
- douyin
- growth
- card-explainer
---

# 高抽象成长卡片

可复用的高抽象成长类图文卡片讲解胶囊：把成年人的泛化困境转成有场景、有解释、有证明、有行动和身份回报的原创认知文案，再按语义 beats 生成可变卡数的白底红黑知识卡视频。

# Entry

* [Capsule Card](CARD.md) - Routing summary, purpose, and usage boundary.

# Contracts

* [Input Schema](contracts/input_schema.yaml) - User input requirements and intake fields.
* [Runtime Contract](contracts/runtime.yaml) - Tool roles, execution constraints, and output contract.
* [Production Contract](contracts/production_contract.yaml) - Evidence floor, semantic outputs, modality requirements, and release gates.

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
