"""Optional Atlas recipient storage. The URI stays in the environment."""
import os
from functools import lru_cache
from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError


@lru_cache(maxsize=1)
def collection(uri, database):
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    return client[database]['recipients']


def active_collection():
    uri = os.environ.get('MONGODB_URI', '').strip()
    return collection(uri, os.environ.get('MONGODB_DATABASE', 'trace')) if uri else None


def recent(store):
    return [dict(row, id=row['_id']) for row in store.find().sort('created', DESCENDING).limit(8)]


def find(store, identifier):
    return store.find_one({'_id': identifier})


def insert(store, identifier, name, email, title, created):
    try:
        store.insert_one({'_id': identifier, 'name': name, 'email': email, 'title': title, 'created': created})
        return True
    except DuplicateKeyError:
        return False


def save_reference(store, digest, payload):
    """Store large feature archives in GridFS so they survive host restarts."""
    import gridfs
    bucket = gridfs.GridFS(store.database, collection='alignment')
    if not bucket.exists({'filename': digest}):
        bucket.put(payload, filename=digest)


def references(store):
    import gridfs
    bucket = gridfs.GridFS(store.database, collection='alignment')
    return [item.read() for item in bucket.find({})]
