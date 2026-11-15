"""Recover a checksummed repeated watermark from a photograph of a full page."""
import io
import warnings
import zlib
import cv2
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import get_file_mimetype, register_heif_opener
from reedsolo import RSCodec, ReedSolomonError
from config import ECC_BYTES, REPEATS, PAIR_OFFSET, NORMAL_WIDTH, NORMAL_HEIGHT
from encoder.watermark import positions

register_heif_opener()

MAX_IMAGE_PIXELS = 40_000_000
IMAGE_READ_ERROR = 'Could not read this image. Upload a valid PNG, JPEG, HEIC or HEIF photo.'

ERROR = 'No valid watermark recovered. Try a larger or sharper image that includes a complete marked patch.'


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


def _load_image(data):
    """Decode the primary phone photo without relying on its filename."""
    if not data:
        raise ValueError(IMAGE_READ_ERROR)
    try:
        mimetype = get_file_mimetype(data)
    except (ValueError, TypeError, RuntimeError):
        mimetype = ''
    if mimetype in ('image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data), formats=['HEIF']) as photo:
                    if photo.width * photo.height > MAX_IMAGE_PIXELS:
                        raise ValueError('Image is too large. Use an image under 40 megapixels.')
                    # libheif applies HEIF container transforms and normalizes
                    # EXIF orientation; this also handles any remaining tag.
                    upright = ImageOps.exif_transpose(photo)
                    rgb = np.asarray(upright.convert('RGB'))
                    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError('Image is too large. Use an image under 40 megapixels.') from exc
        except ValueError as exc:
            if str(exc).startswith('Image is too large.'):
                raise
            raise ValueError(IMAGE_READ_ERROR) from exc
        except (OSError, RuntimeError, SyntaxError) as exc:
            raise ValueError(IMAGE_READ_ERROR) from exc
    # OpenCV applies JPEG EXIF orientation by default, preserving the existing
    # PNG/JPEG path and the color-channel values used by the watermark reader.
    try:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise ValueError(IMAGE_READ_ERROR) from exc
    if image is None:
        raise ValueError(IMAGE_READ_ERROR)
    if image.shape[0] * image.shape[1] > MAX_IMAGE_PIXELS:
        raise ValueError('Image is too large. Use an image under 40 megapixels.')
    return image


def decode(data):
    image = _load_image(data)
    if min(image.shape[:2]) < 300:
        raise ValueError('Image resolution is too low. Use a higher-resolution image.')
    from decoder.tiles import decode_tiles
    tiled = decode_tiles(image)
    if tiled is not None:
        return tiled
    # Phone photos of a screen clip the pale border. Read the known dot grid instead.
    from decoder.page import decode_faint_page
    faint = decode_faint_page(image)
    if faint is not None:
        return faint
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
