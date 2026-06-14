# Tool Recipes

Run all commands from the repo root; wrappers live in `scripts/` and the tool library in `lib/`.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$PROJECT_ROOT"
VIDEO_ARTIFACT_ROOT="${VIDEO_ARTIFACT_ROOT:-$PROJECT_ROOT/output}"
RUN_ROOT="${RUN_ROOT:-$VIDEO_ARTIFACT_ROOT/production_$(date +%Y%m%d_%H%M%S)_topic}"
```

## Single Tool Wrapper

Wrapper call:

```bash
python "scripts/run_tool.py" \
  --tool "GptImage2Tool" \
  --params '{"prompt":"...","aspect_ratio":"9:16"}'
```

Outside a managed session, include an absolute output path when the tool schema requires it.

## Image Generation

Juling GPT Image 2:

```bash
python "scripts/run_tool.py" \
  --tool "GptImage2Tool" \
  --params '{"prompt":"realistic vertical scene...","aspect_ratio":"9:16"}'
```

Juling Seedream5:

```bash
python "scripts/run_tool.py" \
  --tool "Seedream5ImageGeneratorTool" \
  --params '{"prompt":"中文场景描述，竖屏构图，干净自然","aspect_ratio":"9:16"}'
```

With reference:

```json
{
  "prompt": "保持参考人物外观，生成新的室内中景...",
  "aspect_ratio": "9:16",
  "reference_image_paths": ["/abs/ref.png"]
}
```

## Video Generation

Seedance Fast image-to-video:

```bash
python "scripts/run_tool.py" \
  --tool "SeedanceFastVideoGeneratorTool" \
  --params '{"generation_type":"image_to_video","image_path":"/abs/s01.png","prompt":"subject begins moving...","aspect_ratio":"9:16","duration":"10s"}'
```

Seedance Fast timeline:

```json
{
  "generation_type": "image_to_video",
  "image_path": "/abs/s01.png",
  "aspect_ratio": "9:16",
  "duration": "15s",
  "prompt": "[00:00 - 00:04] CU: subject notices the object\n[00:04 - 00:10] MS: subject opens it slowly\n[00:10 - 00:15] ECU: emotional reaction, camera pushes in"
}
```

Seedance 1.5 Pro through `Jimeng35ProVideoGeneratorTool`:

```bash
python "scripts/run_tool.py" \
  --tool "Jimeng35ProVideoGeneratorTool" \
  --params '{"generation_type":"image_to_video","image_path":"/abs/s01.png","prompt":"语音要求：强制中文普通话。角色开口说中文，嘴型自然...","aspect_ratio":"9:16","size":"720P","duration":"10s","auto_language_check":true}'
```

Seedance Fast:

```bash
python "scripts/run_tool.py" \
  --tool "SeedanceFastVideoGeneratorTool" \
  --params '{"generation_type":"image_to_video","image_path":"/abs/s01.png","prompt":"...","aspect_ratio":"9:16"}'
```

## TTS

MiniMax:

```bash
python "scripts/run_tool.py" \
  --tool "TextToSpeechTool" \
  --params '{"text":"旁白文本","voice_id":"female-chengshu-jingpin","speed":1.2,"vol":2.2}'
```

Doubao:

```bash
python "scripts/run_tool.py" \
  --tool "DoubaoTTSTool" \
  --params '{"text":"旁白文本","voice_type":"science_female","speed_ratio":1.2,"encoding":"mp3"}'
```

Use MiniMax `voice_id`, not `voice_type`. Use Doubao `voice_type`, not `voice_id`.

## Generated Music / BGM

Full runs resolve BGM in this order: explicit local `bgm_path`, explicit `music_url`/`audio_url`, Jamendo licensed-search download when `JAMENDO_CLIENT_ID` is configured, Internet Archive Creative Commons/public-domain search download, then Suno generation. Do not use a local music library or scrape arbitrary web pages.

Suno via the universal music wrapper:

```bash
python "scripts/run_tool.py" \
  --tool "suno" \
  --params '{"provider":"suno","mode":"inspiration","description":"30 seconds of warm, minimal instrumental background music for a calm Chinese product explainer","make_instrumental":true,"output_dir":"'"$RUN_ROOT"'/music/suno_bgm"}'
```

For managed sessions, `run_tool.py` injects a local Suno output directory when `SESSION_OUTPUT_DIR` is set. Prefer local downloaded audio paths in plans, manifests, capsules, and reports; do not persist remote Suno URLs.

## RunningHub Action Transfer

Some managed runtimes provide a dedicated action-transfer wrapper. Check that it exists before using it:

```bash
test -f "scripts/run_action_transfer.py" && \
  python "scripts/run_action_transfer.py" \
    --video_path "/abs/reference_dance.mp4" \
    --character "角色描述" \
    --mode multi
```

Portable route through the generic tool wrapper:

```bash
python "scripts/run_tool.py" \
  --tool "ActionImitateTool" \
  --params '{"image_path":"/abs/character.png","video_path":"/abs/ref.mp4","output_path":"'"$RUN_ROOT"'/videos/action_transfer.mp4","output_dir":"'"$RUN_ROOT"'/intermediates/action_transfer","engine":"animate2","chunk_duration":8}'
```

## RunningHub Lip Sync

Mute source first if it has generated audio:

```bash
ffmpeg -y -i source.mp4 -af volume=0 -c:v copy -c:a aac muted.mp4
```

Then:

```bash
python "scripts/run_tool.py" \
  --tool "InfiniteTalkV2VAPI" \
  --params '{"video_path":"/abs/muted.mp4","audio_path":"/abs/tts.mp3","width":576,"height":1024,"instance_type":"plus"}'
```

## RunningHub Super-Resolution

```bash
python "scripts/run_tool.py" \
  --tool "VideoSuperResTool" \
  --params '{"video_path":"/abs/input.mp4","max_resolution":1920,"instance_type":"plus"}'
```

Choose `max_resolution` from the input's long edge, not from the desired short edge. For example, a `704x1248` vertical source must use at least `1248`; use `1920` or higher when the goal is actual upscaling. The wrapper rejects smaller values by default unless `allow_downscale=true`.

Immediately compare source and result:

```bash
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height \
  -of json /abs/input.mp4
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height \
  -of json /abs/superres-output.mp4
```

If narration exists, the enhanced file is not final until its duration matches the narration/audio master. If the enhancement changed timing, use the enhanced video stream only and reattach the original approved audio, or block delivery and rerender.

## Batch Plan Skeleton

There is no portable executor wrapper in every checkout. Use this JSON shape for planning, capsule records, or managed runtimes that explicitly provide `run_executor.py`; otherwise execute scene steps with `run_tool.py` and assemble with the available runtime scripts.

Use only approved tools in scene steps:

```json
{
  "title": "视频标题",
  "aspect_ratio": "9:16",
  "assembly": {
    "tts": true,
    "tts_provider": "minimax",
    "tts_voice": "female-chengshu-jingpin",
    "tts_speed": 1.2,
    "tts_volume": 2.2,
    "voice_volume": 1.5,
    "bgm": "/abs/local_bgm.mp3",
    "bgm_volume": 0.08,
    "subtitle": true,
    "copywriting": true
  },
  "scenes": [
    {
      "id": "s01",
      "description": "开场钩子",
      "narration": "第一句旁白。",
      "steps": [
        {
          "tool": "GptImage2Tool",
          "params": {
            "prompt": "竖屏真实摄影场景...",
            "aspect_ratio": "9:16"
          },
          "output_key": "image"
        },
        {
          "tool": "SeedanceFastVideoGeneratorTool",
          "params": {
            "generation_type": "image_to_video",
            "image_path": "{{s01.0.output}}",
            "prompt": "subject action first, then camera...",
            "aspect_ratio": "9:16",
            "duration": "5s"
          },
          "output_key": "video"
        }
      ]
    }
  ]
}
```

Run:

```bash
if [ -f "scripts/run_executor.py" ]; then
  python "scripts/run_executor.py" \
    --plan /abs/production_plan.json \
    --output_dir "$SESSION_OUTPUT_DIR"
else
  echo "run_executor.py not found; run scene steps through run_tool.py or run_video.py"
fi
```
