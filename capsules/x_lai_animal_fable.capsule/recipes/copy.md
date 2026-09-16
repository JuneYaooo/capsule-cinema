---
type: Video Recipe
title: Copy Recipe
description: Voiceover, subtitles, titles, cover copy, lyrics, and CTA rules.
stage: planning
domain: copy
profile: video.okf.capsule.v1
tags:
- copy
---

# Copy

## Source-Cut Voice

- 原片角色始终活在故事内部，不说“这是广告”“这个梗真好笑”等元话语。
- 默认真正的第一句仍是绵长“妈妈——”，但前面必须先有1-3秒无需台词也能看懂的困境和失败动作；不能一开场无缘无故喊，也不能先插片名、旁白、卖点或解释。
- “妈妈——”只表达求援、恐惧或弱势处境，不把真人儿童身份、家庭创伤或危险遭遇当作娱乐卖点；声音描述只能选不可识别的合成角色声型。
- `X来` 是召唤、觉醒或命题揭示词，通常控制在 `2-6` 字；其他中文单句控制在 `2-12` 字。
- `X来` 中的X必须能准确命名或识别登场主角，并直接来自宣传对象。不能只为押韵选X，也不能由无关角色喊一个与自身形象不一致的X。
- 商品/活动型先说困境或呼唤，卖点留给动作结果和本地信息卡，不让角色背整段广告词。
- 救场角色喊完 `X来！`、完成一个解决动作后，再说一句 `4-14` 字广告语。广告语只讲一个记忆点，优先采用用户提供的 `ad_line` 或 `key_message`；系统生成的只能是待确认候选。
- 默认台词职责固定：弱势角色只说“妈妈——”；另一救场角色说“X来！”和广告语。除非用户明确更换结构，不让主角自己把三句全说完。
- 命题拆解型允许原创成语、谐音和热词，但必须自然、可懂、与主题有因果关系，不能复制参考原句。
- 每个 `5-10s` Agnes 单元优先只有一位说话人。第一单元只让弱势角色说“妈妈——”；第二单元可以让同一个救场角色分两拍说“X来！”和广告语，中间必须隔着可见解决动作。若两句原声不稳定，广告语改用经确认的后期声音或本地文字，不牺牲 `X来` 的清晰度。

## Title Pattern

- 片名默认是 `2-4` 个字，形式可为 `<动物>来`，但必须使用本期原创角色、原创事件和原创对白。
- 片名只负责像一部被遗忘的动物寓言电影，不承诺与任何现有作品存在关系。
- 标题、封面、首镜和结果卡围绕同一个宣传主题；不能出现“剧情讲A、片尾突然宣传B”的断裂。

## Source And Packaging Separation

- `source_cut`：只含严肃剧情、对白、字幕和必要声音，不加入观众笑声、吐槽字卡、反应贴纸或“低成本神作”等元评论。
- `reaction_package`：另存的发布标题、封面候选、导语或反应版剪辑；它可以指出荒诞感，但不得覆盖唯一干净原片。
- 包装文案不能冒充原作续集、官方关联或真实出处，也不能复制对标作品的标题、角色身份、台词或标志性场面。

## Planning Output

规划阶段必须输出：

- `raw_topic`、`subject_type`、`promotion_goal`、`audience`、`key_message`、`known_facts`、`unknown_claims`。
- 至少三个 `variant_candidates`，分别记录mode、首帧、喊词、转折、可见结果、证据需求和风险。
- 被选中的 `animal`、`xlai_entity`、`responder_character`、`promotion_visual_anchor`、`semantic_binding_chain`、`title_or_call`、`theme_connection`、`proof_payload`、`local_text_plan`。
- `problem_setup`、`failed_attempt`、`mama_cry`、`responder_character`、`xlai_call`、`visible_solution`、`ad_line_candidates`、`approved_ad_line` 和 `ad_line_claim_sources`。
- `trivial_incident`、`normal_action_expectation`、`body_anomaly`、`visible_consequence`。
- 三个 `opening_candidates`，分别从身体异常、严肃问题、错误简单动作切入。
- `source_dialogue` 与单独的 `reaction_packaging_candidates`。
- 按 `5-10s` 单元拆分的 `script_outline`、封面文案和风险提醒。
- 宣传型输出追加确定性结尾卡；CTA、价格、日期、地点、数据和来源逐项对应用户材料。

## Text Rendering

- 不要求 Agnes 在图片或视频里生成中文、片名、字幕、Logo 或水印；所有可读文字都在本地后期叠加。
- 字幕只转录正式对白，不额外添加解释笑点的括号吐槽。
- 观众可见文案不得出现提示词、模型、免费额度、生成失败、软锁定等制作说明；这些只进入内部路线报告和 QA。
- Agnes 画面中的偶然文字、Logo、品牌形状和乱码不能作为正式宣传信息；必须去除、遮挡或重生成。
