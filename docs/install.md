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

如果缺少依赖，使用当前系统的标准包管理器安装。macOS 可用 Homebrew，Ubuntu/Debian 可用 apt。安装后用 `python3.12 --version` 和 `ffmpeg -version` 实际验证，不要只根据包管理器输出判断成功。

## 2. 克隆并运行安装脚本

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
- OpenClaw：`~/skills/capsule-cinema/`

脚本升级已有安装时会保留 `.env`、`local-channels/`、`lib/custom_tools/**/local_*_adapter*.py`、`capsules/` 与 `output/`，不会把开发仓库中的密钥、私有渠道、运行产物或测试目录复制进新的安装。Codex / Claude Code 安装副本会把根入口规范化为 `SKILL.md`；源仓库仍保留 OpenClaw 使用的 `skill.md`。

## 3. 安全配置环境变量

先问用户想使用哪条渠道，再只说明需要配置的变量名。不要要求用户把完整密钥粘贴到聊天里。优先使用 Agent 配置、系统环境变量、Secret 管理器或 CI Secret；standalone 本地运行也可让用户自己把安装目录中的 `lib/.env.example` 复制成根目录 `.env` 并在本机填写，文件权限建议设为 `600`。

常见最小组合：

| 目的 | 变量名 |
| --- | --- |
| 让内部规划运行时生成分镜 | `CREW_API_KEY`、`CREW_BASE_URL`、`CREW_MODEL_NAME` |
| 官方火山方舟图片与 Seedance 视频 | `ARK_API_KEY`；可选 `ARK_BASE_URL`、`ARK_SEEDREAM_MODEL`、`ARK_SEEDANCE_MODEL` |
| MiniMax 配音 | `MINIMAX_API_KEY`；部分账号需要 `MINIMAX_GROUP_ID` |
| 豆包配音 | `DOUBAO_TTS_API_KEY`；模型、资源与音色变量为可选项 |
| RunningHub 动作迁移或对口型示例 | `RUNNINGHUB_API_KEY` 与具体工作流声明的变量 |

只做配方浏览、校验、打包、安装不需要生成渠道密钥。只做分镜仍需要可用的规划模型，除非当前 Agent 明确改为在会话内产出并校验 storyboard。

## 4. 验证并重启

```bash
cd <实际安装目录>
PYTHONPATH=lib python3.12 scripts/capsule.py list
python3.12 scripts/provider_menu.py --json
```

完成标志：

1. Codex / Claude Code 安装目录存在 `SKILL.md`，OpenClaw 安装目录存在 `skill.md`。
2. `capsule.py list` 能列出内置配方。
3. `provider_menu.py --json` 能读取当前有效渠道菜单。
4. FFmpeg 已可执行，或者明确告诉用户当前只能做分镜和配方管理。
5. 提醒用户完整重启 Agent。

重启后建议先做不计费测试：

> 用 Capsule Cinema 列出当前配方和可用渠道，然后为「一只橘猫深夜做饭」做一个 20 秒竖屏分镜。先不要生成图片、视频和配音，也不要调用任何计费 API。

确认分镜和工具路线正确后，再让用户决定是否进入媒体生成。

## 5. 清理临时目录

安装和验证完成后可删除 `/tmp/capsule-cinema`。不要删除实际 Skill 安装目录、用户的 `local-channels/`、自建配方或历史 `output/`。
