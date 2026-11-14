"""Independent low-opacity measurements; digital stress is not print/camera proof."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import cv2
import numpy as np
import pymupdf
from eval.synthetic import sample_pdf, render, image_bytes
from eval.crops import transform

CONDITIONS = ('clean', 'crop', 'crop_rotate_23', 'perspective_crop', 'jpeg_noise', 'downsample_jpeg')

@contextmanager
def opacity_level(value):
    import encoder.tiles as tiles
    names = ('TILE_DOT_OPACITY', 'TILE_REGISTRATION_OPACITY')
    previous = {key: getattr(tiles, key) for key in names}
    try:
        for key in names: setattr(tiles, key, value)
        yield
    finally:
        for key, value in previous.items(): setattr(tiles, key, value)


def degrade(image, condition):
    if condition == 'clean': return image
    if condition == 'crop': return transform(image, 'center_60pct')
    if condition in ('crop_rotate_23', 'perspective_crop'): return transform(image, condition)
    rng = np.random.default_rng(51414)
    if condition == 'downsample_jpeg':
        image = cv2.resize(image, None, fx=.70, fy=.70, interpolation=cv2.INTER_AREA)
    if condition in ('jpeg_noise', 'downsample_jpeg'):
        image = cv2.GaussianBlur(image, (0,0), .45)
        # Independent color noise challenges chroma extraction rather than only luminance.
        image = np.clip(image.astype(float)+rng.normal(0,1.5,image.shape),0,255).astype(np.uint8)
        return cv2.imdecode(cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,85])[1],cv2.IMREAD_COLOR)
    raise ValueError(condition)


def visibility(source, marked):
    clean = render(source)
    changed = render(marked)
    paper = np.min(clean,axis=2)>250
    delta = np.abs(changed.astype(float)-clean.astype(float))
    luminance = cv2.cvtColor(clean,cv2.COLOR_BGR2GRAY).astype(float)-cv2.cvtColor(changed,cv2.COLOR_BGR2GRAY)
    ink = paper & (np.max(delta,axis=2)>1)
    return dict(changed_white_pixel_fraction=round(float(np.mean(ink[paper])),5),
                mean_luminance_drop_on_marks=round(float(np.mean(luminance[ink])),3),
                p95_channel_change_on_marks=round(float(np.percentile(delta[ink],95)),3))


def run(samples=5, levels=(.05,.08,.10,.15)):
    from encoder.watermark import watermark_pdf
    from decoder.watermark import decode
    source=sample_pdf()
    rows=[]
    for level in levels:
        counts={c:dict(correct=0,rejected=0,incorrect=0) for c in CONDITIONS}
        for n in range(samples):
            identifier=(0x35AC7163+n*2654435761)%2**32
            with opacity_level(level): marked=watermark_pdf(source,identifier)
            image=render(marked)
            for condition in CONDITIONS:
                try:
                    found=decode(image_bytes(degrade(image,condition),'clean'))[0]
                    outcome='correct' if found==identifier else 'incorrect'
                except ValueError: outcome='rejected'
                counts[condition][outcome]+=1
        rows.append(dict(opacity=level,visibility=visibility(source,marked),outcomes=counts))
    negatives=dict(rejected=0,incorrect=0)
    for condition in CONDITIONS:
        try: decode(image_bytes(degrade(render(source),condition),'clean')); negatives['incorrect']+=1
        except ValueError: negatives['rejected']+=1
    rng=np.random.default_rng(19241)
    for tint in ((10,0,0),(0,4,10),(12,4,0)):
        tinted=np.clip(render(source).astype(float)-np.asarray(tint),0,255).astype(np.uint8)
        texture=rng.normal(0,1.2,tinted.shape[:2])[:,:,None]
        tinted=np.clip(tinted.astype(float)+texture,0,255).astype(np.uint8)
        for condition in ('clean','crop','jpeg_noise','downsample_jpeg'):
            try: decode(image_bytes(degrade(tinted,condition),'clean')); negatives['incorrect']+=1
            except ValueError: negatives['rejected']+=1
    return dict(samples_per_condition=samples,source='Text-heavy A4 PDF rendered at144dpi; controlled digital degradation only',levels=rows,unmarked_controls=negatives)


def calibration(output='eval/opacity-calibration.pdf',levels=(.05,.08,.10,.15)):
    from encoder.watermark import watermark_pdf
    source=sample_pdf()
    merged=pymupdf.open()
    manifest=[]
    for index,level in enumerate(levels):
        identifier=0xCA110000+index
        with opacity_level(level): marked=watermark_pdf(source,identifier)
        with pymupdf.open(stream=marked,filetype='pdf') as doc:
            doc[0].insert_text((55,25),f'CALIBRATION: opacity {level:.0%}; test ID {identifier:08X}; print at actual size',fontsize=9)
            merged.insert_pdf(doc)
        manifest.append(dict(page=index+1,opacity=level,identifier=f'{identifier:08X}'))
    merged.save(output,garbage=3,deflate=True,no_new_id=True)
    merged.close()
    Path(output).with_suffix('.json').write_text(json.dumps(dict(note='Calibration IDs are test IDs, not recipient database records. Physical measurements not yet performed.',pages=manifest),indent=2)+'\n')



def plot_results(result, output='eval/opacity-results.svg'):
    """Small standalone SVG heatmap; values are measured recovery percentages."""
    width,height=960,340
    labels={'clean':'Clean','crop':'Centre crop','crop_rotate_23':'Crop + 23°','perspective_crop':'Perspective crop','jpeg_noise':'JPEG + noise','downsample_jpeg':'70% size + JPEG'}
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="#fff"/>','<g font-family="Arial,sans-serif" fill="#20343d">','<text x="25" y="30" font-size="20" font-weight="bold">Low-opacity digital recovery</text>','<text x="25" y="53" font-size="12">5 IDs per condition · controlled simulation, not a physical camera test</text>']
    for col,c in enumerate(CONDITIONS):
        svg.append(f'<text x="{180+col*124}" y="88" font-size="12">{labels[c]}</text>')
    for row,level in enumerate(result['levels']):
        y=105+row*45
        svg.append(f'<text x="25" y="{y+23}" font-size="14">Opacity {level["opacity"]:.0%}</text>')
        for col,c in enumerate(CONDITIONS):
            pct=level['outcomes'][c]['correct']/result['samples_per_condition']*100
            fill='#d7e8e0' if pct==100 else '#f3ded8'
            svg.append(f'<rect x="{175+col*124}" y="{y}" width="115" height="35" rx="3" fill="{fill}"/><text x="{215+col*124}" y="{y+23}" font-size="14">{pct:.0f}%</text>')
    svg.append(f'<text x="25" y="315" font-size="12">Unmarked controls: {result["unmarked_controls"]["rejected"]} rejected; {result["unmarked_controls"]["incorrect"]} false identifications. Five IDs do not establish field reliability.</text></g></svg>')
    Path(output).write_text('\n'.join(svg)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--samples',type=int,default=5);parser.add_argument('--calibration',action='store_true');parser.add_argument('--photo',type=Path);args=parser.parse_args()
    if args.photo:
        from decoder.watermark import decode
        try:
            identifier,agreement,corrected=decode(args.photo.read_bytes())
        except ValueError as exc:
            raise SystemExit(str(exc))
        manifest=json.loads(Path('eval/opacity-calibration.json').read_text())
        match=next((p for p in manifest['pages'] if p['identifier']==f'{identifier:08X}'),None)
        if match is None: raise SystemExit('Recovered an ID that is not in this calibration manifest.')
        print(json.dumps(dict(calibration_page=match['page'],opacity=match['opacity'],identifier=match['identifier'],signal_agreement=agreement,corrected_bytes=corrected),indent=2))
        raise SystemExit(0)
    result=run(args.samples)
    Path('eval/opacity-results.json').write_text(json.dumps(result,indent=2)+'\n')
    plot_results(result)
    if args.calibration: calibration()
    print(json.dumps(result,indent=2))
