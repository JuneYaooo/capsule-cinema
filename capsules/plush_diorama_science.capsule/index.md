---
okf_version: '0.1'
type: Video Capsule Bundle Index
title: 毛绒手办过程科普
description: 用会动的毛绒手办、可剖开的主容器和玩具实验台，把一个看不见的过程演成 60–90 秒竖屏科普；Blender 程序化渲染，逐句配音，本地叠字与合成音效，附完整制作套件。
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

一条因果链，三个画面世界，一个主容器接力到底。毛绒角色交代动机和结果，剖开的主容器显示过程进行到哪一步，玩具实验台把抽象机制变成看得见的动作。画面、配音、音效、字幕都挂在同一张时间线上，所以声画是算出来对齐的，不是手动对的。

## Fixed And Variable

- 系列固定：毛绒手办微缩布景画风与色板灯光；钩子—原来—步骤—类比—揭晓—提醒的叙事骨架；三个画面世界交替与主容器状态接力；字幕段边界切镜；关键词锚定动作与音效；叠字层版式与动效；逐句配音与听写验收；BGM 整小节剪接；程序合成音效；−14 LUFS 母带；1080×1920、24 fps。
- 推荐默认：60–90 秒；约 400 字配 80 秒；单镜平均 1.8–2.6 秒作参考，固定机位为主、按信息变化切镜；系列固定一个 MiniMax 音色。
- 单期可变：题目、成品、因果链、角色与配饰、主容器、道具、台本、高亮词、章节牌、标签、分镜、BGM、标题封面、发布文案、事实来源。

# Entry

* [Capsule Card](CARD.md) - Routing summary, purpose, and usage boundary.

# Contracts

* [Input Schema](contracts/input_schema.yaml) - User input requirements and intake fields.
* [Content Scope](contracts/content_scope.yaml) - Series-fixed elements, per-episode content, and forbidden reusable literals.
* [Runtime Contract](contracts/runtime.yaml) - Tool roles, execution constraints, and output contract.
* [Production Contract](contracts/production_contract.yaml) - Required outputs, evidence floor, and modality gates.

# Recipes

* [Structure](recipes/structure.md) - 叙事骨架、时长字数预算、三个画面世界、主容器接力、隐喻词典、切镜规则。
* [Copy](recipes/copy.md) - 事实核实、台本句式、字幕段与高亮词、读法与上屏、标题封面同一句、先确认再生产。
* [Visual](recipes/visual.md) - 毛绒手办审美、舞台色板灯光、角色与微观角色、相机、竖屏安全区、程序化制作要点。
* [Audio](recipes/audio.md) - 配音与挑 take、听写验收、时间线留白、BGM 选曲剪接、音效写法与电平、母带。
* [Workflow](recipes/workflow.md) - 从题目到交付的工序、返工代价、确认点。
* [Motion](recipes/motion.md) - 关键词锚定、缓动词汇、动作语法、相机运动、叠字动效、编码与出片检查。

# Assets

* [Asset Index](assets/index.yaml) - 制作套件（Blender 程序化资产库、镜头原型、配音、对齐、混音、叠字、检查脚本）与两套 OFL 字体。
* [Kit README](assets/kit/README.md) - 套件目录布局与逐步命令。

# Quality

* [Rules](quality/rules.yaml) - Machine-readable QA rules.
* [Release Gates](quality/release_gates.yaml) - Required checks before release.

# Learning

* [Promoted Lessons](learning/promoted_lessons.yaml) - Generalized lessons only; raw evidence remains local or archived.

# Examples

* [Illustrative Examples](examples/illustrative.yaml) - Examples for orientation only, not default final content.
