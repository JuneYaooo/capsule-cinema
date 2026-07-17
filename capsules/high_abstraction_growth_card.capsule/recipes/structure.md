---
type: Video Recipe
title: Structure Recipe
description: Lane-aware cognitive argument structure, duration modes, semantic beats, and pacing.
stage: planning
domain: structure
profile: video.okf.capsule.v1
tags:
- structure
---

# Structure

## Planning order

必须先完成内容诊断和完整论证，再把论证切成卡片。视觉不能根据关键词反向决定观点，也不能因为现有插画只有计时器、门槛或路径，就把所有题材改写成行动力问题。

每个 beat 只承担一个语义任务，并包含：`id`、`role`、`theme`、`visible_text`、`narration`、`metaphor_family`，可选 `estimated_seconds` 和 `duration_weight`。`visible_text` 是口播的压缩判断，不是整段口播逐字上屏。

## Duration modes

### short_thesis

- 目标 60-90 秒，固定十个语义任务，但插画顺序和每张卡时长不固定。
- 结构：hook -> concrete_scene -> concrete_scene -> conceptual_split -> proof_or_comparison -> redefinition -> emotional_relief -> action -> action -> identity_close。
- 只讲一个核心判断，但必须出现两个现实场景、一次解释升级、一条证明路线和两个可推导动作。
- 0-3 秒给冲突；3-20 秒建立场景和未闭合问题；20-55 秒完成机制和证明；55 秒后给动作与身份收束。

### deep_cognitive_essay

- 目标 180-330 秒，12-20 个 beats。
- 最少结构：hook -> 三个现实场景 -> 概念二分 -> 深层后果 -> 证明/类比 -> 误区 -> 重定义 -> 两至三个方法 -> 身份升华。
- 情绪曲线为：被说中 -> 看见残酷机制 -> 获得解释性卸压 -> 理解新定义 -> 拿到行动路径 -> 完成身份赋能。
- 每 15-30 秒必须有认知推进；没有新信息的金句、排比和抚慰应删除。

## Beat roles

允许的核心角色包括：

- `counterintuitive_verdict`
- `concrete_scene`
- `common_belief`
- `mechanism_reveal`
- `conceptual_split`
- `consequence`
- `proof`
- `analogy`
- `false_solution`
- `redefinition`
- `contrast`
- `derived_action`
- `emotional_relief`
- `identity_close`

同一角色可以重复，但相邻 beat 不能只换措辞、不增加信息。深度长文可以有多个场景、证明和动作；短论必须压缩，但不能省略机制和证明。

## Card boundaries and timing

- 卡片数量由 beats 决定，不固定为七张。
- 卡片停留时间按逐 beat 的 `estimated_seconds`、`duration_weight` 或口播长度分配，不得平均切分整段口播。
- 第一张卡承担前三秒停留；最后一张卡闭合开场问题。
- 一个 beat 的口播明显过长时，应先拆 beat，而不是让一张卡静止十几秒。
- 卡片切换必须发生在句意边界；不得在一句话中间换到下一层观点。

## Structure rejection rules

以下任一情况需要退回重写：

- 两个所谓具体场景可以互换而不影响文案；
- 深层机制只是“认知、能量、底层逻辑”等空泛名词；
- 证明段只重复观点，没有观察、对比、案例或有效类比；
- 方法与机制之间不存在明确因果关系；
- 只有刺痛，没有解释性卸压；
- 结尾只是把开场换词再说一遍；
- 不同题材最终都收敛成降低门槛、马上行动或重新设计开始。
