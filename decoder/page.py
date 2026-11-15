"""Read a full page when the yellow registration stroke is too faint to trace.

A phone photo of a bright screen lifts blue until the paper clips. The thin
border disappears, but the twelve repeated dot patches are still a known grid.
Opacity is unchanged: the copies are summed and checked with Reed-Solomon and CRC.
"""
import zlib

import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError

from config import TILE_COLS, TILE_ECC_BYTES, TILE_PAIR_OFFSET, TILE_ROWS
from encoder.tiles import tile_points

_CODEC = RSCodec(TILE_ECC_BYTES)
_UNIT = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])


def _pair_points():
    points = np.asarray(tile_points(), np.float64)
    left, right = [], []
    for row in range(TILE_ROWS):
        for col in range(TILE_COLS):
            x0, y0 = 0.035 + col * 0.315, 0.035 + row * 0.235
            left.append(np.column_stack([
                x0 + (points[:, 0] - TILE_PAIR_OFFSET) * 0.30,
                y0 + points[:, 1] * 0.22,
            ]))
            right.append(np.column_stack([
                x0 + (points[:, 0] + TILE_PAIR_OFFSET) * 0.30,
                y0 + points[:, 1] * 0.22,
            ]))
    return np.concatenate(left).astype(np.float32), np.concatenate(right).astype(np.float32)


_LEFT, _RIGHT = _pair_points()


def _order_quad(points):
    # Angle sorting keeps each corner exactly once even at 45 degrees, where
    # independently choosing min/max x+y and x-y can select one corner twice.
    points = np.asarray(points, np.float32)
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    cyclic = points[np.argsort(angles)]
    return np.roll(cyclic, -int(np.argmin(cyclic.sum(axis=1))), axis=0)


def _page_quad(image):
    """Whitest page-sized region, or the whole frame when the page fills the photo.

    A low threshold also lights up the gray viewer around the page. That region is
    larger, so the page is chosen by how white its interior is, not by area.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    scale = min(1.0, 1000 / max(height, width))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    blur = cv2.GaussianBlur(small, (5, 5), 0)
    best = None
    thresholds = [max(float(np.percentile(blur, percentile)), 140) for percentile in (60, 74, 84)]
    # Absolute cuts still find a small white page on a large gray screen.
    thresholds.extend((200, 225))
    for threshold in thresholds:
        mask = (blur >= threshold).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        if area < 0.08 * blur.size or area > 0.985 * blur.size:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.015 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            found = approx.reshape(4, 2).astype(np.float32)
        else:
            found = cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.float32)
        interior = np.zeros(blur.shape, np.uint8)
        cv2.fillConvexPoly(interior, np.int32(found), 255)
        whiteness = float(blur[interior > 0].mean()) if interior.any() else 0
        if best is None or whiteness > best[0]:
            best = (whiteness, found / scale)
    if best is None:
        return np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    return _order_quad(best[1])


def _sample(field, points):
    height, width = field.shape
    x = points[:, 0]
    y = points[:, 1]
    x0 = np.clip(np.floor(x).astype(int), 0, width - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, height - 2)
    wx = np.clip(x - x0, 0, 1)
    wy = np.clip(y - y0, 0, 1)
    return (
        (1 - wx) * (1 - wy) * field[y0, x0]
        + wx * (1 - wy) * field[y0, x0 + 1]
        + (1 - wx) * wy * field[y0 + 1, x0]
        + wx * wy * field[y0 + 1, x0 + 1]
    )


def _scores(field, quad):
    try:
        homography = cv2.getPerspectiveTransform(_UNIT, np.asarray(quad, np.float32))
    except cv2.error:
        return None
    right = cv2.perspectiveTransform(_RIGHT.reshape(1, -1, 2), homography)[0]
    left = cv2.perspectiveTransform(_LEFT.reshape(1, -1, 2), homography)[0]
    return (_sample(field, right) - _sample(field, left)).reshape(TILE_ROWS * TILE_COLS, -1).sum(axis=0)


def _checked(scores):
    try:
        payload, _, errors = _CODEC.decode(np.packbits(scores > 0).tobytes())
    except (ReedSolomonError, ValueError):
        return None
    if len(payload) != 8 or zlib.crc32(payload[:4]) != int.from_bytes(payload[4:], 'big'):
        return None
    expected = np.unpackbits(np.frombuffer(bytes(_CODEC.encode(bytes(payload))), np.uint8))
    agreement = float(np.mean((scores > 0) == expected))
    return int.from_bytes(payload[:4], 'big'), agreement, len(errors)


def _search(field, quad):
    center = quad.mean(axis=0)
    for turn in range(4):
        cycled = np.roll(quad, -turn, axis=0)
        for factor in (1.000, 1.008, 1.012, 1.016):
            base = center + (cycled - center) * float(factor)
            for dy in (-4, -2, 0, 2, 4):
                for dx in (-4, -2, 0, 2, 4):
                    scores = _scores(field, base + np.float32([dx, dy]))
                    if scores is None:
                        continue
                    found = _checked(scores)
                    if found is not None:
                        return found
    return None


def decode_faint_page(image):
    """Recover one recipient ID from a photographed page, or return None."""
    if min(image.shape[:2]) < 32:
        return None
    long_side = max(image.shape[:2])
    if long_side > 2600:
        scale = 2600 / long_side
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    quad = _page_quad(image)
    span = min(
        (np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])) / 2,
        (np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2,
    )
    if span < 400:
        return None
    blue, green, red = cv2.split(image.astype(np.float32))
    chroma = (red + green) * 0.5 - blue
    residual = chroma - cv2.GaussianBlur(chroma, (0, 0), max(10.0, span * 0.012))
    for scale in (0.00050, 0.00074):
        field = cv2.GaussianBlur(residual, (0, 0), max(0.55, span * scale))
        found = _search(field, quad)
        if found is not None:
            return found
    return None
