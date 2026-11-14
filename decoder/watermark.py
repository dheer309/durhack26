import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError
from config import PAGE_WIDTH, PAGE_HEIGHT, COLS, ROWS, MARGIN_X, MARGIN_Y, ECC_BYTES, REPEATS
from encoder.watermark import positions


def flatten(image):
    """Find the page boundary in a photo, or use a tightly cropped page image."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    quad = None
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(contour) < w * h * .22:
            break
        approx = cv2.approxPolyDP(contour, .02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2).astype('float32')
            break
    if quad is None:
        quad = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
    sums = quad.sum(axis=1)
    diffs = np.diff(quad, axis=1).ravel()
    src = np.float32([quad[np.argmin(sums)], quad[np.argmin(diffs)], quad[np.argmax(sums)], quad[np.argmax(diffs)]])
    width, height = 1190, 1684
    dst = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    return cv2.warpPerspective(gray, cv2.getPerspectiveTransform(src, dst), (width, height))


def decode(data):
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Could not read this image. Upload a PNG or JPEG.')
    if image.shape[0] * image.shape[1] > 40_000_000:
        raise ValueError('Image is too large. Use an image under 40 megapixels.')
    page = flatten(image)
    sx = (PAGE_WIDTH - 2*MARGIN_X)/(COLS-1)
    sy = (PAGE_HEIGHT - 2*MARGIN_Y)/(ROWS-1)
    scores = []
    for x, y in positions():
        py = round((PAGE_HEIGHT - (MARGIN_Y + y*sy)) / PAGE_HEIGHT * (page.shape[0]-1))
        vals = []
        for offset in (-3, 3):
            px = round((MARGIN_X + x*sx + offset) / PAGE_WIDTH * (page.shape[1]-1))
            vals.append(float(np.mean(page[py-2:py+3, px-2:px+3])))
        scores.append(vals[0] - vals[1])
    count = (4 + ECC_BYTES) * 8
    repeated = np.array(scores).reshape(REPEATS, count)
    votes = np.sum(repeated, axis=0)
    bits = (votes > 0).astype(int)
    raw = bytes(int(''.join(map(str, bits[i:i+8])), 2) for i in range(0, count, 8))
    try:
        decoded, _, errors = RSCodec(ECC_BYTES).decode(raw)
    except ReedSolomonError as exc:
        raise ValueError('No valid watermark recovered. Try a sharper, evenly lit photo of the full page.') from exc
    confidence = float(np.mean(np.abs(np.sum(np.sign(repeated), axis=0))) / REPEATS)
    if confidence < .45:
        raise ValueError('The watermark signal is too weak to identify reliably. Try another photo.')
    return int.from_bytes(decoded, 'big'), confidence, len(errors)
