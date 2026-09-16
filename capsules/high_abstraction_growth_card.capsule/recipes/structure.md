---
type: Video Recipe
title: Structure Recipe
description: Lane-aware cognitive argument, escalating-question retention, semantic beats, card forms, and pacing.
stage: planning
domain: structure
profile: video.okf.capsule.v1
tags:
- structure
---

# Structure

## Planning order

必须先完成内容诊断和完整论证，再把论证切成卡片。视觉不能根据关键词反向决定观点，也不能因为现有插画只有计时器、门槛或路径，就把所有题材改写成行动力问题。

每个 beat 只承担一个语义任务，并包含：`id`、`role`、`theme`、`visible_text`、`narration`、`metaphor_family`、`emphasis_keywords`、`information_gain`、`card_form` 和 `retention_question`，可选 `supporting_points`、`estimated_seconds`、`duration_weight` 和 `pause_after_seconds`。`visible_text` 必须是本 beat 口播中的原句或连续原文片段，只允许通过换行和去除标点适配画面，不得另写一套高级概括让观众同时翻译眼睛和耳朵。1-2 个核心词用 `**关键词**` 标记，最终渲染为真实粗体，星号不得出现在画面。

一条短论只允许命名一个主模型。模型名必须出现在场景和因果已经成立之后；后续动作继续使用同一组词回指该模型，不得用同义词轮换制造“解释权、判断资格、身份判决、独立取证”式的伪丰富。

## Retention engine: answer one layer, open the next

长内容不能靠重复金句拖时长，而要靠**问题升级链**推进。每一层都必须完成 `旧问题 -> 本层答案 -> 新证据或新区分 -> 下一层问题`：

1. **痛苦是什么**：用不可互换的现实场景让观众确认“这说的是我”。
2. **大众解释为什么不够**：指出旧解释漏掉了哪一层，不能只说“大家都错了”。
3. **真正机制是什么**：用一个可命名、可复述的模型统一解释多个场景。
4. **为什么相信这个解释**：给观察、对比、案例或有边界的跨框架互证。
5. **反方疑问是什么**：主动提出观众最可能的反驳、伦理疑虑或现实条件。
6. **普通人怎么做**：动作从机制推导，并说明先后、条件和失败信号。
7. **最终成为什么样的人**：完成身份重定义，同时闭合第一屏的承诺。

`retention_question` 记录本 beat 结束后观众自然会追问的下一层问题。最终 beat 留空并闭合开场；其余问题必须在后续 1-4 个 beats 内被回答、升级或明确标注边界，不能靠“后面更精彩”空吊胃口。

每 15-30 秒至少发生一次 `information_gain`：`new_scene`、`new_distinction`、`new_mechanism`、`new_evidence`、`objection_resolution`、`new_action` 或 `identity_reframe`。连续两个 beats 如果只表达同一个 gain，应合并或重写。

## Duration modes

### short_thesis

- 目标 60-100 秒，10-14 个语义任务，但插画顺序和每张卡时长不固定。
- 最小结构：hook -> concrete_scene -> concrete_scene -> conceptual_split -> mechanism -> proof_or_comparison -> redefinition -> emotional_relief -> action -> action -> identity_close。
- 只讲一个核心判断，但必须出现两个现实场景、一次解释升级、一条证明路线和两个可推导动作。
- 0-3 秒给冲突；3-20 秒建立场景和未闭合问题；20-55 秒完成机制和证明；55 秒后给动作与身份收束。
- 至少设置两个真实的 `retention_question`，分别把观众从痛点带到原因、再从原因带到做法。

### deep_cognitive_essay

- 目标 180-360 秒，12-24 个 beats。
- 最少结构：hook -> 三个现实场景 -> 概念二分 -> 深层机制 -> 后果 -> 证明/类比 -> 一次反方处理 -> 误区 -> 重定义 -> 两至三个方法 -> 身份升华。
- 情绪曲线为：被说中 -> 看见残酷机制 -> 获得解释性卸压 -> 理解新定义 -> 拿到行动路径 -> 完成身份赋能。
- 每 15-30 秒必须有认知推进；没有新信息的金句、排比和抚慰应删除。
- 至少三个不重复的 `retention_question`；中段必须有一次“到这里你可能会问”式的真实异议处理。

### long_column

- 目标 420-780 秒，24-40 个 beats；适合宏大但能落回现实的哲学、关系、人性、成事能力和认知模型选题。
- 结构不是把 `deep_cognitive_essay` 拉长，而是完整经过：痛点命名 -> 旧解释失效 -> 底层模型 -> 多场景统一 -> 主证据 -> 补充框架 -> 反方疑问 -> 边界条件 -> 3-7 个动作 -> 身份收束。
- 至少四个不可互换的现实场景、三个证明/框架 beats、一次明确反方处理、三个从机制推导的动作和六次问题升级。
- 每 20-35 秒必须领取一个新解释；每 60-90 秒至少发生一次结构级变化，例如从场景进入模型、从模型进入反方、从反方进入方法。
- 任一核心概念都要经历“命名 -> 定义 -> 场景验证 -> 适用边界 -> 行动用途”，否则只是高级词汇堆叠。

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
- `framework_bridge`
- `objection`
- `boundary`
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
- 正式配音必须逐 beat 生成并实测；一旦存在实测时长，`measured_audio_seconds = speech_seconds + pause_after_seconds` 是唯一卡片时长依据，预计秒数不得继续覆盖它。
- 第一张卡承担前三秒停留；最后一张卡闭合开场问题。
- 一个 beat 的口播明显过长时，应先拆 beat，而不是让一张卡静止十几秒。
- 卡片切换必须发生在句意边界；不得在一句话中间换到下一层观点。
- 单卡建议 6-18 秒；超过 18 秒必须有卡内第二状态或拆成新的信息 beat。
- 连续卡片不能超过两张使用同一 `card_form`。形态应跟随论证任务轮换：`verdict_poster`、`scene_card`、`dual_compare`、`model_map`、`question_card`、`action_path`、`identity_poster`。
- 卡形不是装饰：二分用 `dual_compare`，机制或框架用 `model_map`，真实异议用 `question_card`，动作序列用 `action_path`；不得随机换皮。

## Structure rejection rules

以下任一情况需要退回重写：

- 两个所谓具体场景可以互换而不影响文案；
- 深层机制只是“认知、能量、底层逻辑”等空泛名词；
- 证明段只重复观点，没有观察、对比、案例或有效类比；
- 方法与机制之间不存在明确因果关系；
- 只有刺痛，没有解释性卸压；
- 结尾只是把开场换词再说一遍；
- 中段没有问题升级，只靠“更底层、更高级、更重要”等程度副词续命；
- 提出反方疑问但没有回答，或回答绕开现实条件；
- 关键词没有显式加粗，或整句都被加粗导致没有视觉锚点；
- 连续三张以上卡片形态一致；
- 不同题材最终都收敛成降低门槛、马上行动或重新设计开始。
