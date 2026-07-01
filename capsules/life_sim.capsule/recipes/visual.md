---
type: Video Recipe
title: Visual Recipe
description: Visual style, references, characters, scenes, composition, and continuity.
stage: planning
domain: visual
profile: video.okf.capsule.v1
tags:
- visual
---

# Visual

## visual_rules

{
  "adaptive_scene_policy": "不设默认视觉场景池。每期根据主题、人物弧线和叙事转折生成场景；生活物件摇摇机只作为片头隐喻，不强迫正片出现固定地点。",
  "duration_pacing_policy": "微切节奏要有呼吸感：不是所有镜头都 1 秒，也不是每个镜头同一个固定秒数。按信息量、动作可读性、情绪重量、构图复杂度决定停留时长。正文允许 1-5 秒换图，但全片正文平均停留目标必须是 2.6-3.0 秒，60 秒正片通常约 18-22 张独立 Image2 图。如果一个画面承担新地点/新关系/关键情绪/高潮动作/结尾余味，可给 3.2-5.0 秒；如果只是加速、反应、闪回或状态补刀，才压到 1.0-1.6 秒；普通推进优先 2.4-3.2 秒。",
  "micro_cut_policy": "正文默认每个 1-5 秒微切都必须对应一张独立 Image2 关键帧；时长必须按剧情和画面价值分配，不得全部做成 1 秒快闪，也不得全片 5 秒拖住。冲击反应/动作瞬间/转场可用 1.0-1.6 秒；普通推进用 2.4-3.2 秒；出生异象、关键选择、复杂构图、强情绪、高潮动作、落地结算等值得看清的画面用 3.2-5.0 秒。不得仅用同一张图片做推拉、裁切、调色来冒充不同画面。最终 qa/micro_cut_report.json 必须同时证明正文 image_path 唯一、图片内容哈希唯一、max_micro_shot_seconds <= 5、average_micro_shot_seconds 在 2.6-3.0 秒。只有用户明确要求省用量并接受质量下降时，才可临时降级为同图微运动，并必须在 QA 中标记。",
  "visual_storyline_policy": "正文画面必须先有 visual_storyline：用 6-10 个连续视觉段落描述一条可看懂的剧情副线。口播是旁白，画面是正在发生的戏；画面不必逐句复述口播，但必须和口播形成直接、平行或伏笔关系，不能像随机关键词配图。",
  "mini_sequence_policy": "每 3-5 张图形成一个小连续动作，例如推门 -> 看见账单 -> 手抖 -> 做决定 -> 后果出现。小连续动作要比单张海报更重要；观众静音看 contact sheet 也应能看出人物正在一步步走进爽点或反噬。",
  "continuity_anchor_policy": "每个正文微切必须写 continuity_anchor，说明这一镜接住了上一镜的什么：同一主角外观、同一武器/衣物变化、上一镜动作后果、地点推进、光线情绪、身体状态、关系变化或关键道具状态。没有 continuity_anchor 的图，不进入正文微切。",
  "character_lock_policy": "每期正片图生成前必须先建立角色圣经和 character_reference_image。角色圣经至少包含年龄气质、发型脸型、服装颜色、随身道具、身体状态和情绪弧线；每条 Image2 prompt 必须带 compact character anchor，每个微切必须写 actor_state。参考图只锁 identity，不锁死 pose、构图、镜头和场景，必须允许侧脸、背影、三分之二侧身、远景和剪影等符合剧情的变化。",
  "voice_visual_relation_policy": "每个正文微切必须标记 voice_visual_relation：direct 表示口播说什么画面直接演什么；parallel 表示口播讲心理/命运，画面演能承载它的动作或处境；foreshadow 表示画面提前埋后面要发生的物件、地点或人物压力。",
  "sentence_boundary_pacing_policy": "视觉切换必须贴着口播 sentence_boundary：一句话没说完时不能频繁切换画面。正常情况下一个画面至少覆盖 1 句完整口播，优先 1-2 句后切；短句可合并成同一镜头；超长句可以拆成多个画面，但只能在逗号、分号或清楚语义分句/自然停顿处切，并且多个画面必须共享同一句 narration_sentence_id，通过 continuity_anchor 做同一动作、同一空间或同一情绪的连续推进，不能切到新的无关画面。",
  "no_keyword_illustration_storyboard": "禁止关键词插画式 storyboard：不能每条口播抽一个名词生成一张海报感插画。每张图都必须回答：这张图接着上一张发生了什么？主角现在在哪里？手里、身上、身边有什么变化？下一张图为什么能从这里发生？",
  "no_generated_text": "图片生成不要求模型绘制中文字幕、手机文字、品牌或 UI；可见文字统一后期加。",
  "reference_first": "先生成角色参考图和关键场景参考图；后续只继承身份特征、空间气质、核心道具，不能复制同一构图。",
  "immersive_pov_policy": "正文默认强化观众即主角的视觉代入：每组关键段落至少安排 POV、近身视角、肩后视角、手部动作、镜中倒影、手机屏幕视角、桌面物件压迫或空间挤压中的一种。不要全片都用远景旁观主角表演；即使不是第一视角，也要让画面像贴着“你”的生活发生。",
  "embodied_detail_visuals": "第二人称口播里的身体感和生活细节要被画面承接，例如手机震动、钥匙硌手、工牌勒住脖子、出租屋灯闪、账单弹窗、手心出汗、门锁声、地铁玻璃倒影、凌晨电脑蓝光。图片生成仍不负责绘制可读文字，账单/通知/标签等可见字统一后期叠加。",
  "reference_account_visual_ingestion": "当输入 reference_account_analysis_path 时，先提炼参考账号的视觉 DNA：16:9 横屏、AI 动漫/韩漫/美漫故事板、POV、极端表情特写、手机/余额/评论/聊天等现实 UI 道具、情绪色彩递进、道具特写和公开处刑现场。只学习结构和镜头功能，不复制具体桥段、人设和可识别画面。",
  "visual_style_mode_policy": "默认 visual_style_mode=anime_storyboard_drama，服务爽文短剧和强情绪；用户明确要求几米感/绘本感时可用 soft_picture_book，但不能把爽点、反噬和连续剧情削弱成温柔氛围图。",
  "scene_selection_principles": [
    "场景必须服务剧情推进：处境、动作、反转、关系或情绪状态至少满足其一。",
    "每个主要场景要能回答“你现在站在哪里、手里有什么、压力从哪里逼近”。",
    "重复地点可以用构图、道具状态、光线、人物动作变化制造新信息；不为了凑镜头强行换场。",
    "图片生成仍禁止中文字、UI 字、品牌和水印；所有可见文字后期叠加。"
  ],
  "variation_requirement": "正文视觉每 1-5 秒切换独立 Image2 图片；每张图片要体现新的动作、构图、物品状态、空间关系或情绪变化，并通过 continuity_anchor 接住前后镜头。剪辑节奏必须有 1.0-5.0 秒内的时长层次，正文平均 2.6-3.0 秒，并且换图点必须落在完整句子或清楚语义分句边界上，避免整片 1 秒快闪、全片长停留或一句话没说完就频繁切换。交付前同时检查文件路径唯一、内容哈希唯一、最大微切时长不超过 5 秒、平均停留 2.6-3.0 秒、actor_state、角色一致性和 sentence_boundary 对齐。"
}
