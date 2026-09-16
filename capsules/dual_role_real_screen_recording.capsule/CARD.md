---
type: Video Capsule Card
title: 双角色真实录屏项目科普短视频
description: 同一固定数字人身份分饰小白与专家，同时插入 GitHub 浏览录屏和 WorkBuddy 使用录屏；录屏必须保留 raw 文件、来源、时间戳、哈希与隐私检查。
stage: routing
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

## Purpose

同一固定数字人身份分饰小白与专家，以观众痛点、开源项目方案、真实结果、优势亮点、可信信号和一次追问交付构成 12–25 秒的短版，或 40–50 秒的完整项目讲解；中段证据必须包含 GitHub 浏览录屏和 WorkBuddy 使用录屏，所有录屏都要有可复核的本地路径、来源、采集时间、视口、哈希和隐私检查。完整讲解用于需要同时交代痛点、能力范围、真实结果、风险边界和交付动作的项目，不得把 45 秒台本硬压回 18 秒。

## When To Use

- douyin
- dual-role
- digital-human
- project-explainer
- 18s
- 9x16

## When Not To Use

- 需要严肃长篇论证、多人访谈或剧情连续剧的项目。
- 一期同时讲多个互不相关项目的堆叠选题。
- 不绑定具体开源项目、没有官方仓库 Demo 或结果素材可展示的纯原理科普。
- 需要复刻现实人物身份、来源博主外貌、标志性服装或原视频场景。

## Text Policy

默认画面策略为 `clean_title_only`：视频顶部保留一个直接叠在画面上的主标题并预留平台安全区，不使用白色外框、标题卡或色块容器。人物段保持全画布；官方仓库 / Demo 素材无法自然铺满 9:16 时，使用无描边的蓝黑金网格模板底补足空白，不使用白色模糊背景。素材保留原生文字，但不叠加"真实截图"、操作提示、API 采集、来源说明、角色标签、数据卡或烧录字幕。
默认不烧录连续口播字幕；如需强调信息，只使用少量高对比板书式关键词或实拍重点标记，并确保不与 H3 画面文字重复叠加。

## Stage Reading

- Routing: read `capsule.yaml`, `index.md`, this card, `contracts/input_schema.yaml`, and `contracts/content_scope.yaml`.
- Planning: read the input/content-scope contracts and the recipe files named under `read_order.planning`.
- Generation: read the runtime contract, motion recipe, and asset index.
- QA: read the quality rules and release gates.
- Learning: read promoted lessons only; raw evidence is local-only.
