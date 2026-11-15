"""Copy existing SQLite recipients and alignment archives into MongoDB."""
import argparse
import sqlite3
from pathlib import Path

from app import atlas


def migrate(path, store):
    # Open read-only: a typo must never create an empty source database.
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        recipients = [dict(row) for row in connection.execute('SELECT id, name, email, title, created FROM recipients')]
        references = list(connection.execute('SELECT digest, payload FROM document_references'))

    # Check every ID first so a conflicting existing recipient is never replaced.
    for row in recipients:
        existing = atlas.find(store, row['id'])
        expected = {'_id': row['id'], **{key: row[key] for key in ('name', 'email', 'title', 'created')}}
        if existing is not None and any(existing.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Recipient ID {row['id']:08X} conflicts with an existing Atlas record.")

    for row in recipients:
        if not atlas.insert(store, row['id'], row['name'], row['email'], row['title'], row['created']):
            existing = atlas.find(store, row['id'])
            if any(existing.get(key) != row[key] for key in ('name', 'email', 'title', 'created')):
                raise ValueError(f"Recipient ID {row['id']:08X} changed during migration.")
    for row in references:
        atlas.save_reference(store, row['digest'], row['payload'])
    return len(recipients), len(references)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', help='Path to the existing SQLite database')
    args = parser.parse_args()
    store = atlas.active_collection()
    if store is None:
        parser.error('Set MONGODB_URI before migrating.')
    counts = migrate(args.database, store)
    print(f'Copied or already present: {counts[0]} recipients, {counts[1]} alignment archives.')
