# Public Tool Recipes

Set `VIDEO_WRAPPER_ROOT` to this repository's `scripts/` directory and keep all
outputs under the run workspace.

## Official Volcengine image

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool VolcengineImageGeneratorTool \
  --params '{"prompt":"cinematic product close-up, clean background","size":"2K","output_format":"png","watermark":false,"output_path":"output/manual/work/images/scene.png"}'
```

## Official Volcengine video

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool Seedance20VideoGeneratorTool \
  --params '{"prompt":"slow camera push-in, subtle natural motion","generation_type":"image_to_video","image_path":"output/manual/work/images/scene.png","ratio":"9:16","resolution":"720p","duration":5,"generate_audio":true,"return_last_frame":true,"output_path":"output/manual/work/videos/scene.mp4"}'
```

For first/last-frame generation, use `generation_type=first_last_frame` with
`first_frame_path` and `last_frame_path`. For multimodal reference generation,
use `generation_type=multimodal` plus up to 9 `image_paths`, 3 `video_paths`,
and 3 `audio_paths`. Audio cannot be supplied without an image or video.

## Official Agnes free-tier image

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool AgnesImageGeneratorTool \
  --params '{"prompt":"雨后的上海弄堂，电影感自然光，无文字","aspect_ratio":"9:16","size":"1K","output_path":"output/manual/work/images/agnes-scene.png"}'
```

## Official Agnes free-tier short text-to-video

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool AgnesVideoGeneratorTool \
  --params '{"prompt":"雨后弄堂里一只橘猫自然向前走，镜头缓慢推进，无文字","generation_type":"text_to_video","aspect_ratio":"9:16","num_frames":41,"frame_rate":24,"preserve_native_audio":false,"output_path":"output/manual/work/videos/agnes-scene.mp4"}'
```

Use a user-owned `AGNES_API_KEY`; never share one through the repository. The
[Agnes API platform](https://platform.agnes-ai.com/) provides registration and
dashboard key creation. The provider FAQ currently says core models are free
indefinitely, with no published end date, but free/default access is
rate-limited: effective image limits are about 20 RPM at 1K, 10 RPM at 2K, and
1 RPM at 3K/4K; video is about 1 RPM. The provider does not publicly specify a
free daily video-seconds quota, and free access has no production SLA. See the
[FAQ](https://wiki.agnes-ai.com/en/docs/faqs.md) and
[limits](https://wiki.agnes-ai.com/en/docs/tokenplan.md). Returned image/video
dimensions may differ from requested dimensions, so run image inspection and
`ffprobe`. The public Agnes video adapter does not claim image-to-video or
long-duration generation.

## Official MiniMax TTS

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool UniversalTTSTool \
  --params '{"text":"旁白文本","provider":"minimax","voice_type":"male_narrator","output_path":"output/manual/work/audios/narration.mp3","speed":1.1}'
```

## Official Doubao Speech

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool DoubaoTTSTool \
  --params '{"text":"旁白文本","speaker":"zh_female_gaolengyujie_uranus_bigtts","output_path":"output/manual/work/audios/narration.mp3","speed_ratio":1.1,"enable_subtitle":true}'
```

The equivalent universal route is `provider=doubao`. This is the only Doubao
route exposed by the project and is selected by default when
`DOUBAO_TTS_API_KEY` is available.

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
