# Synthetic evaluation

Run `python -m eval.synthetic --samples 10` from the repository root. The script creates a text-heavy, single-page A4 PDF, watermarks it for deterministic IDs, renders at 144 dpi, applies each transformation, then records correct IDs, explicit rejections, and incorrect IDs. It also checks transformed unmarked documents and blank images for false detections. It saves a JSON report and an SVG plot here. JPEG quality is 80; blur is Gaussian sigma 0.8 px; occlusion covers 5% of the page; perspective puts the page on a dark simulated background. `phone_combined` adds perspective, Gaussian blur (sigma 0.45 px), light noise (standard deviation 1), and JPEG quality 80.

These are synthetic, controlled examples, not a measurement of print-and-phone performance. Lighting, paper, printer toner, camera sharpening, lens distortion, and real document content can change results substantially. A rejected scan is counted separately from an incorrect match. Physical validation requires a real printer and phone.

## Partial-page benchmark

Run `python -m eval.crops --samples 5`. This independent benchmark keeps 60% of the width and height for its centre crop (36% of the original area), tests each half page, right-angle and 23° rotation, and perspective applied after cropping. It reports explicit rejections separately from incorrect IDs and includes transformed unmarked controls. `tests/test_crops.py` also checks a crop from every page of a three-page source. A recoverable crop needs a complete independently encoded tile; the benchmark does not establish arbitrary crop or physical-camera reliability.

The saved crop benchmark uses 10 IDs per condition: all 10 recovered in all 12 controlled conditions, with 12/12 transformed unmarked controls rejected and no incorrect IDs returned. These results use the current color registration format. At least one complete tile must survive the crop, with sufficient resolution and contrast. Physical printing, phone optics, paper and real lighting remain unverified.

Monochrome generation uses the prior full-page format. Its regression tests check clean grayscale rendering and all four right-angle orientations; the crop benchmark does not apply to that fallback.

## Low-opacity color marks

Run `python -m eval.opacity --samples 5 --calibration` to produce `opacity-results.json`, a standalone SVG heatmap, and a four-page `opacity-calibration.pdf` with 5%, 8%, 10% and 15% dot/marker opacity. All pages use synthetic text and known test IDs listed in the adjacent JSON. These IDs are not recipient database records. Decode a saved phone image without altering the app database using `python -m eval.opacity --photo /path/to/photo.jpg`; the command checks the recovered ID against the calibration manifest and reports its opacity and signal agreement. Print at actual size with color enabled, photograph each page under venue conditions, and compare recovered IDs to the manifest before claiming camera robustness.

The saved five-ID run recovered all IDs in clean, cropped, rotated-crop and perspective-crop digital examples at all four opacity levels. JPEG plus independent channel noise rejected all 5% examples; 70% resizing plus JPEG rejected 5% and 8%. Ten percent was the lowest tested level recovering all five IDs in all six digital conditions. All 18 unmarked controls, including tinted/textured paper, were rejected; no incorrect IDs were observed.

At 10%, changed marks on white areas reduced mean rendered grayscale luminance by 2.16 values on a 0–255 scale, with a 95th-percentile color-channel change of 25. These image metrics do not measure whether a person can see marks or whether a phone can recover a physical print. Five IDs and synthetic noise are limited evidence; real printer ink, paper texture, camera sharpening, exposure and white balance remain unmeasured.

## Low-opacity color experiment

`python -m eval.opacity` sweeps 5%, 8%, 10% and 15% yellow opacity. The saved five-ID run passed all six controlled conditions at 10% and 15%; 5% failed the JPEG/noise cases and 8% failed the downsample/JPEG case. Eighteen unmarked, tinted or textured controls were rejected. The demo default is 10% for both dots and registration strokes. The earlier 10% setting survived these digital tests and failed real phone photos of a screen. This sweep is not a printer test.

Print `opacity-calibration.pdf` at actual size using a color printer, then photograph a page. `python -m eval.opacity --photo /path/to/photo.jpg` checks it against `opacity-calibration.json` without adding synthetic recipients to the app database. Physical tuning must use those captured images; printer toner, paper, lighting and camera processing can remove a faint signal.
