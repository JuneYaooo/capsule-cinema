# Public Tool Recipes

Set `VIDEO_WRAPPER_ROOT` to this repository's `scripts/` directory and keep all
outputs under the run workspace.

## Official Volcengine image

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool VolcengineImageGeneratorTool \
  --params '{"prompt":"cinematic product close-up, clean background","aspect_ratio":"9:16","output_path":"output/manual/work/images/scene.png"}'
```

## Official Volcengine video

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool Seedance20VideoGeneratorTool \
  --params '{"prompt":"slow camera push-in, subtle natural motion","generation_type":"image_to_video","image_path":"output/manual/work/images/scene.png","aspect_ratio":"9:16","duration":5,"output_path":"output/manual/work/videos/scene.mp4"}'
```

## Official MiniMax TTS

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool UniversalTTSTool \
  --params '{"text":"旁白文本","provider":"minimax","voice_type":"male_narrator","output_path":"output/manual/work/audios/narration.mp3","speed":1.1}'
```

## Official Doubao TTS

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool UniversalTTSTool \
  --params '{"text":"旁白文本","provider":"doubao","voice_type":"science_female","output_path":"output/manual/work/audios/narration.mp3","speed":1.1}'
```

## RunningHub action-transfer example

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool ActionImitateTool \
  --params '{"reference_image_path":"input/character.png","reference_video_path":"input/action.mp4","output_dir":"output/manual/work/action"}'
```

## RunningHub lip-sync example

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool InfiniteTalkV2VTool \
  --params '{"video_path":"input/portrait.mp4","audio_path":"output/manual/work/audios/narration.mp3","output_dir":"output/manual/work/lip_sync"}'
```

Never paste credentials into commands. Remote result URLs must be downloaded
and represented by local artifact paths.
