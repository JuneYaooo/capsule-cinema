# 视频制作经验

当前可复用配方沉淀到 `capsules/<name>.capsule/` 目录包；SQLite 只作为历史证据、反馈记录和显式 fallback。

## 通用建议

| 项目 | 建议 |
|------|------|
| 竖屏短视频 | `9:16`，适合抖音、快手、小红书 |
| 横屏视频 | `16:9`，适合 B 站、YouTube |
| 默认图片引擎 | `gpt-image-2`（Krill AI 渠道） |
| 默认视频引擎 | `seedance-fast` |
| 高画质/电影感 | `veo3` |
| 首尾帧转场 | `veo3.1` |
| image_prompt | 推荐中文；不要要求图片生成文字、标题、字幕 |
| video_prompt | `seedance-fast`/`jimeng35pro`/`veo3`/`veo3.1` 可中文 |
| 分镜类型 | 完整视频工作流只要求普通 `image_to_video` 分镜 |
| 分镜时长 | 根据旁白预估：`中文字数 ÷ 4 + 0.5`，长旁白用 `|` 拆分画面 |
| 视频片段长度 | `veo3`、`veo3.1` 约 8 秒；`jimeng35pro` 默认 5 秒，可按渠道支持选择 10/12 秒 |
| 单次成片时长 | 默认不超过 180 秒；更长内容按章节/系列拆分制作 |
| 长逻辑链路 | 用 `chapter_id`、`continuity_group`、`style_anchor` 和角色 `identity_anchor` 维持跨分镜一致性 |
| 字幕 | 用后期字幕工具叠加，不在图片 prompt 里生成 |
| BGM | 默认先用用户音频 URL/Jamendo/Internet Archive 授权音乐源在线搜索下载；不可用时用 `UniversalMusicGenerationTool` 在线生成；仅在用户明确提供时使用 `bgm_path` |
| BGM 音量 | 有配音时 0.08-0.18，无配音时 0.3-0.5 |
| 配音音量 | 默认 1.5，确保人声清晰 |
| 语言检测 | `jimeng35pro` 需要中文语音时，用 `scripts/run_language_check.py` 检测 |

## 质量规则

- 主体必须具体，不要只写“妈妈”“孩子”；动物场景要写“狗妈妈”“小金毛”等。
- 画面描述优先写主体动作和状态，少写空泛镜头运动。
- 每个分镜只保留一个清晰焦点，避免无关装饰元素堆砌。
- 禁止在图片 prompt 中写文字、标题、logo、字幕。
- `veo3` prompt 避免强刺激审核词；失败时改用更中性的动作和情绪描述。
- `veo3.1` 首尾帧视频要先保证首尾两张图比例、主体和构图稳定一致。

## 长链路一致性

- 先锁角色，再扩分镜：为重复出现的人物/动物/产品生成参考图，写清 `identity_anchor` 和 `fixed_traits`。
- 先锁画风，再批量生成：`style_reference` 和 `visual_style` 是全片默认锚点，不要在单个分镜里随意改写实/卡通/水彩等大风格。
- 同一 `continuity_group` 中只改变动作阶段、表情、景别和镜头角度，不改变服装主色、关键配饰、物种、毛色、道具状态。
- 长剧情先按 `chapter_id` 拆成章节，每章内部再拆 3-8 秒分镜；章节之间复用同一 `consistency_contract`。
- 每批生成后先检查角色脸/毛色/服装、画风、比例和关键道具，再继续下一批。发现漂移时优先重生成场景图，不要直接进入视频生成。

## 胶囊使用

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/capsule_store.py list
PYTHONPATH=lib python3.12 scripts/capsule_store.py show <name> --json
PYTHONPATH=lib python3.12 scripts/capsule_store.py add-feedback --name <name> --summary "问题摘要" --fix "修正方法"
```
