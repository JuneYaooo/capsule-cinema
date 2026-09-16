---
okf_version: '0.1'
type: Video Capsule Bundle Index
title: 双角色真实录屏项目科普短视频
description: 在双角色开源项目科普骨架上，强制加入 GitHub 浏览录屏和 WorkBuddy 原生窗口录屏，并记录完整来源、采集时间、视口、哈希与隐私检查。
profile: video.okf.capsule.v1
primary_workflow: dual_role_project_explainer
tags:
- douyin
- dual-role
- digital-human
- project-explainer
- 18s
- complete-45s
- 9x16
- real-screen-recording
- github-recording
- workbuddy-recording
---

# 双角色开源项目科普短视频

同一固定数字人身份分饰小白与专家，以观众痛点、开源项目方案、真实结果、优势亮点、可信信号和一次追问交付构成 12–25 秒的短版，或 40–50 秒的完整项目讲解；角色对白默认由 AutoDL.Art H3 原生音频与口型同步生成（`minimax_h3_lightx2v_v5`）并逐句过 whisper ASR 验收，官方项目素材默认真实抓取优先（GitHub 页面截图与滚动录屏 → api.github.com 原始素材，本地合成兜底）。

# Entry

* [Capsule Card](CARD.md) - Routing summary, purpose, and usage boundary.

# Contracts

* [Input Schema](contracts/input_schema.yaml) - User input requirements and intake fields.
* [Content Scope](contracts/content_scope.yaml) - Series-fixed elements, per-episode content, and forbidden reusable literals.
* [Runtime Contract](contracts/runtime.yaml) - Tool roles, execution constraints, and output contract.
* [Production Contract](contracts/production_contract.yaml) - Required outputs, evidence floor, and modality gates.

# Recipes

* [Structure](recipes/structure.md) - Story beats, pacing, and scene architecture.
* [Copy](recipes/copy.md) - Voiceover, subtitles, titles, cover copy, lyrics, and CTA rules.
* [Visual](recipes/visual.md) - Visual style, references, characters, scenes, and continuity.
* [Audio](recipes/audio.md) - TTS, original audio, BGM, SFX, mix, and sync rules.
* [Motion](recipes/motion.md) - Camera motion, action, transitions, dynamic generation, and editing rhythm.
* [Screen Recording](recipes/screen_recording.md) - GitHub 与 WorkBuddy 真实录屏的采集、来源、隐私和剪辑规则。

# Assets

* [Asset Index](assets/index.yaml) - Reusable packaged assets and references. Asset files are not loaded unless needed.

# Quality

* [Rules](quality/rules.yaml) - Machine-readable QA rules.
* [Release Gates](quality/release_gates.yaml) - Required checks before release.

# Learning

* [Promoted Lessons](learning/promoted_lessons.yaml) - Generalized lessons only; raw evidence remains local or archived.

# Examples

* [Illustrative Examples](examples/illustrative.yaml) - Examples for orientation only, not default final content.
