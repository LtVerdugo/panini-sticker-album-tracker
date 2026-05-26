import logging
from collections.abc import Mapping, Sequence
from typing import Any

import cv2
import streamlit as st


LOGGER = logging.getLogger(__name__)
DEBUG_OCR_RESULT_SHAPE = False
OCR_MAX_SIDE = 1600


@st.cache_resource
def get_ocr_engine() -> Any:
    # PaddleOCR loads local OCR models on first use, so keep one engine per app process.
    from paddleocr import PaddleOCR

    return PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="paddle",
    )


def _to_serializable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _to_confidence(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result_row(
    text: Any,
    confidence: Any = None,
    bounding_box: Any = None,
) -> dict[str, Any] | None:
    if text is None:
        return None

    parsed_text = str(text).strip()
    if not parsed_text:
        return None

    return {
        "text": parsed_text,
        "confidence": _to_confidence(confidence),
        "bounding_box": _to_serializable(bounding_box),
    }


def _parse_dict_result(raw_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    result_data = raw_result.get("res", raw_result)
    if not isinstance(result_data, Mapping):
        return []

    texts = result_data.get("rec_texts")
    if isinstance(texts, Sequence) and not isinstance(texts, (str, bytes)):
        confidences = result_data.get("rec_scores", [])
        bounding_boxes = result_data.get("rec_polys", result_data.get("dt_polys", []))
        parsed_results = []
        for index, text in enumerate(texts):
            confidence = confidences[index] if index < len(confidences) else None
            bounding_box = (
                bounding_boxes[index] if index < len(bounding_boxes) else None
            )
            parsed_result = _result_row(text, confidence, bounding_box)
            if parsed_result is not None:
                parsed_results.append(parsed_result)
        return parsed_results

    parsed_result = _result_row(
        result_data.get("text", result_data.get("rec_text")),
        result_data.get("confidence", result_data.get("rec_score")),
        result_data.get("bounding_box", result_data.get("rec_poly")),
    )
    return [parsed_result] if parsed_result is not None else []


def _parse_sequence_result(raw_result: Sequence[Any]) -> list[dict[str, Any]]:
    if len(raw_result) >= 2 and isinstance(raw_result[0], str):
        parsed_result = _result_row(raw_result[0], raw_result[1])
        return [parsed_result] if parsed_result is not None else []

    # Older PaddleOCR output can look like [box, (text, confidence)].
    if len(raw_result) >= 2:
        text_data = raw_result[1]
        if (
            isinstance(text_data, Sequence)
            and not isinstance(text_data, (str, bytes))
            and len(text_data) >= 1
            and isinstance(text_data[0], str)
        ):
            confidence = text_data[1] if len(text_data) >= 2 else None
            parsed_result = _result_row(text_data[0], confidence, raw_result[0])
            return [parsed_result] if parsed_result is not None else []

    parsed_results = []
    for item in raw_result:
        parsed_results.extend(parse_paddleocr_results(item))
    return parsed_results


def parse_paddleocr_results(raw_result: Any) -> list[dict[str, Any]]:
    if raw_result is None:
        return []

    if DEBUG_OCR_RESULT_SHAPE:
        LOGGER.debug("PaddleOCR raw result type: %s", type(raw_result).__name__)

    json_data = getattr(raw_result, "json", None)
    if json_data is not None and not isinstance(raw_result, Mapping):
        try:
            raw_result = json_data() if callable(json_data) else json_data
        except Exception:
            return []

    if isinstance(raw_result, Mapping):
        return _parse_dict_result(raw_result)

    if isinstance(raw_result, Sequence) and not isinstance(raw_result, (str, bytes)):
        return _parse_sequence_result(raw_result)

    return []


def _prepare_image_for_paddle(processed_image):
    if len(processed_image.shape) == 2:
        return cv2.cvtColor(processed_image, cv2.COLOR_GRAY2BGR)
    return processed_image


def resize_for_ocr(image, max_side: int = OCR_MAX_SIDE):
    height, width = image.shape[:2]
    longest_side = max(height, width)
    if longest_side <= max_side:
        return image

    scale = max_side / longest_side
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    return cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)


def run_ocr_on_image(processed_image) -> list[dict[str, Any]]:
    try:
        ocr_image = resize_for_ocr(_prepare_image_for_paddle(processed_image))
        raw_result = get_ocr_engine().predict(ocr_image)
    except Exception as error:
        raise RuntimeError(f"PaddleOCR failed to process the image: {error}") from error

    return parse_paddleocr_results(raw_result)
