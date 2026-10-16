---
type: Video Capsule Card
title: 毛绒手办过程科普
description: 用会动的毛绒手办、可剖开的主容器和玩具实验台，把「X 是怎么来的」这类看不见的过程演成 60–90 秒竖屏科普；画面、声音、字全部本地代码生成。
stage: routing
profile: video.okf.capsule.v1
primary_workflow: procedural_3d_process_explainer
tags:
- science-explainer
- process-explainer
- plush
- diorama
- 3d-figurine
- procedural-3d
- blender
- narration
- vertical-video
---

# 毛绒手办过程科普

## Purpose

把一个看不见的过程讲成一条观众听得懂、看得见的因果链。画面在三个世界之间切换：毛绒角色在微缩布景里活动（动机和结果）、同一个主容器剖开看内部（过程进度）、玩具实验台演抽象机制（分解、结合、上限）。每个动作都挂在口播关键词上，配音一换，画面和音效自动对齐。

## Series Contract

- 固定：毛绒手办微缩布景画风（米白台面、灰绿墙、三盏柔光、低饱和加一个暖色焦点）；三个画面世界和主容器接力；只在字幕段边界切镜；关键词锚定的动作和音效；常驻标题带 + 章节牌 + 跳词字幕 + 跟物体走的标签 + 揭晓贴字；逐句 MiniMax 配音、两模型听写验收；BGM 剪整小节落在片尾；程序合成音效落在 BGM 的调上；−14 LUFS 母带；1080×1920、24 fps。
- 每期可变：题目和成品、因果链、角色和配饰、主容器、道具、台本、高亮词、章节牌、标签、分镜、BGM、标题与封面、发布文案、事实来源。
- 默认可改：配音音色（系列内保持同一个）、目标时长（60–90 秒）、主容器类型。

## When To Use

- 讲一个看不见的过程：某样东西是怎么来的、怎么变的、为什么会这样。
- 过程能拆成 5–10 个因果步骤，并且发生在一个可以剖开的容器或地点里。
- 想要可爱、零崩坏的 3D 毛绒手办画风的口播字幕竖屏科普。
- 用户给了一条参考口播，要按这个画风重做一期。

## When Not To Use

- 新闻、时效信息，或需要真实影像当证据的内容。
- 人物访谈、观点争论、产品测评、真人出镜。
- 需要照片级真实感，或扁平矢量、手绘画风。
- 没有因果链的并列清单。
- 不能本地运行 Blender 5.x、ffmpeg 和 whisper 的环境。

## How To Run

这是专用路线（code_rendered_graphics）：通用生成只能出分镜预览，成片必须走胶囊自带的制作套件 `assets/kit/`（工序见 `recipes/workflow.md`，命令见 `assets/kit/README.md`）。文案和分镜表必须先给用户确认，确认后才配音和渲染。

## Stage Reading

- Routing：`capsule.yaml`、`index.md`、本卡片、`contracts/input_schema.yaml`、`contracts/content_scope.yaml`。
- Planning：输入与内容范围契约、`production_contract.yaml`，以及 `recipes/structure.md`、`copy.md`、`visual.md`、`audio.md`。
- Generation：`contracts/runtime.yaml`、`recipes/workflow.md`、`recipes/motion.md`、`assets/index.yaml`。
- QA：`quality/rules.yaml`、`quality/release_gates.yaml`。
- Learning：只读 `learning/promoted_lessons.yaml`。
