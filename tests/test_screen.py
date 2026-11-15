"""Screen simulations are regressions, not real-phone performance claims."""
import cv2
import numpy as np
import pytest
from decoder.watermark import decode
from encoder.watermark import watermark_pdf
from eval.opacity import opacity_level
from eval.screen import CONDITIONS, screen_photo
from eval.synthetic import sample_pdf, render, image_bytes

@pytest.fixture(scope='module')
def faint_page():
    with opacity_level(.10):
        return render(watermark_pdf(sample_pdf(),0x19A40F25))

@pytest.mark.parametrize('condition',CONDITIONS)
def test_faint_screen_pipeline(faint_page,condition):
    assert decode(image_bytes(screen_photo(faint_page,condition),'clean'))[0]==0x19A40F25

@pytest.mark.parametrize('condition',CONDITIONS)
def test_unmarked_screen_rejected(condition):
    with pytest.raises(ValueError):
        decode(image_bytes(screen_photo(render(sample_pdf()),condition),'clean'))


def test_clipped_color_signal_is_rejected():
    import pymupdf
    document=pymupdf.open(); document.new_page(width=595,height=842)
    with opacity_level(.10):
        faint_page=render(watermark_pdf(document.tobytes(),0x19A40F25))
    document.close()
    # Brightness/channel gain clips even the marked blue pixels to255.
    # White page background and marks become identical; there is no data to infer.
    b,g,r=cv2.split(faint_page.astype(np.float32))
    lost=np.dstack((np.minimum(b*1.25,255),g,r)).astype(np.uint8)
    with pytest.raises(ValueError):
        decode(image_bytes(lost,'clean'))


def test_screen_at_45_degrees(faint_page):
    from eval.crops import transform
    image=transform(screen_photo(faint_page),'rotate_45')
    assert decode(image_bytes(image,'clean'))[0]==0x19A40F25
