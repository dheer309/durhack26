"""Low contrast must still survive controlled camera-like digital degradation."""
import cv2
import numpy as np
import pytest
from encoder.watermark import watermark_pdf
from decoder.watermark import decode
from eval.synthetic import sample_pdf, render, image_bytes
from eval.opacity import opacity_level, degrade, visibility

@pytest.fixture(scope='module')
def faint_image():
    source=sample_pdf()
    with opacity_level(.10): marked=watermark_pdf(source,0x8A71350D)
    assert visibility(source,marked)['mean_luminance_drop_on_marks'] < 4
    return render(marked)

@pytest.mark.parametrize('condition',['clean','crop','crop_rotate_23','perspective_crop','jpeg_noise','downsample_jpeg'])
def test_faint_roundtrip_under_digital_stress(faint_image,condition):
    assert decode(image_bytes(degrade(faint_image,condition),'clean'))[0] == 0x8A71350D

@pytest.mark.parametrize('tint',[(10,0,0),(0,4,10),(12,4,0)])
def test_unmarked_colored_paper_is_rejected(tint):
    image=render(sample_pdf())
    image=np.clip(image.astype(float)-np.asarray(tint),0,255).astype(np.uint8)
    with pytest.raises(ValueError):
        decode(image_bytes(degrade(image,'jpeg_noise'),'clean'))
