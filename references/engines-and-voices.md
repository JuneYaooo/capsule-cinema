# 引擎与音色参考

## 图片引擎

| 引擎 | import | 类名 | 备注 |
|------|--------|------|------|
| gpt-image-2 | `custom_tools.image_generation.seedream5_image_generator_tool` | `GptImage2Tool` | 高保真写实、角色源图和精修优先 |
| seedream5 | `custom_tools.image_generation.seedream5_image_generator_tool` | `Seedream5ImageGeneratorTool` | 中文 prompt 友好 |
| gemini3_pro | `custom_tools.image_generation.gemini3_pro_image_tool` | `Gemini3ProImageGeneratorTool` | 通用图片生成 |

## 视频引擎

| 引擎 | import | 类名 | 支持 |
|------|--------|------|------|
| seedance-fast | `custom_tools.video_generation.seedance_video_generator_tool` | `SeedanceFastVideoGeneratorTool` | text_to_video, image_to_video，默认 |
| jimeng35pro | `custom_tools.video_generation.jimeng35pro_video_generator_tool` | `Jimeng35ProVideoGeneratorTool` | text_to_video, image_to_video |
| veo3 | `custom_tools.video_generation.veo3_video_generator_tool` | `Veo3VideoGeneratorTool` | text_to_video, image_to_video |

提示词选择：

| 引擎 | 建议 |
|------|------|
| jimeng35pro | 中文 prompt；需要中文语音时生成后跑语言检测 |
| veo3 | 中英文都可，复杂电影感描述可用英文 |

## 豆包 TTS 音色

默认提供商：`doubao`。

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
