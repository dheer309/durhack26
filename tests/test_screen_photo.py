"""Phone-photo simulation: a page on a laptop screen, not a scan or screenshot.

The camera gain clips the paper and removes the pale registration stroke.
Opacity stays at the configured value.
"""
import cv2
import numpy as np
import pytest

from decoder.watermark import decode
from encoder.watermark import watermark_pdf
from eval.synthetic import render, sample_pdf

IDENTIFIER = 0x19A40F25


def screen_photo(page, seed, rotate=None):
    height, width = page.shape[:2]
    margin = int(0.075 * max(height, width))
    bezel = 34
    screen = np.full((height + 2 * margin, width + 2 * margin, 3), (162, 160, 158), np.uint8)
    screen[margin:margin + height, margin:margin + width] = page
    frame = np.full((screen.shape[0] + 2 * bezel, screen.shape[1] + 2 * bezel, 3), (18, 18, 20), np.uint8)
    frame[bezel:bezel + screen.shape[0], bezel:bezel + screen.shape[1]] = screen
    image = frame.astype(np.float32)
    frame_h, frame_w = image.shape[:2]
    source = np.float32([[0, 0], [frame_w - 1, 0], [frame_w - 1, frame_h - 1], [0, frame_h - 1]])
    tilt = 0.055
    destination = np.float32([
        [frame_w * tilt * 0.45, frame_h * tilt * 0.22],
        [frame_w - 1 - frame_w * tilt * 0.12, frame_h * tilt * 0.62],
        [frame_w - 1 - frame_w * tilt * 0.38, frame_h - 1 - frame_h * tilt * 0.16],
        [frame_w * tilt * 0.22, frame_h - 1 - frame_h * tilt * 0.30],
    ])
    image = cv2.warpPerspective(
        image,
        cv2.getPerspectiveTransform(source, destination),
        (int(frame_w * 1.04), int(frame_h * 1.04)),
        borderValue=(14, 14, 16),
    )
    image = cv2.GaussianBlur(image, (0, 0), 1.15)
    yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]]
    image += (np.sin((xx + yy) * 0.47) * 5)[:, :, None]
    image[:, :, 0] *= 1.08
    image[:, :, 1] *= 1.016
    image *= 1.06
    image = np.clip(image + np.random.default_rng(seed).normal(0, 2.2, image.shape), 0, 255).astype(np.uint8)
    image = cv2.imdecode(cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 76])[1], cv2.IMREAD_COLOR)
    if rotate is not None:
        image = cv2.rotate(image, rotate)
    return image


def _png(image):
    return cv2.imencode('.png', image)[1].tobytes()


@pytest.fixture(scope='module')
def pages():
    source = sample_pdf()
    return render(watermark_pdf(source, IDENTIFIER)), render(source)


@pytest.mark.parametrize('rotate', [
    None,
    cv2.ROTATE_90_CLOCKWISE,
    cv2.ROTATE_180,
    cv2.ROTATE_90_COUNTERCLOCKWISE,
])
def test_screen_photo_recovers_recipient(pages, rotate):
    marked, _ = pages
    recovered, agreement, _ = decode(_png(screen_photo(marked, seed=5, rotate=rotate)))
    assert recovered == IDENTIFIER
    assert 0.8 <= agreement <= 1


def test_page_on_a_large_gray_screen(pages):
    marked, plain = pages
    height, width = marked.shape[:2]
    margin = int(0.55 * max(height, width))

    def surround(page, seed):
        screen = np.full((height + 2 * margin, width + 2 * margin, 3), (150, 148, 146), np.uint8)
        screen[margin:margin + height, margin:margin + width] = page
        image = cv2.GaussianBlur(screen.astype(np.float32), (0, 0), 1.0)
        image[:, :, 0] *= 1.06
        image *= 1.04
        image = np.clip(image + np.random.default_rng(seed).normal(0, 1.5, image.shape), 0, 255).astype(np.uint8)
        return cv2.imdecode(cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])[1], cv2.IMREAD_COLOR)

    recovered, agreement, _ = decode(_png(surround(marked, 3)))
    assert recovered == IDENTIFIER
    assert 0.8 <= agreement <= 1
    with pytest.raises(ValueError):
        decode(_png(surround(plain, 9)))


def test_unmarked_screen_photo_is_rejected(pages):
    _, plain = pages
    with pytest.raises(ValueError):
        decode(_png(screen_photo(plain, seed=25)))
