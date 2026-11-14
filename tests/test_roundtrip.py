import fitz
import pytest
from encoder.watermark import make_pdf
from decoder.watermark import decode


def render(pdf):
    doc = fitz.open(stream=pdf, filetype='pdf')
    return doc[0].get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes('png')


def test_clean_round_trip():
    pdf = make_pdf(0x12345678, 'Confidential brief', 'A short document for a recipient.')
    identifier, confidence, _ = decode(render(pdf))
    assert identifier == 0x12345678
    assert confidence >= .45


def test_invalid_image_rejected():
    with pytest.raises(ValueError):
        decode(b'not an image')


def test_pdf_deterministic():
    assert make_pdf(123, 'Title', 'Body') == make_pdf(123, 'Title', 'Body')


def test_rotated_perspective_photo_roundtrip():
    import cv2
    import numpy as np
    pdf = make_pdf(0x12345678, 'Brief', 'A short document for a recipient.')
    image = cv2.imdecode(np.frombuffer(render(pdf), np.uint8), cv2.IMREAD_COLOR)
    h, w = image.shape[:2]
    src = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
    dst = np.float32([[120, 60], [w+90, 130], [w+140, h+190], [70, h+130]])
    background = np.full((h+260, w+260, 3), 45, np.uint8)
    image = cv2.warpPerspective(image, cv2.getPerspectiveTransform(src, dst), (w+260,h+260), dst=background, borderMode=cv2.BORDER_TRANSPARENT)
    image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    _, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert decode(jpeg.tobytes())[0] == 0x12345678


def test_existing_pdf_pages_and_rotation():
    import pymupdf
    from encoder.watermark import watermark_pdf
    doc = pymupdf.open()
    for w, h, rotation in [(595, 842, 0), (842, 595, 0), (595, 842, 90)]:
        page = doc.new_page(width=w, height=h)
        page.insert_text((72, 72), 'Original content is preserved')
        page.set_rotation(rotation)
    marked = watermark_pdf(doc.tobytes(no_new_id=True), 0xAABBCCDD)
    marked_doc = pymupdf.open(stream=marked, filetype='pdf')
    for page in marked_doc:
        assert 'Original content is preserved' in page.get_text()
        image = page.get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
        assert decode(image)[0] == 0xAABBCCDD


def test_unmarked_page_is_rejected():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72,72), 'An ordinary, unmarked document.')
    image = page.get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
    with pytest.raises(ValueError, match='No valid watermark'):
        decode(image)
