"""Independent behavioral tests for partial-page watermark recovery."""
import cv2
import numpy as np
import pymupdf
import pytest
from encoder.watermark import watermark_pdf
from decoder.watermark import decode
from eval.crops import transform, render_pages
from eval.synthetic import sample_pdf, image_bytes

@pytest.fixture(scope='module')
def marked_page():
    return render_pages(watermark_pdf(sample_pdf(), 0x9AC28173))[0]

@pytest.mark.parametrize('condition',['full','center_60pct','top_half','bottom_half','left_half','right_half','rotate_90','rotate_180','rotate_270','rotate_23','crop_rotate_23','perspective_crop'])
def test_partial_and_rotated_page(marked_page, condition):
    image=transform(marked_page,condition)
    assert decode(image_bytes(image,'clean'))[0] == 0x9AC28173


def test_each_page_of_multipage_pdf():
    doc=pymupdf.open()
    for n in range(3):
        page=doc.new_page(width=595,height=842)
        page.insert_text((70,100),f'Synthetic source page {n+1}')
    for image in render_pages(watermark_pdf(doc.tobytes(no_new_id=True),0x937ABC16)):
        assert decode(image_bytes(transform(image,'center_60pct'),'clean'))[0] == 0x937ABC16

@pytest.mark.parametrize('condition',['full','center_60pct','rotate_23','perspective_crop'])
def test_unmarked_partial_images_are_rejected(condition):
    image=render_pages(sample_pdf())[0]
    with pytest.raises(ValueError):
        decode(image_bytes(transform(image,condition),'clean'))

@pytest.mark.parametrize('condition',['full','rotate_90','rotate_180','rotate_270'])
def test_monochrome_generation_fallback(condition):
    marked=watermark_pdf(sample_pdf(),0x2A765913,grayscale=True)
    image=render_pages(marked)[0]
    image=cv2.cvtColor(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
    assert decode(image_bytes(transform(image,condition),'clean'))[0] == 0x2A765913
