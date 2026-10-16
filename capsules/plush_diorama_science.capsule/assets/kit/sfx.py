"""程序合成的卡通音效（48 kHz 单声道 float32，峰值归一到 1）。

每个函数返回一段 numpy 数组；cues.py 按镜头事件时间摆放，mix.py 混音。只用 numpy：
滤波在频域做（rfft 乘掩码），扫频用相位累加。
有音高的音效（blip / sparkle / ding / tada / alert）都落在 BGM 调的五声音阶上：
混音前先 set_key(主音, 大小调)，主音和调式由 bgm_fit.py 测出来写进 episode.BGM_KEY。
"""
import numpy as np

SR = 48000


def _n(dur):
    return max(1, int(round(dur * SR)))


def _t(dur):
    return np.arange(_n(dur)) / SR


def norm(y):
    return (y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def env(n, tau, attack=0.002):
    t = np.arange(n) / SR
    return np.clip(t / max(attack, 1e-5), 0, 1) * np.exp(-t / tau)


def fade(y, a=0.01, r=0.01):
    y = y.copy()
    na, nr = min(len(y), _n(a)), min(len(y), _n(r))
    y[:na] *= np.linspace(0, 1, na)
    y[len(y) - nr:] *= np.linspace(1, 0, nr)
    return y


def osc(freq, wave="sine"):
    """freq 可以是逐样本的频率数组。"""
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(freq, np.shape(freq))) / SR
    if wave == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    if wave == "square":
        return np.tanh(4 * np.sin(ph))
    return np.sin(ph)


def sweep(f0, f1, dur, tau=None, wave="sine", attack=0.002):
    t = _t(dur)
    f = f0 * (f1 / f0) ** (t / dur)
    return osc(f, wave) * env(len(t), tau or dur / 3, attack)


def band_noise(dur, lo, hi, seed=0):
    n = _n(dur)
    X = np.fft.rfft(np.random.default_rng(seed).standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.clip((f - 0.7 * lo) / (0.3 * lo + 1e-9), 0, 1) * np.clip((1.3 * hi - f) / (0.3 * hi), 0, 1)
    return norm(np.fft.irfft(X * m, n))


def place(out, y, t, gain=1.0):
    s = int(round(t * SR))
    if s >= len(out):
        return
    if s < 0:
        y, s = y[-s:], 0
    e = min(len(out), s + len(y))
    out[s:e] += gain * y[:e - s]


# ------------------------------------------------------------------ 单发

def pop(pitch=1.0):
    """泡泡「啵」：短促上滑。"""
    return norm(sweep(380 * pitch, 1150 * pitch, 0.07, tau=0.022))


def plop(pitch=1.0):
    """果子落下「噗」。"""
    y = sweep(520 * pitch, 150 * pitch, 0.16, tau=0.05)
    y[:_n(0.012)] += 0.3 * band_noise(0.012, 800, 4000, seed=int(pitch * 100)) * np.linspace(1, 0, _n(0.012))
    return norm(y)


def gulp(pitch=1.0):
    """被洞口、容器或嘴吞进去「咕」：更闷的下滑。"""
    return norm(sweep(420 * pitch, 130 * pitch, 0.13, tau=0.045) + 0.4 * sweep(210 * pitch, 70 * pitch, 0.13, tau=0.05))


def step(pitch=1.0, seed=0):
    """毛绒小脚「嗒」。"""
    n = _n(0.06)
    y = 0.55 * band_noise(0.06, 400, 2600, seed=seed) * env(n, 0.006, 0.0005)
    y += osc(np.full(n, 240 * pitch)) * env(n, 0.018, 0.001)
    return norm(y)


def spring(up=True, pitch=1.0):
    """弹簧「啵～嘤」：带颤音的滑音。"""
    t = _t(0.38)
    f0, f1 = (200, 640) if up else (640, 200)
    f = f0 * pitch * (f1 / f0) ** np.minimum(1, t / 0.12) * (1 + 0.06 * np.sin(2 * np.pi * 15 * t))
    return norm(osc(f) * env(len(t), 0.13, 0.003))


def bell(freq, dur=0.6, tau=0.25):
    t = _t(dur)
    y = (np.sin(2 * np.pi * freq * t)
         + 0.4 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t / 0.07)
         + 0.2 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t / 0.035))
    return norm(y * env(len(t), tau, 0.001))


# 音高类音效落在 BGM 调的五声音阶上，和配乐不打架。默认 D 大调，set_key 改。
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PENT = [587.33, 659.25, 739.99, 880.0, 987.77]   # D5 E5 F#5 A5 B5
TRIAD = (0, 2, 3)                                 # 主音、三音、五音在 PENT 里的下标


def set_key(tonic="D", mode="major"):
    """把五声音阶换到 BGM 的调上：主音放在 C5–B5 这个八度；小调用小调五声（0 3 5 7 10）。"""
    k = NOTE_NAMES.index(tonic)
    root = 523.25 * 2 ** (k / 12)
    steps, triad = ((0, 3, 5, 7, 10), (0, 1, 3)) if mode == "minor" else ((0, 2, 4, 7, 9), (0, 2, 3))
    PENT[:] = [root * 2 ** (st / 12) for st in steps]
    global TRIAD
    TRIAD = triad


def note(k):
    """五声音阶第 k 个音（k=0 是主音，每 5 个音升一个八度）。"""
    return PENT[k % 5] * 2 ** (k // 5)


def blip(freq, dur=0.12):
    """有音高的「啵」：25 ms 内从 0.6f 滑到 f 再衰减，连着排就是一串上行音。"""
    t = _t(dur)
    f = freq * (0.6 + 0.4 * np.minimum(1, t / 0.025))
    return norm((osc(f) + 0.25 * osc(2 * f)) * env(len(t), 0.045, 0.002))


def sparkle(n=5, base=None, gap=0.055):
    """闪光：上行琶音小铃（默认从高八度的主音起）。"""
    base = base or note(5)
    ratios = [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2]
    out = np.zeros(_n(gap * n + 0.7), np.float32)
    for i in range(n):
        place(out, bell(base * ratios[i % len(ratios)], 0.6, 0.16), i * gap, 0.88 ** i)
    return norm(out)


def ding():
    """答对「叮～」两声。"""
    out = np.zeros(_n(0.9), np.float32)
    place(out, bell(note(8), 0.8, 0.3), 0.0)
    place(out, bell(note(10), 0.8, 0.4), 0.09)
    return norm(out)


def tada():
    """揭晓：主三和弦（主音、三音、五音、高八度主音）+ 闪光。"""
    t = _t(1.4)
    chord = [PENT[i] for i in TRIAD] + [PENT[0] * 2]
    y = sum(osc(np.full(len(t), f), "tri") for f in chord) * env(len(t), 0.55, 0.004)
    out = np.zeros(len(t), np.float32)
    out += norm(y)
    place(out, sparkle(6, note(10), 0.045), 0.04, 0.55)
    return norm(out)


def crack():
    """外壳「啪」地裂开 + 里面的汁水「噗嗤」。"""
    out = np.zeros(_n(0.35), np.float32)
    snap = band_noise(0.08, 1500, 8000, seed=3) * env(_n(0.08), 0.01, 0.0003)
    place(out, snap, 0.0)
    place(out, band_noise(0.03, 2000, 6000, seed=5) * env(_n(0.03), 0.004, 0.0003), 0.022, 0.6)
    squish = band_noise(0.3, 150, 1100, seed=4) * env(_n(0.3), 0.07, 0.004)
    place(out, squish, 0.015, 0.8)
    return norm(out)


def chomp():
    """小角色「咔嚓」咬一口（分子被咬断、东西被分解）。"""
    out = np.zeros(_n(0.3), np.float32)
    for k, tt in enumerate((0.0, 0.085)):
        place(out, band_noise(0.08, 500, 4000, seed=10 + k) * env(_n(0.08), 0.02, 0.001), tt, 1.0 - 0.3 * k)
        place(out, sweep(170, 70, 0.08, tau=0.02), tt, 0.5)
    return norm(out)


def clack():
    """拨杆开关「咔哒」。"""
    out = np.zeros(_n(0.15), np.float32)
    place(out, band_noise(0.02, 2000, 7000, seed=21) * env(_n(0.02), 0.002, 0.0002), 0.0)
    place(out, sweep(190, 120, 0.06, tau=0.015), 0.0, 0.7)
    place(out, band_noise(0.02, 2500, 8000, seed=22) * env(_n(0.02), 0.0015, 0.0002), 0.028, 0.55)
    return norm(out)


def lock_click():
    """上锁「咔」：带一点金属铃音。"""
    out = clack()
    place(out, bell(3150, 0.12, 0.03), 0.026, 0.45)
    return norm(out)


def buzz():
    """错误、禁止「嗡嗡」两声（故意不在调上）。"""
    out = np.zeros(_n(0.42), np.float32)
    for k in range(2):
        n = _n(0.15)
        y = osc(np.full(n, 165.0), "square") * fade(np.ones(n), 0.006, 0.02)
        place(out, y, k * 0.21)
    return norm(out)


def alert():
    """警示「嘀嘀嘀」。"""
    out = np.zeros(_n(0.36), np.float32)
    for k in range(3):
        n = _n(0.07)
        place(out, osc(np.full(n, note(5))) * fade(np.ones(n), 0.004, 0.012), k * 0.12)
    return norm(out)


def thud(pitch=1.0, seed=0):
    """软软地倒下「咚」。"""
    out = np.zeros(_n(0.25), np.float32)
    place(out, sweep(160 * pitch, 55 * pitch, 0.22, tau=0.06), 0.0)
    place(out, band_noise(0.03, 150, 900, seed=seed) * env(_n(0.03), 0.008, 0.0005), 0.0, 0.4)
    return norm(out)


def stamp():
    """盖章、停止牌、禁止牌「哐」：低沉的一下 + 咔哒。"""
    out = np.zeros(_n(0.3), np.float32)
    place(out, thud(0.8, 31), 0.0)
    place(out, clack(), 0.0, 0.6)
    return norm(out)


def cork():
    """塞子塞紧、洞口堵上「啵」。"""
    out = np.zeros(_n(0.3), np.float32)
    place(out, sweep(760, 240, 0.08, tau=0.025), 0.0)
    place(out, thud(1.3, 41), 0.01, 0.5)
    return norm(out)


def sniff():
    """角色闻香「嗅嗅」。"""
    out = np.zeros(_n(0.5), np.float32)
    for k in range(2):
        n = _n(0.16)
        e = np.sin(np.linspace(0, np.pi, n)) ** 2
        place(out, band_noise(0.16, 1800, 7000, seed=50 + k) * e, k * 0.2, 1.0 - 0.2 * k)
    return norm(out)


def swish():
    """标签切换「咻」。"""
    n = _n(0.26)
    e = np.interp(np.arange(n), [0, int(n * 0.45), n - 1], [0, 1, 0]) ** 2
    return norm(band_noise(0.26, 2000, 10000, seed=61) * e)


def evil_bloop(pitch=1.0):
    """坏角色冒出来：低沉的「啵噜」。"""
    return norm(sweep(150 * pitch, 380 * pitch, 0.1, tau=0.04, wave="tri"))


def hic():
    """打嗝「嗝」（醉、撑、超上限）。"""
    out = np.zeros(_n(0.2), np.float32)
    place(out, band_noise(0.03, 600, 3000, seed=71) * env(_n(0.03), 0.008, 0.001), 0.0, 0.5)
    place(out, sweep(330, 820, 0.09, tau=0.035, wave="tri"), 0.01)
    return norm(out)


def chatter(dur=0.7, rate=13.0):
    """冻得牙齿打颤「哒哒哒」。"""
    out = np.zeros(_n(dur + 0.05), np.float32)
    for k in range(int(dur * rate)):
        n = _n(0.012)
        place(out, band_noise(0.012, 1500, 6000, seed=80 + k) * env(n, 0.002, 0.0002), k / rate,
              0.6 + 0.4 * (k % 2))
    return norm(out)


# ------------------------------------------------------------------ 持续

def slide(f0, f1, dur, vib=0.02):
    """滑哨：数值下降 / 上升（f0 > f1 就是下降）。"""
    t = _t(dur)
    f = (f0 + (f1 - f0) * np.minimum(1, t / (dur * 0.8))) * (1 + vib * np.sin(2 * np.pi * 6 * t))
    return norm(osc(f, "tri") * fade(np.ones(len(t)), 0.02, 0.07))


def dizzy(dur=0.7):
    """晕乎乎的下行颤音。"""
    t = _t(dur)
    f = (900 - 380 * t / dur) * (1 + 0.07 * np.sin(2 * np.pi * 7 * t))
    return norm(osc(f, "tri") * fade(np.ones(len(t)), 0.02, 0.15))


def power_up(dur=0.35):
    t = _t(dur)
    return norm(osc(200 * (4.5 ** (t / dur)), "tri") * fade(np.ones(len(t)), 0.01, 0.08))


def bubbles(dur, rate=14.0, lo=500.0, hi=1400.0, seed=0):
    """一串小气泡；lo/hi 调低就是咕嘟咕嘟的液体声。"""
    rng = np.random.default_rng(seed)
    out = np.zeros(_n(dur + 0.1), np.float32)
    for _ in range(int(dur * rate)):
        f = rng.uniform(lo, hi)
        place(out, sweep(f, f * 2.0, 0.035, tau=0.011), rng.uniform(0, dur), rng.uniform(0.4, 1.0))
    return norm(fade(out, 0.05, 0.12))


def rain(dur, seed=0):
    rng = np.random.default_rng(seed)
    out = 0.35 * band_noise(dur, 1200, 9000, seed=seed)
    for _ in range(int(dur * 45)):
        place(out, band_noise(0.01, 2500, 7000, seed=int(rng.integers(1e6))) * env(_n(0.01), 0.0015, 0.0002),
              rng.uniform(0, dur - 0.02), rng.uniform(0.2, 0.9))
    return norm(fade(out, 0.35, 0.45))


def wind(dur, seed=0):
    t = _t(dur)
    y = band_noise(dur, 90, 650, seed=seed) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.45 * t + 1.0))
    return norm(fade(y, 0.4, 0.5))


def shimmer(dur, seed=0):
    """香气、魔法、发光：几根高频正弦带颤动，逐渐变亮。"""
    rng = np.random.default_rng(seed)
    t = _t(dur)
    y = np.zeros(len(t))
    for _ in range(6):
        f = rng.uniform(2200, 5200)
        y += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(6, 11) * t))
    return norm(y * np.linspace(0.15, 1, len(t)) * fade(np.ones(len(t)), 0.05, 0.25))


def tick_tock(dur, i0=0.22, i1=0.07):
    """延时快进的钟表声，越走越快。"""
    out = np.zeros(_n(dur + 0.05), np.float32)
    tt, k = 0.0, 0
    while tt < dur:
        n = _n(0.02)
        f = 2500 if k % 2 == 0 else 1800
        place(out, osc(np.full(n, float(f))) * env(n, 0.003, 0.0002), tt)
        tt += i0 + (i1 - i0) * min(1.0, tt / dur)
        k += 1
    return norm(out)


def squelch(dur, seed=0):
    """软泥挤压「咕叽」。"""
    t = _t(dur)
    y = band_noise(dur, 140, 900, seed=seed) * (0.5 + 0.5 * np.sin(2 * np.pi * 5.5 * t) ** 2)
    y += 0.5 * osc(110 + 40 * np.sin(2 * np.pi * 3 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 5.5 * t + 1))
    return norm(fade(y, 0.08, 0.15))
