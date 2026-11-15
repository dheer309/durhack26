"""Content registration supplies geometry; only mark payload supplies identity."""
import cv2
import numpy as np
import pymupdf
from decoder.reference import build_reference, decode_with_references
from encoder.watermark import watermark_pdf


def source_pdf():
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((55, 70), 'Distinctive quarterly research summary', fontsize=18)
    rng = np.random.default_rng(31415)
    for index in range(27):
        tokens = [''.join(rng.choice(list('abcdefghijklmnpqrstuvwxyz'), size=8)) for _ in range(7)]
        page.insert_text((55, 110 + index * 24), f'{index + 1}: ' + ' '.join(tokens), fontsize=10)
    return document.tobytes()


def photographed(pdf):
    with pymupdf.open(stream=pdf, filetype='pdf') as document:
        pix = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        image = cv2.imdecode(np.frombuffer(pix.tobytes('png'), np.uint8), cv2.IMREAD_COLOR)
    h, w = image.shape[:2]
    image = image[int(h*.12):int(h*.88), int(w*.12):int(w*.88)]
    h, w = image.shape[:2]
    src = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    dst = np.float32([[25,10],[w+30,35],[w+15,h+40],[10,h+25]])
    image = cv2.warpPerspective(image, cv2.getPerspectiveTransform(src,dst), (w+60,h+60), borderValue=(60,60,60))
    return cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY,90])[1].tobytes()


def test_reference_recovers_cropped_skewed_payload():
    marked = watermark_pdf(source_pdf(), 0x7382AB19)
    result = decode_with_references(photographed(marked), build_reference(marked))
    assert result is not None
    assert result[0] == 0x7382AB19


def test_reference_never_identifies_from_document_text():
    source = source_pdf()
    marked = watermark_pdf(source, 0x7382AB19)
    assert decode_with_references(photographed(source), build_reference(marked)) is None


def test_app_persists_and_uses_registration(tmp_path, monkeypatch):
    from io import BytesIO
    import app.server as server
    monkeypatch.setattr(server, 'DB', tmp_path / 'workspace.db')
    monkeypatch.setattr(server.secrets, 'randbits', lambda _: 0x7382AB19)
    client = server.app.test_client()
    generated = client.post('/generate', data={'name': 'Synthetic recipient', 'email': 'test@example.com', 'document': (BytesIO(source_pdf()), 'source.pdf')})
    assert generated.status_code == 200
    with server.db() as conn:
        assert conn.execute('SELECT count(*) FROM document_references').fetchone()[0] == 1
    def fail_blind(_):
        raise ValueError('No marker registration')
    monkeypatch.setattr(server, 'decode', fail_blind)
    result = client.post('/decode', data={'image': (BytesIO(photographed(generated.data)), 'phone.jpg')})
    assert result.status_code == 200
    assert result.json['identifier'] == '7382AB19'
