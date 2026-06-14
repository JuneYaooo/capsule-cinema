# Storyboard JSON Schema

完整视频工作流会生成 `storyboard.json`，并在 `images/`、`audios/`、`videos/`、`final/` 下保存中间产物。

## 顶层结构

```json
{
  "story": {
    "title": "视频标题",
    "summary": "视频简介",
    "theme": "主题",
    "tone": "情感基调",
    "target_audience": "目标受众",
    "scenes": []
  },
  "scenes": [
    {
      "index": 1,
      "chapter_id": "chapter_01",
      "continuity_group": "opening_kitchen",
      "description": "场景描述",
      "scene_description": "中文场景描述",
      "narration": "旁白文本",
      "subtitle_text": "字幕文本",
      "image_prompt": "图片 prompt",
      "image_prompt_chinese": "中文图片 prompt",
      "video_prompt": "视频 prompt",
      "video_prompt_chinese": "中文视频 prompt",
      "video_prompt_english": "英文视频 prompt",
      "duration": 5.0,
      "video_generation_type": "image_to_video",
      "needs_reference": true,
      "reference_type": "character",
      "reference_ids": ["char_001"],
      "character_ids": ["char_001"],
      "style_anchor": "main_style",
      "use_style_reference": true,
      "continuity_notes": "角色外观、服装主视觉、关键道具和环境状态必须延续"
    }
  ],
  "voice_selection": {
    "voice_type": "zh_male_jieshuoxiaoming_moon_bigtts",
    "speed_ratio": 1.1,
    "voice_mode": "single"
  },
  "music_selection": {
    "music_source": "online",
    "music_style_id": "upbeat",
    "music_query": "轻快、干净、适合短视频的纯音乐背景，无人声",
    "music_filename": "",
    "music_volume": 0.12
  },
  "video_engine_selection": {
    "video_engine": "seedance-fast",
    "reason": "选择原因"
  },
  "reference_design": {
    "reference_type": "character",
    "style_reference": {
      "style_anchor_id": "main_style",
      "fixed_style_traits": ["统一色彩、光线、质感和构图语言"],
      "allowed_style_variations": ["景别、光比、天气和局部道具状态可随剧情变化"]
    },
    "characters": [
      {
        "character_id": "char_001",
        "character_name": "角色名",
        "character_description": "角色描述",
        "identity_anchor": "一句话角色身份证",
        "fixed_traits": ["跨分镜不可改变的角色特征"],
        "allowed_variations": ["表情、动作、姿态等可变项"],
        "image_prompt_chinese": "中文角色 prompt",
        "image_prompt_english": "英文角色 prompt"
      }
    ]
  },
  "consistency_contract": {
    "long_chain_ready": true,
    "style_anchor_id": "main_style",
    "fixed_style_traits": [],
    "allowed_style_variations": [],
    "characters": [],
    "continuity_groups": [],
    "chapters": []
  }
}
```

## scene 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `index` | int | 是 | 场景序号，从 1 开始 |
| `chapter_id` | string | 是 | 章节 ID；单段视频也使用 `chapter_01` |
| `continuity_group` | string | 是 | 连续性组，同一动作/场景/人物状态的分镜共享 |
| `description` / `scene_description` | string | 是 | 场景描述 |
| `narration` | string | 否 | TTS 文本 |
| `subtitle_text` | string | 否 | 字幕文本 |
| `image_prompt` / `image_prompt_chinese` | string | 是 | 场景图 prompt |
| `video_prompt` / `video_prompt_chinese` / `video_prompt_english` | string | 是 | 视频动作 prompt |
| `duration` | float | 是 | 拼接裁剪和旁白预估时长 |
| `video_generation_type` | string | 否 | 完整视频工作流使用 `image_to_video` |
| `needs_reference` | bool | 否 | 是否使用角色/风格参考图 |
| `reference_type` | string | 否 | `character`、`style`、`object` 或 `none` |
| `reference_ids` | list[string] | 否 | 引用的参考角色 ID，如 `char_001` |
| `character_ids` | list[string] | 否 | 本分镜预计出现的角色 ID |
| `style_anchor` | string | 否 | 风格锚点 ID，默认 `main_style` |
| `use_style_reference` | bool | 否 | 是否使用统一风格参考，默认 true |
| `continuity_notes` | string | 否 | 本分镜必须保持的人物、服装、道具、环境状态 |
| `is_sub_scene` | bool | 否 | 是否由长旁白拆分 |
| `sub_scene_index` | int | 否 | 子分镜序号 |
| `parent_description` | string | 否 | 父分镜描述 |

## 约束

- 完整视频工作流只生成普通 `image_to_video` 分镜。
- 单工具 `UniversalVideoGenerationTool` 可单独做 `text_to_video`，但这不属于完整工作流分镜 schema。
- 分镜旁白较长时，用 `|` 标记画面切换点，让后续步骤拆分或调整节奏。
- 默认单次目标时长不超过 180 秒，但 schema 支持长逻辑链路：用 `chapter_id`、`continuity_group`、`style_anchor` 和 `consistency_contract` 让多章节、多批次或系列化内容复用同一人物和画风设定。
- 自动拆分出的子分镜必须继承父分镜的 `chapter_id`、`continuity_group`、`character_ids`、`style_anchor`、`reference_ids` 和 `continuity_notes`。
