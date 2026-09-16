---
type: Video Recipe
title: Audio Recipe
description: TTS, original audio, BGM, SFX, mix, timing, and sync rules.
stage: planning
domain: audio
profile: video.okf.capsule.v1
tags:
- audio
---

# Audio

## Rules

## audio_policy

- 测试视频也必须生成可听的原创口播和低音量 BGM；禁止用静音 AAC 轨冒充完成。
- 正式/效果版必须优先使用 MiniMax 或豆包中文 TTS；配音内容必须来自本期原创脚本。
- 只有缺少外部 TTS 凭证或远程服务失败时，才允许降级到本机 TTS；降级产物只能标记为预览版，不能冒充效果版。
- BGM 优先使用可下载到本地的音频或生成纯音乐；有 Suno 配置时优先 Suno，无可用结果才用本地 ffmpeg 预览底音。
- 用户指定网上寻找 BGM 时，下载为本地文件后可直接混音；曲名、作者、来源或授权信息只作可选备注，不得阻断渲染或交付。配置 `bgm_path` 后不得再调用 Suno。
- BGM 必须低音量垫底，不压过口播，也不使用来源视频原声；Suno 等完整音乐源默认混音音量要显著低于本地弱底音。
- 视频节奏以口播音频时长为准；最终视频不应比口播明显长或短。
- 长栏目配音要保留解释感而非广告腔：反转句稍收紧，证据与反方段落放慢，方法段用清晰分组停顿，身份收束留 0.3-0.8 秒呼吸。不要从头到尾同一语速和同一情绪强度。
- BGM 的段落变化服务论证层级：场景段克制、机制揭示段轻微抬升、反方段回落、身份收束稳定；禁止用不断增强的煽情音乐替代内容推进。
- 完整口播由逐 beat narration 按顺序组成；如果另行提交 voiceover_text，必须与 beats 一致。正式版默认逐 beat 调用远程 TTS，逐段保存源音频、统一采样率、记录真实讲话时长和 0.12-0.8 秒自然停顿，再拼接成 narration master。
- 每张卡的起止时间必须来自对应 beat 的实测讲话时长加显式停顿，动画动作绑定到该 beat，不再用整段 TTS 总时长按字符权重反推分句位置。
- 屏幕主句必须是当前 beat 口播中的原句或连续片段；音频 QA 必须输出逐 beat 的 `start_seconds`、`speech_seconds`、`pause_after_seconds` 和 `end_seconds`。
- 只改画面或动画时允许复用已经测量的逐 beat 配音，但必须逐项核对 beat id 和规范化后的 narration 完全一致；任一项变化都必须重新生成配音，不得把旧时序静默套给新文案。
- 禁止保留参考账号音频、水印音、口头禅或可识别音频片段。
