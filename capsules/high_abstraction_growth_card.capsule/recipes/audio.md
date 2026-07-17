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
- BGM 必须优先使用可下载到本地的授权/生成纯音乐；有 Suno 配置时优先 Suno，无可用结果才用本地 ffmpeg 预览底音。
- 用户指定网上寻找 BGM 时，优先使用许可页明确允许社交媒体和商业/非商业视频使用的音乐；下载后记录曲名、作者、来源页、许可名称、许可页和本地文件哈希。配置 `bgm_path` 后不得再调用 Suno。
- BGM 必须低音量垫底，不压过口播，也不使用来源视频原声；Suno 等完整音乐源默认混音音量要显著低于本地弱底音。
- 视频节奏以口播音频时长为准；最终视频不应比口播明显长或短。
- 完整口播由逐 beat narration 按顺序组成；如果另行提交 voiceover_text，必须与 beats 一致。卡片时长按 beat 预计秒数、权重或口播长度归一到实测音频总时长。
- 禁止保留参考账号音频、水印音、口头禅或可识别音频片段。
