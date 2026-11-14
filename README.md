# Trace

Trace is an experimental forensic document watermark demo. It creates a recipient-specific, single-page PDF and attempts to recover its ID from an image. Recipient details stay in a local SQLite database.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.server
```

Open http://localhost:5000. Create a document, then upload a PNG or JPEG of the page under **Identify a leak**. Keep the local `instance/trace.db` database: IDs cannot be matched to recipients without it.

## Current limits

This is a prototype, not a production security system. Physical print and phone-photo recovery has not been validated. Page-boundary detection requires the page to be visible or tightly cropped; orientation is not automatically corrected. Text overlapping marks, printer characteristics, perspective, cropping and lighting may prevent recovery. Signal agreement is a measure of repeated-bit agreement, not a probability that an identification is correct. The system does not protect against retyping or recreating a document, copy comparison, or database compromise. The deterministic pattern seed is public and is not a security key.

The marks currently use paired positions in a fixed grid, rather than the organic spread-spectrum marks and distinct corner anchors proposed in the brief. See `spec/LANGUAGE.md`. Test with the actual printer before claiming physical robustness.

## Tests

```sh
python -m pytest -q
```
