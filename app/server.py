import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify
from io import BytesIO
from encoder.watermark import make_pdf, body_fits
from decoder.watermark import decode

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
DB = Path(os.environ.get('TRACE_DB', ROOT / 'instance' / 'trace.db'))


def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE IF NOT EXISTS recipients (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, title TEXT NOT NULL, created TEXT NOT NULL)')
    return conn


@app.get('/')
def index():
    with db() as conn:
        recipients = conn.execute('SELECT * FROM recipients ORDER BY created DESC LIMIT 8').fetchall()
    return render_template('index.html', recipients=recipients)


@app.post('/generate')
def generate():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    if not name or not email or not title or not body:
        return jsonify(error='Complete all fields before generating a document.'), 400
    if len(name) > 100 or len(email) > 254 or len(title) > 42 or len(body) > 2400:
        return jsonify(error='One of the fields is too long. Shorten it and try again.'), 400
    if not body_fits(body):
        return jsonify(error='Document content does not fit on one page. Shorten it and try again.'), 400
    with db() as conn:
        while True:
            identifier = secrets.randbits(32)
            if not conn.execute('SELECT 1 FROM recipients WHERE id = ?', (identifier,)).fetchone():
                break
        pdf = make_pdf(identifier, title, body)
        conn.execute('INSERT INTO recipients VALUES (?, ?, ?, ?, ?)', (identifier, name, email, title, datetime.now(timezone.utc).isoformat()))
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=f'trace-{identifier:08X}.pdf')


@app.post('/decode')
def identify():
    upload = request.files.get('image')
    if not upload or not upload.filename:
        return jsonify(error='Choose a photo of a watermarked page first.'), 400
    try:
        identifier, confidence, corrected = decode(upload.read())
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    with db() as conn:
        person = conn.execute('SELECT * FROM recipients WHERE id = ?', (identifier,)).fetchone()
    if not person:
        return jsonify(error='A valid code was found, but its recipient is not in this database.'), 404
    return jsonify(name=person['name'], email=person['email'], title=person['title'], identifier=f'{identifier:08X}', confidence=round(confidence * 100), corrected=corrected)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error='The file is too large. Choose an image under 20 MB.'), 413


if __name__ == '__main__':
    app.run(debug=False, port=5000)
