import io
import random
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reedsolo import RSCodec
from config import PAGE_WIDTH, PAGE_HEIGHT, COLS, ROWS, MARGIN_X, MARGIN_Y, ECC_BYTES, REPEATS, DOT_RADIUS, DOT_GREY, SEED


def positions():
    cells = [(x, y) for y in range(ROWS) for x in range(COLS)]
    random.Random(SEED).shuffle(cells)
    return cells


def body_fits(body):
    y = PAGE_HEIGHT - 164
    for paragraph in body.splitlines():
        lines = simpleSplit(paragraph or ' ', 'Helvetica', 11, PAGE_WIDTH - 116)
        y -= 17 * len(lines) + 9
    return y >= 61


def make_pdf(identifier, title, body):
    if not body_fits(body):
        raise ValueError('Document content does not fit on one page. Shorten it and try again.')
    payload = RSCodec(ECC_BYTES).encode(identifier.to_bytes(4, 'big'))
    bits = [int(bit) for byte in payload for bit in f'{byte:08b}'] * REPEATS
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), invariant=1, pageCompression=1)
    pdf.setTitle(title)
    # Keep watermark on the page itself; the paired positions encode a bit.
    pdf.setFillGray(DOT_GREY)
    sx = (PAGE_WIDTH - 2 * MARGIN_X) / (COLS - 1)
    sy = (PAGE_HEIGHT - 2 * MARGIN_Y) / (ROWS - 1)
    for (x, y), bit in zip(positions(), bits):
        pdf.circle(MARGIN_X + x * sx + (3 if bit else -3), MARGIN_Y + y * sy, DOT_RADIUS, fill=1, stroke=0)
    pdf.setFillColorRGB(.12, .15, .14)
    pdf.setFont('Helvetica-Bold', 21)
    pdf.drawString(58, PAGE_HEIGHT - 115, title[:42])
    pdf.setStrokeColorRGB(.75, .78, .75)
    pdf.line(58, PAGE_HEIGHT - 132, PAGE_WIDTH - 58, PAGE_HEIGHT - 132)
    pdf.setFont('Helvetica', 11)
    y = PAGE_HEIGHT - 164
    for paragraph in body.splitlines():
        for line in simpleSplit(paragraph or ' ', 'Helvetica', 11, PAGE_WIDTH - 116):
            pdf.drawString(58, y, line)
            y -= 17
            if y < 70:
                break
        if y < 70:
            break
        y -= 9
    pdf.setFont('Helvetica', 8)
    pdf.setFillGray(.45)
    pdf.drawString(58, 36, 'CONFIDENTIAL')
    pdf.showPage()
    pdf.save()
    return buf.getvalue()
