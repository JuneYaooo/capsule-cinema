"""出片前后的检查工具（结果都写到 ../qa/）。

python3.12 qa.py safe [sh03,sh07]   预览帧叠上标题带（红 200–370）和字幕带（蓝 1320–1490）→ qa/safe.jpg
python3.12 qa.py contact            每个镜头均匀取 8 帧的联系表（看构图、连续性、穿帮）→ qa/contact.jpg
python3.12 qa.py frames sh09        一个镜头逐帧铺开（快动作镜头逐帧查：穿模、闪烁、物体尺寸）→ qa/frames_sh09.jpg
python3.12 qa.py subs               字幕段起点吸附表：估计时间、吸附后时间、差值（差值大的去听）
python3.12 qa.py probe [../final.mp4]
    成片体检：SAR、色彩标记、帧数、时长、响度/真峰值、音画偏移（对 mix.wav 做互相关）、
    文字里的零宽字符、按 bt709 显式解码抽一帧和合成帧比色差
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
QA = ROOT / "qa"
TITLE_BAND, SUB_BAND = (200, 370), (1320, 1490)


def timeline():
    return json.loads((WORK / "timeline.json").read_text())


def bands(im):
    """在图上叠红（标题带）蓝（字幕带）半透明条。"""
    s = im.size[0] / 1080
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    dr.rectangle((0, TITLE_BAND[0] * s, im.size[0], TITLE_BAND[1] * s), fill=(255, 0, 0, 70))
    dr.rectangle((0, SUB_BAND[0] * s, im.size[0], SUB_BAND[1] * s), fill=(0, 0, 255, 70))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def sheet(tiles, cols, w=180, out="sheet.jpg"):
    h = int(w * 16 / 9)
    rows = (len(tiles) + cols - 1) // cols
    sh = Image.new("RGB", (cols * w, rows * h), (30, 30, 30))
    for k, (label, im) in enumerate(tiles):
        t = im.resize((w, h))
        ImageDraw.Draw(t).text((5, 5), label, fill=(255, 255, 0))
        sh.paste(t, ((k % cols) * w, (k // cols) * h))
    QA.mkdir(parents=True, exist_ok=True)
    sh.save(QA / out, quality=85)
    print(QA / out, sh.size)


def cmd_safe(only=None):
    tiles = []
    for sh in timeline()["shots"]:
        if only and sh["id"] not in only:
            continue
        d = ROOT / "frames" / (sh["id"] + "_preview")
        if not d.is_dir():
            d = ROOT / "frames" / sh["id"]
        fs = sorted(d.glob("*.jpg"))
        for f in (fs[len(fs) // 2], fs[-1]) if len(fs) >= 2 else fs:
            tiles.append((f"{sh['id']} {f.stem}", bands(Image.open(f))))
    sheet(tiles, 16, out="safe.jpg")


def cmd_contact():
    tiles = []
    for sh in timeline()["shots"]:
        n = sh["f1"] - sh["f0"]
        for k in range(8):
            f = ROOT / "frames" / sh["id"] / f"f_{min(n - 1, round(k * (n - 1) / 7)):04d}.jpg"
            if f.exists():
                tiles.append((f"{sh['id']} {f.stem[2:]}", Image.open(f).convert("RGB")))
    sheet(tiles, 16, w=135, out="contact.jpg")


def cmd_frames(shot):
    fs = sorted((ROOT / "frames" / shot).glob("*.jpg"))
    sheet([(f.stem, Image.open(f).convert("RGB")) for f in fs], 12, w=150, out=f"frames_{shot}.jpg")


def cmd_subs():
    for s in timeline()["sentences"]:
        for c in s["chunks"][1:]:
            d = c["t0"] - c["est"]
            flag = "  ← 去听" if abs(d) > 0.6 else ""
            print(f"S{s['id']:02d} {c['sub'][:14]:14s} 估计 {c['est']:7.2f}  吸附 {c['t0']:7.2f}  差 {d:+.2f}{flag}")


def ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True).stderr


def pcm(path, sr=16000):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr),
                                   "-"])
    return np.frombuffer(raw, np.float32)


def cmd_probe(video):
    video = Path(video).resolve()
    tl = timeline()
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                                str(video)]))
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    nf = int(v.get("nb_frames", 0))
    print(f"视频 {v['codec_name']} {v['width']}x{v['height']} SAR {v.get('sample_aspect_ratio')}  "
          f"{v.get('color_primaries')}/{v.get('color_transfer')}/{v.get('color_space')} {v.get('color_range')}")
    print(f"帧数 {nf}（时间线 {tl['frames']}）  时长 {float(probe['format']['duration']):.3f}s  "
          f"音频 {a['codec_name']} {a['sample_rate']} Hz {a['channels']} ch")
    bad = []
    if v.get("sample_aspect_ratio") not in ("1:1", None):
        bad.append("SAR 不是 1:1（显示会变形）")
    if v.get("color_primaries") != "bt709" or v.get("color_space") != "bt709":
        bad.append("色彩标记不是 bt709（检查 h264_metadata bsf）")
    if nf and nf != tl["frames"]:
        bad.append("帧数和时间线不一致")
    txt = ff(["-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)[-1])
    lra = float(re.findall(r"LRA:\s+([\d.]+) LU", txt)[-1])
    pk = float(re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", txt)[-1])
    print(f"响度 {i:.1f} LUFS  LRA {lra:.1f}  真峰值 {pk:.1f} dBTP")
    if abs(i + 14) > 0.5 or pk > -1.0:
        bad.append("响度不在 −14±0.5 LUFS 或真峰值高于 −1 dBTP")
    mix = ROOT / "audio" / "mix.wav"
    if mix.exists():
        sr = 16000
        x, y = pcm(mix, sr), pcm(video, sr)
        n = min(len(x), len(y), 20 * sr)
        c = np.correlate(y[:n], x[sr:5 * sr], "valid")
        off = (int(np.argmax(c)) - sr) / sr * 1000
        print(f"音画偏移（成片音轨 vs mix.wav）{off:+.1f} ms")
        if abs(off) > 21:
            bad.append("音轨偏移超过半帧")
    zw = []
    for p in [WORK / "episode.py", *WORK.glob("*.txt"), *WORK.glob("*.md")]:
        if p.exists():
            s = p.read_text(encoding="utf-8")
            zw += [f"{p.name}:{k}" for k, ch in enumerate(s) if unicodedata.category(ch) == "Cf"]
    print("零宽/格式字符：", zw or "无")
    if zw:
        bad.append("文字里有零宽字符")
    g = tl["frames"] // 2
    ref = ROOT / "frames_final" / f"f_{g:05d}.jpg"
    if ref.exists():
        tmp = QA / "probe_decode.png"
        ff(["-y", "-i", str(video), "-vf", f"select=eq(n\\,{g}),scale=in_color_matrix=bt709:in_range=tv:out_range=full:"
            "flags=accurate_rnd+full_chroma_int,format=rgb24", "-vsync", "0", "-frames:v", "1", str(tmp)])
        d = np.asarray(Image.open(tmp).convert("RGB"), np.float32) - np.asarray(Image.open(ref).convert("RGB"), np.float32)
        print(f"第 {g} 帧按 bt709 解码 vs 合成帧：平均差 {d.reshape(-1, 3).mean(0).round(2)}  MAE {np.abs(d).mean():.2f}")
        tmp.unlink()
        if np.abs(d).mean() > 3:
            bad.append("解码颜色和合成帧差太多（检查编码的色彩矩阵）")
    print("\n" + ("全部通过" if not bad else "需要处理：\n- " + "\n- ".join(bad)))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "safe":
        cmd_safe(set(rest[0].split(",")) if rest else None)
    elif cmd == "contact":
        cmd_contact()
    elif cmd == "frames":
        cmd_frames(rest[0])
    elif cmd == "subs":
        cmd_subs()
    elif cmd == "probe":
        cmd_probe(rest[0] if rest else ROOT / "final.mp4")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
