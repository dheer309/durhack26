import io
import pymupdf
import app.server as server


def test_generate_and_identify(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    client = server.app.test_client()
    response = client.post('/generate', data={'name':'Alex Morgan', 'email':'alex@example.com', 'title':'Private brief', 'body':'A short confidential document.'})
    assert response.status_code == 200
    doc = pymupdf.open(stream=response.data, filetype='pdf')
    image = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png')
    result = client.post('/decode', data={'image': (io.BytesIO(image), 'page.png')})
    assert result.status_code == 200
    assert result.json['name'] == 'Alex Morgan'
    assert result.json['email'] == 'alex@example.com'


def test_long_content_is_not_silently_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    response = server.app.test_client().post('/generate', data={'name':'Alex', 'email':'alex@example.com', 'title':'Brief', 'body':'line\n' * 100})
    assert response.status_code == 400
    assert 'fit' in response.json['error']
