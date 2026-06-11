# Custom Tools

当前打包的工具目录：

```text
custom_tools/
├── audio_generation/      # 豆包 TTS、批量 TTS、音频转写辅助
├── image_generation/      # seedream5、gemini3_pro、参考图、封面图
├── music_generation/      # Suno/通用音乐生成
├── quality_check/         # 图片/视频质量检查、内容审核、Gemini 视频分析
├── utilities/             # 配置读取、网页提取、搜索、文案、音效列表、风格
├── video_generation/      # jimeng35pro、veo3、通用视频包装
└── video_processing/      # 拼接、字幕、时长、帧提取、图片备用视频
```

优先通过 `scripts/run_tool.py` 调用已注册的核心类。新增工具前先补实现、注册表和测试。
