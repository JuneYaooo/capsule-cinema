"""排时间线：配音逐句摆位 → 每句的字幕段（chunk）起止 → 关键词时间 → 镜头表。全片唯一的时间来源。

python3.12 timeline.py   （先跑完 tts_takes.py 和 asr_pick.py）→ timeline.json
镜头动画（kw:<词> 事件）、音效时间、字幕、章节牌全部读 timeline.json，所以声画天然同步。

chunk 起点：whisper 字级时间 + 拼音对齐给出估计，再吸附到停顿结束（人声重新出现）处，
因为 turbo 会把停顿后第一个字标早 0.13–0.6 s。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from pypinyin import lazy_pinyin

WORK = Path(__file__).resolve().parent
AUDIO = WORK.parent / "audio" / "lines"
sys.path.insert(0, str(WORK))
from episode import (EXTRA_GAP, FPS, GAP, LEAD, PRECUT, SENTENCES, SHOT_STARTS, TAIL,  # noqa: E402
                     chunk_sub, chunk_tts)

PUNCT = re.compile(r"[，。、！？：；,.!?:;\s\"“”‘’'（）()%~\-0-9a-zA-Z]")


def load_pcm(path, sr=32000):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                                   "-ar", str(sr), "-"])
    return np.frombuffer(raw, np.float32), sr


def envelope_db(x, sr, hop=0.01):
    w = int(sr * hop)
    n = len(x) // w
    rms = np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(rms + 1e-9)


def find_pauses(db, below=40.0, min_len=0.05, hop=0.01):
    thr = db.max() - below
    voiced = np.where(db > thr)[0]
    v0, v1 = voiced[0], voiced[-1]
    out, start = [], None
    for k in range(v0, v1 + 1):
        if db[k] <= thr:
            start = k if start is None else start
        else:
            if start is not None and (k - start) * hop >= min_len:
                out.append((start * hop, k * hop))
            start = None
    return out, v0 * hop, (v1 + 1) * hop


def align_times(ref_chars, words):
    """把台本每个字对到 ASR 字上（无调拼音编辑距离），返回每个台本字的起始时间。"""
    hyp = []
    for w in words:
        cs = [c for c in w["w"] if not PUNCT.match(c)]
        if not cs:
            continue
        step = (w["e"] - w["s"]) / len(cs)
        hyp += [(c, w["s"] + i * step) for i, c in enumerate(cs)]
    rp = lazy_pinyin("".join(ref_chars))
    hp = lazy_pinyin("".join(c for c, _ in hyp))
    n, m = len(rp), len(hp)
    D = np.zeros((n + 1, m + 1), int)
    D[:, 0] = range(n + 1)
    D[0, :] = range(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (rp[i - 1] != hp[j - 1]))
    times = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + (rp[i - 1] != hp[j - 1]):
            times[i - 1] = hyp[j - 1][1]   # 匹配或同位替换（同音字按位置取时间）
            i, j = i - 1, j - 1
        elif D[i, j] == D[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    # 删掉的字（ASR 没听到/写成数字）线性插值
    known = [k for k, t in enumerate(times) if t is not None]
    for k in range(n):
        if times[k] is None:
            lo = max([q for q in known if q < k], default=None)
            hi = min([q for q in known if q > k], default=None)
            if lo is None:
                times[k] = times[hi]
            elif hi is None:
                times[k] = times[lo] + 0.18 * (k - lo)
            else:
                times[k] = times[lo] + (times[hi] - times[lo]) * (k - lo) / (hi - lo)
    return times


def snap_to_pause(t_est, pauses, v_start):
    """估计时间落在停顿里，或落在停顿开始前 0.35 s 以内 → 改取停顿结束。"""
    best = None
    for a, b in pauses:
        if a - 0.35 <= t_est <= b + 0.12:
            if best is None or abs((a + b) / 2 - t_est) < abs((best[0] + best[1]) / 2 - t_est):
                best = (a, b)
    return (best[1], best[0]) if best else (max(t_est, v_start), None)


def main():
    picks = json.loads((WORK / "picks.json").read_text())
    report = json.loads((WORK / "asr_takes.json").read_text())
    sentences = []
    g = LEAD
    for s in SENTENCES:
        sid = s["id"]
        path = AUDIO / f"s{sid:02d}.mp3"
        x, sr = load_pcm(path)
        dur = len(x) / sr
        db = envelope_db(x, sr)
        pauses, v_start, v_end = find_pauses(db)
        take = picks[str(sid)]
        words = report[str(sid)][take]["large-v3-turbo"]["words"]
        tts_clean = [c for c in s["tts"] if not PUNCT.match(c)]
        times = align_times(tts_clean, words)
        chunks, k = [], 0
        for ci, c in enumerate(s["chunks"]):
            n = len([ch for ch in chunk_tts(c) if not PUNCT.match(ch)])
            t_est = times[k]
            if ci == 0:
                t0 = v_start
            else:
                t0, pause_start = snap_to_pause(t_est, pauses, v_start)
                if pause_start is not None:
                    chunks[-1]["t1_voice"] = pause_start
            chunks.append(dict(sub=chunk_sub(c), tts=chunk_tts(c), t0=t0, est=t_est, char0=k, nchar=n))
            k += n
        for ci, c in enumerate(chunks):
            c.setdefault("t1_voice", chunks[ci + 1]["t0"] if ci + 1 < len(chunks) else v_end)
        # 关键词时间：在 chunk 的上屏文字里找；tts 与上屏一致时按字对齐，否则按比例估
        for c in chunks:
            c["kws"] = []
            for w in s["hl"]:
                pos = c["sub"].find(w)
                if pos < 0:
                    continue
                if c["sub"] == c["tts"]:
                    clean_before = len([ch for ch in c["sub"][:pos] if not PUNCT.match(ch)])
                    t = times[c["char0"] + clean_before] if clean_before else c["t0"]
                    t = max(t, c["t0"])
                else:
                    t = c["t0"] + (c["t1_voice"] - c["t0"]) * pos / max(1, len(c["sub"]))
                c["kws"].append(dict(w=w, t=round(g + t, 3)))
        for c in chunks:
            for key in ("t0", "t1_voice", "est"):
                c[key] = round(g + c[key], 3)
            del c["char0"], c["nchar"]
        sentences.append(dict(id=sid, file=str(path), start=round(g, 3), dur=round(dur, 3),
                              voice=[round(g + v_start, 3), round(g + v_end, 3)], chunks=chunks))
        g += dur + GAP + EXTRA_GAP.get(sid, 0.0)
    total = sentences[-1]["voice"][1] + TAIL
    frames = int(round(total * FPS))

    by_key = {(s["id"], ci): c for s in sentences for ci, c in enumerate(s["chunks"])}
    shots = []
    for i, (sh, sid, ci) in enumerate(SHOT_STARTS):
        start = 0.0 if i == 0 else by_key[(sid, ci)]["t0"] - PRECUT
        shots.append(dict(id=sh, start=start))
    for sh in shots:
        sh["f0"] = int(round(sh["start"] * FPS))
    for i, sh in enumerate(shots):
        sh["f1"] = shots[i + 1]["f0"] if i + 1 < len(shots) else frames
        sh["start"] = sh["f0"] / FPS
        sh["end"] = sh["f1"] / FPS
        sh["dur"] = round(sh["end"] - sh["start"], 3)
        ev = {}
        for s in sentences:
            for ci, c in enumerate(s["chunks"]):
                if sh["start"] - 0.5 <= c["t0"] < sh["end"]:
                    ev[f"c{s['id']}.{ci}"] = round(c["t0"] - sh["start"], 3)
                for kw in c["kws"]:
                    if sh["start"] - 0.5 <= kw["t"] < sh["end"]:
                        ev["kw:" + kw["w"]] = round(kw["t"] - sh["start"], 3)
            if sh["start"] <= s["voice"][1] < sh["end"] + 0.5:
                ev[f"end{s['id']}"] = round(s["voice"][1] - sh["start"], 3)
        sh["events"] = ev
    short = [sh["id"] for sh in shots if sh["f1"] - sh["f0"] < FPS]
    if short:
        print("WARNING: 短于 1 秒的镜头", short, "（合并到相邻镜头，或把切点挪到下一个字幕段）")
    out = dict(fps=FPS, total=round(frames / FPS, 3), frames=frames, sentences=sentences, shots=shots)
    (WORK / "timeline.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for s in sentences:
        print(f"S{s['id']:02d} {s['start']:6.2f}  " + " | ".join(f"{c['t0']:.2f}{c['sub']}" for c in s["chunks"]))
    print("total", out["total"], "s", frames, "frames")
    for sh in shots:
        print(sh["id"], f"{sh['start']:6.2f}-{sh['end']:6.2f} ({sh['dur']:.2f}s)", sh["events"])


if __name__ == "__main__":
    main()
