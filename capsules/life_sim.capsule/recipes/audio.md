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

## audio_rules

{
  "bgm": "优先使用明确授权的线上素材或用户给定本地素材；下载成本地文件并记录来源；BGM 建议 0.035-0.075。",
  "mix": "TTS 是时长真相；先混 narration+BGM+SFX。正文无底部字幕时，不要再走 body ASS 烧字幕步骤。",
  "opening": "抽取机音效只服务系列开场，不使用中奖、下注、奖励等博彩联想强的声音。",
  "opening_tts_duration": "opening_manifest.duration 应在 3.4-4.5 秒；超过 4.5 秒先短句化，不用变速硬压。",
  "body_tts_deduplication": "片头身份锁定句只能出现在 opening.tts；正文 TTS 必须使用 body_narration_script，或使用 strip_opening_tts_from_body_script 对 narration_script 去重后再送 TTS。若正文文本仍以 opening.tts 开头，阻断生成并重写/拆分脚本。",
  "tts": "默认音色仍是 MiniMax male_narrator，语速 1.18；目标听感是年轻、有能量、清楚讲故事的男性叙事口播，避免拖沓、过慢或老派纪录片腔。片头和正文必须同 provider/voice/speed/mix。工具层将 male_narrator 解析到 MiniMax 可用默认男声，禁止静默切换到其它 provider、本机声音或其他音色。",
  "voice_default": "minimax/male_narrator"
}
