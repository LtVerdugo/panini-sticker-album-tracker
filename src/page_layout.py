import cv2
import numpy as np

from src.layout_template import has_layout_template, load_layout_template
from src.page_alignment import CANONICAL_SPREAD_HEIGHT, CANONICAL_SPREAD_WIDTH


PAGE_SIDES = {
    "left": range(1, 11),
    "right": range(11, 21),
}

SLOT_GRID_BOXES = [
    (0.05, 0.08, 0.30, 0.28),
    (0.37, 0.08, 0.62, 0.28),
    (0.69, 0.08, 0.94, 0.28),
    (0.05, 0.31, 0.30, 0.51),
    (0.37, 0.31, 0.62, 0.51),
    (0.69, 0.31, 0.94, 0.51),
    (0.05, 0.54, 0.30, 0.74),
    (0.37, 0.54, 0.62, 0.74),
    (0.69, 0.54, 0.94, 0.74),
    (0.37, 0.77, 0.62, 0.97),
]

SPREAD_HALF_X = {
    "left": 0.0,
    "right": 0.5,
}


def get_slot_layout(page_side: str) -> list[dict]:
    page_side = page_side.lower()
    if page_side not in PAGE_SIDES:
        raise ValueError("page_side must be 'left' or 'right'")

    return [
        {
            "sticker_number": sticker_number,
            "slot_id": f"{page_side}_slot_{index + 1}",
            "x_min": box[0],
            "y_min": box[1],
            "x_max": box[2],
            "y_max": box[3],
        }
        for index, (sticker_number, box) in enumerate(
            zip(PAGE_SIDES[page_side], SLOT_GRID_BOXES)
        )
    ]


def crop_slots(image, page_side: str) -> list[dict]:
    height, width = image.shape[:2]
    slot_crops = []

    for slot in get_slot_layout(page_side):
        x_min = max(0, round(slot["x_min"] * width))
        y_min = max(0, round(slot["y_min"] * height))
        x_max = min(width, round(slot["x_max"] * width))
        y_max = min(height, round(slot["y_max"] * height))

        slot_crops.append(
            {
                **slot,
                "image": image[y_min:y_max, x_min:x_max],
                "pixel_box": (x_min, y_min, x_max, y_max),
            }
        )

    return slot_crops


def get_team_spread_slot_layout() -> list[dict]:
    """Return the fixed 20-slot layout for the canonical aligned spread."""
    saved_template = load_layout_template()
    if saved_template:
        return saved_template

    spread_slots = []
    for page_side in ("left", "right"):
        for slot in get_slot_layout(page_side):
            half_x = SPREAD_HALF_X[page_side]
            spread_slots.append(
                {
                    **slot,
                    "page_side": page_side,
                    "slot_id": f"{page_side}_spread_{slot['sticker_number']}",
                    "x_min": half_x + (slot["x_min"] * 0.5),
                    "x_max": half_x + (slot["x_max"] * 0.5),
                }
            )
    return spread_slots


def get_layout_template_source() -> str:
    if has_layout_template():
        return "Using saved calibrated layout template"
    return "Using approximate fallback layout template"


def _crop_from_slot(image, slot: dict) -> dict:
    height, width = image.shape[:2]
    x_min = max(0, round(slot["x_min"] * width))
    y_min = max(0, round(slot["y_min"] * height))
    x_max = min(width, round(slot["x_max"] * width))
    y_max = min(height, round(slot["y_max"] * height))

    return {
        **slot,
        "image": image[y_min:y_max, x_min:x_max],
        "pixel_box": (x_min, y_min, x_max, y_max),
    }


def _normalized_box_to_pixels(box: dict, image_width: int, image_height: int):
    x_min = max(0, round(box["x_min"] * image_width))
    y_min = max(0, round(box["y_min"] * image_height))
    x_max = min(image_width, round(box["x_max"] * image_width))
    y_max = min(image_height, round(box["y_max"] * image_height))
    return x_min, y_min, x_max, y_max


def _box_center(box: dict) -> tuple[float, float]:
    return (box["x_min"] + box["x_max"]) / 2, (box["y_min"] + box["y_max"]) / 2


def _box_area(box: dict) -> float:
    return max(0.0, box["x_max"] - box["x_min"]) * max(
        0.0,
        box["y_max"] - box["y_min"],
    )


def _box_iou(first_box: dict, second_box: dict) -> float:
    x_min = max(first_box["x_min"], second_box["x_min"])
    y_min = max(first_box["y_min"], second_box["y_min"])
    x_max = min(first_box["x_max"], second_box["x_max"])
    y_max = min(first_box["y_max"], second_box["y_max"])
    intersection = _box_area(
        {
            "x_min": x_min,
            "y_min": y_min,
            "x_max": x_max,
            "y_max": y_max,
        }
    )
    union = _box_area(first_box) + _box_area(second_box) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _refinement_metrics(original_box: dict, refined_box: dict) -> dict:
    original_area = _box_area(original_box)
    refined_area = _box_area(refined_box)
    original_center = _box_center(original_box)
    refined_center = _box_center(refined_box)
    original_width = original_box["x_max"] - original_box["x_min"]
    original_height = original_box["y_max"] - original_box["y_min"]
    refined_width = refined_box["x_max"] - refined_box["x_min"]
    refined_height = refined_box["y_max"] - refined_box["y_min"]

    return {
        "original_area": round(float(original_area), 6),
        "refined_area": round(float(refined_area), 6),
        "area_ratio": round(float(refined_area / original_area), 3)
        if original_area
        else 0.0,
        "center_shift_x": round(
            float(abs(refined_center[0] - original_center[0]) / original_width),
            3,
        )
        if original_width
        else 0.0,
        "center_shift_y": round(
            float(abs(refined_center[1] - original_center[1]) / original_height),
            3,
        )
        if original_height
        else 0.0,
        "iou": round(float(_box_iou(original_box, refined_box)), 3),
        "aspect_ratio": round(float(refined_width / refined_height), 3)
        if refined_height
        else 0.0,
    }


def _rejected_metadata(
    reason: str,
    original_box: dict,
    candidate_box: dict | None = None,
):
    metrics = _refinement_metrics(original_box, candidate_box or original_box)
    return {
        "refined": False,
        "refinement_confidence": 0.0,
        "refinement_reason": reason,
        **metrics,
    }


def _validate_refined_box(original_box: dict, candidate_box: dict):
    metrics = _refinement_metrics(original_box, candidate_box)

    if metrics["center_shift_x"] > 0.15 or metrics["center_shift_y"] > 0.15:
        return False, "rejected: center shift too large", metrics
    if metrics["area_ratio"] < 0.75 or metrics["area_ratio"] > 1.25:
        return False, "rejected: area ratio outside safe range", metrics
    if metrics["aspect_ratio"] < 0.55 or metrics["aspect_ratio"] > 0.95:
        return False, "rejected: aspect ratio outside safe range", metrics
    if metrics["iou"] < 0.65:
        return False, "rejected: IoU below safe threshold", metrics

    return True, "accepted", metrics


def refine_slot_box_with_edges(image, box, padding_ratio=0.08):
    image_height, image_width = image.shape[:2]
    original_box = {
        key: float(box[key])
        for key in ("x_min", "y_min", "x_max", "y_max")
    }
    box_width = original_box["x_max"] - original_box["x_min"]
    box_height = original_box["y_max"] - original_box["y_min"]
    if box_width <= 0 or box_height <= 0:
        return original_box, {
            **_rejected_metadata("invalid original box", original_box),
        }

    padded_box = {
        "x_min": max(0.0, original_box["x_min"] - (box_width * padding_ratio)),
        "y_min": max(0.0, original_box["y_min"] - (box_height * padding_ratio)),
        "x_max": min(1.0, original_box["x_max"] + (box_width * padding_ratio)),
        "y_max": min(1.0, original_box["y_max"] + (box_height * padding_ratio)),
    }
    px_min, py_min, px_max, py_max = _normalized_box_to_pixels(
        padded_box,
        image_width,
        image_height,
    )
    search_region = image[py_min:py_max, px_min:px_max]
    if search_region.size == 0:
        return original_box, {
            **_rejected_metadata("empty search region", original_box),
        }

    gray = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 160)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    original_area = _box_area(original_box)
    original_center = _box_center(original_box)
    original_aspect = box_width / box_height
    best_candidate = None
    best_score = 0.0

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width <= 0 or height <= 0:
            continue

        candidate_box = {
            "x_min": (px_min + x) / image_width,
            "y_min": (py_min + y) / image_height,
            "x_max": (px_min + x + width) / image_width,
            "y_max": (py_min + y + height) / image_height,
        }
        candidate_area = _box_area(candidate_box)
        if candidate_area <= 0:
            continue

        is_valid, _, metrics = _validate_refined_box(original_box, candidate_box)
        if not is_valid:
            continue

        candidate_width = candidate_box["x_max"] - candidate_box["x_min"]
        candidate_height = candidate_box["y_max"] - candidate_box["y_min"]
        candidate_aspect = candidate_width / candidate_height
        aspect_ratio_delta = abs(candidate_aspect - original_aspect) / original_aspect
        if aspect_ratio_delta > 0.45:
            continue

        candidate_center = _box_center(candidate_box)
        center_distance = np.hypot(
            candidate_center[0] - original_center[0],
            candidate_center[1] - original_center[1],
        )
        max_center_distance = max(box_width, box_height) * 0.35
        if center_distance > max_center_distance:
            continue

        contour_area = cv2.contourArea(contour)
        fill_ratio = contour_area / max(1, width * height)
        area_ratio = metrics["area_ratio"]
        score = (
            (1.0 - min(aspect_ratio_delta, 1.0)) * 0.35
            + (1.0 - min(center_distance / max_center_distance, 1.0)) * 0.35
            + min(fill_ratio, 1.0) * 0.15
            + (1.0 - min(abs(1.0 - area_ratio), 1.0)) * 0.15
        )
        if score > best_score:
            best_score = score
            best_candidate = candidate_box

    if best_candidate is None or best_score < 0.45:
        return original_box, {
            **_rejected_metadata("no safe contour found", original_box),
        }

    is_valid, reason, metrics = _validate_refined_box(original_box, best_candidate)
    if not is_valid:
        return original_box, {
            **_rejected_metadata(reason, original_box, best_candidate),
        }

    return best_candidate, {
        "refined": True,
        "refinement_confidence": round(float(best_score), 3),
        "refinement_reason": "accepted",
        **metrics,
    }


def refine_slot_boxes(image, slot_definitions):
    refined_slots = []
    for slot in slot_definitions:
        refined_box, metadata = refine_slot_box_with_edges(image, slot)
        refined_slots.append(
            {
                **slot,
                **refined_box,
                "template_x_min": slot["x_min"],
                "template_y_min": slot["y_min"],
                "template_x_max": slot["x_max"],
                "template_y_max": slot["y_max"],
                **metadata,
            }
        )
    return refined_slots


def crop_team_spread_slots(image, use_refined_boxes=True) -> list[dict]:
    slot_definitions = get_team_spread_slot_layout()
    if use_refined_boxes:
        slot_definitions = refine_slot_boxes(image, slot_definitions)
    else:
        slot_definitions = [
            {
                **slot,
                "refined": False,
                "refinement_confidence": 0.0,
                "refinement_reason": "refinement disabled",
                **_refinement_metrics(slot, slot),
            }
            for slot in slot_definitions
        ]

    return [_crop_from_slot(image, slot) for slot in slot_definitions]


def draw_slot_boxes(image, use_refined_boxes=False):
    overlay = image.copy()
    height, width = overlay.shape[:2]
    slot_definitions = get_team_spread_slot_layout()
    if use_refined_boxes:
        slot_definitions = refine_slot_boxes(image, slot_definitions)

    for slot in slot_definitions:
        x_min = max(0, round(slot["x_min"] * width))
        y_min = max(0, round(slot["y_min"] * height))
        x_max = min(width, round(slot["x_max"] * width))
        y_max = min(height, round(slot["y_max"] * height))
        color = (0, 200, 255) if use_refined_boxes else (0, 255, 0)
        cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), color, 2)
        cv2.putText(
            overlay,
            str(slot["sticker_number"]),
            (x_min + 8, y_min + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
            cv2.LINE_AA,
        )

    return cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)


def canonical_spread_size() -> tuple[int, int]:
    return CANONICAL_SPREAD_WIDTH, CANONICAL_SPREAD_HEIGHT


def classify_slot_occupancy(slot_image) -> str:
    if slot_image.size == 0:
        return "unknown"

    if len(slot_image.shape) == 3:
        gray = cv2.cvtColor(slot_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = slot_image

    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    edges = cv2.Canny(gray, 80, 160)
    edge_density = float(np.count_nonzero(edges)) / edges.size
    dark_text_ratio = float(np.count_nonzero(gray < 90)) / gray.size

    # Empty printed slots are usually bright, sparse, and mostly text outlines.
    if brightness > 150 and contrast < 55 and edge_density < 0.13 and dark_text_ratio < 0.18:
        return "empty_candidate"

    if contrast > 45 or edge_density > 0.10 or dark_text_ratio > 0.16:
        return "filled_candidate"

    return "unknown"
