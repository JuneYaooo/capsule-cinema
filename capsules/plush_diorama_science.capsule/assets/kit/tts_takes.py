"""逐句合成 MiniMax 配音，每句 N 个 take；已存在的 take 跳过。挑 take 见 asr_pick.py。

python3.12 tts_takes.py [--takes 3] [--only 3,7]   → ../audio/takes/sNN_tK.mp3
整句合成（逗号停顿由 TTS 自己处理，语调连贯）；音色和语速读 episode.py。
需要在仓库根目录的 .env 里配好 MiniMax 的 key（脚本只读环境变量，不打印）。
仓库根目录自动向上查找（有 lib/custom_tools 的那一层），也可以用环境变量 CAPSULE_REPO_ROOT 指定。
"""
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORK = Path(__file__).resolve().parent
TAKES = WORK.parent / "audio" / "takes"


def repo_root():
    env = os.environ.get("CAPSULE_REPO_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    for p in [WORK, *WORK.parents]:
        if (p / "lib" / "custom_tools" / "audio_generation").is_dir():
            return p
    sys.exit("找不到仓库根目录：设置 CAPSULE_REPO_ROOT")


ROOT = repo_root()
sys.path.insert(0, str(WORK))
sys.path.insert(0, str(ROOT / "lib"))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from custom_tools.audio_generation.minimax_tts_tool import synthesize_with_minimax  # noqa: E402
from episode import SENTENCES, TTS_SPEED, VOICE_ID  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--takes", type=int, default=3)
ap.add_argument("--only", default="", help="逗号分隔的句号")
args = ap.parse_args()
only = {int(x) for x in args.only.split(",") if x}

TAKES.mkdir(parents=True, exist_ok=True)
jobs = []
for s in SENTENCES:
    if only and s["id"] not in only:
        continue
    for k in range(args.takes):
        out = TAKES / f"s{s['id']:02d}_t{k}.mp3"
        if not (out.exists() and out.stat().st_size > 1000):
            jobs.append((s, out))


def run(job):
    s, out = job
    r = {}
    for attempt in range(8):
        r = synthesize_with_minimax(text=s["tts"], output_path=str(out), voice_type=VOICE_ID, speed=TTS_SPEED)
        if r.get("success"):
            return f"{out.name} OK"
        if "rate limit" in str(r.get("error")).lower():
            time.sleep(15 * (attempt + 1))   # 限流退避：15、30、45 秒……
        else:
            break
    return f"{out.name} FAIL {r.get('error')}"


with ThreadPoolExecutor(2) as ex:   # 并发 2：再多就开始限流
    for msg in ex.map(run, jobs):
        print(msg, flush=True)
