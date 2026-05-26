import re
from collections import Counter

from src.ocr_engine import run_ocr_on_image
from src.page_layout import classify_slot_occupancy, crop_slots, crop_team_spread_slots
from src.text_cleaning import clean_ocr_results


COMPACT_CODE_PATTERN = re.compile(r"\b([A-Z]{3})0*(\d{1,3})\b")


def _catalog_team_codes(catalog_df) -> set[str]:
    return set(catalog_df["team_code"].astype(str).str.upper())


def _detect_team_code(cleaned_results: list[dict], catalog_df) -> str | None:
    catalog_team_codes = _catalog_team_codes(catalog_df)
    candidates = []

    for result in cleaned_results:
        cleaned_text = result["cleaned_text"]
        if cleaned_text in catalog_team_codes:
            candidates.append(cleaned_text)

        for sticker_code in _extract_missing_slot_codes(cleaned_text):
            team_code = sticker_code.split()[0]
            if team_code in catalog_team_codes:
                candidates.append(team_code)

    if not candidates:
        return None

    return Counter(candidates).most_common(1)[0][0]


def _extract_missing_slot_codes(cleaned_text: str) -> list[str]:
    codes = []

    for team_code, number in COMPACT_CODE_PATTERN.findall(cleaned_text):
        codes.append(f"{team_code} {int(number)}")

    # clean_ocr_results already extracts spaced, hyphenated, and underscored forms.
    cleaned_result = clean_ocr_results([{"text": cleaned_text}])
    if cleaned_result:
        codes.extend(cleaned_result[0].get("possible_sticker_codes", []))

    return list(dict.fromkeys(codes))


def _classification_row(sticker: dict) -> dict:
    return {
        "sticker_id": sticker["sticker_id"],
        "display_code": sticker["display_code"],
        "player_name": sticker["player_name"],
        "detected_status": "owned_candidate",
        "evidence_texts": "not detected as missing",
        "confidence": 0.5,
    }


def _set_missing(row: dict, evidence_text: str, confidence) -> None:
    evidence = []
    if row["evidence_texts"] != "not detected as missing":
        evidence = [text for text in row["evidence_texts"].split(", ") if text]

    if evidence_text and evidence_text not in evidence:
        evidence.append(evidence_text)

    row["detected_status"] = "missing_detected"
    row["evidence_texts"] = ", ".join(evidence)
    row["confidence"] = max(row["confidence"] or 0, confidence or 0.95)


def default_confirmed_status(detected_status: str) -> str:
    if detected_status == "missing_detected":
        return "missing"
    if detected_status == "owned_candidate":
        return "owned"
    return "unknown"


def _sticker_id_from_code(team_code: str, sticker_number: int) -> str:
    return f"{team_code}_{sticker_number:03d}"


def _slot_catalog_record(team_catalog, sticker_number: int, team_code: str) -> dict:
    matches = team_catalog.loc[team_catalog["number"].astype(int) == sticker_number]
    if not matches.empty:
        return matches.iloc[0].to_dict()

    sticker_id = _sticker_id_from_code(team_code, sticker_number)
    return {
        "sticker_id": sticker_id,
        "display_code": f"{team_code} {sticker_number}",
        "player_name": "",
    }


def _raw_text_from_ocr_results(ocr_results: list[dict]) -> str:
    return " ".join(str(result.get("text", "")).strip() for result in ocr_results).strip()


def _cleaned_text_from_ocr_results(ocr_results: list[dict]) -> str:
    cleaned_results = clean_ocr_results(ocr_results)
    return " ".join(result["cleaned_text"] for result in cleaned_results).strip()


def _expected_code_found(cleaned_text: str, team_code: str, sticker_number: int) -> bool:
    expected_code = f"{team_code} {sticker_number}"
    return expected_code in _extract_missing_slot_codes(cleaned_text)


def _slot_ocr_confidence(ocr_results: list[dict]) -> float:
    confidences = [
        float(result.get("confidence"))
        for result in ocr_results
        if result.get("confidence") is not None
    ]
    if not confidences:
        return 0.35
    return round(max(confidences), 3)


def _classify_slot_from_ocr_text(
    slot: dict,
    team_code: str,
    sticker: dict,
    ocr_results: list[dict],
) -> dict:
    sticker_number = int(slot["sticker_number"])
    raw_text = _raw_text_from_ocr_results(ocr_results)
    cleaned_text = _cleaned_text_from_ocr_results(ocr_results)
    expected_code = f"{team_code} {sticker_number}"
    expected_found = _expected_code_found(cleaned_text, team_code, sticker_number)

    if expected_found:
        detected_status = "missing_detected"
        confidence = max(0.9, _slot_ocr_confidence(ocr_results))
        evidence_texts = cleaned_text
    else:
        detected_status = "unknown"
        confidence = 0.35
        evidence_texts = "expected code not found"

    return {
        "sticker_number": sticker_number,
        "sticker_id": sticker["sticker_id"],
        "display_code": sticker["display_code"],
        "player_name": sticker["player_name"],
        "slot_id": slot["slot_id"],
        "detected_status": detected_status,
        "confirmed_status": default_confirmed_status(detected_status),
        "raw_slot_ocr_text": raw_text,
        "cleaned_slot_ocr_text": cleaned_text,
        "expected_code": expected_code,
        "expected_code_found": expected_found,
        "evidence_texts": evidence_texts,
        "confidence": confidence,
    }


def classify_slots_with_ocr(slot_crops, team_code, catalog_df):
    if catalog_df.empty or not team_code:
        return []

    normalized_team_code = team_code.strip().upper()
    team_catalog = catalog_df.loc[
        catalog_df["team_code"].astype(str).str.upper() == normalized_team_code
    ].copy()

    classified_rows = []
    for slot in slot_crops:
        sticker_number = int(slot["sticker_number"])
        sticker = _slot_catalog_record(team_catalog, sticker_number, normalized_team_code)
        try:
            ocr_results = run_ocr_on_image(slot["image"])
        except RuntimeError as error:
            ocr_results = [{"text": "", "confidence": None}]
            row = _classify_slot_from_ocr_text(
                slot,
                normalized_team_code,
                sticker,
                ocr_results,
            )
            row["evidence_texts"] = f"OCR error: {error}"
        else:
            row = _classify_slot_from_ocr_text(
                slot,
                normalized_team_code,
                sticker,
                ocr_results,
            )

        classified_rows.append(row)

    return classified_rows


def classify_album_page(ocr_results, catalog_df):
    if catalog_df.empty:
        return []

    cleaned_results = clean_ocr_results(ocr_results)
    team_code = _detect_team_code(cleaned_results, catalog_df)
    if team_code is None:
        return []

    team_catalog = catalog_df.loc[
        catalog_df["team_code"].astype(str).str.upper() == team_code
    ].copy()
    if team_catalog.empty:
        return []

    team_catalog = team_catalog.sort_values("number")
    classified_rows = []
    rows_by_display_code = {}

    for sticker in team_catalog.to_dict("records"):
        row = _classification_row(sticker)
        classified_rows.append(row)
        rows_by_display_code[str(sticker["display_code"]).upper()] = row

    for result in cleaned_results:
        for sticker_code in _extract_missing_slot_codes(result["cleaned_text"]):
            row = rows_by_display_code.get(sticker_code)
            if row is not None:
                _set_missing(row, result["cleaned_text"], result.get("confidence"))

    return classified_rows


def classify_album_page_by_layout(
    image,
    team_code: str,
    catalog_df,
    page_side: str | None = None,
    use_refined_boxes=True,
):
    if catalog_df.empty or not team_code:
        return []

    normalized_team_code = team_code.strip().upper()
    team_catalog = catalog_df.loc[
        catalog_df["team_code"].astype(str).str.upper() == normalized_team_code
    ].copy()
    if team_catalog.empty:
        return []

    stickers_by_number = {
        int(sticker["number"]): sticker
        for sticker in team_catalog.to_dict("records")
    }

    classified_rows = []
    slots = (
        crop_slots(image, page_side)
        if page_side
        else crop_team_spread_slots(image, use_refined_boxes=use_refined_boxes)
    )
    for slot in slots:
        sticker = stickers_by_number.get(slot["sticker_number"])
        if sticker is None:
            continue

        occupancy = classify_slot_occupancy(slot["image"])
        if occupancy == "empty_candidate":
            detected_status = "missing_detected"
            confidence = 0.75
        elif occupancy == "filled_candidate":
            detected_status = "owned_candidate"
            confidence = 0.65
        else:
            detected_status = "unknown"
            confidence = 0.4

        classified_rows.append(
            {
                "sticker_id": sticker["sticker_id"],
                "display_code": sticker["display_code"],
                "player_name": sticker["player_name"],
                "page_side": slot.get("page_side", page_side),
                "slot_id": slot["slot_id"],
                "refined": slot.get("refined", False),
                "refinement_confidence": slot.get("refinement_confidence", 0.0),
                "detected_status": detected_status,
                "evidence_texts": occupancy,
                "confidence": confidence,
            }
        )

    return classified_rows


def classify_team_spread_by_layout(
    image,
    team_code: str,
    catalog_df,
    use_refined_boxes=True,
):
    if catalog_df.empty or not team_code:
        return []

    normalized_team_code = team_code.strip().upper()
    team_catalog = catalog_df.loc[
        catalog_df["team_code"].astype(str).str.upper() == normalized_team_code
    ].copy()
    if team_catalog.empty:
        return []

    stickers_by_number = {
        int(sticker["number"]): sticker
        for sticker in team_catalog.to_dict("records")
    }

    classified_rows = []
    for slot in crop_team_spread_slots(image, use_refined_boxes=use_refined_boxes):
        sticker = stickers_by_number.get(slot["sticker_number"])
        if sticker is None:
            continue

        occupancy = classify_slot_occupancy(slot["image"])
        if occupancy == "empty_candidate":
            detected_status = "missing_detected"
            confidence = 0.75
        elif occupancy == "filled_candidate":
            detected_status = "owned_candidate"
            confidence = 0.65
        else:
            detected_status = "unknown"
            confidence = 0.4

        classified_rows.append(
            {
                "sticker_id": sticker["sticker_id"],
                "display_code": sticker["display_code"],
                "player_name": sticker["player_name"],
                "page_side": slot["page_side"],
                "slot_id": slot["slot_id"],
                "refined": slot.get("refined", False),
                "refinement_confidence": slot.get("refinement_confidence", 0.0),
                "detected_status": detected_status,
                "evidence_texts": occupancy,
                "confidence": confidence,
            }
        )

    return classified_rows
