"""Product lookbook frames and labels, on the same inset grid as the performance."""
from PIL import Image, ImageDraw, ImageFont, ImageOps
import cv2
import numpy as np
from pathlib import Path

FONT_DIR = Path('/System/Library/Fonts/Supplemental')

def panel(product, colors):
    page = Image.new('RGB',(984,1334),'#F4F0E8')
    photo = Image.open(product.get('hero',product['photo'])).convert('RGB')
    fitted = ImageOps.fit(photo,(984,1010),method=Image.Resampling.LANCZOS,centering=(.5,.46))
    page.paste(fitted,(0,0))
    draw = ImageDraw.Draw(page)
    def text(at,words,size,family='Arial.ttf',color='#332C2A'):
        draw.text(at,words,font=ImageFont.truetype(str(FONT_DIR/family),size),fill=color,anchor='lm')
    text((50,1073),'DAXUEN',35,'Arial Bold.ttf')
    draw.line((50,1114,934,1114),fill='#BEB7A9',width=2)
    text((50,1176),product['title'],52,'Arial Unicode.ttf')
    text((50,1263),product['name'],31)
    return cv2.cvtColor(np.array(page),cv2.COLOR_RGB2BGR)

def draw_product(frame, card, progress):
    # A restrained push-in keeps the texture readable and preserves the garment.
    h,w=1010,984
    crop=round(14*progress)
    frame[500:500+h,48:1032]=cv2.resize(card[crop:h-crop,crop:w-crop],(w,h))
    frame[1510:1834,48:1032]=card[h:]

def look_label():
    tag=Image.new('RGB',(201,59),'#F4F0E8')
    d=ImageDraw.Draw(tag)
    d.text((100,29),'配色示范',font=ImageFont.truetype(str(FONT_DIR/'Arial Unicode.ttf'),32),anchor='mm',fill='#332C2A')
    return cv2.cvtColor(np.array(tag),cv2.COLOR_RGB2BGR)
