"""Regression checks on controlled renders, not a guarantee for physical photos."""
import numpy as np
import pytest

from decoder.watermark import decode
from encoder.watermark import watermark_pdf
from eval.synthetic import CONDITIONS, image_bytes, photo, render, sample_pdf


@pytest.fixture(scope='module')
def marked_page():
    return render(watermark_pdf(sample_pdf(), 0x19A40F25))


@pytest.mark.parametrize('condition', CONDITIONS)
def test_synthetic_image_recovers_recipient(marked_page, condition):
    recovered, agreement, _ = decode(image_bytes(photo(marked_page, condition), condition))
    assert recovered == 0x19A40F25
    assert 0 <= agreement <= 1


@pytest.mark.parametrize('condition', ['clean', 'rotate_90', 'phone_combined'])
def test_unmarked_page_is_rejected(condition):
    page = render(sample_pdf())
    with pytest.raises(ValueError):
        decode(image_bytes(photo(page, condition), condition))


def test_blank_image_is_rejected():
    page = np.full((1000, 700, 3), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        decode(image_bytes(page, 'clean'))
