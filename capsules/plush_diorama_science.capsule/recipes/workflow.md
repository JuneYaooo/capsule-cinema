---
type: Video Recipe
title: 生产流程
description: 一期片子从拿到题目到交付的完整工序：每一步用套件里的哪个脚本、产出什么、过什么关；什么时候必须停下来让人确认。
stage: generation
domain: workflow
profile: video.okf.capsule.v1
tags:
- workflow
- procedural-kit
- qa
---

# 生产流程

这个胶囊走的是**纯代码专用路线**：画面用 Blender 程序化渲染，声音用 TTS + 程序合成，字用 PIL 叠。不调用图生视频、文生视频，也不能用通用生成路线冒充成片。全部脚本在胶囊 `assets/kit/` 里，使用说明在 `assets/kit/README.md`。

## 工序

1. **建工程**：给本期建一个工程目录（不放在胶囊里）。把套件脚本拷进 `work/`，模板 `episode.py`、`cues.py` 拷进 `work/`，`shots.py` 拷进 `work/scene3d/`，两个字体拷进 `fonts/`。
2. **文案**（copy）：提取参考口播、核实事实、写台本、字幕段、高亮词、标题、章节牌、标签、发布文案；同时写分镜表（structure）。
   **停：整套文案 + 分镜表给用户确认。**
3. **配音**（audio）：`tts_takes.py` 每句 3 个 take → `asr_pick.py` 挑 take → 有疑问的词用 `asr_force.py` 判定。
4. **时间线**：`timeline.py` 生成全片唯一的时间表；`qa.py subs` 看字幕吸附。
5. **镜头**（structure / visual / motion）：照分镜表从原型改写 `shots.py`，动作全部挂关键词事件。
6. **预览**：`render_all.py --preview`，`qa.py safe` 看安全区，调 `SHIFT_Y` 和道具位置，直到主体都在 400–1290 px 之间。
7. **标签投影**：`project_labels.py`。
8. **正片渲染**：`render_all.py --jobs 2`（约每帧 2 秒）。`qa.py contact` 看整片联系表，快动作镜头 `qa.py frames` 逐帧查。
9. **音乐**：`bgm_fit.py --survey` 挑曲，`bgm_fit.py <曲名>` 测调、找接缝，结果抄进 `episode.py`，戴耳机听接缝。
10. **音效与混音**：写 `cues.py`（时间照抄 `shots.py`），`mix.py` 出 −14 LUFS 的混音。
11. **叠字与编码**：`overlay.py --frames` 抽几帧检查字幕、高亮、章节牌、标签，再 `overlay.py` 全片合成并编码；`cover.py` 出封面。
12. **验收**：`qa.py probe` 全部通过；`asr_final.py` 两个模型全片转写对照台本，有差异的句子逐条试听。
13. **交付**：成片、封面、发布文案、改掉的事实清单、QA 报告（probe 输出 + 听写结果 + 联系表）。

## 返工的代价

改动越往上游，重做的越多。按代价从低到高：

- 改字幕、章节牌、标签文字 → 只重跑叠字和编码（几分钟）。
- 改音效、BGM → 只重跑混音和编码。
- 改某个镜头的动画或构图 → 重渲那一个镜头（几分钟到十几分钟）+ 叠字编码；有标签就重跑标签投影。
- 改台本 → 重新配音、挑 take、排时间线，所有镜头时长都会变，正片要全部重渲。**所以文案必须在配音前确认。**

## 确认点

- 文案 + 分镜表：配音之前必须确认。
- 预览联系表：正片渲染之前，最好给用户看一眼构图和角色。
- 成片：交付时说明哪些地方需要用户自己听（接缝、个别读音）。
