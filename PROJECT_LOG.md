# Project Log

## 2026-05-22

### Created

- Added the initial Streamlit app shell in `app.py`.
- Added sidebar navigation for Scan, Collection, Missing, Duplicates, Dashboard, and Settings.
- Added a title and placeholder message for each section.
- Added a sample Uzbekistan sticker catalog at `data/sticker_catalog.csv`.
- Added the SQLite schema and CSV catalog import helpers in `src/database.py`.
- Added collection queries and quantity updates in `src/collection_service.py`.
- Connected the Collection, Missing, Duplicates, and Settings sections to the local data layer.
- Corrected the visible Uzbekistan catalog slots and expanded the sample page coverage.
- Updated catalog imports to refresh existing sticker rows by `sticker_id`.
- Completed the missing Uzbekistan catalog rows through `UZB_020`.
- Filled `UZB_005` from the visible album page and left unreadable player rows as placeholders.
- Added a manual Collection form to mark stickers as owned before camera and OCR capture.
- Added camera capture and image upload controls to the Scan section.
- Added local original image saving under `scans/original`.
- Updated Scan for mobile-first camera capture from a phone browser.
- Added privacy-first image handling that keeps images temporary by default.
- Added an opt-in debug image saving option under `scans/original`.
- Added OpenCV preprocessing for future OCR preparation.
- Added original and processed Scan image previews.
- Kept processed images in memory only for now.

## 2026-05-23

### Added

- Added PaddleOCR integration for local OCR in the Scan section.
- Added raw OCR result display without changing collection data or SQLite yet.
- Added PaddlePaddle as the local inference engine for the PaddleOCR pipeline.
- Hardened PaddleOCR result parsing across dict-style and nested result formats.
- Normalized grayscale preprocessed images before passing them to PaddleOCR.
- Switched OCR defaults to lightweight PaddleOCR mobile detection and recognition models.
- Added OCR image resizing so mobile images are capped before local inference.
- Added OCR text cleaning and display-code extraction for raw Scan results.
- Added read-only sticker match suggestions against the local catalog.
- Raised the fuzzy player matching threshold and disabled short-text fuzzy matches.
- Added match reasons to prevent unsafe false positives from OCR fragments.
- Added New Zealand catalog rows from `NZL_001` through `NZL_020`.
- Kept exact team codes as context instead of mapping them directly to a sticker.
- Aggregated duplicate OCR sticker matches into one row per sticker suggestion.
- Added read-only album page classification into missing, owned, and unknown states.
- Added human validation and saving for confirmed album page classifications.
- Page scan saves set owned stickers to at least one without creating duplicates.
- Corrected the New Zealand catalog with user-verified player names.
- Reworked album page classification to prioritize missing-slot code detection.
- Player-name evidence is no longer treated as direct owned proof for page scans.
- Non-missing stickers are owned candidates until human validation.
- Added layout-first album page classification from fixed slot crops.
- OCR is now secondary evidence for album page state classification.
- Added mobile photo orientation normalization before preprocessing and layout analysis.
- Added full team spread alignment before slot-based layout analysis.
- Added a canonical aligned spread size of 1600 x 1000 pixels.
- Added a 20-slot overlay debug view for tuning full-spread slot coordinates.
- Added `streamlit-drawable-canvas` for local manual layout calibration.
- Removed `streamlit-drawable-canvas` after a Streamlit compatibility error with
  `streamlit.elements.image.image_to_url`.
- Added `streamlit-image-coordinates` for local click-based layout calibration.
- Added manual layout calibration so the user can click 20 sticker slots once.
- Saved calibrated coordinates to `config/layout_template.json`.
- Reused saved layout templates for overlay drawing, slot crops, and classification.
- Added slot crop review after each scan so all 20 crops can be checked visually.
- Added selective slot recalibration for correcting individual bad slots.
- Kept full layout recalibration available as an optional expander.
- Added template-based spread alignment with ORB feature matching and homography.
- Saved the calibrated reference image to `config/aligned_template.png`.
- New scans now try to align to the saved template image before slot boxes are used.
- If ORB/homography alignment fails, the app falls back to the previous alignment.
- Added local edge-based slot crop refinement after template alignment.
- Color crops remain used for display and visual slot classification.
- Grayscale edge detection is used locally to refine approximate slot boxes.
- Manual selective recalibration remains the fallback when refinement misses.
- Made edge refinement conservative with center, area, aspect, and IoU checks.
- Unsafe refinements are rejected and fall back to the template crop.
- Added per-slot template/refined review controls in Slot crop review.
- Spain testing showed slots 4, 7, and 12 can over-snap without safeguards.
- Added per-slot OCR missing detection for album page scans.
- Missing is detected only when the expected team code and sticker number appear
  inside the same slot crop.
- Owned is not inferred automatically from missing-code absence or player names.
- Added per-slot OCR debug with crop previews and raw/cleaned detected text.
- Edge refinement remains secondary/debug for crop review.

### Album Layout Notes

- For all teams, sticker positions are fixed.
- The left page contains stickers 1 to 10.
- The right page contains stickers 11 to 20.
- These fixed ranges will be used later to improve page classification.

PaddleOCR and PaddlePaddle stay local, but the first OCR run may need to load or
download model assets into the local Paddle cache.
The first real mobile OCR attempt was killed by macOS after large input dimensions
and a server recognition model were logged, so OCR now uses bounded mobile defaults.
Mobile photos can arrive in portrait orientation, so EXIF correction and landscape
normalization now run before preprocessing and layout analysis.

### Current Dependencies

- Python 3.12.13
- Streamlit
- pandas
- Plotly
- OpenCV (`opencv-python`)
- PaddleOCR
- PaddlePaddle
- Pillow
- RapidFuzz
- streamlit-image-coordinates

The pinned environment dependencies are recorded in `requirements.txt`.
`streamlit-image-coordinates` is used only for local manual calibration in the
Streamlit app. Calibration remains local and open source, and it does not call a
paid or cloud service.

### Local Database Setup

1. Open the Settings section in the Streamlit app.
2. Select **Initialize database** to create `data/panini_tracker.db` and its tables.
3. Select **Import catalog CSV** to load `data/sticker_catalog.csv`.

Catalog imports update sticker IDs that are already present. After a catalog correction,
select **Import catalog CSV** again in Settings to refresh local sticker rows.

### Next Step

Test per-slot OCR missing detection with Spain and New Zealand pages.
