# Trace

Trace adds recipient-specific watermarks to existing PDFs and attempts to identify a recipient from a photo of a marked page. Recipient records are stored in a local SQLite database.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.server
```

Open http://localhost:5000. Upload a PDF and enter a recipient to download a marked copy; every page carries the same recipient ID. Before returning the PDF, the app checks that it can recover the ID from a clean render of every page and rejects a page that fails. Print the marked copy and upload a JPEG, PNG, HEIC, HEIF, or PDF under **Identify**. Any one marked page is sufficient; the color format also supports crops that retain a complete repeated patch. Keep `instance/trace.db`: IDs cannot be matched to recipients without that database. The original uploaded PDF is not stored by the application.

Uploads are limited to 20 MB per request and 50 pages. Password-protected PDFs must be unlocked first. Watermarking changes the PDF and may invalidate existing digital signatures. The decoder also supports near-upright, tightly cropped screenshots from the earlier prototype. Its older format has no checksum, so legacy decoding requires a strong signal and remains less reliable than the current format.

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

Newly generated copies store sparse SIFT page features in the local SQLite database. If marker registration fails, these features align a cropped phone photo to its document page; the decoder then reads the marks and requires Reed–Solomon correction and a valid CRC. Text similarity alone never returns a recipient. Source PDF bytes and page images are not retained. Keep the workspace database for this fallback.

To add alignment features for an older issued copy already present in the recipient database, run `python -m app.register_reference /path/to/marked.pdf`. This verifies its watermark before storing features. Sparse or repetitive page content can prevent alignment.
