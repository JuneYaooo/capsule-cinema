"""BGM 适配：测速度、拍点相位和调，找一处剪掉整小节的接缝，让乐曲自然结尾正好落在片尾。

python3.12 bgm_fit.py --survey               → 列出 ../audio/bgm/ 里每首的时长、响度、LRA、速度、调，帮你挑
python3.12 bgm_fit.py <文件名.mp3>            → 读 timeline.json 的片长，给出 BGM_KEY / BGM_CUT，写 bgm_fit.json
选曲：纯音乐、轻快好奇、约 110 bpm、能量平稳（LRA 小）、有自然收尾，比片子长一点（多 1–3 个小节最好剪）。

接缝怎么找：按拍切片，每拍算 chroma（和声）+ 24 段对数频谱（音色）；在第 i 拍剪到第 i+K 拍（K 是整小节），
要求接缝前后各 4 拍的和声、音色都像。剪完用「接缝前 0.1 s 和后 0.01 s 的频谱距离」和整首正常拍点的距离分布比，
接缝距离不超过正常拍点的最大值才算能用——但最后一定要戴耳机听接缝。
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np

WORK = Path(__file__).resolve().parent
BGM_DIR = WORK.parent / "audio" / "bgm"
SR = 22050
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def load(path, sr=SR):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                                   "-ar", str(sr), "-"])
    return np.frombuffer(raw, np.float32).astype(np.float64)


def loudness(path):
    txt = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)[-1])
    lra = float(re.findall(r"LRA:\s+([\d.]+) LU", txt)[-1])
    return i, lra


def onset_flux(x):
    """谱通量起音包络（hop 220 ≈ 10 ms，1024 Hann 窗，log1p(100·S) 压缩）。"""
    hop = 220
    m = len(x) // hop
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (512, 512)), 1024)[::hop][:m]
    L = np.log1p(100 * np.abs(np.fft.rfft(frames * np.hanning(1024), axis=1)))
    flux = np.concatenate([[0], np.maximum(0, np.diff(L, axis=0)).sum(1)])
    flux = np.maximum(flux - np.convolve(flux, np.ones(50) / 50, "same"), 0)
    return flux, SR / hop


def tempo_phase(x, lo=85.0, hi=135.0):
    """自相关在 lo–hi bpm 里每 0.05 bpm 试一次（累加 8 个倍数的周期），再按 2 ms 步长找拍点相位。"""
    flux, fps = onset_flux(x)
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    idx = np.arange(len(ac))
    bpm = max(np.arange(lo, hi, 0.05),
              key=lambda b: sum(np.interp(k * 60 / b * fps, idx, ac) for k in range(1, 9)))
    period = 60 / bpm
    ts = np.arange(len(flux)) / fps
    phase = max(np.arange(0, period, 0.002), key=lambda ph: np.interp(np.arange(ph, ts[-1], period), ts, flux).sum())
    return float(bpm), float(period), float(phase)


def chroma(seg, n=4096):
    seg = np.pad(seg, (0, max(0, n - len(seg))))[:n] * np.hanning(n)
    S = np.abs(np.fft.rfft(seg))
    f = np.fft.rfftfreq(n, 1 / SR)
    sel = (f > 80) & (f < 4000)
    c = np.bincount(np.round(12 * np.log2(f[sel] / 261.63)).astype(int) % 12, S[sel], 12)
    return c / (np.linalg.norm(c) + 1e-9)


def timbre(seg, n=4096):
    seg = np.pad(seg, (0, max(0, n - len(seg))))[:n] * np.hanning(n)
    v = np.array([b.mean() for b in np.array_split(np.log1p(np.abs(np.fft.rfft(seg))), 24)])
    return (v - v.mean()) / (v.std() + 1e-9)


def key_of(x):
    """Krumhansl–Schmuckler：整首的 chroma 和 24 个调的模板做相关，取最大。"""
    hop = 4096
    c = sum(chroma(x[i:i + 4096]) for i in range(0, len(x) - 4096, hop))
    best = max(((np.corrcoef(np.roll(prof, k), c)[0, 1], NOTE_NAMES[k], mode)
                for k in range(12) for prof, mode in ((KS_MAJOR, "major"), (KS_MINOR, "minor"))))
    return best[1], best[2], float(best[0])


def music_end(x, floor_db=-50.0):
    """去掉尾部静音后的乐曲长度（50 ms 窗 RMS 低于 floor_db 视为静音）。"""
    w = int(0.05 * SR)
    n = len(x) // w
    db = 20 * np.log10(np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
    loud = np.where(db > floor_db)[0]
    return (loud[-1] + 1) * w / SR if len(loud) else len(x) / SR


def seam_candidates(x, period, phase, K, top=8):
    beats = np.arange(phase, len(x) / SR - period, period)
    segs = [x[int(b * SR):int((b + period) * SR)] for b in beats]
    C = np.array([chroma(s) for s in segs])
    M = np.array([timbre(s) for s in segs])
    res = []
    for i in range(16, len(beats) - K - 16):   # 不剪前奏，也不剪最后 16 拍（结尾要完整）
        win = range(-4, 4)
        sc = np.mean([float((C[i + d] * C[i + K + d]).sum()) for d in win]) \
            + 0.05 * np.mean([np.corrcoef(M[i + d], M[i + K + d])[0, 1] for d in win])
        res.append((float(sc), i))
    res.sort(reverse=True)
    return [(sc, i, float(beats[i]), float(beats[i + K])) for sc, i in res[:top]], beats


def cos_dist(a, b):
    """1 − 余弦相似度（逐元素乘再求和，不走 BLAS 矩阵乘，避免 macOS Accelerate 报假的浮点警告）。"""
    return 1 - float((a * b).sum())


def spec48(sig, t, sr=48000):
    s = sig[int(t * sr):int(t * sr) + 4096] * np.hanning(4096)
    v = np.log1p(np.abs(np.fft.rfft(s))[:1500])
    return v / (np.linalg.norm(v) + 1e-9)


def seam_jump(path, a, b, period, phase):
    """剪完后接缝处的频谱跳变，和原曲正常拍点处的跳变分布对比（48 kHz，和成片一致）。"""
    sr = 48000
    x = load(path, sr)
    ia, ib, xf = int(a * sr), int(b * sr), int(0.04 * sr)
    w = np.linspace(0, np.pi / 2, xf)
    y = np.concatenate([x[:ia], x[ia:ia + xf] * np.cos(w) + x[ib:ib + xf] * np.sin(w), x[ib + xf:]])
    grid = phase + period * np.arange(30, int((len(x) / sr - 2) / period))
    typ = [cos_dist(spec48(x, t - 0.1), spec48(x, t + 0.01)) for t in grid]
    jump = cos_dist(spec48(y, a - 0.1), spec48(y, a + 0.01))
    return float(jump), float(np.median(typ)), float(np.percentile(typ, 90)), float(max(typ))


def survey(lo, hi):
    for p in sorted(BGM_DIR.glob("*.mp3")) + sorted(BGM_DIR.glob("*.wav")):
        x = load(p)
        i, lra = loudness(p)
        bpm, _, _ = tempo_phase(x, lo, hi)
        tonic, mode, _ = key_of(x)
        print(f"{p.name[:40]:40s} {len(x) / SR:6.1f}s  end {music_end(x):6.1f}s  I {i:6.1f} LUFS  LRA {lra:4.1f}"
              f"  {bpm:6.1f} bpm  {tonic} {mode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bgm", nargs="?")
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--bpm", default="85,135", help="速度搜索范围；测出来是一半或两倍就调这里")
    ap.add_argument("--bar", type=int, default=4, help="每小节几拍（剪的长度是它的整数倍）")
    args = ap.parse_args()
    lo, hi = (float(v) for v in args.bpm.split(","))
    if args.survey or not args.bgm:
        return survey(lo, hi)

    path = BGM_DIR / args.bgm
    x = load(path)
    film = json.loads((WORK / "timeline.json").read_text())["total"]
    bpm, period, phase = tempo_phase(x, lo, hi)
    tonic, mode, kc = key_of(x)
    end = music_end(x)
    need = end - film
    print(f"{path.name}: {bpm:.2f} bpm（拍长 {period:.4f}s，相位 {phase:.3f}s），{tonic} {mode}（相关 {kc:.2f}）")
    print(f"乐曲有声部分 {end:.2f}s，片长 {film:.2f}s，需要剪 {need:.2f}s")
    out = dict(file=path.name, bpm=round(bpm, 2), period=round(period, 4), phase=round(phase, 3),
               key=[tonic, mode], music_end=round(end, 3), film=film, cut=None)
    bar = args.bar * period
    if need < -0.3:
        print("BGM 比片子短：换一首更长的（不要循环拼接，接缝会多）")
    elif need < bar / 2:
        print("不用剪：长度差不到半小节，片尾 0.3 s 淡出即可")
    else:
        K = args.bar * max(1, round(need / bar))
        cands, _ = seam_candidates(x, period, phase, K)
        print(f"剪 {K} 拍（{K // args.bar} 小节，{K * period:.2f}s），剪完结尾落在片尾 {end - K * period - film:+.2f}s 处")
        for sc, i, a, b in cands:
            print(f"  第 {i} 拍 → 第 {i + K} 拍：{a:7.3f}s → {b:7.3f}s  相似度 {sc:.4f}")
        sc, i, a, b = cands[0]
        jump, med, p90, mx = seam_jump(path, a, b, period, phase)
        ok = jump <= mx
        print(f"接缝频谱跳变 {jump:.3f}；正常拍点 中位 {med:.3f} / p90 {p90:.3f} / 最大 {mx:.3f} → "
              + ("可用，去听一下" if ok else "比正常拍点都突兀，试下一个候选或换曲"))
        out.update(cut=[round(a, 3), round(b, 3)], beats_removed=K, seam_jump=round(jump, 3),
                   grid_median=round(med, 3), grid_p90=round(p90, 3), grid_max=round(mx, 3))
    (WORK / "bgm_fit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写进 episode.py：")
    print(f'BGM_FILE = "{path.name}"')
    print(f'BGM_KEY = ("{tonic}", "{mode}")')
    print(f"BGM_CUT = {tuple(out['cut']) if out['cut'] else None}")


if __name__ == "__main__":
    main()
