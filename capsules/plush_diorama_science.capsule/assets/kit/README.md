# 毛绒手办科普 · 制作套件

一期视频的完整生产线，纯本地代码：Blender 程序化建模渲染 + MiniMax 逐句配音 + whisper 对齐验收 + numpy 合成音效 + PIL 叠字 + ffmpeg 编码。
套件只管「怎么做」；「做成什么样、为什么」在胶囊 recipes 里（structure / copy / visual / audio / motion）。

## 开工

给本期建一个工程目录（不要建在胶囊里，下面叫 `<工程>`），布局：

```
<工程>/
  work/                 ← 把 kit/ 里的全部 .py 拷进来；templates/ 里的 episode.py、cues.py 拷到 work/
    scene3d/            ← kit/scene3d/*.py，再把 templates/shots.py 拷到这里
  fonts/                ← 胶囊 assets/fonts/ 里的两个 ttf（字幕、标题、3D 字都从这里读）
  audio/bgm/            ← 选好的 BGM（纯音乐）
```

之后所有产物都落在 `<工程>/` 下：`audio/takes`、`audio/lines`、`audio/mix.wav`、`frames/`、`frames_final/`、`qa/`、`final.mp4`、`cover.jpg`。

环境：Python 3.12（numpy、Pillow、fontTools、pypinyin、python-dotenv、openai-whisper、torch），ffmpeg 7（带 libx264），Blender 5.x（`BLENDER` 环境变量或 PATH）。

## 顺序（每一步都能单独重跑）

| 步 | 命令（在 work/ 里） | 产出 | 看什么 |
|---|---|---|---|
| 1 | 改 `episode.py` 的台本、高亮词、章节牌、标题 | — | 文案先给人确认，确认后才往下 |
| 2 | `python3.12 tts_takes.py --takes 3` | audio/takes | 失败的句子单独 `--only` 重跑 |
| 3 | `python3.12 asr_pick.py` | audio/lines、picks.json | 每句挑出的 take 两个模型 CER 都低 |
| 4 | `python3.12 timeline.py` | timeline.json | 镜头时长 1–4.5 秒；短于 1 秒会警告 |
| 5 | `python3.12 qa.py subs` | — | 吸附差值大的字幕段去听 |
| 6 | 写 `scene3d/shots.py`（从原型改） | — | 每个镜头的关键动作挂在 `kw:` 事件上 |
| 7 | `python3.12 scene3d/render_all.py --preview --jobs 4` | frames/shXX_preview | — |
| 8 | `python3.12 qa.py safe` | qa/safe.jpg | 主体别压红带（标题）蓝带（字幕）；压了就调 SHIFT_Y |
| 9 | `$BLENDER -b --factory-startup -P scene3d/project_labels.py` | labels_px.json | 有标签的镜头改过就重跑 |
| 10 | `python3.12 scene3d/render_all.py --jobs 2` | frames/shXX | 约 2 s/帧，83 秒的片子约 1 小时 |
| 11 | `python3.12 qa.py contact`，快镜头 `qa.py frames shXX` | qa/contact.jpg | 穿模、闪烁、尺寸、连续性 |
| 12 | `python3.12 bgm_fit.py --survey`，再 `bgm_fit.py <曲名>` | bgm_fit.json | 把 BGM_FILE / BGM_KEY / BGM_CUT 抄进 episode.py；戴耳机听接缝 |
| 13 | 写 `cues.py`，`python3.12 mix.py` | audio/mix.wav | −14 LUFS；人声清楚、BGM 不抢 |
| 14 | `python3.12 overlay.py --frames 100,900,1500` | qa/overlay | 字幕、高亮、章节牌、标签位置 |
| 15 | `python3.12 overlay.py --jobs 8` | frames_final、final.mp4 | — |
| 16 | `python3.12 cover.py` | cover.jpg | 封面大字和标题带是同一句 |
| 17 | `python3.12 qa.py probe`，`python3.12 asr_final.py ../final.mp4` | — | 全部通过；全片转写对得上台本 |

## 文件

- `templates/episode.py` 一期的全部文字与参数（台本、字幕段、高亮、镜头起点、章节牌、标签、BGM）。
- `templates/shots.py` 镜头原型库 + 本期镜头映射；`templates/cues.py` 音效表模板。
- `scene3d/lib3d.py` 程序化资产库：布景灯光、毛绒角色、主容器（树、缸）、微观角色、分子、隐喻道具、缓动。
- `scene3d/render_shot.py`、`render_all.py`、`project_labels.py` 渲染与标签投影。
- `tts_takes.py`、`asr_pick.py`、`asr_force.py`、`asr_final.py` 配音与听写验收。
- `timeline.py` 全片唯一的时间来源；`bgm_fit.py` 选曲与剪接；`sfx.py` 音效库；`mix.py` 混音。
- `overlay.py` 叠字与编码；`cover.py` 封面；`qa.py` 检查工具。
