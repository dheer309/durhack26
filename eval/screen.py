"""Deterministic screen-to-camera simulation; not physical camera evidence."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from eval.synthetic import sample_pdf, render, image_bytes
from eval.opacity import opacity_level

CONDITIONS = ('screen_neutral', 'screen_blue_cast', 'screen_warm_cast', 'screen_exposed', 'screen_resize')

def screen_photo(page, condition='screen_blue_cast', seed=51414):
    h,w=page.shape[:2]
    margin=round(.08*max(h,w)); bezel=25
    canvas=np.full((h+2*margin,w+2*margin,3), (155,155,155), np.uint8)
    canvas[margin:margin+h,margin:margin+w]=page
    canvas=cv2.copyMakeBorder(canvas,bezel,bezel,bezel,bezel,cv2.BORDER_CONSTANT,value=(12,12,14))
    H,W=canvas.shape[:2]
    src=np.float32([[0,0],[W-1,0],[W-1,H-1],[0,H-1]])
    dst=np.float32([[W*.025,H*.015],[W*.99,H*.045],[W*.97,H*.99],[W*.01,H*.975]])
    image=cv2.warpPerspective(canvas.astype(np.float32),cv2.getPerspectiveTransform(src,dst),(W,H),borderValue=(12,12,14))
    image=cv2.GaussianBlur(image,(0,0),1.0)
    gains={'screen_neutral':(1,1,1),'screen_blue_cast':(1.08,1.01,.97),'screen_warm_cast':(.97,1.01,1.055),'screen_exposed':(1.08,1.08,1.08),'screen_resize':(1.025,1,1)}[condition]
    image*=np.array(gains,dtype=np.float32)
    yy,xx=np.mgrid[:H,:W]
    # Fine neutral screen pattern and light independent sensor noise.
    image+=(np.sin((xx+yy)*1.2)*1.2)[:,:,None]
    image+=np.random.default_rng(seed).normal(0,1.0,image.shape)
    image=np.clip(image,0,255).astype(np.uint8)
    if condition=='screen_resize':image=cv2.resize(image,None,fx=.8,fy=.8,interpolation=cv2.INTER_AREA)
    return cv2.imdecode(cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,85])[1],1)


def run(samples=3,opacity=.10):
    from encoder.watermark import watermark_pdf
    from decoder.watermark import decode
    source=sample_pdf(); outcomes={c:dict(correct=0,rejected=0,incorrect=0) for c in CONDITIONS}
    for n in range(samples):
        identifier=(0x19A40F25+n*2654435761)%2**32
        with opacity_level(opacity):marked=render(watermark_pdf(source,identifier))
        for condition in CONDITIONS:
            try:got=decode(image_bytes(screen_photo(marked,condition,n),'clean'))[0]; label='correct' if got==identifier else 'incorrect'
            except ValueError:label='rejected'
            outcomes[condition][label]+=1
    negatives=dict(rejected=0,incorrect=0)
    for condition in CONDITIONS:
        try:decode(image_bytes(screen_photo(render(source),condition),'clean'));negatives['incorrect']+=1
        except ValueError:negatives['rejected']+=1
    return dict(opacity=opacity,samples=samples,source='Digitally simulated screen photography; no real captured photo',outcomes=outcomes,unmarked_controls=negatives)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--samples',type=int,default=3);args=parser.parse_args()
    result=run(args.samples);Path('eval/screen-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
