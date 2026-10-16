"""把字叠到渲染帧上：常驻标题、章节牌、字幕（关键词说到时变黄弹一下）、跟物体走的标签、揭晓贴字。

python3.12 overlay.py [--jobs 8]          → ../frames_final/f_%05d.jpg，再和 ../audio/mix.wav 编码成 ../final.mp4
python3.12 overlay.py --frames 100,1200   → 只合成这几帧（全片帧号）到 ../qa/overlay/ 检查
输入：../frames/shXX/f_%04d.jpg，每个镜头取 0..f1-f0-1 帧（渲染时多出的一帧丢掉）。
字体：胶囊自带 ZCOOL 快乐体（字幕、牌子）和庆科黄油体（标题、贴字），都是 SIL OFL 1.1；
找字体的顺序：环境变量 PLUSH_FONT_SUB / PLUSH_FONT_TITLE → ../fonts/（开工时从胶囊 assets/fonts/ 拷过来）。
"""
import argparse
import bisect
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
sys.path.insert(0, str(WORK))
from episode import CHAPTERS, FPS, LABELS, STICKERS, TITLE  # noqa: E402

W, H = 1080, 1920


def find_font(env, name):
    for p in (os.environ.get(env), ROOT / "fonts" / name):
        if p and Path(p).is_file():
            return str(p)
    sys.exit(f"找不到字体 {name}：设置 {env}，或把它放进工程的 fonts/ 目录")


F_SUB = find_font("PLUSH_FONT_SUB", "ZCOOLKuaiLe-Regular.ttf")
F_TITLE = find_font("PLUSH_FONT_TITLE", "ZCOOLQingKeHuangYou-Regular.ttf")
INK = (58, 42, 32, 255)
CREAM = "#fff3d6"
HL = "#ffd23f"
SUB_Y, SUB_SIZE, SUB_MAXW = 1405, 68, 980    # 字幕带 1320–1490
TITLE_Y, TITLE_SIZE = 258, 104              # 标题带 200–370：上面标题，下面章节牌
CHAP_Y, CHAP_SIZE = 342, 40
LEAD = 2 / FPS                              # 字幕比人声早 2 帧
SAFE_Y = (400, 1290)                        # 标签只放在两条带之间

TL = json.loads((WORK / "timeline.json").read_text())
PX_PATH = WORK / "labels_px.json"
PX = json.loads(PX_PATH.read_text()) if PX_PATH.exists() else {}
SHOTS = TL["shots"]
F0S = [s["f0"] for s in SHOTS]
_cache = {}


# ------------------------------------------------------------------ 小工具

def rgba(c):
    if isinstance(c, tuple):
        return c
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def font(path, size):
    k = ("font", path, size)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(path, size)
    return _cache[k]


def ease_out_back(u, s=1.70158):
    u = min(1.0, max(0.0, u)) - 1
    return 1 + u * u * ((s + 1) * u + s)


def smoothstep(a, b, x):
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def paste(base, im, x, y):
    """带裁剪的 alpha 合成（x, y 可以是负数或越界）。"""
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, W - x), min(im.height, H - y)
    if ex > sx and ey > sy:
        base.alpha_composite(im, dest=(x + sx, y + sy), source=(sx, sy, ex, ey))


def paste_center(base, im, cx, cy, s=1.0, angle=0.0):
    if s <= 0.01:
        return
    if s != 1.0:
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.BICUBIC)
    if angle:
        im = im.rotate(angle, Image.BICUBIC, expand=True)
    paste(base, im, cx - im.width / 2, cy - im.height / 2)


def aa_layer(w, h, fn, ss=3):
    """超采样画形状再缩小，边缘抗锯齿。"""
    big = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    fn(ImageDraw.Draw(big), ss)
    return big.resize((w, h), Image.LANCZOS)


def line_img(runs, size, path=F_SUB, stroke=6, shadow=True):
    """一行分段着色的字（先画全部描边再画填色，段与段之间描边不会盖住字）。
    返回 (图, pad, 每段前进宽度)；图的中心就是文字中心。"""
    key = ("line", tuple(runs), size, path, stroke, shadow)
    if key in _cache:
        return _cache[key]
    f = font(path, size)
    advs = [f.getlength(t) for t, _ in runs]
    asc, desc = f.getmetrics()
    pad = stroke + max(8, size // 6)
    w, h = math.ceil(sum(advs)) + 2 * pad, asc + desc + 2 * pad
    base_y = pad + asc

    def draw(d, dy=0, fill=None, with_stroke=True):
        x = pad
        for (t, c), a in zip(runs, advs):
            if c is None:   # 留空位（关键词正在单独弹跳）
                pass
            elif with_stroke:
                d.text((x, base_y + dy), t, font=f, fill=fill or INK, anchor="ls", stroke_width=stroke,
                       stroke_fill=fill or INK)
            else:
                d.text((x, base_y + dy), t, font=f, fill=rgba(c), anchor="ls")
            x += a

    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw(ImageDraw.Draw(sh), dy=max(3, size // 14), fill=(30, 20, 12, 110))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(2, size // 20))))
    d = ImageDraw.Draw(im)
    if stroke:
        draw(d)
    draw(d, with_stroke=False)
    _cache[key] = (im, pad, advs)
    return _cache[key]


def pill(text, size, fill, text_fill=INK, text_stroke=0, outline=4, padx=24):
    """圆角药丸牌（带投影）。"""
    key = ("pill", text, size, fill, text_fill, text_stroke)
    if key in _cache:
        return _cache[key]
    f = font(F_SUB, size)
    ph, pw, m = round(size * 1.5), round(f.getlength(text) + 2 * padx), 14
    w, h = pw + 2 * m, ph + 2 * m + 6
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = aa_layer(w, h, lambda d, ss: d.rounded_rectangle((m * ss, (m + 6) * ss, (m + pw) * ss, (m + ph + 6) * ss),
                                                          radius=ph * ss / 2, fill=(30, 20, 12, 90)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
    im.alpha_composite(aa_layer(w, h, lambda d, ss: d.rounded_rectangle(
        (m * ss, m * ss, (m + pw) * ss, (m + ph) * ss), radius=ph * ss / 2, fill=rgba(fill), outline=INK,
        width=outline * ss)))
    ImageDraw.Draw(im).text((w / 2, m + ph / 2), text, font=f, fill=rgba(text_fill), anchor="mm",
                            stroke_width=text_stroke, stroke_fill=INK)
    _cache[key] = im
    return im


# ------------------------------------------------------------------ 时间表

def clean(sub):
    """去掉句末的逗号句号，句中逗号换成空格。"""
    s = sub.rstrip("，。、")
    return s.replace("，", "  ")


def build_subs():
    flat = [c for s in TL["sentences"] for c in s["chunks"]]
    items = []
    for k, c in enumerate(flat):
        t0 = c["t0"] - LEAD
        nxt = flat[k + 1]["t0"] - LEAD if k + 1 < len(flat) else TL["total"] + 1
        t1 = c["t1_voice"] + 0.35
        if nxt - t1 < 0.5 or k + 1 == len(flat):   # 间隙太短就直接接下一段；最后一句留到片尾
            t1 = nxt
        text = clean(c["sub"])
        marks, pos = [], 0
        for kw in sorted(c["kws"], key=lambda q: text.find(q["w"])):
            i = text.find(kw["w"], pos)
            if i >= 0:
                marks.append((i, i + len(kw["w"]), kw["t"]))
                pos = i + len(kw["w"])
        runs, pos = [], 0
        for a, b, kt in marks:
            if a > pos:
                runs.append((text[pos:a], None))
            runs.append((text[a:b], kt))
            pos = b
        if pos < len(text):
            runs.append((text[pos:], None))
        f = font(F_SUB, SUB_SIZE)
        size = SUB_SIZE if f.getlength(text) <= SUB_MAXW else int(SUB_SIZE * SUB_MAXW / f.getlength(text))
        items.append(dict(t0=t0, t1=min(t1, nxt), runs=runs, size=size))
    return items


SUBS = build_subs()
SUB_T0 = [s["t0"] for s in SUBS]
SENT = {s["id"]: s for s in TL["sentences"]}
CHAPS = sorted((SENT[sid]["chunks"][0]["t0"] - 0.1, text, color) for sid, (text, color) in CHAPTERS.items())


def shot_time(sh, spec, default):
    if spec is None:
        return default
    key, off = spec
    if key is None:
        return off
    return sh["events"][key] + off if key in sh["events"] else None


# ------------------------------------------------------------------ 各层

def draw_title(base, t):
    im, _, _ = line_img(TITLE, TITLE_SIZE, F_TITLE, stroke=9)
    paste_center(base, im, W / 2, TITLE_Y, 0.85 + 0.15 * ease_out_back(t / 0.35))


def draw_chapter(base, t):
    k = bisect.bisect_right([c[0] for c in CHAPS], t) - 1
    if k < 0:
        return
    t0, text, color = CHAPS[k]
    im = pill(text, CHAP_SIZE, color, text_fill="#ffffff", text_stroke=3, padx=26)
    paste_center(base, im, W / 2, CHAP_Y, 0.3 + 0.7 * ease_out_back((t - t0) / 0.3))


def draw_sub(base, t):
    k = bisect.bisect_right(SUB_T0, t) - 1
    if k < 0 or t >= SUBS[k]["t1"]:
        return
    it = SUBS[k]
    state = []   # 每段 (文字, 颜色, 弹跳进度)；说到的关键词变黄并往上跳一下，跳的时候原位留空
    for tx, kt in it["runs"]:
        if kt is None or t < kt - 0.05:
            state.append((tx, "#ffffff", None))
        else:
            u = (t - (kt - 0.05)) / 0.22
            state.append((tx, HL, u if u < 1 else None))
    im, pad, advs = line_img([(tx, None if u is not None else c) for tx, c, u in state], it["size"])
    left = W / 2 - im.width / 2
    paste(base, im, left, SUB_Y - im.height / 2)
    x = left + pad
    for (tx, c, u), a in zip(state, advs):
        if u is not None:
            w_im, _, _ = line_img([(tx, HL)], it["size"])
            j = math.sin(math.pi * u)
            paste_center(base, w_im, x + a / 2, SUB_Y - 14 * j, 1 + 0.1 * j)
        x += a


def draw_leader(base, a, b, s):
    x0, y0 = min(a[0], b[0]) - 16, min(a[1], b[1]) - 16
    w, h = int(max(a[0], b[0]) + 16 - x0) + 1, int(max(a[1], b[1]) + 16 - y0) + 1

    def fn(d, ss):
        p = [((a[0] - x0) * ss, (a[1] - y0) * ss), ((b[0] - x0) * ss, (b[1] - y0) * ss)]
        d.line(p, fill=INK, width=7 * ss)
        d.line(p, fill=rgba(CREAM), width=3 * ss)
        r = 8 * ss * min(1.0, s)
        d.ellipse((p[0][0] - r, p[0][1] - r, p[0][0] + r, p[0][1] + r), fill=rgba(CREAM), outline=INK,
                  width=3 * ss)
    paste(base, aa_layer(w, h, fn), x0, y0)


def draw_labels(base, sh, lf, t):
    for lb in LABELS.get(sh["id"], []):
        t_in, t_out = shot_time(sh, lb.get("t_in"), 0.0), shot_time(sh, lb.get("t_out"), 1e9)
        if t_in is None or t < t_in:
            continue
        s = ease_out_back((t - t_in) / 0.28) * (1 - smoothstep(t_out, t_out + 0.15, t))
        if s <= 0.01:
            continue
        ax, ay = PX[sh["id"]][lb["id"]][lf]
        im = pill(lb["text"], 44, lb.get("color", CREAM))
        dx, dy = lb.get("dx", 0), lb.get("dy", 0)
        cx = min(max(ax + s * dx, im.width / 2 + 10), W - im.width / 2 - 10)
        cy = min(max(ay + s * dy, SAFE_Y[0]), SAFE_Y[1])
        if dx or dy:
            draw_leader(base, (ax, ay), (cx, cy), s)
        paste_center(base, im, cx, cy, s)


def draw_stickers(base, sh, t):
    for st in STICKERS.get(sh["id"], []):
        t_in = shot_time(sh, st.get("t_in"), 0.0)
        if t_in is None or t < t_in:
            continue
        dt = t - t_in
        im, _, _ = line_img([(st["text"], st.get("color", "#ffc23f"))], st.get("size", 140), F_TITLE, stroke=11)
        ang = -12 * (1 - min(1.0, dt / 0.3)) + 6 * math.sin(12 * dt) * math.exp(-4 * dt)
        paste_center(base, im, st["x"], st["y"], ease_out_back(dt / 0.35), ang)


def compose(g):
    k = bisect.bisect_right(F0S, g) - 1
    sh = SHOTS[k]
    lf = g - sh["f0"]
    base = Image.open(ROOT / "frames" / sh["id"] / f"f_{lf:04d}.jpg").convert("RGBA")
    t, ts = g / FPS, lf / FPS
    draw_labels(base, sh, lf, ts)
    draw_stickers(base, sh, ts)
    draw_title(base, t)
    draw_chapter(base, t)
    draw_sub(base, t)
    return base.convert("RGB")


def missing_glyphs():
    """上屏文字里字体没有的字（会显示成方块）。返回 [(字体文件名, 文字, 缺的字)]。"""
    from fontTools.ttLib import TTFont
    cmaps = {p: TTFont(p, lazy=True).getBestCmap() for p in (F_SUB, F_TITLE)}
    texts = [(F_TITLE, "".join(t for t, _ in TITLE))]
    texts += [(F_SUB, t) for t, _ in CHAPTERS.values()]
    texts += [(F_SUB, lb["text"]) for lbs in LABELS.values() for lb in lbs]
    texts += [(F_TITLE, st["text"]) for sts in STICKERS.values() for st in sts]
    texts += [(F_SUB, "".join(t for t, _ in it["runs"])) for it in SUBS]
    out = []
    for path, text in texts:
        miss = sorted({c for c in text if not c.isspace() and ord(c) not in cmaps[path]})
        if miss:
            out.append((Path(path).name, text, "".join(miss)))
    return out


def missing_frames(gs):
    """要合成的全片帧号里，哪些镜头的渲染帧还没有。返回 {镜头: [镜头内帧号, ...]}。"""
    out = {}
    for g in gs:
        sh = SHOTS[bisect.bisect_right(F0S, g) - 1]
        if not (ROOT / "frames" / sh["id"] / f"f_{g - sh['f0']:04d}.jpg").exists():
            out.setdefault(sh["id"], []).append(g - sh["f0"])
    return out


def job(arg):
    g, out = arg
    compose(g).save(out, quality=95, subsampling=0)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    bad = missing_glyphs()
    for name, text, miss in bad:
        print(f"缺字：{name} 里没有「{miss}」——{text}")
    if bad:
        sys.exit("上屏文字里有字体缺的字，会显示成方块：改成汉字（例如 氧气、二氧化碳、摄氏度）再合成")
    if args.frames:
        odir = ROOT / "qa" / "overlay"
        todo = [(int(g), odir / f"g_{int(g):05d}.jpg") for g in args.frames.split(",")]
    else:
        odir = ROOT / "frames_final"
        todo = [(g, odir / f"f_{g:05d}.jpg") for g in range(TL["frames"])]
    stale = [sid for sid in LABELS if sid in {s["id"] for s in SHOTS} and sid not in PX]
    if stale:
        sys.exit(f"这些镜头有标签但没有投影坐标：{stale}。先跑 $BLENDER -b --factory-startup -P scene3d/project_labels.py")
    miss = missing_frames([g for g, _ in todo])
    for sid, fs in miss.items():
        print(f"缺帧：{sid} 少 {len(fs)} 帧（第一张 f_{fs[0]:04d}.jpg）")
    if miss:
        sys.exit("先把这些镜头正式渲完（scene3d/render_all.py --only " + ",".join(miss) + "），再合成")
    odir.mkdir(parents=True, exist_ok=True)
    with Pool(args.jobs) as pool:
        for i, _ in enumerate(pool.imap_unordered(job, todo, chunksize=8)):
            if (i + 1) % 250 == 0:
                print(f"composited {i + 1}/{len(todo)}", flush=True)
    print("composited", len(todo), "->", odir, flush=True)
    if args.frames:
        return
    out = ROOT / "final.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(odir / "f_%05d.jpg"),
        "-i", str(ROOT / "audio" / "mix.wav"),
        "-vf", "scale=in_range=full:in_color_matrix=bt601:out_range=tv:out_color_matrix=bt709:"
               "flags=lanczos+accurate_rnd+full_chroma_int,format=yuv420p,setsar=1",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-tune", "animation",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)], check=True)
    print("encoded ->", out, flush=True)


if __name__ == "__main__":
    main()
