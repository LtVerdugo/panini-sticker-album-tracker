from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps


def normalize_image_orientation(image_bytes: bytes):
    with Image.open(BytesIO(image_bytes)) as image:
        original_width, original_height = image.size
        normalized_image = ImageOps.exif_transpose(image).convert("RGB")

    rotation_applied = False
    if normalized_image.height > normalized_image.width:
        normalized_image = normalized_image.rotate(90, expand=True)
        rotation_applied = True

    normalized_array = np.array(normalized_image)
    normalized_bgr = cv2.cvtColor(normalized_array, cv2.COLOR_RGB2BGR)

    metadata = {
        "original_width": original_width,
        "original_height": original_height,
        "normalized_width": normalized_image.width,
        "normalized_height": normalized_image.height,
        "rotation_applied": rotation_applied,
    }

    return normalized_bgr, metadata


def load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("OpenCV could not decode the selected image.")

    return image


def convert_bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def convert_to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def improve_contrast(image: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(image)


def apply_light_denoising(image: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(image, h=5)


def preprocess_image_for_ocr(image: np.ndarray) -> np.ndarray:
    grayscale = convert_to_grayscale(image)
    contrast_image = improve_contrast(grayscale)
    return apply_light_denoising(contrast_image)


def encode_processed_image_to_png(image: np.ndarray) -> bytes:
    encoded, png_buffer = cv2.imencode(".png", image)
    if not encoded:
        raise ValueError("OpenCV could not encode the processed image as PNG.")

    return png_buffer.tobytes()
