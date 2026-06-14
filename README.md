# Capsule Cinema 胶囊影厂

按配方生产 AI 短视频的本地工作室：用可分享的「视频胶囊」沉淀生产配方，用可扩展的工具链生成各种类型的视频。

## 术语表

| 术语 | 指什么 | 不是什么 |
|------|--------|----------|
| **Capsule Cinema** | 本仓库整套系统：一个统一的 skill（运行时 + 制作方法论） | — |
| **胶囊 Capsule** | 仅指可分享的生产配方数据：本地 SQLite 记录及其打包形式 `.capsule.zip`（配置 + 方法 + 资产 + 质检规则 + 运行历史） | 不是 skill，也不是某次运行的产物 |

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
  logs/
```

最终成片、封面、发布文案、QA 报告和手动工具生成物都必须在本仓库 `output/` 下；不要写到 `/tmp`、仓库根目录、父目录或任意外部目录。`capsules/` 存放官方初始胶囊（标准 `.capsule.zip` 包）；`artifacts/`、`reports/` 为本地 legacy 目录，不入库。

## 视频胶囊

胶囊是**用户本地**的 SQLite 记录（默认 `~/.codex/video-production/capsules.sqlite`，不上传），记录配方、资产、质检规则与运行历史。

首次启用时安装官方初始胶囊（仓库 `capsules/` 下的标准包）：

```bash
python3.12 scripts/capsule_store.py install-defaults
```

自己沉淀的胶囊可打包分享，别人 import 即可使用——初始胶囊与分享胶囊是同一种格式：

```bash
python3.12 scripts/capsule_store.py export <name> --out ./
python3.12 scripts/capsule_store.py import <name>.capsule.zip
```

导出前自动做密钥/远程 URL 扫描；导入校验包版本与 sha256 校验和，资产落地 `~/.codex/video-production/capsule_assets/<name>/` 并自动运行 `doctor`。

## 扩展指南

平台有四个正交扩展轴，优先级：**胶囊 > 工具注册 > 渠道政策 > 改运行时**。90% 的扩展需求不需要改核心代码。

| 想扩展什么 | 怎么做 |
|------------|--------|
| **新视频类型/配方** | 普通图生视频配方沉淀为胶囊：`capsule_store.py upsert` 写入配置、方法、质检规则与本地资产，跑通后 `export` 分享。不需要新 skill；若需要动作迁移、对口型、MV 等专用执行链，用 `local_script` 胶囊或新增 runtime workflow。 |
| **新生成引擎/工具** | 工具类放 `lib/custom_tools/<category>/`，在 `lib/config/tool_registry.yaml` 注册元数据（module、category、provider、limits、strengths）。**禁止**直接改 `scripts/run_tool.py`。 |
| **新渠道/换渠道** | 编辑渠道政策，流程见 `references/channel-customization.md`；新渠道需补齐工具名、必填输入、env 变量、强项、失败模式与 QA 要求。 |
| **新质检规则** | 胶囊内 `quality_rules` 字段 + QA 脚本 rubric（`score_video_quality.py` / `local_video_qa.py`）。 |

只有新自动工作流（超出"完整视频 / 仅分镜 / 分镜重生成 / 拼接 / QA"链路）才需要改运行时核心。专用路线如果能由一个成熟本地脚本稳定完成，优先做成 `local_script` 胶囊；确实要进入 OpenClaw 自动执行时再改 runtime。改之前必读 `references/architecture.md`，改完运行 `npm test`；env 变量需在 `skill.md` permissions、`index.js` 白名单、`lib/.env.example` 三处保持同步。
