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
