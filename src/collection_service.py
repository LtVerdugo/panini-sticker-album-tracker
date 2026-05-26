import pandas as pd

from src.database import get_connection


CATALOG_QUERY = """
    SELECT
        stickers.sticker_id,
        stickers.team_code,
        stickers.number,
        stickers.display_code,
        stickers.player_name,
        stickers.category,
        stickers.page_code,
        stickers.slot_position,
        COALESCE(collection.quantity, 0) AS quantity,
        CASE WHEN COALESCE(collection.quantity, 0) > 0 THEN 1 ELSE 0 END AS owned
    FROM stickers
    LEFT JOIN collection ON collection.sticker_id = stickers.sticker_id
    ORDER BY stickers.team_code, stickers.number
"""


def load_sticker_catalog() -> pd.DataFrame:
    with get_connection() as connection:
        catalog = pd.read_sql_query(CATALOG_QUERY, connection)

    if not catalog.empty:
        catalog["owned"] = catalog["owned"].astype(bool)

    return catalog


def load_collection_status() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT sticker_id, quantity
            FROM collection
            ORDER BY sticker_id
            """,
            connection,
        )


def get_missing_stickers() -> pd.DataFrame:
    catalog = load_sticker_catalog()
    return catalog.loc[~catalog["owned"]].reset_index(drop=True)


def get_duplicate_stickers() -> pd.DataFrame:
    catalog = load_sticker_catalog()
    return catalog.loc[catalog["quantity"] > 1].reset_index(drop=True)


def mark_sticker_as_owned(sticker_id: str) -> None:
    with get_connection() as connection:
        sticker = connection.execute(
            "SELECT sticker_id FROM stickers WHERE sticker_id = ?",
            (sticker_id,),
        ).fetchone()
        if sticker is None:
            raise ValueError(f"Unknown sticker_id: {sticker_id}")

        connection.execute(
            """
            INSERT INTO collection (sticker_id, quantity)
            VALUES (?, 1)
            ON CONFLICT(sticker_id) DO UPDATE SET
                quantity = collection.quantity + 1
            """,
            (sticker_id,),
        )


def save_confirmed_page_classification(classification_rows) -> dict[str, int]:
    if hasattr(classification_rows, "to_dict"):
        classification_rows = classification_rows.to_dict("records")

    summary = {
        "owned_saved_count": 0,
        "missing_confirmed_count": 0,
        "skipped_unknown_count": 0,
        "protected_already_owned_count": 0,
    }

    with get_connection() as connection:
        for row in classification_rows:
            sticker_id = row.get("sticker_id")
            confirmed_status = row.get("confirmed_status")
            if not sticker_id:
                continue

            quantity_row = connection.execute(
                "SELECT quantity FROM collection WHERE sticker_id = ?",
                (sticker_id,),
            ).fetchone()
            current_quantity = quantity_row[0] if quantity_row else 0

            if confirmed_status == "owned":
                if current_quantity >= 1:
                    summary["protected_already_owned_count"] += 1
                    continue

                connection.execute(
                    """
                    INSERT INTO collection (sticker_id, quantity)
                    VALUES (?, 1)
                    ON CONFLICT(sticker_id) DO UPDATE SET
                        quantity = CASE
                            WHEN collection.quantity < 1 THEN 1
                            ELSE collection.quantity
                        END
                    """,
                    (sticker_id,),
                )
                summary["owned_saved_count"] += 1
            elif confirmed_status == "missing":
                if current_quantity >= 1:
                    summary["protected_already_owned_count"] += 1
                else:
                    summary["missing_confirmed_count"] += 1
            else:
                summary["skipped_unknown_count"] += 1

    return summary
