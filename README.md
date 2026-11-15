# Trace

Trace adds recipient-specific watermarks to existing PDFs and attempts to identify a recipient from a photo of a marked page. Recipient records use local SQLite by default or MongoDB Atlas when configured.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.server
```

Open http://localhost:5000. Upload a PDF and enter a recipient to download a marked copy; every page carries the same recipient ID. Before returning the PDF, the app checks that it can recover the ID from a clean render of every page and rejects a page that fails. Print the marked copy and upload a JPEG, PNG, HEIC, HEIF, or PDF under **Identify**. Any one marked page is sufficient; the color format also supports crops that retain a complete repeated patch. Keep `instance/trace.db`: IDs cannot be matched to recipients without that database. The original uploaded PDF is not stored by the application.

Uploads are limited to 20 MB per request and 50 pages. Password-protected PDFs must be unlocked first. Watermarking changes the PDF and may invalidate existing digital signatures. The decoder also supports near-upright, tightly cropped screenshots from the earlier prototype. Its older format has no checksum, so legacy decoding requires a strong signal and remains less reliable than the current format.

## MongoDB Atlas (optional)

Create an Atlas cluster, database user and network access entry following the [Atlas connection guide](https://www.mongodb.com/docs/atlas/driver-connection/). Set `MONGODB_URI` to the connection string in your environment and optionally set `MONGODB_DATABASE` (default `trace`), then start the app. Never commit the URI or credentials. Unset `MONGODB_URI` to use local SQLite instead.

In Atlas mode, recipient records and IDs are stored in the `recipients` collection; `_id` is the 32-bit watermark ID. Sparse alignment features are stored in Atlas GridFS in Atlas mode, so they survive host restarts and are available across machines. In SQLite mode they remain in `instance/trace.db`. Existing SQLite recipients are not automatically migrated. An Atlas connection failure returns an error rather than silently storing new records locally. A shared demo should use synthetic recipient data and restrict access to the database.

For development tests, install `requirements-dev.txt`; the Atlas tests use an in-memory MongoDB-compatible mock, not an actual Atlas cluster.

To preserve existing SQLite recipients and their alignment archives when moving to Atlas, set `MONGODB_URI` and run `python -m app.migrate_sqlite instance/trace.db`. The command is repeatable and refuses to overwrite conflicting recipient IDs. Keep the SQLite file as a backup.

For a container deployment, build with `docker build -t trace-watermark .` and run with `docker run -p 8000:8000 --env-file .env trace-watermark`. The `.env` file should contain `MONGODB_URI` and optionally `MONGODB_DATABASE`. The Atlas network access list must allow the server's outbound address.

## Reliability and limits

This is an experimental prototype, not a production security system. Physical print and phone-photo recovery has **not** been validated. The new color format repeats complete error-corrected payloads across each page with pale-yellow registration boundaries. It can locate surviving patches without a page outline. At least one complete readable patch must remain; arbitrary tiny crops cannot be recovered. Select **Monochrome printer** for the earlier grayscale format, which requires a full-page scan. Cropping, low resolution, poor lighting, page content, printer characteristics or paper can prevent recovery. Signal agreement measures consistency of repeated marks; it is not a probability that an identification is correct.

Both dots and registration strokes use yellow at 10% opacity. This reduces their brightness contrast, but human visibility and physical print robustness still require measurement. Retyping or recreating a document removes the marks. The prototype is not resistant to copy comparison, and its deterministic seed is public. See [the language spec](spec/LANGUAGE.md) and [synthetic evaluation](eval/README.md).

## Tests and synthetic evaluation

```sh
python -m pytest -q
python -m eval.crops --samples 10
```

The saved evaluation is a controlled digital simulation, not a claim about physical-camera performance.

## Cropped phone photos

Newly generated copies store sparse SIFT page features in the configured database (Atlas GridFS or local SQLite). If marker registration fails, these features align a cropped phone photo to its document page; the decoder then reads the marks and requires Reed–Solomon correction and a valid CRC. Text similarity alone never returns a recipient. Source PDF bytes and page images are not retained. Keep the workspace database for this fallback.

To add alignment features for an older issued copy already present in the recipient database, run `python -m app.register_reference /path/to/marked.pdf`. This verifies its watermark before storing features. Sparse or repetitive page content can prevent alignment.

## Hosting on Render

The included `render.yaml` defines a Python web service. In Render, create a Blueprint connected to this branch, set `MONGODB_URI` as a secret environment variable, and allow the service's outbound IP range in Atlas. Free Render instances spin down after inactivity; Atlas stores recipients and alignment features so they persist across restarts. The hosted app has no user authentication: anyone with the URL can upload files and view recent recipient details. Use synthetic recipients for a public demo.

## Hosting on Koyeb

Push the deployment branch to GitHub, then create a Koyeb Web Service from that repository and branch. Choose the Dockerfile build method and the Free instance in Frankfurt or Washington, D.C. Set `MONGODB_URI` to the Atlas connection string using a Koyeb secret; optionally set `MONGODB_DATABASE` (default `trace`). Configure HTTP port `8000` with route `/`; the container listens on Koyeb's `PORT` variable. Allow the service's outbound IP addresses in Atlas Network Access. See [Koyeb's current outbound IP guidance](https://www.koyeb.com/docs/faqs/general#i-want-to-restrict-access-to-a-database-or-other-application-by-ip-address-what-ip-addresses-does-koyeb-use); these addresses can change.

The free instance has 512 MB RAM and sleeps after an hour of inactivity. Koyeb closes HTTP requests after 100 seconds, so test a full generate and identify workflow with the PDFs and photos intended for the demo. Local files do not persist reliably; MongoDB must be configured. As with Render, the hosted app has no user authentication.
