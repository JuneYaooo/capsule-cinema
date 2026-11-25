"""Composite the performance, set and timed palette at 1080 × 1920."""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
FONTS = Path('/System/Library/Fonts/Supplemental')


def title_layer(look, count, caption):
    layer = Image.new('RGBA', (W, 490))
    pen = ImageDraw.Draw(layer)
    for i in range(count):
        x = 287 + 251*i
        pen.ellipse((x-73, 198, x+73, 344), fill=look['colors'][i])
        if i < min(2, count):
            pen.text((x+119, 269), '+', font=ImageFont.truetype(str(FONTS/'Arial Bold.ttf'), 74), fill='#433B37', anchor='mm')
    if caption:
        for line, size, file, y in [(caption[1], 40, 'Arial Unicode.ttf', 389), (caption[2], 41, 'Arial.ttf', 445)]:
            pen.text((W//2, y), line, font=ImageFont.truetype(str(FONTS/file), size),
                     anchor='mm', fill='white', stroke_width=1, stroke_fill=(64,53,45,200))
    return np.array(layer)


def render(params, target):
    video = cv2.VideoCapture(params['performance'])
    masks = cv2.VideoCapture(params['matte'])
    room = cv2.imread(params['room'])
    if room is None or not video.isOpened() or not masks.isOpened():
        raise ValueError('Missing room, matte, or performance')
    # Retain the reference inset and floor contact under the shoes.
    stage = np.zeros((H,W,3), np.uint8)
    stage[86:1834,48:1032] = cv2.resize(room,(984,1748),interpolation=cv2.INTER_CUBIC)
    floor = np.clip((np.arange(H,dtype=np.float32)-1460)/160,0,1)[:,None]
    command = ['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
               '-i',params['performance'],'-map','0:v','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','17',
               '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(target)]
    from product_view import panel, draw_product, look_label
    cards = {i: panel(look["product"], look["colors"]) for i, look in enumerate(params["looks"]) if "product" in look}
    tag = look_label() if cards else None
    fitting = None
    if params.get("tryon_assets"):
        from knit_tryon import KnitTryOn
        fitting = KnitTryOn(params["tryon_assets"],params["looks"])
    cache = {}
    with subprocess.Popen(command,stdin=subprocess.PIPE) as writer:
        frame = 0
        while True:
            ok, src = video.read()
            if not ok:
                break
            ok, mask = masks.read()
            if not ok:
                raise ValueError('Matte is shorter than the performance')
            src = cv2.resize(src,(W,H),interpolation=cv2.INTER_AREA)
            matte = cv2.resize(mask[:,:,0],(W,H),interpolation=cv2.INTER_LINEAR).astype(np.float32)/255
            alpha = np.maximum(matte,floor)
            out = cv2.blendLinear(src, stage, alpha, 1-alpha)
            t = frame/FPS
            index = max(i for i, item in enumerate(params['looks']) if t >= item['start'])
            look = params['looks'][index]
            if fitting is not None:
                fitting.apply(out,src,stage,frame,index)
            count = sum(t >= at for at in look['reveals'])
            caption = next((c for c in reversed(look['captions']) if t >= c[0]), None)
            key = (index, count, caption[0] if caption else None)
            if key not in cache:
                rgba = title_layer(look,count,caption)
                weight = rgba[:,:,3].astype(np.float32)/255
                cache[key] = (cv2.cvtColor(rgba,cv2.COLOR_RGBA2BGR),weight)
            ink,weight = cache[key]
            out[:490] = cv2.blendLinear(ink,out[:490],weight,1-weight)
            if index in cards:
                start, end = look["start"], look["demo_start"]
                if t < end:
                    draw_product(out, cards[index], (t-start)/(end-start))
                else:
                    out[510:569,68:269] = tag
            writer.stdin.write(out.tobytes())
            frame += 1
        writer.stdin.close()
        if writer.wait():
            raise RuntimeError('Encoding failed')
    video.release()
    masks.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument('--dry-run',action='store_true')
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    dest = out/'毛衣多巴胺配色.mp4'
    if not args.dry_run:
        render(json.loads(Path(args.params).read_text()),dest)
    artifacts = [] if args.dry_run else [dict(category='final_video',path=str(dest),title=args.topic)]
    (out/'artifact_manifest.json').write_text(json.dumps(dict(artifacts=artifacts,final_video=str(dest)),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
