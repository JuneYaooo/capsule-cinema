"""成片音轨：配音按句摆位 + BGM（按 bgm_fit 剪掉整小节让乐曲结尾落在片尾，人声下压）+ 程序音效。

python3.12 mix.py → ../audio/mix.wav（48 kHz 立体声 24-bit，−14 LUFS，真峰值约 −1.4 dBTP）
音效表在 cues.py（每期自己写）：时间照抄 scene3d/shots.py 里各镜头的动画节点，保证声画同步。
这里只放通用的混音流程，常量一般不用改。
"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np

import cues
import sfx as X
from episode import BGM_CUT, BGM_FILE, BGM_KEY, CHAPTERS

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
SR = X.SR
BGM = ROOT / "audio" / "bgm" / BGM_FILE
VOICE_LUFS = -20.0           # 每句配音先统一到这个响度，最后整体归一
BGM_FULL_DB, BGM_DUCK_DB = -8.0, -15.5   # 相对 BGM 原始电平：无人声 / 人声下
TARGET_LUFS, PEAK_LIMIT = -14.0, 0.85


def load(path, ch=1):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", str(ch),
                                   "-ar", str(SR), "-"])
    x = np.frombuffer(raw, np.float32).copy()
    return x.reshape(-1, ch) if ch > 1 else x


def lufs_of(data, ch):
    """ffmpeg ebur128 量整段响度和真峰值。"""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", str(ch),
                        "-i", "-", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       input=np.ascontiguousarray(data, np.float32).tobytes(), capture_output=True)
    txt = p.stderr.decode()
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)[-1])
    pk = float(re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", txt)[-1])
    return i, pk


def db(x):
    return 10 ** (x / 20)


def ramp_env(n, spans, attack, release):
    """spans 内为 1，前后线性过渡，重叠取最大。"""
    g = np.zeros(n, np.float32)
    t = np.arange(n) / SR
    for a, b in spans:
        lo, hi = int(max(0, (a - attack) * SR)), int(min(n, (b + release) * SR))
        tt = t[lo:hi]
        v = np.minimum(np.clip((tt - (a - attack)) / attack, 0, 1), np.clip(((b + release) - tt) / release, 0, 1))
        g[lo:hi] = np.maximum(g[lo:hi], v)
    return g


def chapter_times(tl):
    """章节牌切换时刻（与 overlay 一致：该句第一个字幕段前 0.1 s；第 1 句没有牌）。"""
    sents = {s["id"]: s for s in tl["sentences"]}
    return [sents[sid]["chunks"][0]["t0"] - 0.1 for sid in CHAPTERS if sid != 1]


# ------------------------------------------------------------------ 主流程

def main():
    tl = json.loads((WORK / "timeline.json").read_text())
    n = int(round(tl["total"] * SR))

    voice = np.zeros(n, np.float32)
    for s in tl["sentences"]:
        x = load(s["file"])
        i, _ = lufs_of(x, 1)
        X.place(voice, x * db(VOICE_LUFS - i), s["start"])

    bgm = load(BGM, 2)
    if BGM_CUT:   # 剪掉整小节：接缝处 40 ms 等功率交叉淡化
        a, b, xf = int(BGM_CUT[0] * SR), int(BGM_CUT[1] * SR), int(0.04 * SR)
        w = np.linspace(0, np.pi / 2, xf)[:, None]
        bgm = np.concatenate([bgm[:a], bgm[a:a + xf] * np.cos(w) + bgm[b:b + xf] * np.sin(w), bgm[b + xf:]])
    if len(bgm) < n:
        print(f"WARNING: BGM 比片子短 {(n - len(bgm)) / SR:.1f} s，换一首更长的或少剪一段")
    bgm = np.pad(bgm, ((0, max(0, n - len(bgm))), (0, 0)))[:n]
    bgm[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))[:, None]
    spans, cur = [], None
    for s in tl["sentences"]:   # 句间停顿短于 0.7 s 不回弹，免得 BGM 一抽一抽
        v0, v1 = s["voice"]
        cur = [v0, v1] if cur is None or v0 - cur[1] > 0.7 else [cur[0], v1]
        if not spans or spans[-1][0] != cur[0]:
            spans.append(cur)
        else:
            spans[-1] = cur
    duck = ramp_env(n, spans, attack=0.12, release=0.45)
    bgm *= db(BGM_FULL_DB + (BGM_DUCK_DB - BGM_FULL_DB) * duck)[:, None]

    fx = np.zeros((n, 2), np.float32)
    X.set_key(*BGM_KEY)
    events = cues.schedule(tl)
    for t in chapter_times(tl):   # 每段章节牌切换「咻」一声
        events.append((t, X.swish(), -30, 0.0))
    for t, y, gain, pan in events:
        th = (pan + 1) * np.pi / 4   # 等功率声像，pan=0 两边各 −3 dB
        tmp = np.zeros(n, np.float32)
        X.place(tmp, y * db(gain + 3.0), t)
        fx[:, 0] += tmp * np.cos(th)
        fx[:, 1] += tmp * np.sin(th)

    mix = voice[:, None] + bgm + fx   # 人声单声道复制到两边（不是 -ac 2 的 −3 dB 下混）
    for name, d in (("voice", np.repeat(voice[:, None], 2, 1)), ("bgm", bgm), ("sfx", fx), ("mix", mix)):
        print(f"{name:6s} I={lufs_of(d, 2)[0]:6.1f} LUFS  peak={20 * np.log10(np.abs(d).max() + 1e-9):6.1f} dBFS")

    i, _ = lufs_of(mix, 2)
    raw = WORK / "tmp_mix_f32.raw"
    for _ in range(3):   # 增益 → 限幅 → 复测，收敛到目标响度
        (mix * db(TARGET_LUFS - i)).astype(np.float32).tofile(raw)
        out = ROOT / "audio" / "mix.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(raw),
                        "-af", f"alimiter=limit={PEAK_LIMIT}:attack=3:release=60:level=0", "-c:a", "pcm_s24le",
                        str(out)], check=True)
        got, pk = lufs_of(load(out, 2), 2)
        print(f"master  I={got:.2f} LUFS  true-peak={pk:.2f} dBFS")
        if abs(got - TARGET_LUFS) < 0.2:
            break
        i += got - TARGET_LUFS
    raw.unlink()
    print(f"events={len(events)}  ->", out)


if __name__ == "__main__":
    main()
