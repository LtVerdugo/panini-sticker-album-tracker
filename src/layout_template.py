import json
from pathlib import Path


TEMPLATE_PATH = Path("config") / "layout_template.json"
EXPECTED_SLOT_COUNT = 20


def ensure_config_dir() -> None:
    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def validate_template(slot_boxes) -> bool:
    if not isinstance(slot_boxes, list) or len(slot_boxes) != EXPECTED_SLOT_COUNT:
        return False

    required_keys = {
        "sticker_number",
        "slot_id",
        "x_min",
        "y_min",
        "x_max",
        "y_max",
    }
    sticker_numbers = []
    for slot in slot_boxes:
        if not isinstance(slot, dict) or not required_keys.issubset(slot):
            return False

        try:
            sticker_number = int(slot["sticker_number"])
            x_min = float(slot["x_min"])
            y_min = float(slot["y_min"])
            x_max = float(slot["x_max"])
            y_max = float(slot["y_max"])
        except (TypeError, ValueError):
            return False

        if not 1 <= sticker_number <= EXPECTED_SLOT_COUNT:
            return False
        if not (0 <= x_min < x_max <= 1 and 0 <= y_min < y_max <= 1):
            return False

        sticker_numbers.append(sticker_number)

    return sorted(sticker_numbers) == list(range(1, EXPECTED_SLOT_COUNT + 1))


def save_layout_template(slot_boxes) -> None:
    if not validate_template(slot_boxes):
        raise ValueError("Layout template must contain exactly 20 valid slots.")

    ensure_config_dir()
    with TEMPLATE_PATH.open("w", encoding="utf-8") as template_file:
        json.dump(slot_boxes, template_file, indent=2)


def load_layout_template() -> list[dict]:
    if not TEMPLATE_PATH.exists():
        return []

    with TEMPLATE_PATH.open("r", encoding="utf-8") as template_file:
        slot_boxes = json.load(template_file)

    if not validate_template(slot_boxes):
        return []

    return slot_boxes


def has_layout_template() -> bool:
    return bool(load_layout_template())


def get_slot_from_template(sticker_number):
    for slot in load_layout_template():
        if int(slot["sticker_number"]) == int(sticker_number):
            return slot
    return None


def update_slot_in_template(sticker_number, new_box) -> None:
    slot_boxes = load_layout_template()
    if not slot_boxes:
        raise FileNotFoundError("No saved layout template exists.")

    updated_boxes = []
    slot_found = False
    for slot in slot_boxes:
        if int(slot["sticker_number"]) == int(sticker_number):
            updated_slot = {
                **slot,
                **new_box,
                "sticker_number": int(sticker_number),
                "slot_id": slot.get("slot_id", f"slot_{int(sticker_number):03d}"),
            }
            updated_boxes.append(updated_slot)
            slot_found = True
        else:
            updated_boxes.append(slot)

    if not slot_found:
        raise ValueError(f"Sticker {sticker_number} was not found in the template.")

    save_layout_template(updated_boxes)


def normalize_box_coordinates(box, image_width, image_height) -> dict:
    left = float(box.get("left", 0))
    top = float(box.get("top", 0))
    if "right" in box and "bottom" in box:
        right = float(box.get("right", 0))
        bottom = float(box.get("bottom", 0))
        width = right - left
        height = bottom - top
    else:
        width = float(box.get("width", 0)) * float(box.get("scaleX", 1))
        height = float(box.get("height", 0)) * float(box.get("scaleY", 1))

    x_min = max(0.0, min(left, left + width) / image_width)
    x_max = min(1.0, max(left, left + width) / image_width)
    y_min = max(0.0, min(top, top + height) / image_height)
    y_max = min(1.0, max(top, top + height) / image_height)

    return {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
    }
