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

## Per-episode H3 generation boundary

- The capsule stores only the H3 workflow, prompt convention, character input anchors, and QA rules. It must not store any episode H3 video, generated audio, task ID, or result URL.
- Every episode must write fresh H3 prompt/parameter/result records under that episode's run directory and generate a new complete H3 clip for every spoken character shot, even when the character or workflow is unchanged.
- Never copy a prior episode's H3 MP4 or native audio into a new run. Reusing the packaged character reference image is allowed; reusing a generated H3 output is not.

## Voice

- 角色对白默认使用 AutoDL.Art H3 原生语音和口型同步；小白起句直接、困惑中带受挫和着急，专家成熟笃定、重音更准、句末落稳。两者都不能慢速逐词吐字，也不能使用夸张播音腔。
- 只有输入明确选择 `character_audio_mode=external_tts_lipsync` 时，才使用两条已确认的 MiniMax 音色：小白 `Chinese_worker_female`，专家 `moss_audio_aaa1346a-7ce7-11f0-8e61-2e6e3c7ee85d`，并统一在 MiniMax 生成阶段设置 `speed=1.25`。基础音色不得静默替换。
- 外部 TTS 路线必须先生成并试听单句音频，再把该音频与对应人物/真实素材参考板一起提交给 AutoDL.Art H3 `minimax_h3_lightx2v_v5`；H3 只同步画面和口型，不使用自由生成声音。
- 原声或 TTS 必须删除模型生成的无意义长停顿。单句内部超过 0.35 秒的停顿需要有明确语义，否则重生成或在保持音画同步的前提下同时剪掉对应音画。
- TTS 先生成并实测时长，再锁镜头边界。旁白总时长是成片时序权威，禁止画面结束后静音拖尾或音频没说完就冻结。
- 本胶囊对白默认走 H3 原生语音；如用户显式选择外部 TTS，必须先更新输入与工具链确认，不得静默替换。

## Rhythm Bed

- BGM 是低音量节奏床，不承担情绪煽动。对话期间保持清晰可懂，可信信号拍可短暂提升能量，交付拍回落。
- 各优势点的证据切换使用同一家族的轻短 SFX，间距递进但响度不过分；真实结果首次揭示可使用一次清晰切换音。
- BGM 和 SFX 仅使用用户提供、本地有许可或胶囊已打包的素材，不抓取来历不明的网络音频。

## Mix Gate

- 人声全程可懂，BGM 不遮盖辅音，SFX 不压过关键词。
- 两角色切换必须能听出表演状态差异，同时不能像两个毫无关系的人。
- 字幕按最终对白音频的实测词级时间对齐。项目科普的快节奏来自短句、原生或外部 TTS 的明确语速和硬切；后期禁止对专家、小白或任一片段分别使用 `atempo`、变速视频或补帧来改变语速。

## Audio-First H3 For Project Explainers

- 一条对白先确定一条角色音频，再对应生成一条完整 H3 视频；默认音频由 H3 原生生成，只有显式选择外部 TTS 时才来自 MiniMax。音频不可跨镜头拆半，也不可把多条角色音频一起交给 H3 猜顺序。
- 第 0.00 秒必须已经有小白的可听语音。H3 成片若比 TTS 多出尾部空白，只能按 TTS 实测时长裁尾；不得单独移动音频或改变音频速度。
- 专家总口播超过单条 H3 可承载长度时，按完整语义拆段。所有专家段保持同一固定音色、`1.25` 速度、人物资产和相近场景；小白段同理。
- 官方仓库证据默认采用真实抓取优先路线（见 quality/rules.yaml `evidence_media_route`）：真实 GitHub 页面截图与滚动录屏 → api.github.com 官方原始素材（raw SVG、GFM 渲染 README 表格）→ 确实无法抓取时才本地合成。只有选择 `evidence_media_mode=h3_reference_board` 时，才合并成一张 `768x1366` 左右的竖屏参考板交给 H3。两条路线不能在同一段重复叠加。
- 每个 H3 请求仅提交一张压缩参考板、一条短音频和短动作提示。不要提交 README 全文、网页长图、多张图片或多段音频，避免输入过大、素材竞争和口型顺序失控。
- 两角色都要求短句、高密度、情绪饱满：小白急切但不尖叫，专家成熟笃定但不慢讲；无语义停顿不得超过 0.35 秒。每条 H3 镜头的台词字数在写稿阶段按镜头时长预算（约 5.5–7 字/秒），让音频在原生速度下刚好装进镜头；后期禁止用变速找补节奏。
- H3 输出保留输入音频；本地后期允许统一画布、裁尾、原速顺序拼接、顶部标题，以及在真实抓取路线中加入经过来源清单登记的官方项目真实素材。禁止混入 H3 自由声音、重新配音或角色片段差异化加速。
- 真实素材镜头必须以混剪（J-cut）方式压在对应角色的口播音频下：画面切到素材时声音延续该角色 H3 原声，不设独立的无声素材展示段，也不为素材段另配旁白或音效垫底。一个角色的声音贯穿其全部画面。

## H3 Prompt Convention And ASR Gate

- H3 会随机把 prompt 里可念的指令文本念出来，或生成 babble 前缀/后缀；引号包裹不能根除，所以 ASR 验收是硬门。写 prompt 时降低泄漏概率：需要说出来的台词用「」包裹并放在 prompt 最后一行，明确「逐字照读、一字不多一字不少、此外不说任何字」；音频/表演类指令尽量极简，少给可被念出的词。
- 每条可用台词必须过 whisper 词级转写验收（`whisper --model medium --language zh --word_timestamps True --output_format json`）逐字等于台本后才能进剪辑：转写多出指令念白或 babble 的段落，优先换生成；确要保留时在吸气后的静音谷掐头、按包络形状（平切 vs 衰减）切尾，被掐掉的只能是泄漏语音。
- 成片拼装完成后必须再做一次全片 ASR 转写，与台本逐句对照，要求零多余字；转写的同音异形字（如 界別/鉴别）不算内容变化，可用解码音轨 MD5（`ffmpeg -i 成片 -map 0:a:0 -f md5 -`）证明音频逐位一致。

- 每次 H3 通过 ASR 后，必须把实际采用的 `trim_start`、`trim_end` 和对应台词写入本期 run；如果 H3 生成了 prompt 泄漏或 babble，只能裁掉泄漏段，不能用后期静音覆盖后继续保留。最终整片 ASR 仍以台本为准，不能只凭局部听感判断“差不多”。
