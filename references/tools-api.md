# 工具 API 参考

本页只记录当前包里真实存在并可调用的核心工具。优先通过 `scripts/run_tool.py` 调用，复杂的完整视频生成走 `scripts/run_video.py`。

All generated artifacts must stay under this repository's `output/` directory. For manual examples:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$PROJECT_ROOT"
RUN_ROOT="${RUN_ROOT:-$PROJECT_ROOT/output/manual_tool_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$RUN_ROOT"/work/{images,videos,audios,subtitles,temp} "$RUN_ROOT"/release "$RUN_ROOT"/qa
```

## 脚本入口

### 完整视频 / 仅分镜

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --user_requirements "一只橘猫做饭的搞笑短视频" \
  --target_duration 30 \
  --aspect_ratio "9:16" \
  --video_engine seedance-fast
```

仅分镜加 `--storyboard_only`。

按本地 SQLite 胶囊注入合同：

```bash
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --capsule healing_asmr_food_daily_v1 \
  --user_requirements "一只橘猫低头吃小鱼干，真实治愈 ASMR" \
  --storyboard_only
```

专用动作、口播同步和音乐 MV 类型胶囊需要各自的专用路线。`run_video.py --capsule` 默认不会把它们退回普通图生视频完整成片，以免假冒跑通；可用 `--storyboard_only` 做分镜预检，或显式传 `--allow_generic_capsule_fallback` 生成非最终预览。

### 单分镜重生成

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_scene.py \
  --workspace_dir "$PROJECT_ROOT/output/<run_id>" \
  --scene_id 2 \
  --image_prompt "新的图片 prompt" \
  --video_prompt "新的视频 prompt" \
  --image_engine seedream5 \
  --video_engine seedance-fast
```

只重生成视频可加 `--skip_image`，此时脚本会复用 storyboard 中已有的 `image_path`。

### 重新拼接

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_concat.py --workspace_dir "$PROJECT_ROOT/output/<run_id>"
```

### 语言检测

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_language_check.py \
  --video_path /path/to/scene.mp4 \
  --expected_language zh
```

### EditPlan / 修复计划 / 发布检查点

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/build_edit_plan.py \
  --workspace output/<run_id>

PYTHONPATH=lib python3.12 scripts/validate_edit_plan.py \
  --workspace output/<run_id>

PYTHONPATH=lib python3.12 scripts/plan_repairs.py \
  --workspace output/<run_id>

PYTHONPATH=lib python3.12 scripts/release_checkpoint.py \
  --workspace output/<run_id>
```

## run_tool 支持的类名

`scripts/run_tool.py` 当前注册了这些工具：

| 类型 | 工具类 |
|------|--------|
| 图片 | `Seedream5ImageGeneratorTool`, `GptImage2Tool`, `Gemini3ProImageGeneratorTool`（手动/显式批准时使用） |
| 视频 | `SeedanceFastVideoGeneratorTool`, `SeedanceVideoGeneratorTool`, `Jimeng35ProVideoGeneratorTool`, `Veo3VideoGeneratorTool`, `GenerateVideoFromTextTool`, `GenerateVideoFromImageTool`, `UniversalVideoGenerationTool` |
| RunningHub Motion | `ActionImitateTool`, `WanMultiPersonActionImitateTool` |
| RunningHub Lip Sync | `LTX23LipSyncTool`, `InfiniteTalkV2VTool` |
| TTS | `UniversalTTSTool`, `UniversalTTSBatchTool` |
| 拼接/BGM | `ConcatenateVideosTool`, `AddBackgroundMusicTool` |
| 字幕 | `VideoSubtitleTool`, `AdaptiveSubtitleProcessor` |
| 音乐 | `UniversalMusicGenerationTool` |
| 文案 | `SocialMediaCopywritingTool` |
| 质检/分析 | `VideoQualityCheckerTool`, `GeminiVideoAnalyzerTool`, `Gemini3VideoAnalyzerTool` |

## 图片生成

Seedream5：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool Seedream5ImageGeneratorTool \
  --params '{"prompt":"一只橘猫在厨房做饭，写实风格","output_path":"'"$RUN_ROOT"'/work/images/cat.jpg","aspect_ratio":"9:16"}'
```

Gemini 3 Pro：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool Gemini3ProImageGeneratorTool \
  --params '{"prompt":"A chubby orange cat cooking in a kitchen","output_path":"'"$RUN_ROOT"'/work/images/cat.png","aspect_ratio":"9:16"}'
```

## 视频生成

通用单工具：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool UniversalVideoGenerationTool \
  --params '{"prompt":"一只橘猫翻炒锅里的菜","generation_type":"text_to_video","output_dir":"'"$RUN_ROOT"'/work/videos","engine":"seedance-fast","aspect_ratio":"9:16"}'
```

图生视频：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool UniversalVideoGenerationTool \
  --params '{"prompt":"橘猫快速翻炒锅里的菜，动作夸张有趣","generation_type":"image_to_video","image_path":"'"$RUN_ROOT"'/work/images/cat.jpg","output_dir":"'"$RUN_ROOT"'/work/videos","engine":"seedance-fast","aspect_ratio":"9:16"}'
```

Seedance Fast image-to-video：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool SeedanceFastVideoGeneratorTool \
  --params '{"prompt":"橘猫低头吃饭，尾巴轻摆，镜头轻微推进","generation_type":"image_to_video","image_path":"'"$RUN_ROOT"'/work/images/cat.jpg","output_path":"'"$RUN_ROOT"'/work/videos/cat_sd_fast.mp4","aspect_ratio":"9:16","size":"720P","duration":"10s"}'
```

也可以在完整流程中传 `--video_engine seedance-fast`。

## RunningHub Motion

Single-person motion transfer:

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool ActionImitateTool \
  --params '{"image_path":"'"$RUN_ROOT"'/work/images/character.png","video_path":"'"$RUN_ROOT"'/work/videos/reference_dance.mp4","output_path":"'"$RUN_ROOT"'/work/videos/action_transfer.mp4","engine":"animate2","chunk_duration":8,"width":1080,"height":1920,"instance_type":"plus"}'
```

Multi-person motion transfer:

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool WanMultiPersonActionImitateTool \
  --params '{"image_path":"'"$RUN_ROOT"'/work/images/characters.png","video_path":"'"$RUN_ROOT"'/work/videos/reference_dance.mp4","output_path":"'"$RUN_ROOT"'/work/videos/multi_action.mp4","instance_type":"plus","width":576,"height":1024}'
```

## RunningHub Lip Sync

Image + audio:

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool LTX23LipSyncTool \
  --params '{"image_path":"'"$RUN_ROOT"'/work/images/avatar.png","audio_path":"'"$RUN_ROOT"'/work/audios/voice.mp3","output_path":"'"$RUN_ROOT"'/work/videos/lipsync.mp4","action_prompt":"角色面对镜头自然说话，轻微推拉运镜","resolution":1280,"frame_rate":30,"instance_type":"plus"}'
```

Video + audio:

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool InfiniteTalkV2VTool \
  --params '{"video_path":"'"$RUN_ROOT"'/work/videos/source.mp4","audio_path":"'"$RUN_ROOT"'/work/audios/voice.mp3","output_path":"'"$RUN_ROOT"'/work/videos/v2v_lipsync.mp4","width":576,"height":1024,"instance_type":"plus"}'
```

## TTS

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool UniversalTTSTool \
  --params '{"text":"大家好，今天这只橘猫要挑战三分钟做晚饭。","output_path":"'"$RUN_ROOT"'/work/audios/voice.mp3","provider":"doubao","voice_type":"zh_male_jieshuoxiaoming_moon_bigtts","speed":1.1}'
```

## 视频拼接

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool ConcatenateVideosTool \
  --params '{"video_paths":["'"$RUN_ROOT"'/work/videos/a.mp4","'"$RUN_ROOT"'/work/videos/b.mp4"],"output_path":"'"$RUN_ROOT"'/release/final.mp4","voice_volume":1.5}'
```

## 字幕

SRT 字幕：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool VideoSubtitleTool \
  --params '{"video_path":"'"$RUN_ROOT"'/release/final.mp4","subtitle_path":"'"$RUN_ROOT"'/work/subtitles/subtitle.srt","output_path":"'"$RUN_ROOT"'/release/subtitled.mp4","font_size":24}'
```

文本自适应字幕：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool AdaptiveSubtitleProcessor \
  --params '{"video_path":"'"$RUN_ROOT"'/release/final.mp4","subtitle_text":"橘猫开火，厨房马上热闹起来。","output_path":"'"$RUN_ROOT"'/release/subtitled.mp4","position":"bottom","language":"zh"}'
```

## BGM 和音乐

完整流程的 BGM 选择顺序：用户显式提供的本地 `bgm_path`、用户/胶囊显式提供的 `music_url`/`audio_url`、配置 `JAMENDO_CLIENT_ID` 后的 Jamendo 授权音乐搜索下载、Internet Archive Creative Commons/public-domain 搜索下载、Suno 在线生成。不会读取本地音乐库。

生成在线 BGM：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool UniversalMusicGenerationTool \
  --params '{"description":"轻松愉快的美食短视频纯音乐","provider":"suno","output_dir":"'"$RUN_ROOT"'/work/audios/music","make_instrumental":true}'
```

把已生成或用户手动提供的音频混入视频：

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool AddBackgroundMusicTool \
  --params '{"video_path":"'"$RUN_ROOT"'/release/final.mp4","music_path":"'"$RUN_ROOT"'/work/audios/music/generated_bgm.mp3","output_path":"'"$RUN_ROOT"'/release/with_bgm.mp4","music_volume":0.12}'
```

## 质量检测和分析

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool VideoQualityCheckerTool \
  --params '{"video_path":"'"$RUN_ROOT"'/release/final.mp4","check_focus":"quality"}'
```

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool GeminiVideoAnalyzerTool \
  --params '{"video_path":"'"$RUN_ROOT"'/release/final.mp4","analysis_focus":"quality"}'
```

本地 rubric 打分：

```bash
PYTHONPATH=lib python3.12 scripts/score_video_quality.py \
  --run-dir "$PROJECT_ROOT/output/<run_id>" \
  --capsule healing_asmr_food_daily_v1 \
  --aspect-ratio "9:16"
```

口播/同步、有字幕/画面文字、有人物配音的路线建议开启 Gemini3 多模态视频审核：

```bash
PYTHONPATH=lib python3.12 scripts/score_video_quality.py \
  --run-dir "$PROJECT_ROOT/output/<run_id>" \
  --capsule digital_human_presenter_v1 \
  --aspect-ratio "9:16" \
  --multimodal-review \
  --multimodal-provider gemini3
```

评分脚本会在标准 run 目录下输出 `qa/local_video_qa.json`、`qa/video_quality_score.json`、`qa/review_contact_sheet.jpg` 和 `qa/multimodal_video_review.json`，并读取已有的 `qa/edit_plan_validation.json` 作为附加 gate。人工发现的问题可写成 JSON 列表传给 `--manual-issues-json`，每项至少包含 `id` 和 `detail`。口播/同步路线发现声音和画面错位、声音继续但画面卡住、嘴不动或人物动作卡顿时，使用 `speech_visual_sync_reviewed` 或 `talking_head_motion_continuity`。字幕/画面文字溢出、裁切、换行异常、乱码、过小或比例不协调时，使用 `subtitle_text_layout`。画面人物性别、年龄感或角色定位与配音声线明显不匹配时，使用 `voice_character_match`。这些问题应标成 `manual_blocker`。如果多模态模型调用失败，评分层会记录 `unavailable`，不会把必审门当作通过。

## SQLite 胶囊

```bash
PYTHONPATH=lib python3.12 scripts/capsule_store.py init
PYTHONPATH=lib python3.12 scripts/capsule_store.py list
PYTHONPATH=lib python3.12 scripts/capsule_store.py doctor --name example --warnings-ok
```

## 调用边界

`run_tool.py` 注册表之外的类不属于当前工具 API。新增工具前先补实现、注册表和测试。
