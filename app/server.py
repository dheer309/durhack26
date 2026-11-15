import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pymupdf
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from encoder.watermark import watermark_pdf
from decoder.watermark import decode
from decoder.reference import decode_with_references
from app.references import pack_reference, unpack_reference

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
DB = Path(os.environ.get('TRACE_DB', ROOT / 'instance' / 'trace.db'))
MAX_PAGES = 50


@contextmanager
def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS recipients (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, title TEXT NOT NULL, created TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS document_references (digest TEXT PRIMARY KEY, payload BLOB NOT NULL)')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def validate_pdf(data):
    if not data:
        raise ValueError('The PDF is empty. Choose a PDF with at least one page.')
    try:
        document = pymupdf.open(stream=data, filetype='pdf')
    except Exception as exc:
        raise ValueError('Could not read this PDF. Choose a valid, unencrypted PDF.') from exc
    try:
        if not document.is_pdf:
            raise ValueError('Choose a PDF document.')
        if document.needs_pass or document.is_encrypted:
            raise ValueError('This PDF is password protected. Unlock it before uploading.')
        if document.page_count == 0:
            raise ValueError('The PDF has no pages. Choose a PDF with at least one page.')
        if document.page_count > MAX_PAGES:
            raise ValueError(f'This PDF has too many pages. Choose a PDF with at most {MAX_PAGES} pages.')
    finally:
        document.close()


def verify_pdf(pdf_bytes, identifier):
    """Reject copies whose marks cannot be recovered from a clean page render."""
    doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    try:
        for index, page in enumerate(doc):
            # Bound the render size even for very large PDF page dimensions.
            scale = 1600 / max(page.rect.width, page.rect.height)
            try:
                image = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
                recovered, _, _ = decode(image)
            except (ValueError, RuntimeError) as exc:
                raise ValueError(f'Could not reliably watermark page {index + 1}. Its background or content may obscure the marks. Try a lighter or simpler PDF.') from exc
            if recovered != identifier:
                raise ValueError(f'Could not reliably watermark page {index + 1}. Its background or content may obscure the marks. Try a lighter or simpler PDF.')
    finally:
        doc.close()


@app.get('/')
def index():
    with db() as conn:
        recipients = conn.execute('SELECT * FROM recipients ORDER BY created DESC LIMIT 8').fetchall()
    return render_template('index.html', recipients=recipients)


@app.post('/generate')
def generate():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    upload = request.files.get('document')
    if not name or not email or not upload or not upload.filename:
        return jsonify(error='Choose a PDF and enter the recipient’s name and email.'), 400
    if len(name) > 100 or len(email) > 254:
        return jsonify(error='The recipient name or email is too long.'), 400
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return jsonify(error='Enter a valid email address.'), 400
    if not upload.filename.lower().endswith('.pdf'):
        return jsonify(error='Choose a PDF document.'), 400
    data = upload.read()
    try:
        validate_pdf(data)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    filename = secure_filename(upload.filename) or 'document.pdf'
    title = Path(filename).stem[:120] or 'Document'
    try:
        with db() as conn:
            # Reserve the ID under a write lock, so concurrent requests cannot
            # accidentally generate two documents with the same recipient ID.
            conn.execute('BEGIN IMMEDIATE')
            while True:
                identifier = secrets.randbits(32)
                if not conn.execute('SELECT 1 FROM recipients WHERE id = ?', (identifier,)).fetchone():
                    break
            pdf = watermark_pdf(data, identifier, grayscale=request.form.get("mode") == "grayscale")
            verify_pdf(pdf, identifier)
            digest, features = pack_reference(pdf)
            conn.execute("INSERT OR IGNORE INTO document_references VALUES (?, ?)", (digest, features))
            conn.execute('INSERT INTO recipients VALUES (?, ?, ?, ?, ?)', (identifier, name, email, title, datetime.now(timezone.utc).isoformat()))
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=f'{title}-trace-{identifier:08X}.pdf')


def identify_image(data):
    try:
        return decode(data)
    except ValueError as original_error:
        with db() as conn:
            rows = conn.execute("SELECT payload FROM document_references").fetchall()
        references = [ref for row in rows for ref in unpack_reference(row["payload"])]
        if references:
            result = decode_with_references(data, references)
            if result is not None:
                return result
        raise original_error


def decode_upload(data, filename):
    if not filename.lower().endswith('.pdf') and not data.lstrip().startswith(b'%PDF-'):
        return identify_image(data)
    validate_pdf(data)
    with pymupdf.open(stream=data, filetype='pdf') as document:
        results = []
        for page in document:
            scale = 1800 / max(page.rect.width, page.rect.height)
            image = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
            try:
                results.append(identify_image(image))
            except ValueError:
                continue
        if not results:
            raise ValueError('No readable watermark found in this PDF.')
        if len({result[0] for result in results}) != 1:
            raise ValueError('This PDF contains different recipient codes. Upload one page at a time.')
        return max(results, key=lambda result: result[1])


@app.post('/decode')
def identify():
    upload = request.files.get('image')
    if not upload or not upload.filename:
        return jsonify(error='Choose a photo of a watermarked page first.'), 400
    try:
        identifier, confidence, corrected = decode_upload(upload.read(), upload.filename)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    with db() as conn:
        person = conn.execute('SELECT * FROM recipients WHERE id = ?', (identifier,)).fetchone()
    if not person:
        return jsonify(error='A valid code was found, but its recipient is not in this database.'), 404
    return jsonify(name=person['name'], email=person['email'], title=person['title'], identifier=f'{identifier:08X}', confidence=round(confidence * 100), corrected=corrected)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error='The upload is too large. Choose a file under 20 MB.'), 413


if __name__ == '__main__':
    app.run(debug=False, port=5000)
