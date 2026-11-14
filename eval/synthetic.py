"""Reproducible *synthetic* watermark experiments; no physical-print claims.

Run from the project root: python -m eval.synthetic --samples 10
"""
import argparse
import io
import json
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def sample_pdf():
    """A plausible existing document with text distributed across the page."""
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=A4, invariant=1)
    width, height = A4
    page.setFont('Helvetica-Bold', 19)
    page.drawString(55, height - 80, 'Quarterly project brief')
    page.setStrokeColorRGB(.7, .7, .7)
    page.line(55, height - 96, width - 55, height - 96)
    page.setFont('Helvetica', 10)
    lines = [
        'This sample document is used for synthetic testing of the watermark.',
        'The sample includes text across the page to exercise content interference.',
        'Results do not predict performance on a particular printer or camera.',
        'A recipient-specific copy should preserve the contents of this document.',
    ]
    for index in range(32):
        page.drawString(55, height - 125 - 19 * index, lines[index % len(lines)])
    page.showPage()
    page.save()
    return output.getvalue()


def render(pdf):
    with pymupdf.open(stream=pdf, filetype='pdf') as document:
        pix = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        return cv2.imdecode(np.frombuffer(pix.tobytes('png'), dtype=np.uint8), cv2.IMREAD_COLOR)


def photo(page, kind):
    """Apply one specified transformation to a 144-dpi rendered page."""
    if kind == 'clean':
        return page
    if kind == 'jpeg_80':
        return page
    if kind == 'blur_0.8px':
        return cv2.GaussianBlur(page, (0, 0), .8)
    if kind == 'rotate_90':
        return cv2.rotate(page, cv2.ROTATE_90_CLOCKWISE)
    if kind == 'rotate_180':
        return cv2.rotate(page, cv2.ROTATE_180)
    if kind == 'rotate_270':
        return cv2.rotate(page, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if kind == 'occlusion_5pct':
        image = page.copy()
        h, w = image.shape[:2]
        image[int(h * .37):int(h * .62), int(w * .40):int(w * .60)] = 90
        return image
    if kind == 'phone_combined':
        image = photo(page, 'perspective')
        image = cv2.GaussianBlur(image, (0, 0), .45)
        noise = np.random.default_rng(26014).normal(0, 1.0, image.shape[:2])[:, :, None]
        return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if kind == 'perspective':
        h, w = page.shape[:2]
        out_w, out_h = w + 200, h + 200
        src = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
        dst = np.float32([[98, 65], [w + 95, 115], [w + 55, h + 120], [65, h + 75]])
        matrix = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(page, matrix, (out_w, out_h), borderValue=(55, 55, 55))
    raise ValueError(f'Unknown transformation: {kind}')


def image_bytes(page, kind):
    extension = '.jpg' if kind in ('jpeg_80', 'phone_combined') else '.png'
    params = [cv2.IMWRITE_JPEG_QUALITY, 80] if extension == '.jpg' else []
    ok, data = cv2.imencode(extension, page, params)
    if not ok:
        raise RuntimeError('Could not encode synthetic image')
    return data.tobytes()


CONDITIONS = ('clean', 'jpeg_80', 'blur_0.8px', 'rotate_90', 'rotate_180', 'rotate_270', 'occlusion_5pct', 'perspective', 'phone_combined')


def run(samples):
    from encoder.watermark import watermark_pdf
    from decoder.watermark import decode

    source = sample_pdf()
    outcomes = {name: {'correct': 0, 'rejected': 0, 'incorrect': 0} for name in CONDITIONS}
    for index in range(samples):
        identifier = (0x19A40F25 + index * 2654435761) % (2 ** 32)
        marked = watermark_pdf(source, identifier)
        rendered = render(marked)
        for name in CONDITIONS:
            try:
                recovered, _, _ = decode(image_bytes(photo(rendered, name), name))
                outcome = 'correct' if recovered == identifier else 'incorrect'
            except ValueError:
                outcome = 'rejected'
            outcomes[name][outcome] += 1
    # Unmarked controls must never be reported as valid recipient IDs.
    negative_outcomes = {'rejected': 0, 'incorrect': 0}
    raw_page = render(source)
    for name in CONDITIONS:
        try:
            decode(image_bytes(photo(raw_page, name), name))
            negative_outcomes['incorrect'] += 1
        except ValueError:
            negative_outcomes['rejected'] += 1
    for value in (255, 128, 0):
        blank = np.full_like(raw_page, value)
        try:
            decode(image_bytes(blank, 'clean'))
            negative_outcomes['incorrect'] += 1
        except ValueError:
            negative_outcomes['rejected'] += 1
    return {'samples_per_condition': samples, 'source': 'Synthetic A4 text PDF, rendered at 144 dpi; transformations applied digitally.', 'outcomes': outcomes, 'unmarked_controls': negative_outcomes}


def svg_report(report):
    count = report['samples_per_condition']
    rows = list(report['outcomes'].items())
    height = 98 + len(rows) * 45
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" viewBox="0 0 760 {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="24" y="29" font-family="sans-serif" font-size="19" fill="#182c21">Synthetic recovery by condition</text>',
             f'<text x="24" y="51" font-family="sans-serif" font-size="12" fill="#465d4d">{count} IDs per condition · digital simulation, not print or camera testing</text>']
    for i, (name, result) in enumerate(rows):
        y = 72 + i * 45
        parts.append(f'<text x="24" y="{y+14}" font-family="sans-serif" font-size="13" fill="#182c21">{name}</text>')
        x = 185
        for key, color in [('correct', '#267b50'), ('rejected', '#dbb451'), ('incorrect', '#bd4b45')]:
            width = result[key] / count * 430
            if width:
                parts.append(f'<rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="18" fill="{color}"/>')
            x += width
        parts.append(f'<text x="625" y="{y+14}" font-family="sans-serif" font-size="12" fill="#182c21">{result["correct"]}/{count} correct</text>')
    parts.append(f'<text x="24" y="{height-12}" font-family="sans-serif" font-size="11" fill="#465d4d">Green: correct · amber: rejected · red: incorrect ID</text></svg>')
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=10)
    parser.add_argument('--out', type=Path, default=Path('eval'))
    args = parser.parse_args()
    if args.samples < 1 or args.samples > 1000:
        parser.error('--samples must be between 1 and 1000')
    report = run(args.samples)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'synthetic-results.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.out / 'synthetic-results.svg').write_text(svg_report(report))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
