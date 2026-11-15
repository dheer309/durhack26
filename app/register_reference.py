"""Register sparse alignment features for an already-issued local PDF."""
import argparse
from pathlib import Path
import pymupdf
from app.server import db
from app import atlas
from app.references import pack_reference
from decoder.watermark import decode


def register(path):
    data = Path(path).read_bytes()
    with pymupdf.open(stream=data, filetype='pdf') as document:
        page = document[0]
        scale = 1800 / max(page.rect.width, page.rect.height)
        identifier, _, _ = decode(page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png'))
    digest, payload = pack_reference(data)
    store = atlas.active_collection()
    if store is not None:
        if not atlas.find(store, identifier):
            raise ValueError('This PDF has no recipient record in this workspace.')
        atlas.save_reference(store, digest, payload)
    else:
        with db() as connection:
            if not connection.execute('SELECT 1 FROM recipients WHERE id = ?', (identifier,)).fetchone():
                raise ValueError('This PDF has no recipient record in this workspace.')
            connection.execute('INSERT OR IGNORE INTO document_references VALUES (?, ?)', (digest, payload))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf')
    args = parser.parse_args()
    register(args.pdf)
    print('Alignment reference registered.')
