"""HEIC inputs are actual encoded files, not JPEGs with renamed extensions."""
from io import BytesIO
import pymupdf
import pytest
from PIL import Image
import pillow_heif
from encoder.watermark import watermark_pdf
from decoder.watermark import decode
import app.server as server

pillow_heif.register_heif_opener()
IDENTIFIER = 0x6A48B291


def source_pdf():
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 80), 'Synthetic HEIC upload test')
        return doc.tobytes()


def render(data):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def heic(image, quality=95):
    out = BytesIO()
    image.save(out, format='HEIF', quality=quality)
    data = out.getvalue()
    assert b'ftyp' in data[:16]
    return data


@pytest.fixture(scope='module')
def marked_image():
    return render(watermark_pdf(source_pdf(), IDENTIFIER))


@pytest.mark.parametrize('turns', [0, 1])
def test_real_heic_watermark_roundtrip(marked_image, turns):
    image = marked_image.rotate(90 * turns, expand=True)
    assert decode(heic(image))[0] == IDENTIFIER


def test_heic_upload_identifies_stored_recipient(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'heic.db')
    monkeypatch.setattr(server.secrets, 'randbits', lambda _: IDENTIFIER)
    client = server.app.test_client()
    response = client.post('/generate', data={'name':'HEIC recipient', 'email':'heic@example.com', 'document':(BytesIO(source_pdf()), 'source.pdf')})
    assert response.status_code == 200
    result = client.post('/decode', data={'image':(BytesIO(heic(render(response.data))), 'photo.HEIC')})
    assert result.status_code == 200, result.json
    assert result.json['name'] == 'HEIC recipient'


def test_corrupt_heic_is_validation_error(marked_image):
    data = heic(marked_image)
    with pytest.raises(ValueError):
        decode(data[:100])


def test_unmarked_heic_is_not_identified():
    with pytest.raises(ValueError):
        decode(heic(render(source_pdf())))


def test_heic_container_orientation_is_applied_once(marked_image):
    from decoder.watermark import _load_image
    exif = marked_image.getexif()
    exif[274] = 6
    out = BytesIO()
    marked_image.save(out, format='HEIF', quality=95, exif=exif.tobytes())
    loaded = _load_image(out.getvalue())
    assert loaded.shape[:2] == (marked_image.width, marked_image.height)
    assert decode(out.getvalue())[0] == IDENTIFIER


def test_heic_header_pixel_limit(marked_image, monkeypatch):
    import decoder.watermark as reader
    encoded = heic(marked_image)
    monkeypatch.setattr(reader, 'MAX_IMAGE_PIXELS', 1_000_000)
    with pytest.raises(ValueError, match='too large'):
        reader.decode(encoded)
