import io
import pymupdf
import app.server as server


def example_pdf(pages=2):
    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 200), f'Existing document, page {index + 1}')
    result = doc.tobytes()
    doc.close()
    return result


def test_generate_and_identify(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    client = server.app.test_client()
    response = client.post('/generate', data={
        'name': 'Alex Morgan', 'email': 'alex@example.com',
        'document': (io.BytesIO(example_pdf()), 'private-brief.pdf'),
    })
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.mimetype == 'application/pdf'
    doc = pymupdf.open(stream=response.data, filetype='pdf')
    assert len(doc) == 2
    assert 'Existing document, page 1' in doc[0].get_text()
    assert 'Existing document, page 2' in doc[1].get_text()
    for page in doc:
        image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png')
        result = client.post('/decode', data={'image': (io.BytesIO(image), 'page.png')})
        assert result.status_code == 200, result.get_data(as_text=True)
        assert result.json['name'] == 'Alex Morgan'
        assert result.json['email'] == 'alex@example.com'


def test_bad_pdf_does_not_create_recipient(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    client = server.app.test_client()
    response = client.post('/generate', data={
        'name': 'Alex', 'email': 'alex@example.com',
        'document': (io.BytesIO(b'not a pdf'), 'document.pdf'),
    })
    assert response.status_code == 400
    with server.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM recipients').fetchone()[0] == 0


def test_missing_pdf_and_bad_email_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    client = server.app.test_client()
    assert client.post('/generate', data={'name': 'Alex', 'email': 'alex@example.com'}).status_code == 400
    response = client.post('/generate', data={
        'name': 'Alex', 'email': 'invalid',
        'document': (io.BytesIO(example_pdf(1)), 'document.pdf'),
    })
    assert response.status_code == 400


def test_encrypted_pdf_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    document = pymupdf.open(stream=example_pdf(1), filetype='pdf')
    protected = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret')
    document.close()
    response = server.app.test_client().post('/generate', data={
        'name': 'Alex', 'email': 'alex@example.com',
        'document': (io.BytesIO(protected), 'document.pdf'),
    })
    assert response.status_code == 400
    assert 'password' in response.json['error'].lower()


def test_page_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    response = server.app.test_client().post('/generate', data={
        'name': 'Alex', 'email': 'alex@example.com',
        'document': (io.BytesIO(example_pdf(51)), 'large.pdf'),
    })
    assert response.status_code == 400
    assert '50 pages' in response.json['error']


def test_rotated_pdf_page_can_be_identified(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    source = pymupdf.open(stream=example_pdf(1), filetype='pdf')
    source[0].set_rotation(90)
    data = source.tobytes()
    source.close()
    client = server.app.test_client()
    response = client.post('/generate', data={
        'name': 'Alex', 'email': 'alex@example.com',
        'document': (io.BytesIO(data), 'rotated.pdf'),
    })
    assert response.status_code == 200, response.get_data(as_text=True)
    doc = pymupdf.open(stream=response.data, filetype='pdf')
    image = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png')
    result = client.post('/decode', data={'image': (io.BytesIO(image), 'page.png')})
    assert result.status_code == 200, result.get_data(as_text=True)
    assert result.json['name'] == 'Alex'


def test_empty_photo_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    response = server.app.test_client().post('/decode', data={'image': (io.BytesIO(b''), 'empty.png')})
    assert response.status_code == 422
    assert 'Could not read' in response.json['error']


def test_verification_failure_does_not_create_recipient(tmp_path, monkeypatch):
    def reject(*args):
        raise ValueError("Could not reliably watermark page 1.")
    monkeypatch.setattr(server, "verify_pdf", reject)
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(page.rect, fill=(0, 0, 0))
    data = doc.tobytes()
    doc.close()
    response = server.app.test_client().post('/generate', data={
        'name': 'Alex', 'email': 'alex@example.com',
        'document': (io.BytesIO(data), 'dark.pdf'),
    })
    assert response.status_code == 422
    assert 'page 1' in response.json['error'].lower()
    with server.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM recipients').fetchone()[0] == 0


def test_marked_pdf_can_be_identified_directly(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    client = server.app.test_client()
    marked = client.post('/generate', data={'name': 'Alex', 'email': 'alex@example.com', 'document': (io.BytesIO(example_pdf(2)), 'brief.pdf')})
    assert marked.status_code == 200
    result = client.post('/decode', data={'image': (io.BytesIO(marked.data), 'marked.pdf')})
    assert result.status_code == 200
    assert result.json['name'] == 'Alex'
