"""Persist sparse page-registration features, never recipient guesses."""
from io import BytesIO
import hashlib
import numpy as np
from decoder.reference import build_reference


def pack_reference(pdf_bytes):
    references = build_reference(pdf_bytes)
    arrays = {'count': np.array(len(references), dtype=np.int32)}
    for index, reference in enumerate(references):
        for key in ('points', 'descriptors', 'size'):
            arrays[f'{index}_{key}'] = reference[key]
    buffer = BytesIO()
    np.savez_compressed(buffer, **arrays)
    return hashlib.sha256(pdf_bytes).hexdigest(), buffer.getvalue()


def unpack_reference(payload):
    with np.load(BytesIO(payload), allow_pickle=False) as arrays:
        return [{key: arrays[f'{index}_{key}'] for key in ('points', 'descriptors', 'size')}
                for index in range(int(arrays['count']))]
