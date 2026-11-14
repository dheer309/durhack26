"""Recover a checksummed repeated watermark from a photograph of a full page."""
import zlib
import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError
from config import ECC_BYTES, REPEATS, PAIR_OFFSET, NORMAL_WIDTH, NORMAL_HEIGHT
from encoder.watermark import positions

ERROR = 'No valid watermark recovered. Use a clear photo of the entire watermarked page, or upload its PNG or JPEG render.'


def _ordered_corners(image):
    """Locate a page against its background; use image bounds if cropped."""
    h, w = image.shape[:2]
    scale = min(1., 1800 / max(h, w))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 35, 100)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    sh, sw = gray.shape
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(contour)
        if area < sw * sh * .20:
            break
        approx = cv2.approxPolyDP(contour, .02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2).astype(np.float32) / scale
            sums = quad.sum(axis=1)
            diffs = np.diff(quad, axis=1).ravel()
            ordered = np.float32([quad[np.argmin(sums)], quad[np.argmin(diffs)], quad[np.argmax(sums)], quad[np.argmax(diffs)]])
            if len(np.unique(ordered, axis=0)) == 4:
                return ordered
    return np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])


def flatten(image):
    corners = _ordered_corners(image)
    destination = np.float32([[0,0],[NORMAL_WIDTH-1,0],[NORMAL_WIDTH-1,NORMAL_HEIGHT-1],[0,NORMAL_HEIGHT-1]])
    return cv2.warpPerspective(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.getPerspectiveTransform(corners, destination), (NORMAL_WIDTH, NORMAL_HEIGHT))


def _try_page(page):
    smooth = cv2.GaussianBlur(page, (5,5), .8).astype(np.float32)
    pts = np.asarray(positions())
    ys = np.rint(pts[:,1]*(NORMAL_HEIGHT-1)).astype(int)
    left = np.rint((pts[:,0]-PAIR_OFFSET)*(NORMAL_WIDTH-1)).astype(int)
    right = np.rint((pts[:,0]+PAIR_OFFSET)*(NORMAL_WIDTH-1)).astype(int)
    count = (8 + ECC_BYTES)*8
    for dy, dx in ((0,0),(-2,0),(2,0),(0,-2),(0,2),(-2,-2),(-2,2),(2,-2),(2,2),(-4,0),(4,0),(0,-4),(0,4)):
        scores = (smooth[ys+dy, left+dx]-smooth[ys+dy, right+dx]).reshape(REPEATS, count)
        bits = np.sum(scores, axis=0) > 0
        raw = np.packbits(bits).tobytes()
        try:
            decoded, _, errors = RSCodec(ECC_BYTES).decode(raw)
        except (ReedSolomonError, ValueError):
            continue
        if len(decoded) != 8 or zlib.crc32(decoded[:4]) != int.from_bytes(decoded[4:], 'big'):
            continue
        agreement = float(np.mean(np.abs(np.sum(np.sign(scores), axis=0))) / REPEATS)
        if agreement < .35 or float(np.mean(np.abs(scores))) < 1.5:
            continue
        return int.from_bytes(decoded[:4], 'big'), agreement, len(errors)
    return None


def decode(data):
    # OpenCV applies JPEG EXIF orientation by default.
    if not data:
        raise ValueError('Could not read this image. Upload a PNG or JPEG; HEIC is not supported.')
    try:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise ValueError('Could not read this image. Upload a PNG or JPEG; HEIC is not supported.') from exc
    if image is None:
        raise ValueError('Could not read this image. Upload a PNG or JPEG; HEIC is not supported.')
    if image.shape[0] * image.shape[1] > 40_000_000:
        raise ValueError('Image is too large. Use an image under 40 megapixels.')
    if min(image.shape[:2]) < 300:
        raise ValueError('Image resolution is too low. Use a clearer photo of the full page.')
    corners = _ordered_corners(image)
    destination = np.float32([[0,0],[NORMAL_WIDTH-1,0],[NORMAL_WIDTH-1,NORMAL_HEIGHT-1],[0,NORMAL_HEIGHT-1]])
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    for orientation in range(4):
        src = np.roll(corners, -orientation, axis=0)
        page = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(src, destination), (NORMAL_WIDTH, NORMAL_HEIGHT))
        result = _try_page(page)
        if result is not None:
            return result
    # The first prototype used a different format with no checksum.
    # Only its strongly corroborated lattice candidates are accepted.
    from decoder.legacy import decode_legacy
    legacy = decode_legacy(image)
    if legacy is not None:
        return legacy
    raise ValueError(ERROR)
