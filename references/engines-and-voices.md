# 引擎与音色参考

## 图片引擎

| 引擎 | import | 类名 | 备注 |
|------|--------|------|------|
| gpt-image-2 | `custom_tools.image_generation.seedream5_image_generator_tool` | `GptImage2Tool` | Krill AI / Cherry Studio 兼容渠道，高保真写实、角色源图和精修优先 |
| gpt-image-2-pro | `custom_tools.image_generation.seedream5_image_generator_tool` | `GptImage2ProTool` | ZeakAI 备用 Image2 通道；Krill 主通道不可用且凭证存在时使用 |
| seedream5 | `custom_tools.image_generation.seedream5_image_generator_tool` | `Seedream5ImageGeneratorTool` | 中文 prompt 友好 |
| gemini3_pro | `custom_tools.image_generation.gemini3_pro_image_tool` | `Gemini3ProImageGeneratorTool` | 已注册但非默认 fallback；仅手动或项目政策允许时使用 |

## 视频引擎

| 引擎 | import | 类名 | 支持 |
|------|--------|------|------|
| seedance-fast | `custom_tools.video_generation.seedance_video_generator_tool` | `SeedanceFastVideoGeneratorTool` | text_to_video, image_to_video，默认 |
| seedance | `custom_tools.video_generation.seedance_video_generator_tool` | `SeedanceVideoGeneratorTool` | text_to_video, image_to_video，Pro 档 |
| seedance2.0 | `custom_tools.video_generation.seedance_video_generator_tool` | `Seedance20VideoGeneratorTool` | text_to_video, image_to_video，Ark/BytePlus 路线 |
| jimeng35pro | `custom_tools.video_generation.jimeng35pro_video_generator_tool` | `Jimeng35ProVideoGeneratorTool` | text_to_video, image_to_video |
| veo3 | `custom_tools.video_generation.veo3_video_generator_tool` | `Veo3VideoGeneratorTool` | text_to_video, image_to_video |
| veo3.1 | `custom_tools.video_generation.veo31_video_generator_tool` | `Veo31VideoGeneratorTool` | text_to_video, image_to_video, first_last_frame |

提示词选择：

| 引擎 | 建议 |
|------|------|
| seedance-fast | 中文 prompt；普通图生视频默认选择，适合快速迭代 |
| seedance | 中文 prompt；需要 Seedance Pro 档时使用 |
| seedance2.0 | 中文 prompt；电商商品展示和写实商品运动优先 |
| jimeng35pro | 中文 prompt；需要中文语音时生成后跑语言检测 |
| veo3 | 中英文都可，复杂电影感描述可用英文 |
| veo3.1 | 中文 prompt 可用；首尾帧视频要保证两张图主体和构图一致 |

## TTS 音色

完整流程通过 `UniversalTTSTool` / `UniversalTTSBatchTool` 生成音频。未指定 provider 时，代码默认尝试 `minimax`，胶囊或用户可以显式设置 `tts_provider: doubao`。下面是常用豆包音色；使用豆包时尽量选择已开通的 `_mars_bigtts` 音色。

| 音色 ID | 描述 | 适合 |
|---------|------|------|
| `zh_male_jieshuoxiaoming_moon_bigtts` | 解说小明 | 旁白、科普、解说 |
| `zh_male_chunhou_moon_bigtts` | 淳厚男声 | 成熟男性、故事旁白 |
| `zh_female_shuangkuaisisi_moon_bigtts` | 爽快思思 | 成熟女性、生活内容 |
| `zh_female_tianmeixiaoyuan_moon_bigtts` | 甜美小媛 | 年轻女性、可爱内容 |
| `zh_female_sajiaonvyou_moon_bigtts` | 撒娇女友 | 可爱女性角色 |
| `zh_female_wanwanxiaohe_moon_bigtts` | 弯弯小何 | 温柔女性角色 |

避免使用已知 403 的音色：

- `zh_female_yueyuequnshan_moon_bigtts`
- `zh_female_qingxinnvsheng_moon_bigtts`
- `zh_male_shaonianluntan_moon_bigtts`
- `zh_male_zhangjianxiake_moon_bigtts`
