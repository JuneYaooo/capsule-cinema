# Capsule Cinema 胶囊影厂

按配方生产 AI 短视频的本地工作室：用可分享的「视频胶囊」沉淀生产配方，用可扩展的工具链生成各种类型的视频。

## 术语表

| 术语 | 指什么 | 不是什么 |
|------|--------|----------|
| **Capsule Cinema（平台）** | 本仓库整套系统 | 不是某个单独的 skill |
| **Skill** | 平台内的能力模块（见下表），按角色命名 | skill 名不带 capsule 字样 |
| **胶囊 Capsule** | 仅指可分享的生产配方数据：本地 SQLite 记录及其打包形式 `.capsule.zip`（配置 + 方法 + 资产 + 质检规则 + 运行历史） | 不是 skill，也不是某次运行的产物 |

## Skills

| Skill | 职责 |
|-------|------|
| `video-agent/` | 可执行运行时（OpenClaw plugin）：分镜、生成、拼接、QA 脚本、工具注册表、胶囊存储。运行时维护规则见 `video-agent/skill.md` 的「运行时维护」章节。 |
| `video-production/` | 制作指南：路由决策、渠道政策、制作模式、质检标准、胶囊路由。脚本统一引用 `$VIDEO_AGENT_ROOT/scripts/`。 |
| `account-distillation/` | 对标账号蒸馏：账号分析、hook 提取、产出可复用胶囊模板。 |

## 产物路径

每次运行落在 `output/<run_id>/`（run_id = `<workflow>_<timestamp>[_<project>]`）：

```text
output/<run_id>/
  release/   # 最终成片 + manifest
  work/      # 中间产物（images/audios/videos/temp 等）
  qa/        # 质检报告
  logs/
```

`capsules/` 存放官方初始胶囊（标准 `.capsule.zip` 包）；`artifacts/`、`reports/` 为本地 legacy 目录，不入库。

## 视频胶囊

胶囊是**用户本地**的 SQLite 记录（默认 `~/.codex/video-production/capsules.sqlite`，不上传），记录配方、资产、质检规则与运行历史。

首次启用时安装官方初始胶囊（仓库 `capsules/` 下的标准包）：

```bash
python3.12 video-agent/scripts/capsule_store.py install-defaults
```

自己沉淀的胶囊可打包分享，别人 import 即可使用——初始胶囊与分享胶囊是同一种格式：

```bash
python3.12 video-agent/scripts/capsule_store.py export <name> --out ./
python3.12 video-agent/scripts/capsule_store.py import <name>.capsule.zip
```

导出前自动做密钥/远程 URL 扫描；导入校验包版本与 sha256 校验和，资产落地 `~/.codex/video-production/capsule_assets/<name>/` 并自动运行 `doctor`。
