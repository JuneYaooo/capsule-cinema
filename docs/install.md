# Capsule Cinema 安装指南（给 AI Agent 读）

> 这是给 AI 助手执行的安装说明。人类用户只要把本文 URL 发给 Codex、Claude Code、OpenClaw、Cursor、Trae、Hermes Agent 或其他支持 Skills 的 Agent，不需要手动照抄每条命令。

仓库：<https://github.com/JuneYaooo/capsule-cinema>

## 安装目标

把 Capsule Cinema 安装为当前 Agent 可发现的 Skill，装好 Python 运行依赖，检查 FFmpeg，并告诉用户如何安全配置自己的规划、图片、视频和 TTS 渠道。不要读取、打印、提交或迁移用户已有的密钥值。

## 1. 检查前置依赖

必需：

- Git
- Python 3.12 与 pip
- rsync
- FFmpeg（只看配方、只做分镜时可暂缺；生成成片前必须有）
- 可显示中文的系统字体；Linux 推荐安装 Noto Sans CJK

如果缺少依赖，使用当前系统的标准包管理器安装。macOS 可用 Homebrew，Ubuntu/Debian 可用 apt。安装后用 `python3.12 --version` 和 `ffmpeg -version` 实际验证，不要只根据包管理器输出判断成功。

字体会按项目资源、macOS/Windows/Linux 系统字体和 Linux fontconfig 自动发现。若服务器没有中文字体，可安装 `fonts-noto-cjk`，或通过 `VIDEO_DEFAULT_FONT_PATH` 指定字体文件；需要分别控制字重时使用 `VIDEO_FONT_REGULAR_PATH` 和 `VIDEO_FONT_BOLD_PATH`。

## 2. 克隆并运行安装脚本

如果当前客户端支持标准 Agent Skills，可以先直接安装分发入口：

```bash
npx skills add JuneYaooo/capsule-cinema --skill capsule-cinema
```

这个入口会在第一次使用时定位完整源码仓库，或把公开运行时下载到 Skill 目录的 `runtime/`。如果需要在安装阶段就准备完整运行时、Python 依赖和 FFmpeg 检查，继续执行下面的安装脚本：

```bash
git clone https://github.com/JuneYaooo/capsule-cinema.git /tmp/capsule-cinema
cd /tmp/capsule-cinema

# Claude Code
bash install_as_skill.sh --target claude --yes

# Codex
bash install_as_skill.sh --target codex --yes

# OpenClaw
bash install_as_skill.sh --target openclaw --yes
```

只执行与当前 Agent 对应的一条。安装目录分别是：

- Claude Code：`~/.claude/skills/capsule-cinema/`
- Codex：`${CODEX_HOME:-~/.codex}/skills/capsule-cinema/`
- OpenClaw：`~/.openclaw/skills/capsule-cinema/`

脚本升级已有安装时会保留 `.env`、`local-channels/`、`lib/custom_tools/**/local_*_adapter*.py`、`capsules/` 与 `output/`，不会把开发仓库中的密钥、私有渠道、运行产物或测试目录复制进新的安装。Codex、Claude Code 和 OpenClaw 都使用大写 `SKILL.md`；源码仓库中的标准分发目录是 `skills/capsule-cinema/`。

旧版本曾把 OpenClaw 安装到 `~/skills/capsule-cinema/`。新版遵循 OpenClaw 当前标准，改用 `~/.openclaw/skills/capsule-cinema/`。安装器不会自动迁移旧目录中的凭据或用户数据；如果检测到旧目录，会保留原目录并明确提示，由用户自行审查后迁移需要保留的 `.env`、自建配方、私有渠道和历史产物。

## 3. 安全配置环境变量

先问用户想使用哪条渠道，再只说明需要配置的变量名。不要要求用户把完整密钥粘贴到聊天里。优先使用 Agent 配置、系统环境变量、Secret 管理器或 CI Secret；standalone 本地运行也可让用户自己把安装目录中的 `lib/.env.example` 复制成根目录 `.env` 并在本机填写，文件权限建议设为 `600`。

常见最小组合：

| 目的 | 变量名 |
| --- | --- |
| 让内部规划运行时生成分镜 | `CREW_API_KEY`、`CREW_BASE_URL`、`CREW_MODEL_NAME` |
| 官方火山方舟图片与 Seedance 视频 | `ARK_API_KEY`；可选 `ARK_BASE_URL`、`ARK_SEEDREAM_MODEL`、`ARK_SEEDANCE_MODEL` |
| Agnes 官方免费层图片与文生短视频 | `AGNES_API_KEY`；可选 `AGNES_BASE_URL`、`AGNES_IMAGE_MODEL`、`AGNES_VIDEO_MODEL` |
| MiniMax 配音 | `MINIMAX_API_KEY`；部分账号需要 `MINIMAX_GROUP_ID` |
| 豆包配音 | `DOUBAO_TTS_API_KEY`；模型、资源与音色变量为可选项 |
| RunningHub 动作迁移或对口型示例 | `RUNNINGHUB_API_KEY` 与具体工作流声明的变量 |

只做配方浏览、校验、打包、安装不需要生成渠道密钥。只做分镜仍需要可用的规划模型，除非当前 Agent 明确改为在会话内产出并校验 storyboard。

Agnes 必须使用安装者自己的 Key，不能由安装脚本、仓库或部署模板提供共享 Key。第一次试跑可以到 [Agnes API 平台](https://platform.agnes-ai.com/) 注册并在控制台生成 Key；[官方 FAQ](https://wiki.agnes-ai.com/en/docs/faqs.md) 当前表示核心模型可无限期免费使用，没有公布结束日期。免费不等于无限额度：[官方限额](https://wiki.agnes-ai.com/en/docs/tokenplan.md) 当前给免费默认档视频约 1 RPM，图片按分辨率约为 20/10/1 RPM；免费用户每日视频秒数没有公开，500 秒/天属于付费 Token Plan。免费档没有生产 SLA。它适合低频图片和几秒级文生视频试做，不应被安装器静默设为完整视频工作流的默认渠道。

## 4. 验证并重启

完整安装脚本会把运行时直接放在 Skill 安装目录。只通过 `npx skills add` 安装标准入口时，先定位客户端实际安装的 `capsule-cinema` Skill 目录，再让引导脚本返回运行时目录：

```bash
SKILL_DIR=<实际 capsule-cinema Skill 目录>
RUNTIME_DIR=$(bash "$SKILL_DIR/scripts/bootstrap-runtime.sh")
cd "$RUNTIME_DIR"

# 只通过 npx 安装标准入口时执行；完整安装脚本已经完成这一步。
python3.12 -m pip install -r lib/requirements.txt
PYTHONPATH=lib python3.12 scripts/capsule.py list
python3.12 scripts/provider_menu.py --json
```

使用完整安装脚本时，也可以直接把 `RUNTIME_DIR` 设为实际安装目录。

完成标志：

1. Codex、Claude Code 和 OpenClaw 安装目录都存在大写 `SKILL.md`，且不再依赖小写 `skill.md`。
2. 运行时目录存在 `scripts/capsule.py` 和 `lib/requirements.txt`，且 `capsule.py list` 能列出内置配方。
3. `provider_menu.py --json` 能读取当前有效渠道菜单。
4. FFmpeg 已可执行，或者明确告诉用户当前只能做分镜和配方管理。
5. 提醒用户完整重启 Agent。

重启后建议先做不计费测试：

> 用 Capsule Cinema 列出当前配方和可用渠道，然后为「一只橘猫深夜做饭」做一个 20 秒竖屏分镜。先不要生成图片、视频和配音，也不要调用任何计费 API。

确认分镜和工具路线正确后，再让用户决定是否进入媒体生成。

## 5. 清理临时目录

安装和验证完成后可删除 `/tmp/capsule-cinema`。不要删除实际 Skill 安装目录、用户的 `local-channels/`、自建配方或历史 `output/`。
