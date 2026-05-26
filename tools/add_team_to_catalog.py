import argparse
import csv
import json
import re
from pathlib import Path


CATALOG_PATH = Path("data") / "sticker_catalog.csv"
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
PLACEHOLDER_NAME = "To be completed"


def parse_slot_code(code: str) -> tuple[str, int]:
    match = re.search(r"\b([A-Za-z]{3})[\s_-]*(\d{1,3})\b", str(code))
    if not match:
        raise ValueError(f"Could not read sticker code: {code}")

    team_code = match.group(1).upper()
    number = int(match.group(2))
    return team_code, number


def category_for_number(number: int) -> str:
    if number == 1:
        return "badge"
    if number == 13:
        return "team_photo"
    return "player"


def generate_catalog_row(team_code: str, slot: dict) -> dict:
    code_team, number = parse_slot_code(slot.get("code", ""))
    if code_team != team_code:
        raise ValueError(
            f"Slot code team {code_team} does not match scan team {team_code}"
        )

    player_name = str(slot.get("name", "")).strip() or PLACEHOLDER_NAME
    return {
        "sticker_id": f"{team_code}_{number:03d}",
        "team_code": team_code,
        "number": str(number),
        "display_code": f"{team_code} {number}",
        "player_name": player_name,
        "category": category_for_number(number),
        "page_code": team_code.lower(),
        "slot_position": f"slot_{number:02d}",
    }


def load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []

    with CATALOG_PATH.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = set(CATALOG_COLUMNS) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Catalog CSV is missing columns: {missing}")
        return list(reader)


def save_catalog(rows: list[dict]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def add_team_to_catalog(scan_json_path: Path) -> tuple[int, int, str]:
    with scan_json_path.open(encoding="utf-8") as json_file:
        scan_result = json.load(json_file)

    team_code = str(scan_result.get("team_code", "")).strip().upper()
    if not team_code:
        raise ValueError("Scan JSON is missing team_code")

    raw_slots = scan_result.get("raw_slots", [])
    if not isinstance(raw_slots, list) or not raw_slots:
        raise ValueError("Scan JSON must contain a non-empty raw_slots array")

    generated_rows = [generate_catalog_row(team_code, slot) for slot in raw_slots]

    catalog_rows = load_catalog()
    existing_by_id = {row["sticker_id"]: row for row in catalog_rows}
    added_count = 0
    updated_count = 0

    for new_row in generated_rows:
        existing_row = existing_by_id.get(new_row["sticker_id"])
        if existing_row:
            if (
                existing_row.get("player_name", "").strip() == PLACEHOLDER_NAME
                and new_row["player_name"] != PLACEHOLDER_NAME
            ):
                existing_row["player_name"] = new_row["player_name"]
                updated_count += 1
            continue

        catalog_rows.append(new_row)
        existing_by_id[new_row["sticker_id"]] = new_row
        added_count += 1

    save_catalog(catalog_rows)
    return added_count, updated_count, team_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a team from a /scan JSON result to sticker_catalog.csv."
    )
    parser.add_argument("scan_json", help="Path to a JSON file returned by /scan.")
    args = parser.parse_args()

    added_count, updated_count, team_code = add_team_to_catalog(Path(args.scan_json))
    print(f"Added {added_count} new, updated {updated_count} existing rows for team {team_code}")


if __name__ == "__main__":
    main()
