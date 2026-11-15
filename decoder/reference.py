"""Content geometry registration followed by independent watermark validation.

Reference features align an issued page; they never select the returned ID.
Only a recovered Reed-Solomon payload with a valid CRC is returned.
"""
import cv2
import numpy as np
import pymupdf
from decoder.page import _LEFT, _RIGHT, _sample, _checked
from config import TILE_ROWS, TILE_COLS


def build_reference(pdf_bytes):
    references = []
    sift = cv2.SIFT_create(nfeatures=3500)
    with pymupdf.open(stream=pdf_bytes, filetype='pdf') as doc:
        for page in doc:
            factor = 1600 / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False, colorspace=pymupdf.csGRAY)
            gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
            keys, descriptors = sift.detectAndCompute(gray, None)
            if descriptors is None or len(keys) < 24:
                continue
            points = np.float32([key.pt for key in keys]) / np.float32([pix.width - 1, pix.height - 1])
            references.append({'points': points, 'descriptors': descriptors, 'size': np.int32([pix.width, pix.height])})
    return references


def _validated_quad(points, matches, keys, image):
    source = np.float32([points[m.queryIdx] for m in matches])
    target = np.float32([keys[m.trainIdx].pt for m in matches])
    homography, mask = cv2.findHomography(source, target, cv2.RANSAC, 3.)
    if homography is None or mask is None or not np.isfinite(homography).all():
        return None
    good = mask.ravel().astype(bool)
    if good.sum() < 24 or good.mean() < .2:
        return None
    # Text repeated across pages can create a tiny, degenerate match. Require
    # spatially distributed correspondences, not merely an inlier count.
    if cv2.contourArea(cv2.convexHull(source[good])) < .025:
        return None
    if cv2.contourArea(cv2.convexHull(target[good])) < image.shape[0] * image.shape[1] * .025:
        return None
    quad = cv2.perspectiveTransform(np.float32([[[0, 0], [1, 0], [1, 1], [0, 1]]]), homography)[0]
    area = abs(cv2.contourArea(quad))
    if not cv2.isContourConvex(quad) or not .1 < area / (image.shape[0] * image.shape[1]) < 12:
        return None
    return homography


def _decode_registered(image, homography):
    b, g, r = cv2.split(image.astype(np.float32))
    # Signed chroma keeps weak opposing noise symmetric instead of clipping it
    # into a false positive bias. Remove the screen's broad color cast.
    raw = (r + g) * .5 - b
    raw -= cv2.GaussianBlur(raw, (0, 0), 20)
    left = cv2.perspectiveTransform(_LEFT.reshape(1, -1, 2), homography)[0]
    right = cv2.perspectiveTransform(_RIGHT.reshape(1, -1, 2), homography)[0]
    height, width = raw.shape
    valid = ((left[:, 0] >= 3) & (left[:, 0] < width - 3) & (left[:, 1] >= 3) & (left[:, 1] < height - 3)
             & (right[:, 0] >= 3) & (right[:, 0] < width - 3) & (right[:, 1] >= 3) & (right[:, 1] < height - 3))
    for sigma in (.65, 1., 1.5):
        field = cv2.GaussianBlur(raw, (0, 0), sigma)
        for dy, dx in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            shift = np.float32([dx, dy])
            pairs = (_sample(field, right + shift) - _sample(field, left + shift)) * valid
            evidence = pairs.reshape(TILE_ROWS * TILE_COLS, -1)
            scores = evidence.sum(axis=0)
            if float(np.mean(np.abs(scores))) < 1.:
                continue
            found = _checked(scores)
            if found is not None:
                return found
            # A single intact patch may have better SNR than the combined crop.
            for patch in evidence:
                if np.count_nonzero(patch) >= 240:
                    found = _checked(patch)
                    if found is not None:
                        return found
    return None


def decode_with_references(image_bytes, references):
    from decoder.watermark import _load_image
    image = _load_image(image_bytes)
    if max(image.shape[:2]) > 2600:
        factor = 2600 / max(image.shape[:2])
        image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    sift = cv2.SIFT_create(nfeatures=5000)
    keys, descriptors = sift.detectAndCompute(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), None)
    if descriptors is None or len(keys) < 24:
        return None
    matcher = cv2.BFMatcher()
    for reference in references:
        points, original = reference['points'], reference['descriptors']
        if len(original) < 24:
            continue
        pairs = matcher.knnMatch(np.asarray(original, np.float32), descriptors, k=2)
        matches = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < .70 * pair[1].distance]
        if len(matches) < 24:
            continue
        homography = _validated_quad(points, matches, keys, image)
        if homography is None:
            continue
        found = _decode_registered(image, homography)
        if found is not None:
            return found
    return None
