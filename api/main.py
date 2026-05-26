import base64
import csv
import io
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from groq import APIConnectionError, APIStatusError, Groq
from PIL import ExifTags, Image

from src.collection_service import (
    get_duplicate_stickers,
    get_missing_stickers,
    load_sticker_catalog,
    save_confirmed_page_classification,
)
from src.database import get_connection, import_catalog_from_csv


PROMPT = """
This is a Panini FIFA World Cup 2026 album page.
The image shows 20 sticker slots for one national team.

CRITICAL RULE — Read this carefully:

EMPTY slot (sticker NOT placed = MISSING):
- You can SEE and READ the printed text on the slot
- The slot background color is visible (red, green, blue, etc.)
- The team code + number is printed and readable
- Example: you can read "ESP 8" on the slot background

FILLED slot (sticker IS placed = OWNED):
- A physical rectangular sticker card covers the slot
- You can see a REAL PHOTO of a player, badge or team
- The printed background text is HIDDEN under the sticker
- The sticker has visible card edges

THE RULE IS:
If you can READ the slot code → it is EMPTY → add to empty_slots
If you see a PHOTO covering the slot → it is FILLED → do NOT add to empty_slots

Look at every slot from 1 to 20.
Only add a slot number to empty_slots if you can 
clearly read the printed code on the background.

Return ONLY this JSON, no markdown, no extra text:
{
  "team_code": "ESP",
  "empty_slots": [1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 
                  13, 14, 15, 16, 17, 18, 20]
}
"""

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CATALOG_CSV_PATH = "data/sticker_catalog.csv"
FULL_CATALOG_CSV_PATH = "data/sticker_catalog_full.csv"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
CATALOG_COLUMNS = [
    "sticker_id",
    "team_code",
    "number",
    "display_code",
    "player_name",
    "category",
    "page_code",
    "slot_position",
]
FULL_CATALOG_IMPORT_COLUMNS = [
    "sticker_id",
    "team_code",
    "number",
    "display_code",
    "player_name",
    "category",
    "page_code",
    "slot_position",
    "page_number",
    "sticker_type",
]
PLACEHOLDER_NAME = "To be completed"
FULL_CATALOG_IMPORTED = False
SPECIAL_TEAM_CODES = {"FWC", "WP", "CCE", "HCC"}
PAGE_MAP = {
    "FWC": 2,
    "WP": 1,
    "CCE": 56,
    "HCC": 6,
}
TEAM_CODE_ALIASES = {
    "EGV": "EGY",
    "TUR": "TUR",
}

load_dotenv()
print(f"Team code aliases loaded: {TEAM_CODE_ALIASES}")

app = FastAPI(title="Panini Camera Tracker API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_page_number_column() -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                "ALTER TABLE stickers ADD COLUMN page_number INTEGER DEFAULT 0"
            )
    except Exception:
        pass


_ensure_page_number_column()


def _ensure_sticker_type_column() -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                "ALTER TABLE stickers ADD COLUMN sticker_type TEXT DEFAULT 'player'"
            )
    except Exception:
        pass


_ensure_sticker_type_column()


def _import_full_catalog_from_csv(csv_path: str | Path) -> int:
    _ensure_page_number_column()
    _ensure_sticker_type_column()
    csv_path = Path(csv_path)
    rows = []

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = set(FULL_CATALOG_IMPORT_COLUMNS) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Full catalog CSV is missing columns: {missing}")

        for row in reader:
            rows.append(
                (
                    row["sticker_id"].strip(),
                    row["team_code"].strip(),
                    int(row["number"] or 0),
                    row["display_code"].strip(),
                    row["player_name"].strip(),
                    row["category"].strip(),
                    row["page_code"].strip(),
                    row["slot_position"].strip(),
                    int(row.get("page_number") or 0),
                    row.get("sticker_type", "player").strip() or "player",
                )
            )

    if not rows:
        return 0

    with get_connection() as connection:
        before_count = connection.total_changes
        connection.executemany(
            """
            INSERT INTO stickers (
                sticker_id,
                team_code,
                number,
                display_code,
                player_name,
                category,
                page_code,
                slot_position,
                page_number,
                sticker_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sticker_id) DO UPDATE SET
                team_code = excluded.team_code,
                number = excluded.number,
                display_code = excluded.display_code,
                player_name = excluded.player_name,
                category = excluded.category,
                page_code = excluded.page_code,
                slot_position = excluded.slot_position,
                page_number = excluded.page_number,
                sticker_type = excluded.sticker_type
            """,
            rows,
        )
        return connection.total_changes - before_count


def _groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is missing from .env",
        )
    return Groq(api_key=api_key)


def _image_data_url(file_bytes: bytes, filename: str | None, content_type: str | None):
    mime_type = content_type or mimetypes.guess_type(filename or "")[0]
    if not mime_type:
        mime_type = "image/jpeg"

    encoded_image = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_image}"


def apply_exif_rotation(image_bytes: bytes) -> bytes:
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        exif = pil_img._getexif()
        if exif:
            for tag, value in exif.items():
                if ExifTags.TAGS.get(tag) == "Orientation":
                    if value == 3:
                        pil_img = pil_img.rotate(180, expand=True)
                    elif value == 6:
                        pil_img = pil_img.rotate(270, expand=True)
                    elif value == 8:
                        pil_img = pil_img.rotate(90, expand=True)
                    break
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()
    except Exception:
        return image_bytes


def preprocess_album_image(image_bytes: bytes) -> str:
    """
    Preprocess album page image to improve AI sticker detection.
    Returns base64 encoded processed image.
    """
    image_bytes = apply_exif_rotation(image_bytes)

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        Image.open(io.BytesIO(image_bytes)).convert("RGB")
        raise ValueError("Could not decode uploaded image")

    # Step 1: Auto-rotate if portrait (album pages are landscape)
    h, w = img.shape[:2]
    if h > w:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        h, w = img.shape[:2]

    # Step 2: Resize to optimal size for AI (max 1600px on longest side)
    max_side = 1600
    scale = min(max_side / w, max_side / h, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Step 3: Enhance contrast with CLAHE
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # Step 4: Slight sharpening
    kernel = np.array([
        [0, -0.5, 0],
        [-0.5, 3, -0.5],
        [0, -0.5, 0],
    ])
    img = cv2.filter2D(img, -1, kernel)
    img = np.clip(img, 0, 255).astype(np.uint8)

    # Step 5: Encode as JPEG with high quality
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 92]
    _, buffer = cv2.imencode(".jpg", img, encode_params)

    # Return as base64
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def _parse_ai_json_response(raw_text: str, provider_name: str) -> dict[str, Any]:
    raw_text = _decode_response_text(raw_text)
    try:
        parsed = json.loads(_extract_json_text(raw_text))
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} response was not valid JSON: {error}; raw={raw_text}",
        )

    return _normalize_slot_names(parsed)


def _decode_response_text(content: Any) -> str:
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content or "").encode("utf-8", errors="replace").decode("utf-8")


def _decode_escaped_unicode(value: Any) -> str:
    text = str(value or "")
    if "\\u" not in text:
        return text

    try:
        return text.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return text


def _normalize_slot_names(parsed: dict[str, Any]) -> dict[str, Any]:
    slots = parsed.get("slots", [])
    if not isinstance(slots, list):
        return parsed

    for slot in slots:
        if isinstance(slot, dict):
            slot["name"] = _decode_escaped_unicode(slot.get("name", ""))

    return parsed


def _is_quota_error(error: Exception) -> bool:
    error_text = str(error).lower()
    return "quota" in error_text or "rate limit" in error_text or "429" in error_text


def _is_auth_error(error: Exception) -> bool:
    error_text = str(error).lower()
    return (
        "api key" in error_text
        or "unauthorized" in error_text
        or "401" in error_text
        or "403" in error_text
    )


def _call_groq_vision(image_data_url: str) -> dict[str, Any]:
    try:
        response = _groq_client().chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                    ],
                }
            ],
        )
    except APIStatusError as error:
        if _is_auth_error(error):
            raise HTTPException(status_code=401, detail="Groq authentication error")
        if _is_quota_error(error):
            raise HTTPException(status_code=429, detail="Groq quota or rate limit error")
        raise HTTPException(status_code=502, detail=f"Groq API error: {error}")
    except APIConnectionError as error:
        raise HTTPException(status_code=502, detail=f"Groq connection error: {error}")

    return _parse_ai_json_response(response.choices[0].message.content, "Groq")


def _slot_number_from_code(code: str) -> int | None:
    parts = str(code).replace("_", " ").replace("-", " ").split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _normalize_team_code(team_code: str) -> str:
    code = str(team_code or "").strip().upper()
    return TEAM_CODE_ALIASES.get(code, code)


def _normalized_slot_code(code: str) -> str:
    return " ".join(str(code).replace("_", " ").replace("-", " ").upper().split())


def _deduplicate_slots_by_code(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated = {}
    for slot in slots:
        code_key = _normalized_slot_code(slot.get("code", ""))
        if not code_key:
            continue

        # Dict assignment keeps the last value for each code.
        deduplicated[code_key] = slot

    return list(deduplicated.values())


def _slot_sort_key(slot: dict[str, Any]) -> int:
    slot_number = _slot_number_from_code(slot.get("code", ""))
    return slot_number if slot_number is not None else 999


def _row_sort_key(row: dict[str, Any]) -> int:
    slot_number = _slot_number_from_code(row.get("code", ""))
    return slot_number if slot_number is not None else 999


def _ensure_full_catalog_imported() -> None:
    global FULL_CATALOG_IMPORTED
    if FULL_CATALOG_IMPORTED:
        return

    csv_path = Path(FULL_CATALOG_CSV_PATH)
    if csv_path.exists():
        _import_full_catalog_from_csv(csv_path)
        FULL_CATALOG_IMPORTED = True


def _full_catalog_ids() -> set[str]:
    csv_path = Path(FULL_CATALOG_CSV_PATH)
    if not csv_path.exists():
        return set()

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        return {row["sticker_id"] for row in reader if row.get("sticker_id")}


def _scoped_catalog():
    _ensure_full_catalog_imported()
    catalog = load_sticker_catalog()
    full_ids = _full_catalog_ids()
    if full_ids and not catalog.empty:
        catalog = catalog.loc[catalog["sticker_id"].isin(full_ids)].reset_index(drop=True)
    if not catalog.empty and "page_number" not in catalog.columns:
        page_numbers = _catalog_page_numbers()
        catalog["page_number"] = (
            catalog["sticker_id"].map(page_numbers).fillna(0).astype(int)
        )
    return catalog


def _catalog_page_numbers() -> dict[str, int]:
    _ensure_page_number_column()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT sticker_id, page_number FROM stickers"
        ).fetchall()

    return {
        sticker_id: int(page_number or 0)
        for sticker_id, page_number in rows
    }


def _lookup_player_name(team_code: str, number: int) -> str:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT player_name
            FROM stickers
            WHERE team_code = ? AND number = ?
            """,
            (team_code, number),
        ).fetchone()

    if row and row[0]:
        return row[0]
    return PLACEHOLDER_NAME


def _lookup_sticker_by_id(sticker_id: str) -> dict[str, Any] | None:
    if not sticker_id:
        return None

    _ensure_page_number_column()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT player_name, page_number
            FROM stickers
            WHERE sticker_id = ?
            """,
            (sticker_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "player_name": row[0],
        "page_number": int(row[1] or 0),
    }


def _empty_slot_numbers(ai_response: dict[str, Any]) -> set[int]:
    empty_slots = ai_response.get("empty_slots", [])
    if not isinstance(empty_slots, list):
        return set()

    numbers = set()
    for value in empty_slots:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= 20:
            numbers.add(number)
    return numbers


def _classify_slots(ai_response: dict[str, Any]) -> dict[str, Any]:
    _ensure_full_catalog_imported()

    missing = []
    owned = []
    raw_slots = []
    team_code = _normalize_team_code(ai_response.get("team_code", ""))
    empty_slots = _empty_slot_numbers(ai_response)
    all_slots = set(range(1, 21))
    empty_set = set(empty_slots)
    owned_set = all_slots - empty_set

    # Do not auto-flip detection. The review screen remains the correction point.
    if len(owned_set) <= 1:
        print(
            "WARNING: Very few owned slots detected. "
            "Check if image is clear."
        )
    elif len(owned_set) > 18:
        print(
            "WARNING: Very many owned slots detected. "
            "Check if image is clear."
        )

    for number in range(1, 21):
        code = f"{team_code} {number}"
        name = _lookup_player_name(team_code, number)
        readable = number in empty_slots
        row = {"code": code, "name": name}
        raw_slot = {"code": code, "name": name, "readable": readable}
        raw_slots.append(raw_slot)

        if readable:
            missing.append(row)
        else:
            owned.append(row)

    return {
        "team_code": team_code,
        "missing": sorted(missing, key=_row_sort_key),
        "owned": sorted(owned, key=_row_sort_key),
        "raw_slots": sorted(raw_slots, key=_slot_sort_key),
    }


def _sticker_id_from_code(code: str) -> str:
    parts = str(code).replace("_", " ").replace("-", " ").split()
    if len(parts) < 2:
        return ""
    try:
        number = int(parts[1])
    except ValueError:
        return ""
    return f"{parts[0].upper()}_{number:03d}"


def _number_from_slot(slot: dict[str, Any]) -> int:
    number = _slot_number_from_code(slot.get("code", ""))
    if number is not None:
        return number

    for value in (slot.get("sticker_id", ""), slot.get("code", "")):
        match = re.search(r"\d+", str(value))
        if match:
            return int(match.group(0))

    return 0


def _team_code_from_scan_result(scan_result: dict[str, Any]) -> str:
    team_code = _normalize_team_code(scan_result.get("team_code", ""))
    if team_code:
        return team_code

    for slot in scan_result.get("owned", []) + scan_result.get("missing", []):
        parts = str(slot.get("code", "")).replace("_", " ").replace("-", " ").split()
        if parts:
            return _normalize_team_code(parts[0])

    return ""


def _category_for_slot_number(number: int) -> str:
    if number == 1:
        return "badge"
    if number == 13:
        return "team_photo"
    return "player"


def _is_special_team_code(team_code: str) -> bool:
    return str(team_code or "").upper() in SPECIAL_TEAM_CODES


def _catalog_row_from_slot(team_code: str, slot: dict[str, Any]) -> dict[str, Any] | None:
    number = _number_from_slot(slot)
    sticker_id = str(slot.get("sticker_id", "")).strip()
    display_code = str(slot.get("code", "")).strip()
    is_special = _is_special_team_code(team_code)

    if is_special and sticker_id:
        sticker = _lookup_sticker_by_id(sticker_id)
        name = str(slot.get("name", "")).strip() or PLACEHOLDER_NAME
        if sticker and sticker["player_name"]:
            name = sticker["player_name"]

        return {
            "sticker_id": sticker_id,
            "team_code": team_code,
            "number": number,
            "display_code": display_code or sticker_id,
            "player_name": name,
            "category": "special",
            "page_code": team_code.lower(),
            "slot_position": sticker_id,
            "page_number": PAGE_MAP.get(team_code, 0),
            "sticker_type": "special",
        }

    if number == 0:
        return None

    name = _lookup_player_name(team_code, number)
    if name == PLACEHOLDER_NAME:
        name = str(slot.get("name", "")).strip() or PLACEHOLDER_NAME

    return {
        "sticker_id": sticker_id or f"{team_code}_{number:03d}",
        "team_code": team_code,
        "number": number,
        "display_code": display_code or f"{team_code} {number}",
        "player_name": name,
        "category": _category_for_slot_number(number),
        "page_code": team_code.lower(),
        "slot_position": f"slot_{number:02d}",
        "page_number": PAGE_MAP.get(team_code, 0),
        "sticker_type": "player",
    }


def _has_real_name(name: str) -> bool:
    return bool(name.strip()) and name.strip() != PLACEHOLDER_NAME


def _resolve_confirm_sticker_id(slot: dict[str, Any], team_code: str) -> str:
    payload_sticker_id = str(slot.get("sticker_id", "")).strip()
    if payload_sticker_id:
        return payload_sticker_id

    number = _number_from_slot(slot)
    if team_code:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT sticker_id
                FROM stickers
                WHERE team_code = ? AND number = ?
                """,
                (team_code, number),
            ).fetchone()
        if row and row[0]:
            return row[0]

    if team_code and number:
        return f"{team_code}_{number:03d}"

    return ""


def _ensure_catalog_entries(scan_result: dict[str, Any]) -> None:
    _ensure_full_catalog_imported()
    _ensure_page_number_column()
    _ensure_sticker_type_column()

    team_code = _team_code_from_scan_result(scan_result)
    if not team_code:
        return

    catalog_rows = []
    for slot in scan_result.get("owned", []) + scan_result.get("missing", []):
        row = _catalog_row_from_slot(team_code, slot)
        if row:
            catalog_rows.append(row)

    if not catalog_rows:
        return

    inserted_rows = []

    with get_connection() as connection:
        for row in catalog_rows:
            existing = connection.execute(
                "SELECT player_name FROM stickers WHERE sticker_id = ?",
                (row["sticker_id"],),
            ).fetchone()

            if existing is not None:
                continue

            connection.execute(
                """
                INSERT INTO stickers (
                    sticker_id,
                    team_code,
                    number,
                    display_code,
                    player_name,
                    category,
                    page_code,
                    slot_position,
                    page_number,
                    sticker_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["sticker_id"],
                    row["team_code"],
                    row["number"],
                    row["display_code"],
                    row["player_name"],
                    row["category"],
                    row["page_code"],
                    row["slot_position"],
                    row.get("page_number", 0),
                    row.get("sticker_type", "player"),
                ),
            )
            inserted_rows.append(row)

    if inserted_rows:
        _sync_catalog_csv(inserted_rows)


def _sync_catalog_csv(new_rows: list[dict[str, Any]]) -> None:
    csv_path = Path(CATALOG_CSV_PATH)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = []

    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            existing_rows = list(reader)

    rows_by_id = {row["sticker_id"]: row for row in existing_rows}
    for new_row in new_rows:
        sticker_id = new_row["sticker_id"]
        csv_row = {column: str(new_row[column]) for column in CATALOG_COLUMNS}
        existing_row = rows_by_id.get(sticker_id)

        if existing_row is None:
            existing_rows.append(csv_row)
            rows_by_id[sticker_id] = csv_row
        elif (
            existing_row.get("player_name", "").strip() == PLACEHOLDER_NAME
            and _has_real_name(csv_row["player_name"])
        ):
            existing_row["player_name"] = csv_row["player_name"]

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        writer.writerows(existing_rows)


def _build_stats() -> dict[str, Any]:
    catalog = _scoped_catalog()
    total = int(len(catalog))
    owned = int((catalog["quantity"] > 0).sum()) if total else 0
    duplicates = int((catalog["quantity"] > 1).sum()) if total else 0
    missing = total - owned
    completion_pct = round((owned / total * 100), 2) if total else 0.0
    return {
        "total": total,
        "owned": owned,
        "missing": missing,
        "duplicates": duplicates,
        "completion_pct": completion_pct,
    }


def _dataframe_records(dataframe):
    return dataframe.to_dict("records")


@app.post("/scan")
async def scan(file: UploadFile = File(...)):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        processed_b64 = preprocess_album_image(file_bytes)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Image preprocessing failed: {error}")

    try:
        groq_client = _groq_client()
        response = groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{processed_b64}",
                            },
                        },
                    ],
                }
            ],
        )
    except APIStatusError as error:
        if _is_auth_error(error):
            raise HTTPException(status_code=401, detail="Groq authentication error")
        if _is_quota_error(error):
            raise HTTPException(status_code=429, detail="Groq quota or rate limit error")
        raise HTTPException(status_code=502, detail=f"Groq API error: {error}")
    except APIConnectionError as error:
        raise HTTPException(status_code=502, detail=f"Groq connection error: {error}")

    ai_response = _parse_ai_json_response(response.choices[0].message.content, "Groq")
    return _classify_slots(ai_response)


@app.post("/confirm")
async def confirm(scan_result: dict[str, Any]):
    _ensure_catalog_entries(scan_result)

    classification_rows = []
    team_code = _team_code_from_scan_result(scan_result)
    for slot in scan_result.get("owned", []):
        sticker_id = _resolve_confirm_sticker_id(slot, team_code)
        classification_rows.append(
            {
                "sticker_id": sticker_id,
                "confirmed_status": "owned",
                "is_special": _is_special_team_code(team_code),
            }
        )

    for slot in scan_result.get("missing", []):
        sticker_id = _resolve_confirm_sticker_id(slot, team_code)
        classification_rows.append(
            {
                "sticker_id": sticker_id,
                "confirmed_status": "missing",
                "is_special": _is_special_team_code(team_code),
            }
        )

    classification_rows = [row for row in classification_rows if row["sticker_id"]]
    summary = {
        "owned_saved_count": 0,
        "missing_confirmed_count": 0,
        "protected_already_owned_count": 0,
    }

    with get_connection() as connection:
        for row in classification_rows:
            sticker_id = row["sticker_id"]
            confirmed_status = row["confirmed_status"]

            if confirmed_status == "owned":
                quantity_row = connection.execute(
                    "SELECT quantity FROM collection WHERE sticker_id = ?",
                    (sticker_id,),
                ).fetchone()
                current_quantity = quantity_row[0] if quantity_row else 0

                connection.execute(
                    """
                    INSERT INTO collection (sticker_id, quantity)
                    VALUES (?, 1)
                    ON CONFLICT(sticker_id) DO UPDATE SET
                        quantity = collection.quantity + 1
                    """,
                    (sticker_id,),
                )

                if current_quantity >= 1:
                    summary["protected_already_owned_count"] += 1
                else:
                    summary["owned_saved_count"] += 1

                if row.get("is_special"):
                    saved_quantity_row = connection.execute(
                        "SELECT quantity FROM collection WHERE sticker_id = ?",
                        (sticker_id,),
                    ).fetchone()
                    quantity = saved_quantity_row[0] if saved_quantity_row else 0
                    print(f"Saved special sticker: {sticker_id} quantity={quantity}")
            elif confirmed_status == "missing":
                summary["missing_confirmed_count"] += 1

    return {
        "saved": len(classification_rows),
        "owned": summary["owned_saved_count"]
        + summary["protected_already_owned_count"],
        "missing": summary["missing_confirmed_count"],
        "stats": _build_stats(),
    }


@app.post("/catalog/import")
async def import_catalog():
    try:
        imported_count = import_catalog_from_csv(CATALOG_CSV_PATH)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return {"imported": imported_count}


@app.post("/catalog/import/full")
async def import_full_catalog():
    csv_path = Path(FULL_CATALOG_CSV_PATH)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Full catalog CSV not found")

    sections = {}
    try:
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                section = row.get("section", "Unknown") or "Unknown"
                sections[section] = sections.get(section, 0) + 1

        imported_count = _import_full_catalog_from_csv(csv_path)
        global FULL_CATALOG_IMPORTED
        FULL_CATALOG_IMPORTED = True
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return {"imported": imported_count, "sections": sections}


@app.post("/sticker/{sticker_id}/decrement")
async def decrement_sticker_quantity(sticker_id: str):
    with get_connection() as connection:
        quantity_row = connection.execute(
            "SELECT quantity FROM collection WHERE sticker_id = ?",
            (sticker_id,),
        ).fetchone()
        current_quantity = quantity_row[0] if quantity_row else 0

        if current_quantity > 1:
            new_quantity = current_quantity - 1
            connection.execute(
                "UPDATE collection SET quantity = ? WHERE sticker_id = ?",
                (new_quantity, sticker_id),
            )
        elif current_quantity == 1:
            new_quantity = 1
            connection.execute(
                "UPDATE collection SET quantity = ? WHERE sticker_id = ?",
                (new_quantity, sticker_id),
            )
        else:
            new_quantity = 0

    return {"sticker_id": sticker_id, "quantity": new_quantity}


@app.get("/collection")
async def collection():
    catalog = _scoped_catalog()
    return _dataframe_records(catalog.loc[catalog["quantity"] > 0])


@app.get("/missing")
async def missing():
    catalog = _scoped_catalog()
    return _dataframe_records(catalog.loc[~catalog["owned"]].reset_index(drop=True))


@app.get("/duplicates")
async def duplicates():
    catalog = _scoped_catalog()
    return _dataframe_records(catalog.loc[catalog["quantity"] > 1].reset_index(drop=True))


@app.get("/stats")
async def stats():
    return _build_stats()


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
