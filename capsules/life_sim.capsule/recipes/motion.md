---
type: Video Recipe
title: Motion Recipe
description: Camera motion, action, transitions, dynamic generation, and editing rhythm.
stage: generation
domain: motion
profile: video.okf.capsule.v1
tags:
- motion
---

# Motion

## Rules

## settled_body_motion

- 正片默认 `settled_hold`：画面可以有轻微位移，但不能一直抖动。观众应该感到镜头在稳稳地看一张动态漫画分镜，而不是每秒都被摇晃。
- 单张静态 Image2 正片图默认 `static_hold`，只有在画面需要呼吸感时才加非常慢的推、拉、轻平移。常规慢推拉幅度控制在 0.8%-1.8%，不能每张都同方向持续漂移。
- 片头 life_shaker 的摇动只属于 opening。进入正片后不得继续使用摇摇机式抖动、随机 jitter、频繁左右摆动或模拟手持晃动。
- 冲击瞬间可以有一次短促 punctuation shake，例如摔门、砸桌、终场哨、评论爆发、反派破防，但单次不得超过 0.25 秒，同一段落不能连续使用。
- 正文镜头停留要和口播句子绑定：一张图通常覆盖 1-2 句，平均 2.6-3.0 秒；强情绪、复杂构图、高潮动作和结尾余味可以停 3.2-5.0 秒。
- 不允许用同一张图反复裁切、放大、调色来冒充不同画面。运动只能增强一张图的可看性，不能替代独立 Image2 关键帧。

## motion_qa

- 正片 QA 必须记录 `body_motion_style=settled_hold`、`continuous_shake=false`、`opening_shake_scope=opening_only`。
- 抽查 body segments 时，若多数镜头都有明显持续 zoompan、左右漂移或抖动，应视为观感问题而不是通过项。
- 允许少量慢推拉，但优先让图片本身的构图、人物表情、道具状态和剧情连续性承担注意力。
