"""Pose-driven knit panels sampled from photographed garments, with parsing-based occlusion."""
from pathlib import Path
import json
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

def smoothstep(lo,hi,x):
    t=np.clip((x-lo)/(hi-lo),0,1)
    return t*t*(3-2*t)

def sample(im,x,y):
    return cv2.remap(im,x.astype('f'),y.astype('f'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)

def material(im,style,u,v,sleeve=False):
    # Coordinates below refer to the normalized 500 × 600 source photographs.
    u=np.clip(u,0,1);v=np.clip(v,0,1)
    if style==0:
        if sleeve:
            x=320+51*u+29*v
            y=240+268*v
        else:
            center=239-12*v
            side=2*u-1
            x=center+side*(74+9*v)
            # Source hair falls across the upper left front. Borrow only that obscured patch.
            x=np.where(side<0,center+(-side)*67,x)
            y=231+231*v
        return sample(im,x,y)
    if style==1:
        if sleeve:
            x=145-64*v+(u-.5)*24
            y=199+253*v
        else:
            x=249+(2*u-1)*(86+32*smoothstep(0,.24,v))
            y=166+290*v
        return sample(im,x,y)
    if sleeve:
        x=310+34*u+12*np.sin(v*np.pi)
        y=69+102*v
    else:
        x=183+142*u
        y=366+143*v
    return sample(im,x,y)

class KnitTryOn:
    def __init__(self,root,looks):
        self.root=Path(root)
        points=np.array(json.loads((self.root/'pose.json').read_text()),dtype='f')[:,:,:2]*[540,960]
        self.pose=points.copy()
        for start,end in [(0,90),(90,133),(133,240),(240,296),(296,387),(387,len(points))]:
            self.pose[start:end]=gaussian_filter1d(points[start:end],.72,axis=0,mode='nearest')
        self.photos=[cv2.resize(cv2.imread(str(self.root/'cloth'/f'{i}.jpg')),(500,600)) for i in range(len(looks))]

    def apply(self,out,original,stage,i,style):
        points=self.pose[i]
        # Restrict all work to the moving upper body. Coordinates are in half-resolution pixels.
        x0=max(55,int(points[:6,0].min()-43));x1=min(500,int(points[:6,0].max()+43))
        y0=max(245,int(points[:6,1].min()-40));y1=min(760,int(points[6:8,1].max()+39))
        sl=np.s_[2*y0:2*y1,2*x0:2*x1]
        old=original[sl];dest=out[sl]
        yy,xx=np.mgrid[2*y0:2*y1,2*x0:2*x1].astype('f')*.5
        seg=cv2.imread(str(self.root/'parsing'/f'{i:03}.png'),0)
        if seg is None:raise ValueError(f'Missing clothing parsing for frame {i}')
        lab=cv2.resize(seg[y0-245:y1-245,x0-55:x1-55],(xx.shape[1],xx.shape[0]),interpolation=cv2.INTER_NEAREST)
        p,q=points[:2];s=(p+q)/2;hip=(points[6]+points[7])/2
        span=max(64,np.linalg.norm(q-p));tilt=(q[1]-p[1])/span
        neck=s[1]-span*.21
        hem=hip[1]+span*[.00,.055,.145][style]
        if style==0 and i>=90:hem-=.095*span
        v=(yy-neck-(xx-s[0])*tilt)/(hem-neck)
        mid=s[0]+(hip[0]-s[0])*np.clip(v,0,1)
        half=span*([.57,.61,.64][style]+.045*np.sin(np.pi*np.clip(v,0,1))-.012*smoothstep(.8,1,v))
        dx=(xx-mid)/half;u=.5+.50*dx
        top=.018+.094*np.abs(dx)**2
        collar=[.15,.085,.235][style]*np.maximum(0,1-np.abs(dx)/[.42,.39,.39][style])
        bottom=1-.019*dx**2+.006*np.sin(6*dx)
        body=(np.abs(dx)<1)&(v>=np.maximum(top,collar))&(v<bottom)
        # Bind torso texture to the shoulder/hip frame, with subtle fold displacement.
        u_tex=u+.009*np.sin(10*v+4*dx)*np.sin(np.pi*np.clip(u,0,1))
        cloth=material(self.photos[style],style,u_tex,(v-.05)/.95)
        cover=body.copy()
        for side,(a,b,c) in enumerate([(points[0],points[2],points[4]),(points[1],points[3],points[5])]):
            lengths=[np.linalg.norm(b-a),np.linalg.norm(c-b)]
            total=sum(lengths)
            best=np.full(xx.shape,np.inf,dtype='f');across=np.zeros_like(xx);along=across.copy()
            for j,(start,end) in enumerate([(a,b),(b,c)]):
                vector=end-start;length=max(np.linalg.norm(vector),1)
                vx,vy=vector/length
                ax,ay=xx-start[0],yy-start[1]
                distance=ax*vx+ay*vy
                proj=np.clip(distance,0,length)
                lateral=-vy*ax+vx*ay
                d=np.hypot(distance-proj,lateral)
                keep=d<best
                best=np.minimum(best,d)
                across=np.where(keep,lateral,across)
                t=(proj+(lengths[0] if j else 0))/max(total,1)
                along=np.where(keep,t,along)
            radius=span*([.157,.147,.173][style] +.038*np.sin(np.pi*along)-.051*smoothstep(.77,1,along))
            # A flat cuff rather than a rounded mitten at the wrist.
            forward=(c-b)/max(lengths[1],1)
            beyond=(xx-c[0])*forward[0]+(yy-c[1])*forward[1]
            sleeve=(best<radius)&(beyond<span*.015)
            # The shoulder panel overlaps the sleeve seam until the arm clears the torso.
            use=sleeve&(~body | (along>.40))
            fabric=material(self.photos[style],style,.5+across/(2*radius),along,True)
            light=(1-.16*(np.minimum(best/radius,1)**2))[:,:,None]
            cloth[use]=(fabric*light).astype('uint8')[use]
            cover |= sleeve
        # Cover original hems and side seams during large differences in pose.
        if style==1 and i>=240:
            blue=(old[:,:,0].astype('f')>old[:,:,2].astype('f')+10)&(old[:,:,0]>105)
            tails=blue&(np.abs(dx)<.90)&(v>.72)&(v<1.10)&(lab==4)
            columns=np.where(tails.any(axis=0))[0]
            if len(columns)>12:
                bottom_y=y0+tails[:,columns].argmax(axis=0)*.5
                hemline=np.interp(np.arange(xx.shape[1]),columns,bottom_y)
                hemline=gaussian_filter1d(hemline,8)
                cover &= ~((yy>=hemline[None,:])&(np.abs(dx)<1.02))
        oldshirt=(lab==4)&(v>.07)&(v<1.22)
        extra=oldshirt&(~cover)
        # Remove the previous silhouette where it protrudes beyond the fitted knit.
        outside=extra & ((np.abs(dx)>.94)|(v>1)) & (yy<hem+span*.28)
        if style==0 and i>=90:
            outside &= v<1
        if style==1:
            # Recover the old flared cuff even when the parser labels it as an arm.
            b,g,r=cv2.split(old.astype('f'))
            original_orange=(r>g*1.28)&(g>b*1.25)&(r>85)
            outside |= original_orange & (~cover) & (np.abs(dx)>.85) & (lab!=11) & (lab!=2)
        repair=cv2.GaussianBlur(outside.astype('f'),(0,0),1.4)
        dest[:]=cv2.blendLinear(stage[sl],dest,repair,1-repair)
        # The photograph supplies the knit surface, while a ribbed neckline defines the cut.
        if style==2:
            inner=(np.abs(dx)<.40)&(v<collar)&(v>.033)&(lab==4)
            cloth[inner]=[168,184,192] if i<387 else [58,65,79]
            cover|=inner
            rib=(np.abs(dx)<.43)&(v>=collar)&(v<collar+.033)
            cloth[rib]=np.clip(cloth[rib].astype('f')*(.91+.045*np.cos(yy[rib]*2))[:,None],0,255)

        # Hair, neck, hands, scarves and bags stay in front of the cloth.
        hands=np.zeros_like(cover)
        for wrist,elbow in [(points[4],points[2]),(points[5],points[3])]:
            direction=(wrist-elbow)/max(1,np.linalg.norm(wrist-elbow))
            proj=(xx-wrist[0])*direction[0]+(yy-wrist[1])*direction[1]
            hands |= (np.hypot(xx-wrist[0],yy-wrist[1])<span*.58)&(proj>-span*.05)
        protected=np.isin(lab,[1,2,3,8,11,16,17]) | (hands&np.isin(lab,[14,15]))
        # Restrict neck skin preservation to the natural collar opening.
        protected &= ~((lab==11)&(v>collar+.006)&(v>.036))
        # High-resolution dark hair strands at parsing boundaries.
        near_hair=cv2.dilate((lab==2).astype('uint8'),np.ones((11,11),'uint8'))>0
        gray=cv2.cvtColor(old,cv2.COLOR_BGR2GRAY)
        if style==1 and i>=240:
            blue=(old[:,:,0].astype('f')>old[:,:,2].astype('f')+10)&(old[:,:,0]>110)
            protected |= blue & (((v>.78)&(np.abs(dx)<1.02))|((v<.2)&(np.abs(dx)<.45)))
        protected |= near_hair&(gray<66)
        edge=cv2.GaussianBlur(cover.astype('f'),(0,0),1.35)
        occl=cv2.GaussianBlur(protected.astype('f'),(0,0),1.0)
        weight=edge*(1-occl)
        # Transfer the original knit's local fold shading only where cloth existed.
        luma=cv2.GaussianBlur(gray.astype('f'),(0,0),2.3)
        low=cv2.GaussianBlur(luma,(0,0),16)
        folds=cv2.GaussianBlur(np.clip((luma+36)/(low+36),.80,1.17),(0,0),1.5)
        fold_mask=oldshirt.astype('f')
        if style==2:
            # Cross-layer shadows from the reference's dark tank must not print through the knit.
            fold_mask*=smoothstep(115,165,luma)*.45
        shade=1+(folds-1)*cv2.GaussianBlur(fold_mask,(0,0),5.5)
        shade*=1-.055*np.minimum(np.abs(dx),1)**3
        cloth=np.clip(cloth*shade[:,:,None],0,255).astype('uint8')
        dest[:]=cv2.blendLinear(cloth,dest,weight,1-weight)
