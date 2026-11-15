# AGENTS.md

Guidance for AI coding agents working in this repo.

## Project

Hackathon entry for the QRT challenge at DurHack 2026 (14-15 Nov, 24 hours):
"Information Hidden in Plain Sight - Invent a physical language that encodes digital information."

We are building a forensic document watermark. A confidential PDF is generated per recipient with a hidden pattern of faint marks in the page. If the page is printed and a phone photo of it leaks, a decoder recovers the recipient ID from the photo.

Inspiration: printer Machine Identification Codes (yellow dots).

The challenge brief is one line. Check the QRT Discord channel for any extra rules before making design changes.

## Judging criteria

Creativity & Innovation, Technical Competence & Execution, Research & Learning, Polish & Completion.

Work should be easy to show against each: a written language spec, measured error rates, and a clean live demo.

## The "language"

The physical language must survive: PDF -> print -> phone photo -> decode. It must not read as a QR code or barcode.

Original design goals:
- Four distinguishable, faint corner anchors for orientation.
- Organic, noise-like micro-marks spread across the page, not drawn crosses or grids.
- Redundancy: every payload bit is spread over the whole page, or the payload is repeated across the page, so a thumb, fold, or stain degrades signal instead of deleting data.
- Reed-Solomon (reedsolo) on top of the payload.
- Payload is a short ID (about 32 bits plus ECC). Name, email, IP, and timestamp live in a database keyed by that ID, not in the marks.

Current implementation: color PDFs use repeated independently decodable pale-yellow patches with rectangular registration boundaries; monochrome mode uses the older full-page format. The rectangles are a departure from the organic-mark goal. For cropped phone photos, the app can use sparse local page features to align the photo, then independently decode and validate the watermark. Physical print-and-phone performance remains unverified. See `spec/LANGUAGE.md` before changing the format or decoder.

Recommended decoding approach (confirm with the team before changing):
- Deterministic decoding with OpenCV and NumPy: detect anchors, `cv2.warpPerspective` to flatten, then recover bits (cross-correlation against seeded PRNG patterns for the spread-spectrum variant).
- Do not use an LLM or vision API as the decoder. It is nondeterministic, cannot return bit-exact payloads, and sends leaked documents to a third party. An LLM may be used for the demo UI or explanations only.

## Stack

- Python
- Encoder: ReportLab or PyMuPDF
- Decoder: OpenCV, NumPy, reedsolo
- Optional: Streamlit (or small React app) for the forensic dashboard

## Suggested layout

```
/encoder      PDF generation and watermark embedding
/decoder      anchor detection, warp, bit recovery, ECC
/spec         LANGUAGE.md: alphabet, capacity, ECC, anchor geometry
/eval         scripts that measure bit error rate vs blur, rotation, occlusion, JPEG quality
/samples      test prints, phone photos, synthetic renders
/app          dashboard
```

## Build order

1. Print a test sheet with mark sizes (about 0.3 to 0.8mm) at several opacities. Photograph it at an angle with a phone. The stealth vs robustness limit decides the rest.
2. Anchor detection and perspective warp.
3. Decoder working on clean synthetic renders.
4. Decoder working on real phone photos of real prints.
5. Reed-Solomon, then occlusion and blur tests.
6. Dashboard and demo script.

## Conventions

- Keep everything deterministic. Seed all PRNGs. The same inputs must give the same PDF bytes.
- Decoder must expose signal agreement and fail loudly when ECC cannot recover the payload. Never return a guessed ID; signal agreement is not a probability of identification.
- Keep the color watermark at 10% opacity unless the user approves an increase. Preserve compatibility with previously issued formats.
- Keep parameters (mark size, opacity, grid, ECC symbols, seed) in one config file shared by encoder and decoder.
- Write tests for round trips: encode, simulate degradation (rotate, blur, noise, JPEG, occlusion), decode.
- Report results with plots in `/eval`. Do not claim robustness that has not been measured.
- Tune against the actual printer available at the venue. Keep a grayscale fallback in case it is mono.

## Demo plan

- Print two visually identical pages for different recipients.
- A judge picks one, photographs it with their own phone, and the decoder identifies the recipient live.
- Keep pre-captured backup photos in case lighting or printing fails.
- Be ready for: two recipients comparing or averaging copies (collusion-resistant codes such as Tardos are a stretch answer), and retyping or screenshotting the content, which defeats any such watermark. State that limit openly.

## Out of scope

- Defeating adversaries who retype or re-render the text.
- Production key management. Use a demo key and say so.

## Open questions

- Final mark type: dots, small boxes, or halftone-style modulation.
- Single spread-spectrum payload vs repeated tiles with voting.
- Printer and paper available at the venue.
