---
name: capsule-cinema
version: 2.0.0
description: "Capsule Cinema 胶囊影厂：按配方生产 AI 短视频的本地工作室。运行时（分镜、图片/视频/TTS、字幕/BGM、质检）+ 制作方法论（路由、渠道政策、钩子审计、产物规范）+ SQLite 胶囊配方仓库"
author: june2
license: MIT

capabilities:
  - id: generate-full-video
    description: "根据一句话需求生成本地短视频：LLM 分镜、图片、视频、TTS、拼接、字幕、BGM 和文案"
  - id: generate-storyboard
    description: "只生成分镜 JSON，不执行图片、视频和音频生成"
  - id: feedback-driven-regeneration
    description: "在已有 workspace 中重生成指定分镜的图片/视频，再用拼接脚本重组"
  - id: generate-image
    description: "使用 gpt-image-2、seedream5 或 gemini3_pro 生成图片"
  - id: generate-video-clip
    description: "使用 seedance-fast、seedance、jimeng35pro、veo3 或 veo3.1 生成单个视频片段"
  - id: generate-tts-audio
    description: "使用 Universal TTS（MiniMax 或豆包 provider）将文本转成语音"
  - id: concatenate-videos
    description: "将多个视频片段和可选配音拼接为一个视频"
  - id: add-subtitles
    description: "为视频烧录字幕，支持普通自适应字幕和 SRT 字幕"
  - id: add-background-music
    description: "默认在线搜索/下载授权 BGM，失败时在线生成原创 BGM 并混入视频；也支持用户手动提供音频路径"
  - id: generate-social-copy
    description: "根据视频内容生成社交平台文案和标签"
  - id: check-video-quality
    description: "检测视频质量、生成本地 QA 报告，并按 rubric 打分"
  - id: build-edit-plan
    description: "从 workspace/storyboard 和本地媒体生成 work/edit_plan.json，作为可审计的时间线中间层"
  - id: validate-edit-plan
    description: "校验 work/edit_plan.json 的本地媒体路径、时间线连续性、场景覆盖和源文件时长，生成 qa/edit_plan_validation.json"
  - id: plan-repairs
    description: "把质量评分中的 blocker/manual review 项转换为 qa/repair_plan.json 修复建议"
  - id: create-release-checkpoint
    description: "汇总 final、manifest、EditPlan、QA、修复计划和审片资产，生成 release/release_checkpoint.json"
  - id: analyze-video-content
    description: "使用 Gemini 视频分析工具分析本地视频"
  - id: detect-video-language
    description: "检测视频语音语言，支持 jimeng35pro 中文语音不符时自动重试"
  - id: manage-local-capsules
    description: "使用本地 SQLite 胶囊仓库安装默认胶囊、注入胶囊合同/资产、记录/查询/更新制作经验，并导入/导出可分享胶囊包"
  - id: generate-music
    description: "使用 Suno 生成原创 BGM"

permissions:
  network: true
  filesystem: true
  shell: true
  env:
    - PYTHON_BIN
    - DOTENV_PATH
    - VIDEO_RESOURCES_PATH
    - OPENCLAW_OUTPUT_DIR
    - JULING_BASE_URL
    - JULING_API_KEY
    - JULING_VEO31_MODEL
    - VEO3_BASE_URL
    - VEO3_API_KEY
    - VEO_ACCESS_TOKEN
    - GEMEINI_IMAGE_MODEL_BASE_URL
    - GEMEINI_IMAGE_MODEL_API_KEY
    - GEMINI_ANALYSIS_API_BASE_URL
    - GEMINI3_API_KEY
    - GEMINI3_BASE_URL
    - GEMINI3_PRO_BASE_URL
    - GEMINI3_PRO_API_KEY
    - VIDEO_ANALYSIS_API_KEY
    - VIDEO_ANALYSIS_BASE_URL
    - CREW_API_KEY
    - CREW_BASE_URL
    - CREW_MODEL_NAME
    - DOUBAO_TTS_APPID
    - DOUBAO_TTS_ACCESS_TOKEN
    - DOUBAO_TTS_SECRET_KEY
    - DOUBAO_TTS_CLUSTER_ID
    - DOUBAO_ARK_API_KEY
    - SUNO_BASE_URL
    - SUNO_API_KEY
    - JAMENDO_CLIENT_ID
    - JAMENDO_API_BASE
    - ONLINE_MUSIC_MAX_MB
    - ONLINE_MUSIC_SEARCH_LIMIT
    - ONLINE_MUSIC_REQUEST_TIMEOUT
    - ONLINE_MUSIC_ENABLE_ARCHIVE
    - INTERNET_ARCHIVE_SEARCH_API
    - INTERNET_ARCHIVE_METADATA_BASE
    - INTERNET_ARCHIVE_DOWNLOAD_BASE
    - RUNNINGHUB_API_KEY
    - WANANIMATE2_API_KEY
    - WANANIMATE2_WEBAPP_ID
    - WAN22_API_KEY
    - WAN22_WEBAPP_ID
    - SILICONFLOW_API_KEY
    - SILICONFLOW_API_BASE
    - MULTIMODAL_API_KEY
    - MULTIMODAL_BASE_URL
    - MODERATION_API_KEY
    - MODERATION_BASE_URL
    - MODERATION_MODEL_NAME
    - OPENAI_BASE_URL
    - OPENAI_API_KEY
    - VIDEO_CAPSULE_DB
    - VIDEO_PRODUCTION_CAPSULE_DB

inputs:
  - name: user_requirements
    type: string
    required: false
    description: "完整视频或仅分镜工作流的视频创作需求，例如：一只橘猫做饭的搞笑短视频"
  - name: workflow
    type: string
    required: false
    default: "auto"
    description: "auto、full-video、storyboard-only、concat 或 feedback"
  - name: target_duration
    type: number
    required: false
    default: 30
    description: "目标时长，单位秒，最大 180"
  - name: aspect_ratio
    type: string
    required: false
    default: "9:16"
    description: "画面比例：9:16、16:9 或 1:1"
  - name: video_engine
    type: string
    required: false
    default: "seedance-fast"
    description: "视频引擎：seedance-fast、seedance、jimeng35pro、veo3 或 veo3.1"
  - name: image_engine
    type: string
    required: false
    default: "seedream5"
    description: "feedback 工作流图片引擎：seedream5、gpt-image-2 或 gemini3_pro"
  - name: bgm_path
    type: string
    required: false
    description: "可选的用户自定义 BGM 音频路径；默认完整流程在线搜索/下载授权 BGM，失败时在线生成原创 BGM"
  - name: capsule
    type: string
    required: false
    description: "可选的本地 SQLite 胶囊名；会注入胶囊合同、默认参数和本地资产"
  - name: capsule_db
    type: string
    required: false
    description: "可选的胶囊 SQLite DB 路径；默认使用 VIDEO_CAPSULE_DB、VIDEO_PRODUCTION_CAPSULE_DB 或用户目录默认 DB"
  - name: allow_generic_capsule_fallback
    type: boolean
    required: false
    default: false
    description: "专用路线胶囊是否允许退回普通图生视频预览；默认禁止"
  - name: workspace_dir
    type: string
    required: false
    description: "已有 workspace 路径；提供后自动进入 feedback 工作流"
  - name: scene_id
    type: number
    required: false
    description: "要重生成的分镜编号，从 1 开始"
  - name: image_prompt
    type: string
    required: false
    description: "feedback 工作流中的新图片 prompt"
  - name: video_prompt
    type: string
    required: false
    description: "feedback 工作流中的新视频 prompt"
  - name: skip_image
    type: boolean
    required: false
    default: false
    description: "feedback 工作流是否跳过图片重生成，只重生成视频"

outputs:
  - name: video_path
    type: string
    description: "最终视频本地路径"
  - name: workspace_dir
    type: string
    description: "工作目录路径"
  - name: storyboard
    type: object
    description: "完整分镜数据"
  - name: storyboard_formatted
    type: object
    description: "适合展示的分镜摘要"
  - name: storyboard_path
    type: string
    description: "storyboard.json 路径"
  - name: cover_image
    type: string
    description: "封面或首张预览图路径"
  - name: preview_images
    type: object
    description: "前几张场景图路径"
  - name: reference_images
    type: object
    description: "角色/风格参考图路径"
  - name: scene_video_paths
    type: object
    description: "前几个分镜视频路径"
  - name: progress_summary
    type: string
    description: "当前产物阶段摘要"
  - name: duration
    type: number
    description: "最终视频时长"
  - name: scene_count
    type: number
    description: "分镜数量"
  - name: engine_used
    type: string
    description: "实际视频引擎"

tags:
  - video-generation
  - ai-video
  - short-video
  - tts
  - local-sqlite
  - capsules
  - content-creation

dependencies:
  skills: []

execution:
  timeout: 600
  longRunning: true

minOpenClawVersion: "2.1.0"
---

## Agent Operating Contract

Before planning or running tools, classify the request and read `references/production-guide.md` before planning for video-production routing. Use the runtime only within the workflows registered in this package.

- Route first: choose post-production, reference remake, capsule, new AI video, action transfer, digital human/lip sync, music MV, or blocker before writing prompts.
- Capsule first: for capsule tasks, inspect the local SQLite capsule contract with `scripts/capsule_store.py show <name> --contract` before planning.
- Policy first: choose tools only after reading the active channel policy and `lib/config/tool_registry.yaml`; never fall back to an unapproved provider.
- Prototype first: for new AI video, generate and inspect one representative hard scene before batching.
- Release first: final deliverables must stay under `output/` and include `artifact_manifest.json`, QA reports, repair plan when needed, and `release/release_checkpoint.json`.
- Blockers are honest output: if route, channel, asset, QA, EditPlan validation, visible copy lint, or release checkpoint blocks delivery, fix it or report it; do not describe the run as complete.

## 当前边界

Capsule Cinema 是一个本地短视频生成 skill：`scripts/` 下的 Python 封装脚本是命令入口（OpenClaw 场景由 `index.js` 调用）。当前能力范围：完整视频、仅分镜、指定分镜重生成、单工具调用、拼接、EditPlan 时间线及校验、release checkpoint、质量修复计划、语言检测、SQLite 胶囊仓库（默认胶囊安装、胶囊合同/资产注入、记录更新、导入导出分享）和本地 QA。超出这些工作流时，不扩展新工作流；只能按现有短视频生成链路处理，无法处理时说明需要额外实现。

## 制作方法论

做视频前先读 `references/production-guide.md`（任务路由、渠道政策、钩子审计、受众审计、产物落盘规范、生产循环）。它会按需路由到其余 references：分镜技巧（storyboard-craft）、制作模式（production-patterns）、命令配方（tool-recipes）、渠道政策与自定义（channel-policy / channel-customization）、胶囊 SQLite（local-capsule-sqlite）、装配质检踩坑（assembly-qc-pitfalls）、审片门（video-review-gate）等。硬性规则（契约、QA 门、注册表）在运行时代码里；方法论指导创作判断。

默认单次成片仍按短视频/中短视频设计，`target_duration` 上限为 180 秒。系统需要支持“长逻辑链路”：当内容包含连续剧情、固定人物、系列章节、教程步骤或产品故事时，必须先建立可复用的一致性契约，再按分镜批量生成。长链路支持不等于单个模型直接生成长视频，而是通过章节、角色锚点、风格锚点、参考图和分段拼接来保持人物与画风一致。

长链路一致性要求：

- 规划阶段输出 `consistency_strategy`，明确角色一致性、画风一致性、章节策略和允许变化项。
- 参考设计阶段输出 `style_anchor_id`、`fixed_style_traits`、角色 `identity_anchor`、`fixed_traits` 和 `allowed_variations`。
- 每个分镜携带 `chapter_id`、`continuity_group`、`character_ids`、`style_anchor`、`continuity_notes`。
- 自动拆分的子分镜必须继承父分镜的角色、风格和连续性字段。
- 同一角色跨分镜不得改变物种/年龄感/体型/脸型或毛色/发型/服装主视觉/关键配饰；同一视频默认不得切换画风。

## 工作流

| 意图 | 执行方式 |
|------|----------|
| 一句话生成完整短视频 | `scripts/run_video.py`，OpenClaw workflow 为 `full-video` |
| 只要分镜脚本 | `scripts/run_video.py --storyboard_only`，workflow 为 `storyboard-only` |
| 重生成指定分镜 | `scripts/run_scene.py`，workflow 为 `feedback` |
| 重新拼接 workspace | `scripts/run_concat.py`，workflow 为 `concat` |
| 检测视频语音语言 | `scripts/run_language_check.py` |
| 校验分镜契约 | `scripts/validate_storyboard.py` |
| 检查人物/画风一致性契约 | `scripts/run_consistency_qa.py` |
| 成片技术 QA | `scripts/local_video_qa.py` |
| 成片质量评分 | `scripts/score_video_quality.py` |
| 生成时间线中间层 | `scripts/build_edit_plan.py` |
| 校验时间线中间层 | `scripts/validate_edit_plan.py` |
| 生成 QA 修复计划 | `scripts/plan_repairs.py` |
| 生成发布检查点 | `scripts/release_checkpoint.py` |
| 调单个底层工具 | `scripts/run_tool.py` |
| 管理、导入导出经验胶囊 | `scripts/capsule_store.py` |

架构边界见 `references/architecture.md`。工具 API 见 `references/tools-api.md`。引擎和音色见 `references/engines-and-voices.md`。分镜结构见 `references/storyboard-schema.md`。制作经验见 `references/video-recipes.md`。

## 运行约定

本包自包含 Python 代码，运行时从 `lib` 加入 `PYTHONPATH`。优先用 `python3.12`，并先安装依赖：

```bash
cd "$(git rev-parse --show-toplevel)"
python3.12 -m pip install -r lib/requirements.txt
```

常用环境变量：

| 变量 | 用途 |
|------|------|
| `PYTHON_BIN` | OpenClaw 子进程 Python，默认 `python3.12` |
| `DOTENV_PATH` | 可选 `.env` 路径 |
| `VIDEO_RESOURCES_PATH` | 字体、音效等大资源目录；BGM 默认在线生成 |
| `OPENCLAW_OUTPUT_DIR` | 生成物根目录；必须指向本仓库 `output/` 或其子目录 |
| `CREW_API_KEY` / `CREW_BASE_URL` / `CREW_MODEL_NAME` | LLM 分镜规划 |
| `JULING_BASE_URL` / `JULING_API_KEY` | seedream5、gpt-image-2、seedance-fast、seedance、jimeng35pro、veo3.1 |
| `JULING_VEO31_MODEL` | 可选，Juling Veo 3.1 模型覆盖，默认 `veo3.1_fast` |
| `VEO3_BASE_URL` / `VEO3_API_KEY` | veo3 |
| `DOUBAO_TTS_APPID` / `DOUBAO_TTS_ACCESS_TOKEN` | 豆包 TTS |
| `SUNO_BASE_URL` / `SUNO_API_KEY` | Suno 音乐生成 |
| `JAMENDO_CLIENT_ID` / `JAMENDO_API_BASE` | 可选，授权音乐搜索下载；未配置时跳过搜索 |
| `ONLINE_MUSIC_ENABLE_ARCHIVE` / `INTERNET_ARCHIVE_*` | 可选，免 key 的授权音频搜索下载 |
| `ONLINE_MUSIC_MAX_MB` / `ONLINE_MUSIC_SEARCH_LIMIT` / `ONLINE_MUSIC_REQUEST_TIMEOUT` | 可选，在线音乐下载限制 |
| `VIDEO_CAPSULE_DB` | SQLite 胶囊仓库路径 |

输出目录布局：每次运行在输出根目录下创建一个 run 目录（通常是 `output/general_video_<timestamp>/` 或 `output/<workflow>_<timestamp>[_<project>]/`），包含 `artifact_manifest.json`、`release/`（最终成片、发布文件和 `release_checkpoint.json`）、`work/`（`edit_plan.json`、images/audios/videos/reference_images/temp 等中间产物）、`qa/`（`edit_plan_validation.json`、质检报告和 `repair_plan.json`）、`prompts/`（分镜、图片、视频、TTS、音乐和装配参数快照）、`logs/`。完整视频主流程会把 scene 级 `audio_path` / `image_path` / `video_path` 回写到 `storyboard.json`，并在成功后自动生成 EditPlan、EditPlan 校验、本地 QA、修复计划和发布检查点。
最终交付件、QA 报告、封面、发布文案和手动 `run_tool.py` 产物都必须写在本仓库 `output/` 下；不要写到 `/tmp`、仓库根目录、父目录或任意外部目录。

## 运行时维护

维护本运行时（脚本、包元数据、工具注册表、测试、环境变量管道）时遵循以下规则：

1. 改模块边界前读 `references/architecture.md`；改封装脚本或工具参数前读 `references/tools-api.md`；改分镜输出/校验前读 `references/storyboard-schema.md`。
2. 元数据、env 白名单、包或封装脚本变更后运行 `npm test`。
3. 保持小写 `skill.md`；不要新建 `SKILL.md`（大小写不敏感文件系统会覆盖本文件）。
4. 脚本用显式 `python3.12` 运行，不依赖可执行权限位；`--help` 与参数校验阶段延迟重型 import。
5. 不要硬编码 API key、签名 URL、cookie、私有端点。env 变量需在本文件 permissions 与 `index.js` 白名单中保持同步。
6. 新工具不要直接加进 `scripts/run_tool.py`；更新 `lib/config/tool_registry.yaml` 注册元数据，并把工具类放入 `lib/custom_tools/<category>/`。
7. 不要创建 `lib/.env`（测试会拒绝）；保持 `lib/.env.example` 无密钥，并与本文件、`index.js`、`references/channel-policy.md` 对齐。

## 脚本示例

完整视频：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --user_requirements "一只橘猫做饭的搞笑短视频" \
  --target_duration 30 \
  --aspect_ratio "9:16" \
  --video_engine seedance-fast
```

按本地胶囊生成分镜：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --capsule healing_asmr_food_daily_v1 \
  --user_requirements "一只橘猫低头吃小鱼干，真实治愈 ASMR" \
  --storyboard_only
```

仅分镜：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --user_requirements "一只橘猫做饭的搞笑短视频" \
  --target_duration 30 \
  --storyboard_only
```

重生成第 2 个分镜：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_scene.py \
  --workspace_dir output/<run_id> \
  --scene_id 2 \
  --image_prompt "新的图片描述" \
  --video_prompt "新的视频动作描述" \
  --image_engine seedream5 \
  --video_engine seedance-fast
```

单工具调用：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool Seedream5ImageGeneratorTool \
  --params '{"prompt":"一只橘猫在厨房做饭","output_path":"output/manual_tool/work/images/cat.jpg","aspect_ratio":"9:16"}'
```

成片质量评分：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/score_video_quality.py \
  --run-dir output/<run_id> \
  --capsule healing_asmr_food_daily_v1 \
  --aspect-ratio "9:16"
```

口播/同步、有字幕/画面文字、有人物配音的路线成片评分加多模态视频审核：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/score_video_quality.py \
  --run-dir output/<run_id> \
  --capsule digital_human_presenter_v1 \
  --aspect-ratio "9:16" \
  --multimodal-review \
  --multimodal-provider gemini3
```

多模态审核结果会映射到 `speech_visual_sync_reviewed`、`talking_head_motion_continuity`、`subtitle_text_layout` 和 `voice_character_match`。必审门缺少可用多模态结果时不能算通过。

生成时间线、修复计划和发布检查点：

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

## Prompt 规则

- 完整视频工作流当前只要求分镜输出普通 `image_to_video` 场景。
- `image_prompt` 推荐中文，且不要要求模型生成文字、标题或字幕。
- `video_prompt`：`seedance-fast`、`seedance`、`jimeng35pro`、`veo3` 和 `veo3.1` 可用中文。
- 旁白始终按中文短视频节奏写，单段较长时用 `|` 标记画面切换点。
- `jimeng35pro` 需要中文语音时，生成后用 `scripts/run_language_check.py` 做语言检测。
- 有人物连续出现时，必须优先使用角色参考图和 `reference_ids`；不要只在 prompt 里写“同一个人/同一只猫”。
- 有统一画风要求时，必须使用 `style_reference` 和 `visual_style`，所有场景默认 `use_style_reference=true`。
- 对长链路或系列化内容，先生成并检查一组角色/风格参考图，再批量扩展分镜。

## 胶囊仓库

制作经验使用 `scripts/capsule_store.py` 写入用户本地 SQLite（默认 `~/.codex/video-production/capsules.sqlite`，不随仓库分发）。用户层优先通过对话请求“使用某个胶囊”“启用官方初始胶囊”“把满意视频保存成胶囊”或“整理成可分享胶囊包”；运行时再调用对应的安装、查询、写入、导入或导出能力。仓库根目录 `capsules/` 存放官方初始胶囊（标准 `.capsule.zip` 包），首次启用时安装：

```bash
python3.12 scripts/capsule_store.py install-defaults
```

胶囊可打包分享给其他人（初始胶囊与分享胶囊同一格式）：

```bash
# 导出为可分享的包（含本地资产与脚本，路径自动相对化，附 sha256 校验）
python3.12 scripts/capsule_store.py export <name> --out /path/to/dir

# 在另一台机器导入（资产默认落地 ~/.codex/video-production/capsule_assets/<name>/）
python3.12 scripts/capsule_store.py import <name>.capsule.zip [--assets-dir DIR] [--name NEW] [--force]
```

导出前会自动做密钥/远程 URL 扫描，命中即拒绝导出；导入会校验包版本与文件校验和，并自动运行 `doctor`。
