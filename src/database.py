import csv
import sqlite3
from pathlib import Path


DB_PATH = Path("data") / "panini_tracker.db"

CATALOG_COLUMNS = (
    "sticker_id",
    "team_code",
    "number",
    "display_code",
    "player_name",
    "category",
    "page_code",
    "slot_position",
)


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS stickers (
                sticker_id TEXT PRIMARY KEY,
                team_code TEXT NOT NULL,
                number INTEGER NOT NULL,
                display_code TEXT NOT NULL,
                player_name TEXT NOT NULL,
                category TEXT NOT NULL,
                page_code TEXT NOT NULL,
                slot_position TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collection (
                sticker_id TEXT PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                FOREIGN KEY (sticker_id) REFERENCES stickers (sticker_id)
            );

            CREATE TABLE IF NOT EXISTS scans (
                scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT,
                scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS scan_results (
                scan_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                sticker_id TEXT,
                raw_text TEXT,
                confidence REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scan_id) REFERENCES scans (scan_id),
                FOREIGN KEY (sticker_id) REFERENCES stickers (sticker_id)
            );
            """
        )


def import_catalog_from_csv(csv_path: str | Path) -> int:
    csv_path = Path(csv_path)

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = set(CATALOG_COLUMNS) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Catalog CSV is missing columns: {missing}")

        rows = [
            tuple(row[column].strip() for column in CATALOG_COLUMNS)
            for row in reader
        ]

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
                slot_position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sticker_id) DO UPDATE SET
                team_code = excluded.team_code,
                number = excluded.number,
                display_code = excluded.display_code,
                player_name = excluded.player_name,
                category = excluded.category,
                page_code = excluded.page_code,
                slot_position = excluded.slot_position
            """,
            rows,
        )
        return connection.total_changes - before_count
