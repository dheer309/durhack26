"""Exercise the Atlas path with an isolated MongoDB-compatible in-memory store."""
import io
import mongomock
import mongomock.gridfs
mongomock.gridfs.enable_gridfs_integration()
import pymupdf
import app.server as server
from app.migrate_sqlite import migrate


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
    assert len(server.atlas.references(store)) == 1
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


def test_sqlite_migration_is_repeatable_and_rejects_conflicts(tmp_path):
    import sqlite3
    import pytest
    path = tmp_path / 'source.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE recipients (id INTEGER PRIMARY KEY, name TEXT, email TEXT, title TEXT, created TEXT)')
        connection.execute('CREATE TABLE document_references (digest TEXT PRIMARY KEY, payload BLOB)')
        connection.execute('INSERT INTO recipients VALUES (1, ?, ?, ?, ?)', ('Alex', 'a@example.com', 'Brief', '2026'))
        connection.execute('INSERT INTO document_references VALUES (?, ?)', ('digest', b'features'))
    store = mongomock.MongoClient().trace.recipients
    assert migrate(path, store) == (1, 1)
    assert migrate(path, store) == (1, 1)
    assert store.count_documents({}) == 1
    assert server.atlas.references(store) == [b'features']
    store.update_one({'_id': 1}, {'$set': {'name': 'Someone else'}})
    with pytest.raises(ValueError, match='conflicts'):
        migrate(path, store)
