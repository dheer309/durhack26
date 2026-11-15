"""Exercise the Atlas path with an isolated MongoDB-compatible in-memory store."""
import io
import mongomock
import pymupdf
import app.server as server


def test_atlas_generate_and_identify(tmp_path, monkeypatch):
    store = mongomock.MongoClient().trace.recipients
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    monkeypatch.setattr(server.atlas, 'active_collection', lambda: store)
    monkeypatch.setattr(server.secrets, 'randbits', lambda _: 0x12345678)
    document = pymupdf.open()
    document.new_page().insert_text((72, 100), 'Private test document')
    source = document.tobytes()
    document.close()
    client = server.app.test_client()
    generated = client.post('/generate', data={'name': 'Alex', 'email': 'alex@example.com', 'document': (io.BytesIO(source), 'brief.pdf')})
    assert generated.status_code == 200
    assert store.find_one({'_id': 0x12345678})['name'] == 'Alex'
    assert b'Alex' in client.get('/').data
    document = pymupdf.open(stream=generated.data, filetype='pdf')
    photo = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png')
    document.close()
    response = client.post('/decode', data={'image': (io.BytesIO(photo), 'photo.png')})
    assert response.status_code == 200
    assert response.json['email'] == 'alex@example.com'


def test_database_failure_does_not_fall_back(tmp_path, monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError
    monkeypatch.setattr(server, 'DB', tmp_path / 'test.db')
    def unavailable():
        raise ServerSelectionTimeoutError('connection failed')
    monkeypatch.setattr(server.atlas, 'active_collection', unavailable)
    response = server.app.test_client().get('/')
    assert response.status_code == 503
    assert 'connection' in response.json['error'].lower()
