---
okf_version: '0.1'
type: Video Capsule Bundle Index
title: X来低模主题宣传变体
description: 用户输入一个宣传主题，自动规划“遇事失败→哭喊妈妈——→X实体化主角喊X来救场→广告语”的完整低模宣传故事；X、主角形象、动作和宣传对象必须直接一致。
profile: video.okf.capsule.v1
primary_workflow: agnes_segmented_animal_fable
tags:
- agnes
- free-tier
- animal-fable
- low-poly
- 5-10s
- long-video
- theme-variants
- promotion
---

# X来低模主题宣传变体

用户只需输入一个 `topic`。胶囊先生成不同机制的创意候选，再选择一条用 Agnes 生产低模剧情单元，并在本地加入准确字幕、宣传信息、证据卡和CTA。

## Core Route

- 规划：从同一主题至少产生 `summon_solution`、`self_awakening`、`visual_pun`、`conflict_proof` 中互不重复的候选，并标出各自钩子、结果、证据需求和风险。
- `5-10s`：一个 Agnes 生成单元；只在 `hook_test` 中作为单拍测试，不能冒充默认完整故事。
- 默认 `full_story`：约 `12-18s`，第一单元负责困境、失败和哭腔“妈妈——”，第二单元由另一救场角色负责“X来”、解决和广告语。
- `11-300s`：按语义拆成多个 `5-10s` 单元，逐个生成、逐个质检，再本地统一规格并拼接。
- Agnes 图片和视频均为纯文本生成；图片不能作为 Agnes 视频参考输入。
- 默认故事节奏为 `困境 -> 失败 -> 哭腔妈妈—— -> 另一角色X来 -> 解决 -> 救场角色广告语 -> 本地信息卡`；弱势角色与救场角色必须是两个不同个体，但默认属于同一个X视觉家族。
- 默认语义闭环为 `宣传对象 -> 可视觉化X -> 全片角色世界X化 -> X实体化救场主角 -> X特有解决动作 -> 同一对象广告语`。动物X默认只出现同种动物角色；商品/物件X默认只出现本体或拟人本体角色，例如“书来”用小书受困、大书救场，不能出现山羊、狗或其他无关动物。仅靠寓意、职业联想或片尾Logo不合格。
- Agnes 原生音频仍默认删除；选择原声时，必须逐字转写“妈妈”、原创X来词和广告语，人工审听三段顺序、哭腔、声音反差与救场角色声线连续性。失败不自动切换付费TTS。
- 长视频的角色一致性只能通过重复文本锚点做软锁定，不能声称参考图级严格一致。
- 所有卖点、价格、日期、数据、品牌文字、Logo、报名方式和CTA只使用用户提供或已核验的材料，并在本地确定性渲染。

## Start Here

先生成最难、最能代表风格的一个 `5-10s` 场景并让用户确认。没有通过首镜样片，不批量消耗免费层视频请求。

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
* [Theme Variants](recipes/theme_variants.md) - Theme intake, mode routing, variant matrix, proof payload, and selection rules.
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
