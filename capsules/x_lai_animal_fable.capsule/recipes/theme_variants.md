---
type: Video Recipe
title: Theme Variant Recipe
description: Convert one promotional topic into distinct X来 story variants with evidence-safe payoff cards.
stage: planning
domain: theme_variants
profile: video.okf.capsule.v1
tags:
- theme-routing
- variants
- promotion
---

# Theme To Variants

## Minimum Intake

`topic` 是唯一必填项。缺少其他信息时可以生成创意方向，但不能生成未经提供的卖点、数字、价格、日期、地址、效果、资质、榜单、用户评价或行动承诺。

规划前把输入整理为：

- `raw_topic`：逐字保留用户输入。
- `subject_type`：商品、服务、品牌、活动、观点、数据热点、公共信息或其他。
- `promotion_goal`：认知、解释、互动、转化、报名或热点表达。
- `audience`、`key_message`、`proof_points`、`source_materials`、`call_to_action`。
- `known_facts` 与 `unknown_claims`：后者不能进入公开文案。
- `problem_character`、`xlai_entity`、`responder_character`、`promotion_visual_anchor`：分别说明谁受困、X是谁、谁以X的身份作为核心主角登场、宣传对象如何进入其造型或动作。

## Semantic Binding

- 先从宣传主题提炼一个能被看见的 `xlai_entity`，再设计救场主角；不能先选喜欢的动物，最后硬配一句X来。
- 动物主题：`马来 -> 马主角 -> 奔跑/驮运/抵达 -> 马术或与马直接相关的宣传内容`。
- 商品/物件主题：`书来 -> 拟人书本主角 -> 翻页/排书/搭书路 -> 读书会或图书内容`。
- 服务主题：优先使用服务的真实工具、载体或经用户确认的品牌角色做主角；若服务无法被直接实体化，先向用户提供2-3种视觉化方案，不能用无关动物代替。
- 活动主题：主角必须是活动核心参与者、器材、场景物件或经授权IP；普通象征物只有在观众不看说明也能识别活动时才可用。
- 广告语继续由同一救场主角说，并指向同一宣传对象。X、角色、动作、广告语四者任一断裂都要重写候选。

## Variant Modes

### Summon Solution

适合商品、服务、工具和活动：

`具体麻烦 -> 主角尝试失败 -> 主角哭喊“妈妈——” -> 另一救场角色喊 X来 -> 一个动作解决 -> 救场角色说广告语 -> 本地信息卡`

结果必须对应真实功能，不能把普通功能夸成无法证明的神奇效果。

### Self Awakening

适合品牌精神、人物、团队、赛事和情绪型热点：

`对立/受阻 -> 主角尝试失败并哭喊“妈妈——” -> 导师或同伴喊 X来 -> 主角在帮助下完成身份翻转 -> 救场角色说广告语 -> 主题卡`

觉醒是叙事隐喻，不得转化为未经证实的性能、收益或健康承诺。

### Visual Pun

适合成语、节日、栏目命题、谐音和概念传播：

`怪文字/物件 -> 主角错误理解后哭喊“妈妈——” -> 另一揭示角色喊 X来 -> 环境组成命题答案 -> 揭示角色说广告语`

谐音必须自然可懂；所有汉字和文字物体本地渲染，不能依赖 Agnes 生成可读文字。

### Conflict Proof

适合带证据的热点解释、数据变化和对比传播：

`两种力量对峙 -> 主角可见落败并哭喊“妈妈——” -> 第二角色强声喊 X来 -> 一击反转 -> 救场角色说广告语 -> 截图/数据证明`

最后的证明必须来自用户材料或可核验数据，并标注来源与时间。财经、健康、功效、教育结果等高风险领域只做合规表达，不给个体建议，不伪造收益或见证。

## Auto Router

- `product/service`：优先 `summon_solution`，另给 `self_awakening` 和 `visual_pun` 候选。
- `brand/idea`：优先 `self_awakening`，另给 `visual_pun` 和 `summon_solution` 候选。
- `event`：优先 `summon_solution` 或 `visual_pun`，结尾使用本地 `event` 卡。
- `data_topic/public_info`：只有证据充足才选 `conflict_proof`；否则降级为不含事实断言的概念预告。
- `auto/other`：至少产生三条机制不同的候选，按首秒可读性、主题贴合、证据可得性、Agnes 可生成性和合规风险排序。

## Variant Plan Contract

每个候选必须记录：

- `variant_id`、`mode`、`title_or_call`、`one_line_premise`。
- `first_frame_hook`、`failed_attempt`、`mama_cry`、`responder_character`、`xlai_call`、`turn_or_arrival`、`visible_payoff`、`ad_line`。
- `xlai_entity`、`responder_visual_identity`、`promotion_visual_anchor`、`semantic_binding_chain` 和 `replacement_test`；replacement_test必须说明为何不能把该主角随意换成其他动物或物件。
- `opening_audio_signature`、`mama_timing`、`xlai_voice_contrast`、`responder_voice_anchor`、`ad_line_voice_mode`、`dialogue_generation_units` 和 `native_dialogue_review_plan`。
- `theme_connection`：画面结果如何证明或记住主题，不能只换片尾Logo。
- `proof_payload`：需要哪些用户事实或材料；没有则写 `none`。
- `local_text_plan`：字幕、品牌字、数据、来源、日期、CTA的本地渲染方式。
- `agnes_units`：每个 `5-10s` 单元的任务边界和预计调用数。
- `risk_notes`、`originality_boundary`、`recommendation_score`。

候选之间不能只是更换动物、颜色或一句台词。至少在冲突关系、转折机制或结果证明上不同。

## Selection Gate

- 规划可以一次输出 `1-6` 条候选，默认 `3` 条。
- 云端生成前只能选择一条候选，并展示视频调用数、音频策略、软一致性和免费层限制。
- 默认候选使用 `mama_then_xlai`；主题不适合童声联想时必须明确改为 `xlai_only` 或 `none`，不能机械套用。
- `full_story` 默认规划两个 Agnes 单元：约5秒的困境/失败/妈妈单元，以及约8-10秒的救场角色X来/解决/广告语单元。`hook_test` 只能验证单拍，不得冒充完整候选成片。
- 选中候选前先审核语义绑定。角色只与X存在职业、寓意或文化弱联想时，必须改成X本体、拟人化商品、真实服务载体或经用户确认的品牌角色。
- 首个最难单元通过后，才生成同一候选的剩余单元。
- 用户要求多版本成片时，每个版本仍单独经过首镜门槛，不把 `variant_count` 当作自动批量授权。

## Proof Card

宣传型成片默认保留 `1.5-4s` 的本地确定性结尾卡：

- `message`：一句经过用户确认的核心信息。
- `evidence`：数据、来源和时间。
- `offer`：经用户提供的价格或权益，不自动制造稀缺性。
- `event`：名称、日期、地点和报名方式，逐项来自用户输入。

证据卡不覆盖剧情高潮；它是高潮之后的验证与记忆闭环。
