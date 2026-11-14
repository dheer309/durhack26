# Synthetic evaluation

Run `python -m eval.synthetic --samples 10` from the repository root. The script creates a text-heavy, single-page A4 PDF, watermarks it for deterministic IDs, renders at 144 dpi, applies each transformation, then records correct IDs, explicit rejections, and incorrect IDs. It also checks transformed unmarked documents and blank images for false detections. It saves a JSON report and an SVG plot here. JPEG quality is 80; blur is Gaussian sigma 0.8 px; occlusion covers 5% of the page; perspective puts the page on a dark simulated background. `phone_combined` adds perspective, Gaussian blur (sigma 0.45 px), light noise (standard deviation 1), and JPEG quality 80.

These are synthetic, controlled examples, not a measurement of print-and-phone performance. Lighting, paper, printer toner, camera sharpening, lens distortion, and real document content can change results substantially. A rejected scan is counted separately from an incorrect match. Physical validation requires a real printer and phone.

## Partial-page benchmark

Run `python -m eval.crops --samples 5`. This independent benchmark keeps 60% of the width and height for its centre crop (36% of the original area), tests each half page, right-angle and 23° rotation, and perspective applied after cropping. It reports explicit rejections separately from incorrect IDs and includes transformed unmarked controls. `tests/test_crops.py` also checks a crop from every page of a three-page source. A recoverable crop needs a complete independently encoded tile; the benchmark does not establish arbitrary crop or physical-camera reliability.

The saved crop benchmark uses 10 IDs per condition: all 10 recovered in all 12 controlled conditions, with 12/12 transformed unmarked controls rejected and no incorrect IDs returned. These results use the current color registration format. At least one complete tile must survive the crop, with sufficient resolution and contrast. Physical printing, phone optics, paper and real lighting remain unverified.

Monochrome generation uses the prior full-page format. Its regression tests check clean grayscale rendering and all four right-angle orientations; the crop benchmark does not apply to that fallback.
