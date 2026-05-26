import sqlite3
from pathlib import Path

import cv2
import streamlit as st
from pandas.errors import DatabaseError

try:
    from streamlit_image_coordinates import streamlit_image_coordinates
except ImportError:
    streamlit_image_coordinates = None

from src.collection_service import (
    get_duplicate_stickers,
    get_missing_stickers,
    load_sticker_catalog,
    mark_sticker_as_owned,
    save_confirmed_page_classification,
)
from src.database import import_catalog_from_csv, init_db
from src.image_preprocessing import (
    convert_bgr_to_rgb,
    load_image_from_bytes,
    normalize_image_orientation,
    preprocess_image_for_ocr,
)
from src.image_storage import (
    get_image_bytes,
    get_image_display_name,
    save_image_for_debug,
)
from src.layout_template import (
    TEMPLATE_PATH,
    load_layout_template,
    normalize_box_coordinates,
    save_layout_template,
    update_slot_in_template,
    validate_template,
)
from src.ocr_engine import resize_for_ocr, run_ocr_on_image
from src.page_alignment import align_team_spread_with_template
from src.page_classifier import (
    classify_album_page,
    classify_album_page_by_layout,
    classify_slots_with_ocr,
    default_confirmed_status,
)
from src.page_layout import (
    crop_team_spread_slots,
    draw_slot_boxes,
    get_layout_template_source,
)
from src.text_cleaning import clean_ocr_results
from src.text_matching import aggregate_match_suggestions, suggest_sticker_matches
from src.template_alignment import TEMPLATE_IMAGE_PATH, save_template_image


SECTIONS = {
    "Scan": "Capture or upload sticker images for later processing.",
    "Collection": "Track owned stickers and quantities from the local catalog.",
    "Missing": "Stickers with no owned copies appear here.",
    "Duplicates": "Stickers with more than one owned copy appear here.",
    "Dashboard": "Collection insights and progress charts will appear here.",
    "Settings": "Initialize local storage and import the sticker catalog.",
}

CATALOG_CSV_PATH = Path("data") / "sticker_catalog.csv"


def show_data_error(error: Exception) -> None:
    st.error(f"Collection data is not ready: {error}")
    st.caption("Initialize the database and import the catalog in Settings.")


def _team_code_options(catalog) -> list[str]:
    if catalog.empty:
        return []
    return sorted(catalog["team_code"].dropna().astype(str).str.upper().unique())


def _detect_team_code_from_ocr_results(ocr_results: list[dict], team_codes: list[str]):
    for result in ocr_results:
        text = str(result.get("text", "")).strip().upper()
        if text in team_codes:
            return text
    return team_codes[0] if team_codes else ""


def show_page_classification_editor(classification_rows, key_prefix: str) -> None:
    validation_rows = [
        {
            **row,
            "confirmed_status": row.get(
                "confirmed_status",
                default_confirmed_status(row["detected_status"]),
            ),
        }
        for row in classification_rows
    ]
    disabled_columns = [
        column
        for column in validation_rows[0]
        if column != "confirmed_status"
    ] if validation_rows else []
    confirmed_rows = st.data_editor(
        validation_rows,
        column_config={
            "confirmed_status": st.column_config.SelectboxColumn(
                "confirmed_status",
                options=["owned", "missing", "unknown"],
                required=True,
            )
        },
        disabled=disabled_columns,
        hide_index=True,
        width="stretch",
        key=f"{key_prefix}_classification_editor",
    )
    if st.button("Save confirmed page classification", key=f"{key_prefix}_save"):
        summary = save_confirmed_page_classification(confirmed_rows)
        st.success(
            "Saved confirmed page classification: "
            f"{summary['owned_saved_count']} owned saved, "
            f"{summary['missing_confirmed_count']} missing confirmed, "
            f"{summary['skipped_unknown_count']} unknown skipped, "
            f"{summary['protected_already_owned_count']} already owned protected."
        )


def _get_calibration_state() -> dict:
    if "layout_calibration" not in st.session_state:
        st.session_state["layout_calibration"] = {
            "slot_boxes": [],
            "pending_click": None,
            "click_history": [],
            "last_click_key": None,
        }
    return st.session_state["layout_calibration"]


def _draw_calibration_preview(image, slot_boxes, pending_click=None):
    preview = image.copy()
    image_height, image_width = preview.shape[:2]

    for slot in slot_boxes:
        x_min = round(slot["x_min"] * image_width)
        y_min = round(slot["y_min"] * image_height)
        x_max = round(slot["x_max"] * image_width)
        y_max = round(slot["y_max"] * image_height)
        cv2.rectangle(preview, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        cv2.putText(
            preview,
            str(slot["sticker_number"]),
            (x_min + 8, y_min + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    if pending_click:
        cv2.circle(
            preview,
            (round(pending_click["x"]), round(pending_click["y"])),
            8,
            (0, 0, 255),
            -1,
        )

    return cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)


def _add_calibration_click(click_position, image_width, image_height) -> None:
    calibration = _get_calibration_state()
    slot_number = len(calibration["slot_boxes"]) + 1
    if slot_number > 20:
        return

    click = {
        "x": float(click_position["x"]),
        "y": float(click_position["y"]),
    }
    calibration["click_history"].append(click)

    if calibration["pending_click"] is None:
        calibration["pending_click"] = click
        return

    top_left = calibration["pending_click"]
    bottom_right = click
    coordinates = normalize_box_coordinates(
        {
            "left": top_left["x"],
            "top": top_left["y"],
            "right": bottom_right["x"],
            "bottom": bottom_right["y"],
        },
        image_width,
        image_height,
    )
    calibration["slot_boxes"].append(
        {
            "sticker_number": slot_number,
            "slot_id": f"slot_{slot_number:03d}",
            **coordinates,
        }
    )
    calibration["pending_click"] = None


def _undo_calibration_click() -> None:
    calibration = _get_calibration_state()
    if calibration["pending_click"] is not None:
        calibration["pending_click"] = None
        if calibration["click_history"]:
            calibration["click_history"].pop()
    elif calibration["slot_boxes"]:
        calibration["slot_boxes"].pop()
        if calibration["click_history"]:
            calibration["click_history"].pop()
        if calibration["click_history"]:
            calibration["pending_click"] = calibration["click_history"].pop()
    calibration["last_click_key"] = None


def _reset_calibration() -> None:
    st.session_state["layout_calibration"] = {
        "slot_boxes": [],
        "pending_click": None,
        "click_history": [],
        "last_click_key": None,
    }


def _get_selective_calibration_state() -> dict:
    if "selective_slot_calibration" not in st.session_state:
        st.session_state["selective_slot_calibration"] = {
            "slot_boxes": {},
            "pending_click": None,
            "active_sticker_number": None,
            "last_click_key": None,
        }
    return st.session_state["selective_slot_calibration"]


def _reset_selective_calibration() -> None:
    st.session_state["selective_slot_calibration"] = {
        "slot_boxes": {},
        "pending_click": None,
        "active_sticker_number": None,
        "last_click_key": None,
    }


def _add_selective_calibration_click(
    click_position,
    sticker_number,
    image_width,
    image_height,
) -> None:
    calibration = _get_selective_calibration_state()
    click = {
        "x": float(click_position["x"]),
        "y": float(click_position["y"]),
    }

    if calibration["pending_click"] is None:
        calibration["pending_click"] = click
        calibration["active_sticker_number"] = sticker_number
        return

    top_left = calibration["pending_click"]
    bottom_right = click
    coordinates = normalize_box_coordinates(
        {
            "left": top_left["x"],
            "top": top_left["y"],
            "right": bottom_right["x"],
            "bottom": bottom_right["y"],
        },
        image_width,
        image_height,
    )
    calibration["slot_boxes"][sticker_number] = {
        "sticker_number": sticker_number,
        "slot_id": f"slot_{sticker_number:03d}",
        **coordinates,
    }
    calibration["pending_click"] = None
    calibration["active_sticker_number"] = None


def _undo_selective_calibration_click() -> None:
    calibration = _get_selective_calibration_state()
    if calibration["pending_click"] is not None:
        calibration["pending_click"] = None
        calibration["active_sticker_number"] = None
    elif calibration["slot_boxes"]:
        last_sticker_number = list(calibration["slot_boxes"])[-1]
        calibration["slot_boxes"].pop(last_sticker_number)
    calibration["last_click_key"] = None


def show_layout_calibration(prepared_scan) -> None:
    with st.expander("Full layout recalibration"):
        st.caption(
            "Calibrate stickers in order. For each sticker, click the top-left "
            "corner, then the bottom-right corner."
        )
        st.write(f"Current layout source: {get_layout_template_source()}")

        if streamlit_image_coordinates is None:
            st.warning(
                "Install streamlit-image-coordinates from requirements.txt to use "
                "click-based layout calibration."
            )
            return

        calibration = _get_calibration_state()
        aligned_image = prepared_scan["aligned_image"]
        image_height, image_width = aligned_image.shape[:2]
        display_width = min(1000, image_width)
        display_height = round(display_width * image_height / image_width)
        display_image = cv2.resize(
            aligned_image,
            (display_width, display_height),
            interpolation=cv2.INTER_AREA,
        )
        slot_number = len(calibration["slot_boxes"]) + 1
        if slot_number <= 20:
            corner_label = (
                "bottom-right"
                if calibration["pending_click"] is not None
                else "top-left"
            )
            st.info(f"Click {corner_label} corner for sticker {slot_number}")
        else:
            st.success("All 20 sticker boxes have been captured.")

        preview_image = _draw_calibration_preview(
            display_image,
            calibration["slot_boxes"],
            calibration["pending_click"],
        )
        click_position = streamlit_image_coordinates(
            preview_image,
            key="layout_calibration_image",
            width=display_width,
        )
        if click_position:
            click_key = (
                click_position.get("x"),
                click_position.get("y"),
                click_position.get("width"),
                click_position.get("height"),
            )
            if click_key != calibration["last_click_key"]:
                calibration["last_click_key"] = click_key
                _add_calibration_click(click_position, display_width, display_height)
                st.rerun()

        slot_boxes = calibration["slot_boxes"]
        st.write(f"Detected rectangles: {len(slot_boxes)} / 20")

        if slot_boxes:
            st.dataframe(slot_boxes, hide_index=True, width="stretch")

        undo_column, reset_column, save_column, clear_column = st.columns(4)
        with undo_column:
            if st.button("Undo last click"):
                _undo_calibration_click()
                st.rerun()

        with reset_column:
            if st.button("Reset calibration"):
                _reset_calibration()
                st.rerun()

        with save_column:
            if st.button("Save layout template"):
                if not validate_template(slot_boxes):
                    st.error("Capture exactly 20 valid boxes before saving.")
                else:
                    try:
                        save_layout_template(slot_boxes)
                        template_image_path = save_template_image(
                            prepared_scan["aligned_image"]
                        )
                    except ValueError as error:
                        st.error(f"Layout template was not saved: {error}")
                    except OSError as error:
                        st.error(f"Template image was not saved: {error}")
                    else:
                        st.success(
                            f"Layout template saved to {TEMPLATE_PATH}; "
                            f"template image saved to {template_image_path}"
                        )
                        st.rerun()

        with clear_column:
            if st.button("Clear layout template"):
                if TEMPLATE_PATH.exists():
                    TEMPLATE_PATH.unlink()
                    st.success("Layout template cleared.")
                    _reset_selective_calibration()
                    st.rerun()
                else:
                    st.info("No saved layout template exists yet.")

        if st.button("Clear template image"):
            if TEMPLATE_IMAGE_PATH.exists():
                TEMPLATE_IMAGE_PATH.unlink()
                st.success("Template image cleared.")
                st.rerun()
            else:
                st.info("No saved template image exists yet.")


def _status_by_sticker_number(layout_classification) -> dict[int, str]:
    status_by_number = {}
    for row in layout_classification:
        display_code = str(row.get("display_code", ""))
        try:
            sticker_number = int(display_code.split()[-1])
        except (IndexError, ValueError):
            continue
        status_by_number[sticker_number] = row.get("detected_status", "")
    return status_by_number


def _slot_crops_by_number(slot_crops) -> dict[int, dict]:
    return {int(slot["sticker_number"]): slot for slot in slot_crops}


def show_slot_crop_review(
    template_slot_crops,
    refined_slot_crops,
    layout_classification,
) -> list[int]:
    st.subheader("Slot crop review")
    status_by_number = _status_by_sticker_number(layout_classification)
    template_crops_by_number = _slot_crops_by_number(template_slot_crops)
    review_rows = []

    for index in range(0, len(refined_slot_crops), 5):
        columns = st.columns(5)
        for column, slot in zip(columns, refined_slot_crops[index : index + 5]):
            sticker_number = int(slot["sticker_number"])
            template_slot = template_crops_by_number.get(sticker_number, slot)
            detected_status = status_by_number.get(sticker_number, "not classified")
            with column:
                st.image(
                    convert_bgr_to_rgb(template_slot["image"]),
                    caption=(
                        f"Template {sticker_number} | {template_slot['slot_id']}"
                    ),
                    width="stretch",
                )
                if slot.get("refined"):
                    st.image(
                        convert_bgr_to_rgb(slot["image"]),
                        caption=f"Refined {sticker_number}",
                        width="stretch",
                    )
                else:
                    st.caption("Refined crop unavailable; using template box.")

                default_choice = (
                    "Use refined box" if slot.get("refined") else "Use template box"
                )
                box_choice = st.selectbox(
                    f"Box choice {sticker_number}",
                    ["Use template box", "Use refined box"],
                    index=1 if default_choice == "Use refined box" else 0,
                    key=f"slot_box_choice_{sticker_number}",
                )
                review_status = st.radio(
                    f"Review sticker {sticker_number}",
                    ["Crop OK", "Needs recalibration"],
                    horizontal=True,
                    key=f"slot_review_{sticker_number}",
                    label_visibility="collapsed",
                )
                review_rows.append(
                    {
                        "sticker_number": sticker_number,
                        "slot_id": slot["slot_id"],
                        "detected_status": detected_status,
                        "refined": slot.get("refined", False),
                        "box_choice": box_choice,
                        "refinement_confidence": slot.get(
                            "refinement_confidence",
                            0.0,
                        ),
                        "refinement_reason": slot.get("refinement_reason", ""),
                        "iou": slot.get("iou", 0.0),
                        "area_ratio": slot.get("area_ratio", 0.0),
                        "review_status": review_status,
                    }
                )

    st.dataframe(review_rows, hide_index=True, width="stretch")
    st.info(
        "Per-slot template/refined choices are for review in this version. "
        "Layout classification still follows the global refinement checkbox."
    )
    return [
        row["sticker_number"]
        for row in review_rows
        if row["review_status"] == "Needs recalibration"
    ]


def show_selective_slot_recalibration(prepared_scan, selected_slot_numbers) -> None:
    st.subheader("Selective slot recalibration")
    if not load_layout_template():
        st.info("Save a full layout template before recalibrating individual slots.")
        return

    if not selected_slot_numbers:
        st.caption("Mark one or more slots as Needs recalibration above.")
        return

    if streamlit_image_coordinates is None:
        st.warning(
            "Install streamlit-image-coordinates from requirements.txt to use "
            "selective slot recalibration."
        )
        return

    calibration = _get_selective_calibration_state()
    selected_slot_numbers = sorted(set(selected_slot_numbers))
    for sticker_number in list(calibration["slot_boxes"]):
        if sticker_number not in selected_slot_numbers:
            calibration["slot_boxes"].pop(sticker_number)
    if calibration["active_sticker_number"] not in selected_slot_numbers:
        calibration["pending_click"] = None
        calibration["active_sticker_number"] = None

    aligned_image = prepared_scan["aligned_image"]
    image_height, image_width = aligned_image.shape[:2]
    display_width = min(1000, image_width)
    display_height = round(display_width * image_height / image_width)
    display_image = cv2.resize(
        aligned_image,
        (display_width, display_height),
        interpolation=cv2.INTER_AREA,
    )

    pending_slots = [
        sticker_number
        for sticker_number in selected_slot_numbers
        if sticker_number not in calibration["slot_boxes"]
    ]
    active_sticker_number = calibration["active_sticker_number"]
    if active_sticker_number is None:
        active_sticker_number = pending_slots[0] if pending_slots else None

    if active_sticker_number is None:
        st.success("All selected slots have corrected boxes ready to save.")
    else:
        corner_label = (
            "bottom-right"
            if calibration["pending_click"] is not None
            else "top-left"
        )
        st.info(f"Click {corner_label} corner for sticker {active_sticker_number}")

    corrected_boxes = list(calibration["slot_boxes"].values())
    preview_image = _draw_calibration_preview(
        display_image,
        corrected_boxes,
        calibration["pending_click"],
    )
    click_position = streamlit_image_coordinates(
        preview_image,
        key="selective_slot_calibration_image",
        width=display_width,
    )
    if click_position and active_sticker_number is not None:
        click_key = (
            click_position.get("x"),
            click_position.get("y"),
            click_position.get("width"),
            click_position.get("height"),
            active_sticker_number,
        )
        if click_key != calibration["last_click_key"]:
            calibration["last_click_key"] = click_key
            _add_selective_calibration_click(
                click_position,
                active_sticker_number,
                display_width,
                display_height,
            )
            st.rerun()

    if corrected_boxes:
        st.dataframe(corrected_boxes, hide_index=True, width="stretch")

    undo_column, reset_column, save_column = st.columns(3)
    with undo_column:
        if st.button("Undo selective click"):
            _undo_selective_calibration_click()
            st.rerun()

    with reset_column:
        if st.button("Reset selective recalibration"):
            _reset_selective_calibration()
            st.rerun()

    with save_column:
        if st.button("Save corrected slots"):
            if pending_slots or not corrected_boxes:
                st.error("Capture corrected boxes for all selected slots first.")
                return

            try:
                for sticker_number in selected_slot_numbers:
                    slot_box = calibration["slot_boxes"][sticker_number]
                    update_slot_in_template(sticker_number, slot_box)
            except (FileNotFoundError, ValueError) as error:
                st.error(f"Corrected slots were not saved: {error}")
            else:
                _reset_selective_calibration()
                st.success("Corrected slots saved to the layout template.")
                st.rerun()


def show_per_slot_ocr_results(per_slot_rows, slot_crops) -> None:
    st.subheader("Per-slot OCR results")
    st.dataframe(per_slot_rows, hide_index=True, width="stretch")

    st.info(
        "Per-slot OCR only marks missing when the expected team code and sticker "
        "number are found inside that same slot. Owned is not inferred."
    )
    show_page_classification_editor(per_slot_rows, "per_slot_ocr")

    crops_by_number = _slot_crops_by_number(slot_crops)
    with st.expander("Per-slot OCR debug"):
        for index in range(0, len(per_slot_rows), 4):
            columns = st.columns(4)
            for column, row in zip(columns, per_slot_rows[index : index + 4]):
                sticker_number = int(row["sticker_number"])
                crop = crops_by_number.get(sticker_number)
                with column:
                    st.write(f"Sticker {sticker_number}")
                    st.write(row["sticker_id"])
                    if crop is not None:
                        st.image(
                            convert_bgr_to_rgb(crop["image"]),
                            caption="OCR crop",
                            width="stretch",
                        )
                    st.write(f"Raw: {row['raw_slot_ocr_text'] or '(none)'}")
                    st.write(f"Cleaned: {row['cleaned_slot_ocr_text'] or '(none)'}")
                    st.write(f"Expected: {row['expected_code']}")
                    st.write(f"Found: {row['expected_code_found']}")
                    st.write(f"Status: {row['detected_status']}")
                    st.write(f"Confidence: {row['confidence']}")


def show_scan() -> None:
    st.info("Open this app from your phone browser for the best camera experience.")
    camera_image = st.camera_input("Take a photo")
    uploaded_image = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg"],
    )
    save_for_debug = st.checkbox("Save image for debugging", value=False)

    selected_image = camera_image or uploaded_image
    source_label = "camera" if camera_image else "upload"

    if camera_image and uploaded_image:
        st.info("Camera input is being used instead of the uploaded image.")

    if selected_image is None:
        st.caption("Capture or upload an image to preview it before analysis.")
        return

    st.image(selected_image, caption="Selected image", width="stretch")

    if st.button("Prepare image for analysis"):
        try:
            image_bytes = get_image_bytes(selected_image)
            image_name = get_image_display_name(selected_image, source_label)
            original_image = load_image_from_bytes(image_bytes)
            normalized_image, orientation_metadata = normalize_image_orientation(
                image_bytes
            )
            aligned_image, alignment_metadata = align_team_spread_with_template(
                normalized_image
            )
            processed_image = preprocess_image_for_ocr(aligned_image)
            ocr_image = resize_for_ocr(processed_image)
            saved_path = None
            if save_for_debug:
                saved_path = save_image_for_debug(selected_image, source_label)
        except OSError as error:
            st.error(f"Image preparation failed: {error}")
        except ValueError as error:
            st.error(f"Image preprocessing failed: {error}")
        else:
            if saved_path:
                st.success(f"Debug image saved to {saved_path}")
            else:
                st.success("Image prepared in memory and was not permanently saved.")

            st.session_state["prepared_scan"] = {
                "source_label": source_label,
                "image_name": image_name,
                "image_size": len(image_bytes),
                "save_for_debug": save_for_debug,
                "original_image": original_image,
                "normalized_image": normalized_image,
                "orientation_metadata": orientation_metadata,
                "aligned_image": aligned_image,
                "alignment_metadata": alignment_metadata,
                "processed_image": processed_image,
                "ocr_image_shape": ocr_image.shape,
                "ocr_results": None,
            }

    prepared_scan = st.session_state.get("prepared_scan")
    if prepared_scan is None:
        return
    if "aligned_image" not in prepared_scan:
        st.info("Prepare the image again to create the aligned spread view.")
        return

    use_refined_boxes = st.checkbox(
        "Refine slot boxes with edge detection. Failed refinements fall back to template boxes.",
        value=True,
    )

    original_preview, normalized_preview = st.columns(2)
    with original_preview:
        st.image(
            convert_bgr_to_rgb(prepared_scan["original_image"]),
            caption="Original image",
            width="stretch",
        )
    with normalized_preview:
        st.image(
            convert_bgr_to_rgb(prepared_scan["normalized_image"]),
            caption="Orientation-normalized image",
            width="stretch",
        )

    aligned_preview, template_overlay_preview = st.columns(2)
    with aligned_preview:
        st.image(
            convert_bgr_to_rgb(prepared_scan["aligned_image"]),
            caption="Aligned team spread",
            width="stretch",
        )
    with template_overlay_preview:
        st.image(
            draw_slot_boxes(prepared_scan["aligned_image"], use_refined_boxes=False),
            caption="Template slot overlay",
            width="stretch",
        )

    refined_overlay_preview, processed_preview = st.columns(2)
    with refined_overlay_preview:
        st.image(
            draw_slot_boxes(
                prepared_scan["aligned_image"],
                use_refined_boxes=use_refined_boxes,
            ),
            caption="Refined slot overlay",
            width="stretch",
        )
    with processed_preview:
        st.image(
            prepared_scan["processed_image"],
            caption="Processed image",
            width="stretch",
        )

    st.subheader("Analysis placeholder")
    st.write(f"Image source: {prepared_scan['source_label']}")
    st.write(f"Image name: {prepared_scan['image_name']}")
    st.write(f"Original byte size: {prepared_scan['image_size']} bytes")
    orientation_metadata = prepared_scan["orientation_metadata"]
    st.write(
        "Original dimensions: "
        f"{orientation_metadata['original_width']} x "
        f"{orientation_metadata['original_height']} px"
    )
    st.write(
        "Normalized dimensions: "
        f"{orientation_metadata['normalized_width']} x "
        f"{orientation_metadata['normalized_height']} px"
    )
    st.write(f"Rotation applied: {orientation_metadata['rotation_applied']}")
    alignment_metadata = prepared_scan["alignment_metadata"]
    st.write(
        "Aligned spread dimensions: "
        f"{alignment_metadata['aligned_width']} x "
        f"{alignment_metadata['aligned_height']} px"
    )
    st.write(f"Alignment method: {alignment_metadata['alignment_method']}")
    if alignment_metadata.get("crop_box"):
        st.write(f"Alignment crop box: {alignment_metadata['crop_box']}")
    st.write(f"Alignment status: {alignment_metadata.get('alignment_status')}")
    st.write(
        "Template alignment method: "
        f"{alignment_metadata.get('template_alignment_method')}"
    )
    st.write(
        "Template alignment success: "
        f"{alignment_metadata.get('template_alignment_success')}"
    )
    st.write(
        "Template good matches: "
        f"{alignment_metadata.get('template_good_matches', 0)}"
    )
    st.write(
        "Template inliers: "
        f"{alignment_metadata.get('template_inliers', 0)}"
    )
    st.write(f"Template reason: {alignment_metadata.get('template_reason')}")
    if alignment_metadata.get("alignment_status") == "Using template homography alignment":
        st.success("Using template homography alignment")
    elif alignment_metadata.get("alignment_status") == "Using fallback alignment":
        st.warning("Using fallback alignment")
    else:
        st.info("No template image available yet")
    if alignment_metadata.get("alignment_failed"):
        st.warning(
            "Spread alignment used the resize fallback. Slot boxes may need manual "
            "tuning for this image."
        )
    processed_height, processed_width = prepared_scan["processed_image"].shape[:2]
    ocr_height, ocr_width = prepared_scan["ocr_image_shape"][:2]
    st.write(f"Processed image dimensions: {processed_width} x {processed_height} px")
    st.write(f"OCR input dimensions: {ocr_width} x {ocr_height} px")
    st.write(f"Debug saving enabled: {prepared_scan['save_for_debug']}")
    template_source = get_layout_template_source()
    st.write(f"Layout template source: {template_source}")
    if template_source == "Using saved calibrated layout template":
        st.success(template_source)
    else:
        st.warning(template_source)
    st.info(
        "If the normalized image is rotated the wrong way, we will add a manual "
        "rotate button next."
    )
    st.caption("First OCR run may take longer while local models load or download.")

    show_layout_calibration(prepared_scan)

    try:
        scan_catalog = load_sticker_catalog()
    except (sqlite3.Error, DatabaseError) as error:
        show_data_error(error)
        scan_catalog = None

    if scan_catalog is not None and not scan_catalog.empty:
        team_codes = _team_code_options(scan_catalog)
        detected_team_code = _detect_team_code_from_ocr_results(
            prepared_scan.get("ocr_results") or [],
            team_codes,
        )
        selected_team_code = st.selectbox(
            "Team code",
            team_codes,
            index=team_codes.index(detected_team_code)
            if detected_team_code in team_codes
            else 0,
        )

        template_slot_crops = crop_team_spread_slots(
            prepared_scan["aligned_image"],
            use_refined_boxes=False,
        )
        refined_slot_crops = crop_team_spread_slots(
            prepared_scan["aligned_image"],
            use_refined_boxes=use_refined_boxes,
        )
        layout_classification = classify_album_page_by_layout(
            prepared_scan["aligned_image"],
            selected_team_code,
            scan_catalog,
            use_refined_boxes=use_refined_boxes,
        )
        selected_slot_numbers = show_slot_crop_review(
            template_slot_crops,
            refined_slot_crops,
            layout_classification,
        )
        show_selective_slot_recalibration(prepared_scan, selected_slot_numbers)

        st.info(
            "Per-slot OCR may take longer because it runs OCR on up to 20 crops."
        )
        if st.button("Run OCR per slot"):
            with st.spinner("Running OCR on slot crops..."):
                per_slot_rows = classify_slots_with_ocr(
                    refined_slot_crops,
                    selected_team_code,
                    scan_catalog,
                )
            st.session_state["per_slot_ocr_results"] = {
                "team_code": selected_team_code,
                "rows": per_slot_rows,
            }

        per_slot_state = st.session_state.get("per_slot_ocr_results")
        if (
            per_slot_state is not None
            and per_slot_state.get("team_code") == selected_team_code
        ):
            show_per_slot_ocr_results(per_slot_state["rows"], refined_slot_crops)

        if layout_classification:
            st.subheader("Layout-based album page classification")
            st.dataframe(layout_classification, hide_index=True, width="stretch")
            st.info(
                "Layout-based classification uses the aligned full spread and fixed "
                "20-slot positions. OCR is secondary evidence for now."
            )
            show_page_classification_editor(layout_classification, "layout")

    if st.button("Run OCR"):
        try:
            prepared_scan["ocr_results"] = run_ocr_on_image(
                prepared_scan["processed_image"]
            )
        except RuntimeError as error:
            st.error(str(error))

    if prepared_scan["ocr_results"] is not None:
        st.subheader("Raw OCR results")
        if prepared_scan["ocr_results"]:
            st.dataframe(
                [
                    {
                        "text": result["text"],
                        "confidence": result["confidence"],
                    }
                    for result in prepared_scan["ocr_results"]
                ],
                hide_index=True,
                width="stretch",
            )

            cleaned_results = clean_ocr_results(prepared_scan["ocr_results"])
            st.subheader("Cleaned OCR text")
            st.dataframe(cleaned_results, hide_index=True, width="stretch")

            try:
                catalog = load_sticker_catalog()
            except (sqlite3.Error, DatabaseError) as error:
                show_data_error(error)
            else:
                if catalog.empty:
                    st.warning(
                        "Catalog is empty. Initialize the database and import the "
                        "catalog in Settings."
                    )
                else:
                    match_suggestions = suggest_sticker_matches(
                        cleaned_results,
                        catalog,
                    )
                    st.subheader("Sticker match suggestions")
                    st.dataframe(
                        [
                            {
                                "raw_text": suggestion["raw_text"],
                                "cleaned_text": suggestion["cleaned_text"],
                                "matched_sticker_id": suggestion[
                                    "matched_sticker_id"
                                ],
                                "matched_display_code": suggestion[
                                    "matched_display_code"
                                ],
                                "matched_player_name": suggestion[
                                    "matched_player_name"
                                ],
                                "match_type": suggestion["match_type"],
                                "score": suggestion["score"],
                                "match_reason": suggestion["match_reason"],
                            }
                            for suggestion in match_suggestions
                        ],
                        hide_index=True,
                        width="stretch",
                    )
                    st.info(
                        "Suggestions are not saved yet. Human validation comes next."
                    )

                    aggregated_suggestions = aggregate_match_suggestions(
                        match_suggestions
                    )
                    st.subheader("Aggregated sticker suggestions")
                    st.dataframe(
                        aggregated_suggestions,
                        hide_index=True,
                        width="stretch",
                    )
                    st.info(
                        "Aggregated suggestions are not saved yet. Human validation "
                        "comes next."
                    )

                    page_classification = classify_album_page(
                        prepared_scan["ocr_results"],
                        catalog,
                    )
                    if page_classification:
                        st.subheader("Album page classification")
                        st.dataframe(
                            page_classification,
                            hide_index=True,
                            width="stretch",
                        )
                        st.info(
                            "For album pages, visible sticker codes usually mean "
                            "missing slots. Non-detected stickers are treated as "
                            "owned candidates and must be validated."
                        )
                        show_page_classification_editor(page_classification, "ocr")
        else:
            st.warning("No text was detected in the prepared image.")

    st.info("OCR text and match suggestions stay in this app session for now.")


def show_collection() -> None:
    try:
        catalog = load_sticker_catalog()
    except (sqlite3.Error, DatabaseError) as error:
        show_data_error(error)
        return

    if catalog.empty:
        st.info("The catalog is empty. Import the catalog CSV in Settings.")
        return

    with st.form("manual_collection_update"):
        st.subheader("Manual collection update")
        selected_sticker_id = st.selectbox(
            "Sticker ID",
            catalog["sticker_id"].tolist(),
        )
        selected_sticker = catalog.loc[
            catalog["sticker_id"] == selected_sticker_id
        ].iloc[0]
        st.write(
            f"{selected_sticker['display_code']} - {selected_sticker['player_name']}"
        )
        submitted = st.form_submit_button("Mark as owned")

    if submitted:
        try:
            mark_sticker_as_owned(selected_sticker_id)
            catalog = load_sticker_catalog()
        except (sqlite3.Error, DatabaseError, ValueError) as error:
            st.error(f"Collection update failed: {error}")
        else:
            st.success(f"Marked {selected_sticker_id} as owned.")

    st.dataframe(catalog, hide_index=True, width="stretch")


def show_missing_stickers() -> None:
    try:
        missing = get_missing_stickers()
    except (sqlite3.Error, DatabaseError) as error:
        show_data_error(error)
        return

    if missing.empty:
        st.success("No missing stickers found.")
        return

    st.dataframe(missing, hide_index=True, width="stretch")


def show_duplicate_stickers() -> None:
    try:
        duplicates = get_duplicate_stickers()
    except (sqlite3.Error, DatabaseError) as error:
        show_data_error(error)
        return

    if duplicates.empty:
        st.info("No duplicate stickers found.")
        return

    st.dataframe(duplicates, hide_index=True, width="stretch")


def show_settings() -> None:
    if st.button("Initialize database"):
        try:
            init_db()
        except sqlite3.Error as error:
            st.error(f"Database initialization failed: {error}")
        else:
            st.success("Database initialized.")

    if st.button("Import catalog CSV"):
        try:
            inserted_count = import_catalog_from_csv(CATALOG_CSV_PATH)
        except (FileNotFoundError, sqlite3.Error, ValueError) as error:
            st.error(f"Catalog import failed: {error}")
        else:
            st.success(
                f"Catalog import complete. Imported or updated {inserted_count} stickers."
            )


def main() -> None:
    st.set_page_config(
        page_title="Panini Camera Tracker",
        page_icon=":camera:",
        layout="wide",
    )

    st.sidebar.title("Panini Camera Tracker")
    # Keep the first app shell simple while camera and data layers are pending.
    section = st.sidebar.radio("Navigation", list(SECTIONS))

    st.title(section)
    st.info(SECTIONS[section])

    if section == "Scan":
        show_scan()
    elif section == "Collection":
        show_collection()
    elif section == "Missing":
        show_missing_stickers()
    elif section == "Duplicates":
        show_duplicate_stickers()
    elif section == "Settings":
        show_settings()


if __name__ == "__main__":
    main()
