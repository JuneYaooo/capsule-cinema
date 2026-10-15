#!/usr/bin/env python3
"""Render a narrated vertical forest fable using procedural vector artwork.

Usage: python scripts/render_storybook_episode.py RUN_DIR [--preview] [--sample]
Requires Pillow, numpy, aggdraw and ffmpeg. Timed scenes and per-scene MP3 files
are read from RUN_DIR/work; no network calls are made by this renderer.
Set STORYBOOK_SERIF_FONT and STORYBOOK_SANS_FONT to Chinese-capable font files
on systems without the default macOS fonts.
"""
from __future__ import annotations
import argparse, json, math, os, subprocess, wave
from functools import lru_cache
from pathlib import Path
import aggdraw
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W,H,S=1080,1920,2
INK='#263d36'; CREAM='#f2edda'; RED='#bd553d'; GOLD='#b9a777'
FONT=os.environ.get('STORYBOOK_SERIF_FONT','/System/Library/Fonts/Supplemental/Songti.ttc')
SANS=os.environ.get('STORYBOOK_SANS_FONT','/System/Library/Fonts/Hiragino Sans GB.ttc')

def rgb(c):return tuple(int(c[i:i+2],16) for i in (1,3,5))
def mix(a,b,t):return tuple(round(x*(1-t)+y*t) for x,y in zip(rgb(a),rgb(b)))
def ease(t):t=max(0,min(1,t));return t*t*(3-2*t)
def clamp(t,a=0,b=1):return max(a,min(b,t))

_ACTIVE_DRAW=None
_ACTIVE_IMAGE=None

def flush():
 global _ACTIVE_DRAW,_ACTIVE_IMAGE
 if _ACTIVE_DRAW is not None:_ACTIVE_DRAW.flush()
 _ACTIVE_DRAW=None;_ACTIVE_IMAGE=None

def drawing(im):
 global _ACTIVE_DRAW,_ACTIVE_IMAGE
 if _ACTIVE_IMAGE is not im:
  flush();_ACTIVE_DRAW=aggdraw.Draw(im);_ACTIVE_IMAGE=im
 return _ACTIVE_DRAW

class Art:
 def __init__(self,im,ox=0,oy=0,scale=1):self.im=im;self.x=ox;self.y=oy;self.s=scale
 def xy(self,x,y):return ((x*self.s+self.x)*S,(y*self.s+self.y)*S)
 def path(self,pts,fill,stroke=None,width=1):
  p=aggdraw.Path()
  for a in pts:
   if a[0]=='M':p.moveto(*self.xy(*a[1:]))
   elif a[0]=='L':p.lineto(*self.xy(*a[1:]))
   elif a[0]=='C':p.curveto(*sum((self.xy(*a[i:i+2]) for i in (1,3,5)),()))
   elif a[0]=='Q':pass
   elif a[0]=='Z':p.close()
  d=drawing(self.im);d.path(p,aggdraw.Brush(fill) if fill else None,aggdraw.Pen(stroke,width*S*self.s) if stroke else None)
 def sculpt(self,pts,fill,bounds):
  # Soft light over an exact vector mask gives paper puppets rounded volume.
  x0,y0,x1,y1=bounds
  flush()
  patch=sculpt_patch(tuple(pts),fill,tuple(bounds),round(self.s,4))
  px,py=self.xy(x0,y0)
  self.im.paste(patch,(round(px),round(py)),patch)

 def ellipse(self,box,fill,stroke=None,width=1):
  d=drawing(self.im);d.ellipse((*self.xy(*box[:2]),*self.xy(*box[2:])),aggdraw.Brush(fill) if fill else None,aggdraw.Pen(stroke,width*S*self.s) if stroke else None)
 def line(self,pts,color,width=1):self.path([('M',*pts[0])]+[('L',*p) for p in pts[1:]],None,color,width)
 def text(self,t,x,y,size=24,color=INK,font=FONT,anchor='mm'):
  flush()
  patch,off=text_patch(t,font,round(size*self.s*S),color,anchor)
  px,py=self.xy(x,y);self.im.paste(patch,(round(px+off[0]),round(py+off[1])),patch)

@lru_cache(512)
def text_patch(text,font,size,color,anchor):
 f=getfont(font,size);box=f.getbbox(text,anchor=anchor);pad=3
 patch=Image.new('RGBA',(box[2]-box[0]+pad*2,box[3]-box[1]+pad*2))
 ImageDraw.Draw(patch).text((pad-box[0],pad-box[1]),text,font=f,fill=color,anchor=anchor)
 return patch,(box[0]-pad,box[1]-pad)

@lru_cache(None)
def getfont(path,size):return ImageFont.truetype(path,size)

@lru_cache(256)
def sculpt_patch(pts,color,bounds,scale):
 x0,y0,x1,y1=bounds;w=max(1,math.ceil((x1-x0)*scale*S));h=max(1,math.ceil((y1-y0)*scale*S))
 mask=Image.new('L',(w,h));a=Art(mask,-x0*scale,-y0*scale,scale);a.path(pts,255)
 yy,xx=np.mgrid[0:h,0:w];u=xx/max(1,w-1);v=yy/max(1,h-1)
 shade=13*np.exp(-((u-.27)/.28)**2)-25*(u**2)-7*v
 c=np.array(rgb(color));arr=np.clip(c[None,None,:]+shade[:,:,None],0,255).astype('uint8')
 flush();result=Image.fromarray(arr).convert('RGBA');result.putalpha(mask);return result

def orb(a,box,color):
 x0,y0,x1,y1=box;k=.5522848;cx=(x0+x1)/2;cy=(y0+y1)/2;rx=(x1-x0)/2;ry=(y1-y0)/2
 pts=[('M',cx+rx,cy),('C',cx+rx,cy+k*ry,cx+k*rx,cy+ry,cx,cy+ry),('C',cx-k*rx,cy+ry,cx-rx,cy+k*ry,cx-rx,cy),('C',cx-rx,cy-k*ry,cx-k*rx,cy-ry,cx,cy-ry),('C',cx+k*rx,cy-ry,cx+rx,cy-k*ry,cx+rx,cy),('Z',)]
 a.sculpt(pts,color,box)

@lru_cache(None)
def background(mode='day'):
 yy,xx=np.mgrid[0:H,0:W];v=np.clip(yy/H,0,1)
 top=np.array(rgb('#9daea0' if mode!='night' else '#30483f'));bot=np.array(rgb('#e0e1ce' if mode!='night' else '#90a28a'))
 arr=top[None,None,:]*(1-v[:,:,None])+bot[None,None,:]*v[:,:,None]
 light=np.exp(-((xx-W*.55)**2/(W*.65)**2+(yy-H*.4)**2/(H*.7)**2))*12
 rng=np.random.default_rng(13);grain=rng.normal(0,.8,(H,W,1))
 arr=np.clip(arr+light[:,:,None]+grain,0,255).astype('uint8');im=Image.fromarray(arr)
 a=Art(im)
 # Receding curved hills, bamboo silhouettes, and clouds.
 for i,col in enumerate(['#a7b9a8','#b4c2ad','#c5ccb7']):
  y=615+i*52
  a.path([('M',0,y+65),('C',60,y-90,125,y-30,185,y+24),('C',265,y-155,345,y-150,540,y+35),('L',540,850),('L',0,850),('Z',)],col)
 for x in [21,45,487,519]:
  a.path([('M',x,718),('C',x-8,515,x+7,343,x-9,240)],None,'#a5b29e',1.2)
  for j in range(7):
   y=335+j*49
   a.path([('M',x,y),('C',x-35,y-29,x-39,y-60,x,y-14),('C',x+25,y-48,x+40,y-42,x,y)],'#a5b29e')
 a.path([('M',0,790),('C',160,765,380,800,540,780),('L',540,960),('L',0,960),('Z',)],'#dedfca')
 a.line([(0,808),(540,808)],'#c5cbb7',.6)
 flush();return im

@lru_cache(64)
def shadow_patch(w,h):
 pad=20;layer=Image.new('RGBA',(round((w+pad)*4),round((h+pad)*4)))
 d=ImageDraw.Draw(layer);d.ellipse((pad*2,pad*2,(pad+2*w)*2,(pad+2*h)*2),fill=(44,64,43,38))
 return layer.filter(ImageFilter.GaussianBlur(9))

def shadow(im,x,y,w=70,h=9):
 flush();layer=shadow_patch(w,h);im.paste(layer,(round((x-w-20)*S),round((y-h-20)*S)),layer)

def leaf(a,x,y,s=1,angle=0,col='#6a8061'):
 a.path([('M',x,y),('C',x-10*s,y-19*s,x+8*s,y-30*s,x+24*s,y-30*s),('C',x+20*s,y-10*s,x+6*s,y-2*s,x,y),('Z',)],col)
 a.line([(x,y),(x+19*s,y-25*s)],'#a4b185',.5)

def fruit(a,x,y,r=16,seed=0):
 col=['#c56946','#c89d4e','#a84e39'][seed%3]
 orb(a,(x-r,y-r*.85,x+r,y+r),col)
 a.path([('M',x-r*.62,y+r*.2),('C',x-r*.8,y-r*.65,x-r*.1,y-r*.78,x+r*.3,y-r*.62)],None,mix(col,'#f4d599',.4),max(.6,r*.025))
 a.path([('M',x-6,y-r*.4),('C',x-12,y-r*.9,x-2,y-r*.9,x+2,y-r*.7)],None,'#efd294',1.1)
 a.line([(x,y-r*.7),(x+2,y-r*1.2)],'#746943',2)
 leaf(a,x+1,y-r,.34)

def hat(a,x,y,s=1):
 a.path([('M',x-92*s,y+11*s),('C',x-51*s,y+2*s,x-14*s,y-8*s,x-3*s,y-33*s),('L',x+5*s,y-33*s),('C',x+22*s,y-4*s,x+58*s,y+3*s,x+93*s,y+11*s),('C',x+30*s,y+20*s,x-42*s,y+20*s,x-92*s,y+11*s),('Z',)],'#c7bd88')
 for j in range(-8,9):
  a.path([('M',x+j*.65*s,y-27*s),('C',x+j*2*s,y-5*s,x+j*7*s,y+8*s,x+j*10*s,y+12*s)],None,'#a59e73',.55)
 a.path([('M',x-89*s,y+11*s),('C',x-28*s,y+19*s,x+27*s,y+20*s,x+92*s,y+11*s)],None,'#8b9169',1)
 a.ellipse((x-5*s,y-35*s,x+5*s,y-29*s),'#b7ac76')

def monkey(im,x,y,s,t,pose='walk',robe='#e5dfc7',withhat=True):
 # Root at feet. Independent tail, feet, cloth, hands, face and hat animation.
 a=Art(im,x,y,s);walk=math.sin(t*9);bob=abs(math.sin(t*9))*2 if pose=='walk' else math.sin(t*2)*1.4
 a.path([('M',28,-96),('C',100,-90,101,-17,66,-25),('C',47,-33,64,-61,78,-44)],None,'#a69773',6)
 for side in [-1,1]:
  step=walk*7*side if pose=='walk' else 0
  a.path([('M',side*13,-39),('L',side*15+step,-7),('L',side*26+step,-2)],None,'#7b7860',4)
  a.ellipse((side*15+step-10,-6,side*15+step+13,0),'#8e8e70')
 a=Art(im,x,y+bob,s)
 # Folded fabric silhouette.
 a.sculpt([('M',-12,-216),('C',-43,-209,-39,-142,-64,-28),('C',-36,-18,10,-21,49,-28),('C',33,-102,39,-182,14,-216),('Z',)],robe,(-65,-218,51,-18))
 a.path([('M',-7,-213),('C',-24,-166,-23,-91,-29,-26),('L',-50,-27),('C',-34,-117,-34,-188,-7,-213)],mix(robe,'#a6a88f',.42))
 a.path([('M',9,-210),('C',25,-161,3,-105,18,-24),('L',37,-26),('C',13,-119,40,-181,9,-210)],mix(robe,'#ffffff',.36))
 for i in range(8):
  x0=-30+i*8
  a.path([('M',x0*.3,-190),('C',x0,-132,x0+math.sin(i)*10,-70,x0,-27)],None,mix(robe,'#8c987c',.25),.6)
 # Coral scarf tails.
 a.path([('M',-13,-212),('C',0,-200,12,-204,19,-211),('L',11,-190),('C',7,-151,21,-140,22,-115),('L',10,-120),('C',3,-151,-1,-170,-3,-191),('L',-17,-206),('Z',)],'#bc624b')
 # Voluminous sleeves and tiny hands.
 reach=14*math.sin(t*2) if pose=='talk' else 0
 a.path([('M',-22,-202),('C',-54,-186,-68,-144,-47,-134),('C',-25,-141,-12,-167,4,-174+reach),('L',-3,-187+reach),('C',-16,-185,-23,-173,-30,-167),('Z',)],mix(robe,'#f5f0dd',.25))
 a.ellipse((-1,-189+reach,12,-176+reach),'#d5b994')
 a.path([('M',20,-199),('C',57,-178,53,-152,20,-154),('L',7,-177),('C',28,-173,29,-183,20,-199)],mix(robe,'#acb19c',.18))
 a.ellipse((0,-181,12,-169),'#dac2a0')
 # Ears, fur head, muzzle, eyes.
 a.ellipse((-39,-261,-18,-232),'#afa588');a.ellipse((18,-261,39,-232),'#afa588')
 a.ellipse((-35,-256,-22,-237),'#d6b396');a.ellipse((22,-256,35,-237),'#d6b396')
 orb(a,(-29,-278,29,-215),'#a59a77')
 a.ellipse((-26,-266,2,-226),'#e8d6b0');a.ellipse((-2,-266,26,-226),'#e8d6b0')
 orb(a,(-20,-247,20,-216),'#e8d6b0')
 a.path([('M',-28,-264),('C',-16,-283,10,-282,28,-264),('C',15,-267,8,-261,0,-259),('C',-5,-264,-17,-270,-28,-264)],'#726f52')
 blink=(int(t*30)%109)>104
 for ex in [-12,12]:
  if blink:a.line([(ex-4,-245),(ex+4,-245)],INK,1.4)
  else:
   a.ellipse((ex-4,-250,ex+4,-240),'#fff5d9');a.ellipse((ex-1,-249,ex+3,-241),'#283d30');a.ellipse((ex,-248,ex+1,-246),'#ffffff')
  a.path([('M',ex-5,-254),('C',ex-1,-257,ex+3,-257,ex+5,-253)],None,'#6c6950',1.2)
 a.ellipse((-19,-237,-9,-231),'#d4a185');a.ellipse((9,-237,19,-231),'#d4a185')
 a.path([('M',-3,-234),('L',0,-232),('L',3,-234)],None,'#a27c5c',1)
 a.path([('M',-6,-227),('C',-1,-223,4,-224,7,-228)],None,'#7e6651',1.2)
 if withhat:hat(a,0,-272,.87)
 else:
  a.path([('M',-8,-274),('C',-13,-293,4,-296,6,-279),('C',11,-287,16,-282,12,-273)],'#777656')

@lru_cache(None)
def furball():
 im=Image.new('RGBA',(400,360));a=Art(im,100,100,1)
 a.ellipse((-60,-53,60,50),'#e1e1cf');a.ellipse((-56,-57,57,44),'#f3f0df')
 rng=np.random.default_rng(6)
 for _ in range(470):
  ang=rng.uniform(0,math.tau);rad=rng.uniform(.55,1);x=math.cos(ang)*56*rad;y=math.sin(ang)*49*rad
  a.path([('M',x,y),('C',x+math.cos(ang)*5,y+3,x+math.cos(ang)*10,y+8,x+math.cos(ang)*15,y+11)],None,['#f9f6e8','#eeeedd','#e4e5d3'][int(rng.integers(3))],.7)
 flush();return im

@lru_cache(32)
def scaled_fur(s):return furball().resize((int(400*s),int(360*s)),Image.Resampling.LANCZOS)

def spirit(im,x,y,s,t,mood='happy'):
 a=Art(im,x,y,s);bounce=math.sin(t*4)*3
 for side in [-1,1]:a.path([('M',side*18,-33),('L',side*18+math.sin(t*9)*side*3,-2),('L',side*24,-1)],None,'#686f50',2)
 f=scaled_fur(s)
 flush();im.paste(f,(int((x-100*s)*S),int((y-143*s+bounce)*S)),f)
 a=Art(im,x,y+bounce,s)
 a.path([('M',-38,-84),('C',-56,-93,-51,-108,-48,-116),('C',-43,-100,-35,-99,-27,-91)],'#5f6f51')
 a.path([('M',32,-85),('C',51,-91,53,-108,48,-116),('C',43,-98,37,-99,25,-92)],'#5f6f51')
 for ex in [-15,15]:
  a.ellipse((ex-5,-57,ex+5,-50),'#b38343');a.ellipse((ex-1,-57,ex+2,-50),'#334c37')
 a.path([('M',-5,-42),('C',0,-38,5,-38,9,-43)],None,'#7e6c4f',1.6)
 if mood=='shock':a.ellipse((-4,-43,4,-35),'#937d58')

@lru_cache(None)
def tree_asset():
 im=Image.new('RGBA',(760,1180));a=Art(im,180,550,1)
 a.path([('M',-153,0),('C',-87,-55,-99,-183,-88,-287),('C',-100,-363,-109,-404,-153,-440),('L',-135,-454),('C',-88,-438,-70,-400,-64,-369),('C',-40,-434,-58,-500,-44,-535),('L',5,-537),('C',-10,-471,20,-432,15,-371),('C',61,-397,91,-450,120,-470),('L',133,-451),('C',83,-367,48,-337,63,-259),('C',89,-145,64,-53,139,0),('Z',)],'#8b8c64')
 a.path([('M',-120,-2),('C',-53,-121,-65,-203,-64,-289),('C',-64,-368,-24,-434,-36,-526),('L',-13,-529),('C',-31,-417,3,-356,-13,-296),('C',-40,-156,-8,-71,11,-2)],'#a5a379')
 a.path([('M',47,-2),('C',11,-90,45,-168,23,-246),('C',5,-332,40,-365,84,-399),('C',55,-346,36,-318,54,-250),('C',81,-149,62,-73,102,-2)],'#727b58')
 for j in range(18):
  x=-90+j*11
  a.path([('M',x,0),('C',x-22,-105,x+25,-180,x*.42,-315)],None,'#767f5b',.65)
 a.ellipse((-64,-282,56,-116),'#65704e');a.ellipse((-54,-275,46,-124),'#394b36')
 a.path([('M',-40,-155),('C',-6,-171,26,-156,42,-149),('L',34,-131),('C',7,-120,-26,-127,-40,-139),('Z',)],'#bf984d')
 a.ellipse((-42,-154,39,-139),'#d1ae62')
 for x,y,s in [(-100,-440,1.5),(-37,-509,1.3),(95,-435,1.7),(44,-360,1.3),(-115,-70,1.1)]:
  leaf(a,x,y,s);leaf(a,x-3,y+7,s*.8)
 for x,y in [(-47,-130),(-19,-127),(13,-130)]:fruit(a,x,y,14,int(x))
 flush();return im

@lru_cache(32)
def scaled_tree(s):
 pic=tree_asset();return pic.resize((int(pic.width*s),int(pic.height*s)),Image.Resampling.LANCZOS)

def tree(im,x,y,s=1):
 pic=scaled_tree(s)
 flush();im.paste(pic,(int((x-180*s)*S),int((y-550*s)*S)),pic)

def mote(im,x,y,s,t,red=False):
 a=Art(im,x,y,s);c='#c08a63' if red else '#e8dfad'
 orb(a,(-20,-29,20,27),c)
 a.ellipse((9,-34,30,-11),mix(c,'#ffffe8',.1));a.ellipse((-9,-7,-4,-2),INK);a.ellipse((5,-7,10,-2),INK)
 a.path([('M',-4,7),('C',0,10,5,10,8,6)],None,'#998363',1)
 for side in [-1,1]:a.path([('M',side*17,5),('C',side*24,3,side*27,-7+math.sin(t*4)*4,side*31,-8)],None,'#b3a77f',1.8)
 a.ellipse((-8,-23,1,-15),'#f9f2d4')

def bacterium(im,x,y,s,t):
 a=Art(im,x,y,s)
 for j in range(10):
  z=j*math.tau/10;a.line([(math.cos(z)*23,math.sin(z)*23),(math.cos(z)*32,math.sin(z)*32)],'#87946a',2)
 a.ellipse((-25,-24,25,24),'#98a778')
 a.ellipse((-12,-7,-6,1),INK);a.ellipse((6,-7,12,1),INK)
 a.path([('M',-7,11),('C',-3,6,3,6,8,11)],None,'#4b6550',1.5)

def bubble(a,x,y,r=7):
 a.ellipse((x-r,y-r,x+r,y+r),None,'#ece9cd',1.1)
 a.path([('M',x-r*.55,y),('C',x-r*.6,y-r*.55,x,y-r*.65,x+r*.2,y-r*.6)],None,'#ffffff',.7)

def label(a,text,x,y,size=20,col=INK):a.text(text,x,y,size,col)

def particles(im,t):
 a=Art(im)
 for j in range(17):
  x=(j*97+math.sin(t*.4+j)*17)%540;y=290+(j*47-t*8)%475
  a.ellipse((x,y,x+1.2,y+1.2),'#edf0d6')

def make_frame(scene,t,dur,global_t=0):
 kind=scene['kind'];p=t/max(dur,.01);im=background('day').copy();a=Art(im)
 # A world rather than UI panels; atmospheric drifting specks and a horizon.
 particles(im,global_t)
 if kind in ['hook','legend','fruit','bubbles']:
  tree(im,357,790,.78)
  shadow(im,183,791,74);monkey(im,181+math.sin(t*.9)*5,791,.99,t,'walk')
  shadow(im,72,794,34);spirit(im,73,792,.46,t)
  if kind in ['hook','bubbles']:
   for j in range(10):
    u=(t*.42+j*.13)%1;bubble(a,347+math.sin(j*2+u*5)*26,666-u*150,3+u*6)
   if kind=='hook':
    a.text('？',183,455+math.sin(t*3)*4,60,RED)
    a.text('一口仙酿？',365,338,25,INK)
  if kind=='legend':
   a.ellipse((333,478,407,552),None,'#e7ddaa',2);mote(im,370,516,.67,t)
   a.line([(344,548),(319,579)],'#e7ddaa',3)
  if kind=='fruit':
   for j in range(5):
    q=(t*.6+j*.22)%1;x=221+q*123;y=593-86*math.sin(q*math.pi)+q*70
    fruit(a,x,y,10,j)
   a.text('藏一颗，再藏一颗',266,375,24,INK)
  if kind=='bubbles':a.text('我只是送水果的…',153,419,23,INK)
 elif kind=='yeast':
  # A gigantic fruit with a microscopic loupe populated by animated yeast.
  fruit(a,177,623,112,0)
  a.ellipse((232,412,476,656),'#a2b49a',CREAM,3)
  a.line([(438,620),(486,682)],'#e5dfc2',12)
  for j in range(5):mote(im,293+(j%2)*95+math.sin(t*1.8+j)*8,474+(j//2)*66,.8 if j<4 else .55,t+j)
  shadow(im,112,794,50);monkey(im,108,794,.63,t,'talk')
  a.text('放大看看',354,366,25,INK)
 elif kind=='sugar':
  mote(im,269,566,2.4,t)
  for j in range(6):
   q=(t*.36+j/6)%1;x=60+q*155;y=550+math.sin(q*math.pi*2+j)*37
   a.ellipse((x-11,y-11,x+11,y+11),'#f0d49a');a.text('糖',x,y,13,'#8c6f42')
  for j in range(8):
   q=(t*.32+j/8)%1;x=323+q*160;y=528-q*90+math.sin(j)*35
   bubble(a,x,y,5+q*7)
  a.path([('M',321,636),('C',380,650,394,642,454,650)],None,'#be9c57',3)
  a.ellipse((393,616,451,672),'#d2ae60');a.text('酒精',423,643,18,'#5c6042')
  a.text('果糖 · 葡萄糖',127,684,20);a.text('二氧化碳 ↑',425,393,20)
  spirit(im,270,797,.65,t)
 elif kind in ['myth','evidence']:
  shadow(im,270,790,140)
  monkey(im,184,791,1.15,t,'talk',robe='#b8c8c5')
  spirit(im,368,790,.88,t,'shock' if kind=='myth' else 'happy')
  if kind=='myth':
   a.text('仙酿？',279,380,52,RED)
   a.path([('M',210,411),('C',255,419,299,404,346,414)],None,RED,2)
   a.text('先把传说与事实分开',278,454,22)
  else:
   fruit(a,379,526,48,1)
   a.text('天然发酵的果实',361,408,24)
   a.text('观察到了',363,444,18,'#61765b')
   for j in range(4):bubble(a,369+j*9,507-(t*22+j*15)%58,4)
 elif kind=='danger':
  tree(im,272,818,1.04)
  for j in range(7):
   th=j*math.tau/7+t*.25;x=277+math.cos(th)*142;y=541+math.sin(th)*120
   if j%2:bacterium(im,x,y,.7+(.1*j),t+j)
   else:mote(im,x,y,.72,t+j,True)
  a.text('谁都可能来串门',271,349,25)
  spirit(im,93,805,.6,t,'shock')
 elif kind=='stop':
  shadow(im,277,794,117);monkey(im,167,795,1.1,t,'talk')
  spirit(im,385,794,.75,t,'shock')
  a.path([('M',320,568),('C',330,611,411,611,422,568),('Z',)],'#d5ccb1')
  a.ellipse((320,555,422,580),'#9c864f');a.ellipse((326,559,416,575),'#c3a25d')
  a.ellipse((316,501,425,610),None,RED,5)
  a.line([(334,519),(408,593)],RED,5)
  a.text('不入口',371,444,40,RED)
 elif kind=='end':
  tree(im,405,797,.7)
  monkey(im,135,793,.97,t,'walk')
  spirit(im,247,790,.63,t)
  for j in range(4):mote(im,154+j*70,445+math.sin(t*2+j)*17,.7,t+j)
  a.text('看不见，也在改变世界',268,352,25)
 elif kind=='punch':
  monkey(im,171+math.sin(t)*3,792,1.12,t,'walk')
  spirit(im,369,790,.88,t)
  mote(im,285,563,1.16,t)
  a.text('我只是路过',167,401,25)
  a.text('是我干的！',327,465,24,RED)
  leaf(a,457,744,1.5)
 # Camera movement is restricted to the illustrated stage, keeping captions stable.
 zoom={'hook':1.10,'legend':1.04,'fruit':1.06,'yeast':1.02,'sugar':1.05,'bubbles':1.09,'myth':1.02,'evidence':1.02,'danger':1.04,'stop':1.07,'end':1.02,'punch':1.04}[kind]+.025*ease(p)
 flush();stage=(0,260*S,W,818*S);world=im.crop(stage);sw,sh=world.size
 enlarged=world.resize((round(sw*zoom),round(sh*zoom)),Image.Resampling.BICUBIC)
 dx=(enlarged.width-sw)//2;dy=enlarged.height-sh
 im.paste(enlarged.crop((dx,dy,dx+sw,dy+sh)),(0,260*S));a=Art(im)
 # Header, chapter marker and generous typographic hierarchy.
 a.text('山 野 奇 遇',46,62,14,'#526c5c',anchor='lm')
 a.text('自然手记',494,62,13,'#526c5c',anchor='rm')
 a.line([(46,83),(494,83)],'#81977f',.6)
 title=scene['title'];size=39 if len(title)<=10 else 32
 a.text(title,270,153,size,INK)
 a.text(scene['subtitle'],270,207,19,'#536d58')
 # Small vermilion seal, reminiscent of a print rather than a dashboard badge.
 flush();ImageDraw.Draw(im).rounded_rectangle((483*S,112*S,506*S,158*S),radius=2*S,fill=RED)
 a.text('山',494.5,125,13,CREAM);a.text('记',494.5,145,13,CREAM)
 # Narration captions: short balanced chunks, paced against their own audio.
 chunks=scene.get('captions',[])
 if not chunks:
  import re
  chunks=[c for c in re.split('[，。？！]',scene['text']) if c]
 weights=[len(c)+1 for c in chunks];total=sum(weights);target=p*total;acc=0;cap=chunks[-1]
 for c,w in zip(chunks,weights):
  acc+=w
  if target<acc:cap=c;break
 lines=[cap] if len(cap)<=17 else [cap[:len(cap)//2],cap[len(cap)//2:]]
 for j,line in enumerate(lines):a.text(line,270,859+j*29,23,INK,font=SANS)
 a.text(f'{scene["id"]+1:02d}',47,926,13,'#72846d',font=SANS)
 a.line([(72,926),(494,926)],'#bac4ae',.8)
 a.line([(72,926),(72+422*p,926)],'#71866b',1.5)
 flush();return im

def synth_score(scenes,root):
 # Original, sparse pentatonic plucked accompaniment and event accents.
 sr=44100;duration=sum(s['duration'] for s in scenes);n=round(duration*sr);out=np.zeros(n,dtype=np.float64)
 rng=np.random.default_rng(71)
 def pluck(start,f,d=.6,amp=.016):
  k=min(int(d*sr),n-int(start*sr));
  if k<=0:return
  tt=np.arange(k)/sr;sig=np.sin(2*math.pi*f*tt)+.35*np.sin(2*math.pi*f*2.005*tt)+.14*np.sin(2*math.pi*f*3*tt)
  sig*=np.exp(-tt*7)*np.minimum(tt*200,1);out[int(start*sr):int(start*sr)+k]+=sig*amp
 notes=[293.66,440,493.88,587.33,659.25,440,392,329.63]
 for i,start in enumerate(np.arange(.1,duration,.6)):
  pluck(start,notes[(i*3+i//8)%len(notes)],amp=.009 if i%4 else .016)
  if i%4==0:pluck(start,146.83,1.8,.013)
 cursor=0
 for s in scenes:
  pluck(cursor+.08,880,.25,.025)
  if s['kind'] in ['fruit','bubbles','sugar']:
   for z in np.arange(.4,s['duration'],.8):pluck(cursor+z,450+rng.random()*650,.14,.02)
  if s['kind']=='stop':
   pluck(cursor+.15,146.83,1,.04);pluck(cursor+.18,155.56,.8,.025)
  cursor+=s['duration']
 out*=np.minimum(np.arange(n)/sr/.3,1)*np.minimum((n-np.arange(n))/sr/.6,1)
 with wave.open(str(root/'work/score.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(out,-1,1)*32767).astype('<i2').tobytes())

def render(root,preview=False,sample=False):
 for name in ['work','qa','release']:(root/name).mkdir(parents=True,exist_ok=True)
 for font in [FONT,SANS]:
  if not Path(font).is_file():raise FileNotFoundError(f'Chinese font unavailable: {font}; set STORYBOOK_SERIF_FONT and STORYBOOK_SANS_FONT')
 plan_path=root/'work/timed_scenes.json'
 if not plan_path.exists():plan_path=root/'storyboard.json'
 plan=json.loads(plan_path.read_text());scenes=plan['scenes']
 for s in scenes:s.setdefault('duration',len(s['text'])/4.4)
 if preview:
  for s in scenes:
   make_frame(s,min(2,s['duration']/2),s['duration'],s['id']*5).save(root/'qa'/f'scene_{s["id"]:02d}.jpg',quality=94)
  canvas=Image.new('RGB',(1080,1440),'#eeeeee')
  for i,s in enumerate(scenes):
   pic=Image.open(root/'qa'/f'scene_{s["id"]:02d}.jpg');pic.thumbnail((270,480));canvas.paste(pic,((i%4)*270,(i//4)*480))
  canvas.save(root/'qa/contact_sheet.jpg',quality=95);return
 if sample:scenes=scenes[:1]
 fps=plan.get('fps',30);out=root/('work/sample_silent.mp4' if sample else 'work/animation.mp4')
 cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE);elapsed=0;frame_index=0
 try:
  for s in scenes:
   end=round((elapsed+s['duration'])*fps)
   while frame_index<end:
    t=frame_index/fps-elapsed;im=make_frame(s,max(0,t),s['duration'],frame_index/fps)
    proc.stdin.write(im.tobytes());frame_index+=1
   elapsed+=s['duration'];print('rendered',s['id'],round(elapsed,2),flush=True)
 finally:proc.stdin.close()
 if proc.wait()!=0:raise RuntimeError('FFmpeg render failed')
 if sample:return
 # Decode each narration segment separately, concatenate samples for gapless audio.
 sr=44100;clips=[]
 for s in scenes:
  raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(root/'work/audio'/f'{s["id"]:02d}.mp3'),'-f','s16le','-ar',str(sr),'-ac','1','-'])
  data=np.frombuffer(raw,dtype='<i2');wanted=round(s['duration']*sr)
  clips.append(np.pad(data,(0,max(0,wanted-len(data))))[:wanted])
 with wave.open(str(root/'work/narration.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(np.concatenate(clips).astype('<i2').tobytes())
 synth_score(scenes,root)
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(out),'-i',str(root/'work/narration.wav'),'-i',str(root/'work/score.wav'),'-filter_complex','[1:a]loudnorm=I=-16:TP=-1.5:LRA=8,aresample=44100[voice];[voice][2:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]','-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(elapsed),'-movflags','+faststart',str(root/'release/猴儿酒.mp4')],check=True)
 # Export independently editable captions and cover.
 index=1;elapsed=0;lines=[]
 def ts(t):
  ms=round(t*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
 import re
 for s in scenes:
  chunks=[c for c in re.split('[，。？！]',s['text']) if c];weights=[len(c)+1 for c in chunks];total=sum(weights);cursor=elapsed
  for c,wgt in zip(chunks,weights):
   end=cursor+s['duration']*wgt/total;lines.append(f'{index}\n{ts(cursor)} --> {ts(end)}\n{c}\n');cursor=end;index+=1
  elapsed+=s['duration']
 (root/'release/字幕.srt').write_text('\n'.join(lines))
 make_frame(scenes[0],1.6,scenes[0]['duration']).save(root/'release/封面.jpg',quality=96)
 print('FINAL',root/'release/猴儿酒.mp4',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run_dir',type=Path);p.add_argument('--preview',action='store_true');p.add_argument('--sample',action='store_true');a=p.parse_args();render(a.run_dir.resolve(),a.preview,a.sample)
