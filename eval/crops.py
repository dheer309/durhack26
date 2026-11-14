"""Controlled crop/rotation benchmark. This does not simulate real printing."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import pymupdf
from eval.synthetic import sample_pdf, image_bytes

CONDITIONS = ('full', 'center_60pct', 'top_half', 'bottom_half', 'left_half', 'right_half', 'rotate_90', 'rotate_180', 'rotate_270', 'rotate_23', 'crop_rotate_23', 'perspective_crop')

def transform(image, kind):
    h, w = image.shape[:2]
    if kind == 'full': return image
    if kind == 'center_60pct': return image[int(h*.2):int(h*.8), int(w*.2):int(w*.8)]
    if kind == 'top_half': return image[:h//2]
    if kind == 'bottom_half': return image[h//2:]
    if kind == 'left_half': return image[:, :w//2]
    if kind == 'right_half': return image[:, w//2:]
    if kind.startswith('rotate_'):
        angle = int(kind.split('_')[1])
        if angle == 90: return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        if angle == 180: return cv2.rotate(image, cv2.ROTATE_180)
        if angle == 270: return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        matrix = cv2.getRotationMatrix2D((w/2,h/2), angle, 1)
        cos, sin = abs(matrix[0,0]), abs(matrix[0,1])
        nw, nh = int(h*sin+w*cos), int(h*cos+w*sin)
        matrix[:,2] += [nw/2-w/2, nh/2-h/2]
        return cv2.warpAffine(image,matrix,(nw,nh),borderValue=(80,80,80))
    if kind == 'crop_rotate_23': return transform(transform(image,'center_60pct'),'rotate_23')
    if kind == 'perspective_crop':
        crop=transform(image,'center_60pct'); h,w=crop.shape[:2]
        src=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
        dst=np.float32([[45,20],[w+10,45],[w+35,h+25],[20,h+45]])
        return cv2.warpPerspective(crop,cv2.getPerspectiveTransform(src,dst),(w+80,h+80),borderValue=(70,70,70))
    raise ValueError(kind)

def render_pages(data):
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        return [cv2.imdecode(np.frombuffer(p.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).tobytes('png'),np.uint8),cv2.IMREAD_COLOR) for p in doc]

def run(samples=3):
    from encoder.watermark import watermark_pdf
    from decoder.watermark import decode
    outcomes={c:dict(correct=0,rejected=0,incorrect=0) for c in CONDITIONS}
    source=sample_pdf()
    for n in range(samples):
        identifier=(0x35AC7163+n*2654435761)%2**32
        image=render_pages(watermark_pdf(source,identifier))[0]
        for kind in CONDITIONS:
            try: result=decode(image_bytes(transform(image,kind),'clean'))[0]; outcome='correct' if result==identifier else 'incorrect'
            except ValueError: outcome='rejected'
            outcomes[kind][outcome]+=1
    negatives=dict(rejected=0,incorrect=0)
    for kind in CONDITIONS:
        try: decode(image_bytes(transform(render_pages(source)[0],kind),'clean')); negatives['incorrect']+=1
        except ValueError: negatives['rejected']+=1
    return dict(samples_per_condition=samples,source='Synthetic text PDF rendered at 144 dpi; no real print/camera tests',outcomes=outcomes,unmarked_controls=negatives)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--samples',type=int,default=3);args=parser.parse_args()
    result=run(args.samples);Path('eval/crop-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
