from datetime import datetime
from pathlib import Path


ORIGINAL_SCANS_DIR = Path("scans") / "original"


def save_image_for_debug(image_file, source_label: str) -> str:
    original_name = Path(getattr(image_file, "name", ""))
    extension = original_name.suffix.lower() or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    saved_path = ORIGINAL_SCANS_DIR / f"{source_label}_{timestamp}{extension}"

    ORIGINAL_SCANS_DIR.mkdir(parents=True, exist_ok=True)
    with saved_path.open("wb") as output_file:
        output_file.write(get_image_bytes(image_file))

    return str(saved_path)


def get_image_bytes(image_file) -> bytes:
    return bytes(image_file.getbuffer())


def get_image_display_name(image_file, source_label: str) -> str:
    original_name = getattr(image_file, "name", "")
    if original_name:
        return f"{source_label}: {original_name}"

    return f"{source_label}: temporary image"
