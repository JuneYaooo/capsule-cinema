# Capsule Cinema 胶囊影厂

按配方生产 AI 短视频的本地工作室：用可分享的「视频胶囊」沉淀生产配方，用可扩展的工具链生成各种类型的视频。

## 术语表

| 术语 | 指什么 | 不是什么 |
|------|--------|----------|
| **Capsule Cinema** | 本仓库整套系统：一个统一的 skill（运行时 + 制作方法论） | — |
| **胶囊 Capsule** | 仅指可分享的生产配方数据：本地 SQLite 记录及其打包形式 `.capsule.zip`（配置 + 方法 + 资产 + 质检规则 + 运行历史） | 不是 skill，也不是某次运行的产物 |

## 和 AI 交互使用

安装这个 skill 之后，用户主要通过对话提出目标，不需要记脚本名。AI 会根据 `skill.md` 的能力入口选择完整视频、分镜、反馈重做、拼接、单工具、质检或胶囊工作流。

| 想做什么 | 对 AI 这样说 |
|----------|--------------|
| 从一句话做完整短视频 | “用 Capsule Cinema 做一个 30 秒竖屏短视频，主题是 `<主题>`，目标观众是 `<人群>`，风格要 `<风格>`。” |
| 先只看分镜方案 | “先只生成分镜，不要生成图片、视频和配音。主题是 `<主题>`，我确认后再继续制作。” |
| 修改已有成片里的某个分镜 | “这个 workspace 里第 `<编号>` 个分镜不满意，请保留其他部分，只重做这个分镜的画面和动作：`<修改要求>`。” |
| 重新拼接已有素材 | “这些分镜素材已经可以了，请重新拼接，并按我的新字幕/BGM/节奏要求调整最终成片。” |
| 只做某个素材或工具步骤 | “这次只生成 `<图片/视频片段/配音/BGM/字幕/文案>`，不要跑完整视频流程。” |
| 检查成片质量并给修复建议 | “请检查这个成片是否可发布，重点看画面、声音、字幕、时长、语言匹配和胶囊质检规则，再给我修复计划。” |
| 使用、保存或分享胶囊 | “请使用 `<胶囊名>` 胶囊做这个视频。” / “这条视频满意，请保存成 `<胶囊名>` 胶囊。” / “请把这个胶囊整理成可分享版本并先检查敏感信息。” |

## 仓库结构

```text
skill.md       # 统一入口：能力声明、工作流、运行约定、维护规则
index.js       # OpenClaw plugin 适配层
scripts/       # 命令入口：run_video / run_scene / run_tool / QA / capsule_store 等
lib/           # Python 工具库：流程编排、契约、工具注册表、custom_tools
references/    # 方法论 + 架构文档：production-guide（总路由）、渠道政策、分镜技巧、质检踩坑等
capsules/      # 官方初始胶囊（标准 .capsule.zip 包）
tests/         # skill 元数据与安全测试（npm test）
```

分发单元只有两个：**胶囊**（`.capsule.zip`，配方，高频分享）和**本 skill 整体**（运行时 + 方法论，装一次）。本地可能还存在 `account-distillation/`（对标账号蒸馏），属于私有 skill，已 gitignore，不随仓库分发。

## 快速开始

```bash
# 1. 安装运行时依赖
python3.12 -m pip install -r lib/requirements.txt

# 2. 配置密钥（参考 lib/.env.example，环境变量说明见 skill.md）
cp lib/.env.example /path/to/your/.env  # 填入密钥后 export DOTENV_PATH=/path/to/your/.env

# 3. 安装官方初始胶囊
python3.12 scripts/capsule_store.py install-defaults

# 4. 生成第一个视频
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --user_requirements "一只橘猫做饭的搞笑短视频" \
  --target_duration 30 --aspect_ratio "9:16"
```

做视频前的方法论（任务路由、渠道政策、钩子审计、产物规范）见 `references/production-guide.md`。

## 产物路径

每次运行落在 `output/<run_id>/`（run_id = `<workflow>_<timestamp>[_<project>]`）：

```text
output/<run_id>/
  release/   # 最终成片 + manifest + release_checkpoint.json
  work/      # 中间产物（edit_plan.json、images/audios/videos/temp 等）
  qa/        # 质检报告 + repair_plan.json
  prompts/   # 分镜、图片、视频、TTS、音乐和装配参数快照
  logs/
```

完整视频主流程会回写 scene 级 `audio_path` / `image_path` / `video_path`，生成 `prompts/prompt_index.json`，并在 `artifact_manifest.json` 中登记中间素材；`run_video.py` 成功后会自动生成 `work/edit_plan.json`、`qa/local_video_qa.json`、`qa/repair_plan.json` 和 `release/release_checkpoint.json`。最终成片、封面、发布文案、QA 报告和手动工具生成物都必须在本仓库 `output/` 下；不要写到 `/tmp`、仓库根目录、父目录或任意外部目录。`capsules/` 存放官方初始胶囊（标准 `.capsule.zip` 包）；`artifacts/`、`reports/` 为本地 legacy 目录，不入库。

## 视频胶囊

胶囊是**用户本地**的 SQLite 记录（默认 `~/.codex/video-production/capsules.sqlite`，不上传），记录配方、资产、质检规则与运行历史。胶囊资产（例如背景音乐、参考图片、本地脚本）是胶囊合同的一部分；AI 使用胶囊时应优先按胶囊资产执行，缺失或不可用时先说明影响，再决定是否替代。

### 和 AI 对话使用初始胶囊

用户安装 Capsule Cinema 后，不需要知道脚本路径或胶囊内部结构。直接在对话里点名胶囊、说明目标、提供素材或链接即可。AI 应先读取胶囊合同，确认模式、资产、输入要求和质检规则，再按胶囊路线执行。

可以这样开口：

| 想做什么 | 可用初始胶囊 | 对 AI 这样说 |
|----------|--------------|--------------|
| 展示一个 GitHub 仓库、AI 工具或 Agent Skill | `github_skills_showcase` | “使用 `github_skills_showcase` 胶囊，帮我做一个展示这个 GitHub 仓库的短视频：<仓库链接或本地路径>。目标观众是 <人群>，重点突出 <最想讲的价值>。” |
| 做治愈食物、宠物吃播、手作 ASMR | `healing_asmr_food_daily_v1` | “使用 `healing_asmr_food_daily_v1` 胶囊，做一个 <食物/宠物/手作> 的治愈 ASMR 短视频。不要旁白，重点是质感、动作和节奏。” |
| 做 AI 科技新闻快闪 | `ai_tech_news_flash_v1` | “使用 `ai_tech_news_flash_v1` 胶囊，把这条 AI 新闻做成竖屏快闪视频：<新闻内容或链接>。语气克制，突出事实、影响和适合谁关注。” |
| 做国风历史文化讲解 | `guofeng_history_explainer_v1` | “使用 `guofeng_history_explainer_v1` 胶囊，讲 <历史人物/典故/制度/文化主题>。希望是国风水墨国漫质感，重点讲清楚反差和启发。” |
| 拆解爆款视频、案例或传播机制 | `viral_breakdown_explainer_v1` | “使用 `viral_breakdown_explainer_v1` 胶囊，拆解这个案例：<链接/文案/现象>。不要复述原片，帮我讲清楚为什么有效、哪里能迁移、哪里不要模仿。” |
| 做舞蹈、健身、武术等动作迁移 | `action_transfer_dance_v1` | “使用 `action_transfer_dance_v1` 胶囊，基于这张角色图和这个参考动作，做动作迁移视频。先检查素材是否适合 RunningHub 动作路线，不要用普通图生视频冒充动作迁移。” |
| 做数字人口播或对口型讲解 | `digital_human_presenter_v1` | “使用 `digital_human_presenter_v1` 胶囊，做一个数字人口播视频。主题是 <主题>，我会提供人脸源图/源视频；请先写口播脚本，再生成配音并做对口型。” |
| 做角色 MV 或音乐情绪短片 | `music_character_mv_v1` | “使用 `music_character_mv_v1` 胶囊，围绕这首歌做角色 MV：<歌曲/音频/风格说明>。请以音乐为主线设计镜头，不要用 TTS 口播冒充歌曲。” |

如果不确定该用哪个胶囊，可以直接说：“请先查看 Capsule Cinema 的初始胶囊，根据我的目标推荐一个胶囊，并说明还需要我补哪些素材。” 对于 `draft` 胶囊，AI 应先做小样和 QA；对于 `local_script` 胶囊，AI 应按胶囊自己的脚本路线执行，而不是把它拆成普通视频生成流程。

### 把满意视频保存成自己的胶囊

当一条视频已经跑通、风格满意、后续还想复用时，直接让 AI 把这次经验保存成胶囊。用户不需要自己整理参数；AI 应从本次成片、分镜、提示词、素材、BGM、质检报告和修改反馈里提炼可复用部分，区分“一次性项目素材”和“未来可复用配方”。

可以这样说：

| 场景 | 对 AI 这样说 |
|------|--------------|
| 保存为新胶囊 | “这条视频我满意。请把这次工作流保存成一个新胶囊，名字叫 `<胶囊名>`，适合以后做 `<适用场景>`。请保留可复用的画面风格、结构、默认时长、字幕/BGM 策略、质量规则和本地资产。” |
| 从某个已有胶囊改进 | “这次是在 `<已有胶囊名>` 基础上做出来的，我觉得新版更好。请把这次改动沉淀回这个胶囊，记录版本变化和为什么要这样改。” |
| 只保存方法，不保存敏感素材 | “请把这次视频沉淀成胶囊，但不要保存客户资料、私密文件、一次性链接、账号信息或任何密钥。只保留可复用的方法、参数、公开素材和本地授权资产。” |
| 保存失败经验 | “这次没有完全成功，但这里的失败很有价值。请把问题写进相关胶囊的反馈：哪里失败、证据是什么、下次怎么避免。” |
| 准备分享给别人 | “请把这个胶囊整理成可分享版本。先检查里面没有密钥、私密路径、远程签名链接或不可分发素材，再告诉我这个胶囊适合谁用、需要哪些输入。” |

保存胶囊时，AI 应优先保存这些信息：目标人群、适用/不适用场景、默认画幅和时长、分镜结构、视觉风格、音频策略、可复用本地资产、质量规则、成功样片路径、已知坑和修复方法。不要把具体客户项目、一次性新闻正文、临时下载链接、密钥、cookie、私有接口或不可授权素材写进胶囊。

如果初始胶囊还没启用，可以对 AI 说：“请帮我启用 Capsule Cinema 的官方初始胶囊，并列出现在能用的胶囊。” AI 会从仓库 `capsules/` 下的标准包安装到用户本地胶囊仓库。

自己沉淀的胶囊也可以分享给别人。可以对 AI 说：“请把 `<胶囊名>` 整理成可分享胶囊包，先检查里面没有密钥、私密路径、远程签名链接或不可分发素材。” 别人拿到胶囊包后，可以对 AI 说：“请导入这个胶囊包，并告诉我这个胶囊需要哪些输入、适合做什么视频。”

导出前 AI 应触发密钥/远程 URL 扫描；导入时应校验包版本与 sha256 校验和，让资产落地到用户本地胶囊资产目录，并完成健康检查。

## 扩展指南

平台有四个正交扩展轴，优先级：**胶囊 > 工具注册 > 渠道政策 > 改运行时**。90% 的扩展需求不需要改核心代码。

| 想扩展什么 | 怎么做 |
|------------|--------|
| **新视频类型/配方** | 普通图生视频配方沉淀为胶囊：`capsule_store.py upsert` 写入配置、方法、质检规则与本地资产，跑通后 `export` 分享。不需要新 skill；若需要动作迁移、对口型、MV 等专用执行链，用 `local_script` 胶囊或新增 runtime workflow。 |
| **新生成引擎/工具** | 工具类放 `lib/custom_tools/<category>/`，在 `lib/config/tool_registry.yaml` 注册元数据（module、category、provider、limits、strengths）。**禁止**直接改 `scripts/run_tool.py`。 |
| **新渠道/换渠道** | 编辑渠道政策，流程见 `references/channel-customization.md`；新渠道需补齐工具名、必填输入、env 变量、强项、失败模式与 QA 要求。 |
| **新质检规则** | 胶囊内 `quality_rules` 字段 + QA 脚本 rubric（`score_video_quality.py` / `local_video_qa.py`）。 |

只有新自动工作流（超出"完整视频 / 仅分镜 / 分镜重生成 / 拼接 / QA"链路）才需要改运行时核心。专用路线如果能由一个成熟本地脚本稳定完成，优先做成 `local_script` 胶囊；确实要进入 OpenClaw 自动执行时再改 runtime。改之前必读 `references/architecture.md`，改完运行 `npm test`；env 变量需在 `skill.md` permissions、`index.js` 白名单、`lib/.env.example` 三处保持同步。
