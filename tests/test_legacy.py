"""Regression for v1 documents without storing any real user material."""
import io
import random
import cv2
import numpy as np
import pymupdf
import pytest
from reportlab.pdfgen import canvas
from reedsolo import RSCodec
from decoder.watermark import decode


def legacy_image(identifier, crop=True):
    width, height = 595.2756, 841.8898
    buf = io.BytesIO()
    doc = canvas.Canvas(buf, pagesize=(width, height), invariant=1)
    doc.setFillGray(.7)
    cells = [(x, y) for y in range(16) for x in range(24)]
    random.Random(26014).shuffle(cells)
    payload = RSCodec(8).encode(identifier.to_bytes(4, 'big'))
    bits = [int(bit) for byte in payload for bit in f'{byte:08b}'] * 4
    for (x, y), bit in zip(cells, bits):
        doc.circle(42 + x * (width - 84) / 23 + (3 if bit else -3),
                   55 + y * (height - 110) / 15, 1.35, fill=1, stroke=0)
    doc.setFillGray(.1)
    doc.setFont('Helvetica', 18)
    doc.drawString(58, height - 115, 'Synthetic test document')
    doc.showPage()
    doc.save()
    pdf = pymupdf.open(stream=buf.getvalue(), filetype='pdf')
    pix = pdf[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    image = cv2.imdecode(np.frombuffer(pix.tobytes('png'), np.uint8), cv2.IMREAD_COLOR)
    if crop:
        image = image[20:-20, 13:-20]
    return cv2.imencode('.png', image)[1].tobytes()


@pytest.mark.parametrize('identifier', [0x12345678, 0xffffffff, 0x847f83ac, 42, 0xaabbccdd])
def test_v1_cropped_screenshot_roundtrip(identifier):
    assert decode(legacy_image(identifier))[0] == identifier


def test_v1_full_page_roundtrip():
    assert decode(legacy_image(0x31415926, crop=False))[0] == 0x31415926


@pytest.mark.parametrize('seed', range(6))
def test_unmarked_noise_is_rejected(seed):
    rng = np.random.default_rng(seed)
    image = np.full((842, 595, 3), 255, np.uint8)
    for x, y in rng.integers([0, 0], [595, 842], size=(450, 2)):
        cv2.circle(image, (int(x), int(y)), 1, (180, 180, 180), -1)
    with pytest.raises(ValueError):
        decode(cv2.imencode('.png', image)[1].tobytes())
