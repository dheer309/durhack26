"""Deterministic repeated watermark for existing PDFs."""
import io
import random
import zlib
import pymupdf
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reedsolo import RSCodec
from config import (PAGE_WIDTH, PAGE_HEIGHT, COLS, ROWS, MARGIN_X, MARGIN_Y,
                    ECC_BYTES, REPEATS, PAIR_OFFSET, DOT_RADIUS, DOT_GREY,
                    DOT_OPACITY, ANCHOR_SIZE, SEED)


def positions():
    """Seeded, slightly jittered cell centres, in normalized page coordinates."""
    rng = random.Random(SEED)
    cells = []
    for y in range(ROWS):
        for x in range(COLS):
            # Small fixed offsets prevent the visible pattern becoming a regular grid.
            cx = MARGIN_X + (1 - 2*MARGIN_X) * (x + .5 + rng.uniform(-.16,.16)) / COLS
            cy = MARGIN_Y + (1 - 2*MARGIN_Y) * (y + .5 + rng.uniform(-.16,.16)) / ROWS
            cells.append((cx, cy))
    rng.shuffle(cells)
    return cells


def payload_bits(identifier):
    if not isinstance(identifier, int) or not 0 <= identifier <= 0xffffffff:
        raise ValueError('Recipient ID must be a 32-bit unsigned integer.')
    raw = identifier.to_bytes(4, 'big')
    raw += zlib.crc32(raw).to_bytes(4, 'big')
    encoded = RSCodec(ECC_BYTES).encode(raw)
    return [int(bit) for byte in encoded for bit in f'{byte:08b}'] * REPEATS


def watermark_pdf(pdf_bytes, identifier):
    """Overlay marks onto every displayed page without replacing its contents."""
    bits = payload_bits(identifier)
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    except Exception as exc:
        raise ValueError('Could not read this PDF. Choose a valid PDF file.') from exc
    try:
        if doc.needs_pass:
            raise ValueError('Password-protected PDFs are not supported.')
        if not len(doc):
            raise ValueError('The PDF has no pages.')
        for page in doc:
            # PyMuPDF draws in unrotated coordinates. Convert displayed normalized
            # positions back to page coordinates to preserve pre-rotated PDFs.
            display = page.rect
            inverse = page.derotation_matrix
            width, height = display.width, display.height
            shape = page.new_shape()
            radius = width * DOT_RADIUS
            for (x, y), bit in zip(positions(), bits):
                center = pymupdf.Point((x + (PAIR_OFFSET if bit else -PAIR_OFFSET))*width, y*height) * inverse
                shape.draw_circle(center, radius)
            shape.finish(color=None, fill=(DOT_GREY,)*3, fill_opacity=DOT_OPACITY)
            shape.commit(overlay=True)
            # Four small distinct castellated marks aid human orientation checks.
            # The decoder also tries all four orientations and validates the CRC.
            anchors = ((.023,.023,0),(.962,.023,1),(.962,.965,2),(.023,.965,3))
            shape = page.new_shape()
            for ax, ay, variant in anchors:
                for dx,dy in ((0,0),(1,0),(2,0),(0,1),(2,1),(variant % 2, 2 + variant // 2)):
                    rect = pymupdf.Rect((ax+dx*ANCHOR_SIZE)*width,(ay+dy*ANCHOR_SIZE)*height,
                                        (ax+(dx+.75)*ANCHOR_SIZE)*width,(ay+(dy+.75)*ANCHOR_SIZE)*height)
                    shape.draw_rect(rect * inverse)
            shape.finish(color=None, fill=(DOT_GREY,)*3, fill_opacity=DOT_OPACITY)
            shape.commit(overlay=True)
        return doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Could not watermark this PDF. Check that it is not damaged or restricted.') from exc
    finally:
        doc.close()


def body_fits(body):
    y = PAGE_HEIGHT - 164
    for paragraph in body.splitlines():
        y -= 17 * len(simpleSplit(paragraph or ' ', 'Helvetica', 11, PAGE_WIDTH - 116)) + 9
    return y >= 61


def make_pdf(identifier, title, body):
    """Compatibility helper for synthetic fixtures."""
    if not body_fits(body):
        raise ValueError('Document content does not fit on one page. Shorten it and try again.')
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), invariant=1, pageCompression=1)
    pdf.setTitle(title)
    pdf.setFont('Helvetica-Bold', 21)
    pdf.drawString(58, PAGE_HEIGHT - 115, title[:42])
    pdf.setFont('Helvetica', 11)
    y = PAGE_HEIGHT - 164
    for paragraph in body.splitlines():
        for line in simpleSplit(paragraph or ' ', 'Helvetica', 11, PAGE_WIDTH - 116):
            pdf.drawString(58, y, line)
            y -= 17
        y -= 9
    pdf.showPage()
    pdf.save()
    return watermark_pdf(buf.getvalue(), identifier)
