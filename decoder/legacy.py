"""Read the original v1 dot pattern, including a tightly cropped screenshot.

V1 has Reed-Solomon parity but no checksum. Require strong lattice evidence,
low correction and consistent repeats; ambiguous images must be rejected.
"""
import random
import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError


def _lattice(gray):
    height, width = gray.shape
    if height < 300 or width < 300:
        return None
    binary = (gray < 220).astype(np.uint8)
    _, _, stats, centers = cv2.connectedComponentsWithStats(binary)
    # Scale the component-size window with the image, which is bounded to
    # approximately 1200px wide by the caller.
    limit = max(5, round(width * .011))
    good = ((stats[:, 4] >= 3) & (stats[:, 4] <= limit * limit)
            & (stats[:, 2] >= 2) & (stats[:, 3] >= 2)
            & (stats[:, 2] <= limit) & (stats[:, 3] <= limit))
    points = centers[good]
    if len(points) < 200:
        return None
    ys = np.rint(points[:, 1]).astype(int)
    yh = np.convolve(np.bincount(ys, minlength=height), np.ones(5), mode='same')
    starts = np.flatnonzero(yh[:int(.15 * height)] >= 4)
    if not len(starts):
        return None
    steps = np.linspace(height * .055, height * .063, 201)
    starts_grid, step_grid = np.meshgrid(starts, steps, indexing='ij')
    rows = np.rint(starts_grid[:, :, None] + step_grid[:, :, None] * np.arange(16)).astype(int)
    valid = rows[:, :, -1] < height
    score = np.minimum(yh[np.clip(rows, 0, height - 1)], 24).sum(axis=2)
    score[~valid] = 0
    i, j = np.unravel_index(score.argmax(), score.shape)
    if score[i, j] < 200:
        return None
    y0, dy = float(starts_grid[i, j]), float(step_grid[i, j])
    selected = np.abs((points[:, 1] - y0) / dy - np.rint((points[:, 1] - y0) / dy)) < .025
    x_points = points[selected, 0]
    if len(x_points) < 200:
        return None
    xhist = np.bincount(np.rint(x_points).astype(int), minlength=width)
    xhist = np.convolve(xhist, np.ones(5), mode='same')
    starts = np.arange(int(width * .035), int(width * .09), .75)
    steps = np.linspace(width * .035, width * .043, 180)
    starts_grid, step_grid = np.meshgrid(starts, steps, indexing='ij')
    x = starts_grid[:, :, None] + step_grid[:, :, None] * np.arange(24)
    left = np.rint(x - step_grid[:, :, None] * .1353).astype(int)
    right = np.rint(x + step_grid[:, :, None] * .1353).astype(int)
    score = np.maximum(xhist[np.clip(left, 0, width - 1)], xhist[np.clip(right, 0, width - 1)]).sum(axis=2)
    score[(left[:, :, 0] < 0) | (right[:, :, -1] >= width)] = 0
    i, j = np.unravel_index(score.argmax(), score.shape)
    if score[i, j] < 150:
        return None
    x0, dx = float(starts_grid[i, j]), float(step_grid[i, j])
    for _ in range(3):
        row = np.rint((points[:, 1] - y0) / dy).astype(int)
        keep = (row >= 0) & (row < 16) & (np.abs(points[:, 1] - (y0 + row * dy)) < 3.5)
        if keep.sum() < 200:
            return None
        y0, dy = np.linalg.lstsq(np.column_stack((np.ones(keep.sum()), row[keep])), points[keep, 1], rcond=None)[0]
        px = points[keep, 0]
        column = np.rint((px - x0) / dx).astype(int)
        side = np.sign(px - (x0 + column * dx))
        keep_x = ((column >= 0) & (column < 24)
                  & (np.abs(px - (x0 + (column + side * .1353) * dx)) < 4))
        if keep_x.sum() < 200:
            return None
        index = column[keep_x] + side[keep_x] * .1353
        x0, dx = np.linalg.lstsq(np.column_stack((np.ones(len(index)), index)), px[keep_x], rcond=None)[0]
    return x0, dx, y0, dy


def decode_legacy(image):
    """Return (ID, agreement, corrected bytes) or None for an invalid v1 image."""
    height, width = image.shape[:2]
    scale = 1200 / width
    # Restrict to plausible full-page screenshots; this does not claim to
    # handle perspective-distorted photos of the old format.
    if not 1.2 < height / width < 1.7:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    fit = _lattice(gray)
    if fit is None:
        return None
    x0, dx, y0, dy = fit
    cells = [(x, y) for y in range(16) for x in range(24)]
    random.Random(26014).shuffle(cells)
    scores = []
    for x, y in cells:
        py = round(y0 + (15 - y) * dy)
        cx = x0 + x * dx
        left = round(cx - dx * .1353)
        right = round(cx + dx * .1353)
        if py < 2 or py + 3 > gray.shape[0] or left < 2 or right + 3 > gray.shape[1]:
            return None
        a = float(np.mean(gray[py-2:py+3, left-2:left+3]))
        b = float(np.mean(gray[py-2:py+3, right-2:right+3]))
        scores.append(a - b)
    repeated = np.asarray(scores).reshape(4, 96)
    agreement = float(np.mean(np.abs(np.sign(repeated).sum(axis=0))) / 4)
    # V1 has no checksum. Require near-unanimous repeated symbols and a strong
    # local contrast, and reject any candidate needing many byte corrections.
    if agreement < .85 or float(np.mean(np.abs(repeated))) < 8:
        return None
    try:
        decoded, _, errors = RSCodec(8).decode(np.packbits(repeated.sum(axis=0) > 0).tobytes())
    except (ReedSolomonError, ValueError):
        return None
    if len(decoded) != 4 or len(errors) > 2:
        return None
    return int.from_bytes(decoded, 'big'), agreement, len(errors)
