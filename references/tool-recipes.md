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

## Official MiniMax H3 high-resolution video

H3 V2 currently generates only `2K`, so Capsule Cinema keeps the normal
complete-video default on Seedance `720p` and uses this route only when high
resolution is explicit.

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool MiniMaxH3VideoGeneratorTool \
  --params '{"prompt":"雨后街道上的人物自然回头，镜头缓慢推进，无文字","generation_type":"image_to_video","image_path":"output/manual/work/images/scene.png","aspect_ratio":"9:16","resolution":"2K","duration":5,"output_path":"output/manual/work/videos/h3-scene.mp4"}'
```

For a complete-video run, either describe an explicit 2K/high-resolution
requirement or force the runtime engine:

```bash
python "$VIDEO_WRAPPER_ROOT/run_video.py" \
  --user_requirements "制作一条 2K 高分辨率竖屏短视频" \
  --video_engine minimax-h3 \
  --aspect_ratio 9:16
```

Use `generation_type=first_last_frame` with `first_frame_path` and
`last_frame_path`. Use `generation_type=multimodal` with up to 9
`image_paths`, 3 `video_paths`, and 3 `audio_paths`; audio cannot be the only
reference. Text-to-video requires a concrete ratio, while first/last-frame
image-to-video is always adaptive. Configure `MINIMAX_API_KEY` locally; do not
paste the key into the command.

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

## RunningHub MiniMax H3 FL2VA first/last-frame example

This public RunningHub AI App uses workflow `2084086089706459137`. The
published workflow advertises 832×480 and 5 seconds and may take about ten
minutes; RunningHub may normalize the actual output dimensions and include
native audio, so inspect the returned local file. `ratio_select=3` is the
ratio value shown in the provider example.

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool RunningHubMiniMaxH3VideoGeneratorTool \
  --params '{"first_frame_path":"input/start.png","last_frame_path":"input/end.png","duration_seconds":5,"ratio_select":"3","prompt":"0-2s: medium wide shot, the boy raises his hand; 2-5s: camera steadily pushes to a facial close-up, clothes and hair sway softly","output_path":"output/manual/work/videos/runninghub-h3.mp4"}'
```

Set `RUNNINGHUB_API_KEY` locally. The tool uploads local images through the
RunningHub binary-media endpoint, polls `/openapi/v2/query`, and downloads the
result before returning; it never returns the expiring remote result URL.

## RunningHub MiniMax H3 multi-image reference example

This workflow is `2084192196529582081`. It accepts up to three reference
images. The documented example uses `832×480`, `16:9`, and 10 seconds; the
workflow requires a 6000D-capable instance and may take substantially longer
than the first/last-frame app.

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool RunningHubMiniMaxH3MultiReferenceVideoGeneratorTool \
  --params '{"image_paths":["input/subject.png","input/style.png","input/product.png"],"prompt":"保持参考图主体一致，镜头缓慢推进，衣物自然摆动，无文字","aspect_ratio":"16:9","width":832,"height":480,"duration_seconds":10,"output_path":"output/manual/work/videos/runninghub-h3-multi.mp4"}'
```

## RunningHub MiniMax H3 text-to-video example

This workflow is `2084109189609246721`. It does not use reference images.
The documented example uses `832×480`, `16:9`, and 5 seconds.

```bash
python "$VIDEO_WRAPPER_ROOT/run_tool.py" \
  --tool RunningHubMiniMaxH3TextToVideoGeneratorTool \
  --params '{"prompt":"复古红色汽车在午后公路上缓慢前进，电影感胶片颗粒，镜头平稳向前推进，无文字","aspect_ratio":"16:9","width":832,"height":480,"duration_seconds":5,"output_path":"output/manual/work/videos/runninghub-h3-text.mp4"}'
```
