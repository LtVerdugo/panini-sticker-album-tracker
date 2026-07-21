# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000`. For iPhone access on the same WiFi: `ipconfig getifaddr en0` to get the local IP.

Requires `GROQ_API_KEY` in `.env` (copy from `.env.example`).

## Architecture

**FastAPI backend** (`api/main.py`) serves both the REST API and the static frontend — the frontend is mounted at `/` via `StaticFiles`, so there is no separate dev server.

**SQLite database** (`data/panini_tracker.db`) has two tables that matter:
- `stickers` — the full catalog (980 entries, 48 teams). Has two columns added via `ALTER TABLE` at startup: `page_number` and `sticker_type`. The `_ensure_*_column()` helpers guard these migrations so they're safe to run repeatedly.
- `collection` — tracks quantity owned per `sticker_id`. `quantity > 1` means duplicate.

**Catalog loading flow**: On first API request, `_ensure_full_catalog_imported()` imports `data/sticker_catalog_full.csv` into the DB. All data queries go through `_scoped_catalog()`, which joins `stickers` + `collection` via pandas and filters to only sticker IDs present in the full CSV. This is the single source of truth for `/collection`, `/missing`, `/duplicates`, and `/stats`.

**AI scan flow**:
1. `POST /scan` receives an image → preprocessed (EXIF rotation, auto-rotate portrait→landscape, resize to 1600px, CLAHE contrast, sharpen) → sent to Groq Vision (`llama-4-scout-17b`)
2. The AI returns `{"team_code": "ESP", "empty_slots": [2, 5, 7, ...]}` — slot numbers 1–20 where the background text is visible (sticker not placed)
3. `_classify_slots()` maps empty slot numbers to missing stickers and filled slots to owned, looking up player names from the DB
4. Frontend shows a review screen where the user can correct the AI's guesses before confirming

**`POST /confirm`** takes the user's final classification and upserts quantities into `collection`. Each "owned" slot increments quantity by 1 (so scanning a page twice adds duplicates). The `save_confirmed_page_classification()` function in `src/collection_service.py` is legacy and not called by the API.

**Special stickers** — teams `FWC`, `WP`, `CCE`, `HCC` are flagged in `SPECIAL_TEAM_CODES` (both backend and frontend). They cannot be scanned; users mark them manually from the Missing tab. The backend's `PAGE_MAP` dict holds their fixed album page numbers.

**Frontend** (`frontend/app.js`) is vanilla JS with a single `state` object and `refreshAllData()` to reload from the API. The five pages (Album, Missing, Swap, Stats + Scan modal) are all in `index.html`; tab switching just toggles `active` CSS class. The `share-button` class is `position: fixed` and visibility is toggled per-page in `switchPage()`.

## Key data quirks

- `sticker_catalog.csv` (basic) and `sticker_catalog_full.csv` (complete, 980 stickers) coexist. Only the full CSV matters for the running app.
- Team code alias `EGV → EGY` is handled in `_normalize_team_code()` — add new aliases to `TEAM_CODE_ALIASES` in `api/main.py`.
- After editing frontend files, the browser must be hard-refreshed (`Cmd+Shift+R`) because FastAPI serves them as static files with no cache-busting.
- There are no automated tests.
