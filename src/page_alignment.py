import cv2

from src.template_alignment import (
    align_to_template,
    has_template_image,
    load_template_image,
)


CANONICAL_SPREAD_WIDTH = 1600
CANONICAL_SPREAD_HEIGHT = 1000
CANONICAL_SPREAD_SIZE = (CANONICAL_SPREAD_WIDTH, CANONICAL_SPREAD_HEIGHT)
CANONICAL_SPREAD_ASPECT_RATIO = CANONICAL_SPREAD_WIDTH / CANONICAL_SPREAD_HEIGHT


def _center_crop_to_aspect_ratio(image, target_aspect_ratio: float):
    height, width = image.shape[:2]
    current_aspect_ratio = width / height

    if current_aspect_ratio > target_aspect_ratio:
        crop_width = round(height * target_aspect_ratio)
        x_min = max(0, (width - crop_width) // 2)
        x_max = min(width, x_min + crop_width)
        y_min = 0
        y_max = height
    else:
        crop_height = round(width / target_aspect_ratio)
        x_min = 0
        x_max = width
        y_min = max(0, (height - crop_height) // 2)
        y_max = min(height, y_min + crop_height)

    return image[y_min:y_max, x_min:x_max], (x_min, y_min, x_max, y_max)


def align_team_spread(image):
    height, width = image.shape[:2]
    metadata = {
        "input_width": width,
        "input_height": height,
        "canonical_width": CANONICAL_SPREAD_WIDTH,
        "canonical_height": CANONICAL_SPREAD_HEIGHT,
        "alignment_method": "center_crop",
        "alignment_failed": False,
        "crop_box": None,
    }

    try:
        cropped_image, crop_box = _center_crop_to_aspect_ratio(
            image,
            CANONICAL_SPREAD_ASPECT_RATIO,
        )
        if cropped_image.size == 0:
            raise ValueError("Center crop produced an empty image.")

        aligned_image = cv2.resize(
            cropped_image,
            CANONICAL_SPREAD_SIZE,
            interpolation=cv2.INTER_AREA,
        )
        metadata["crop_box"] = crop_box
    except Exception as error:
        # Fall back to a direct resize so the Scan flow can keep going.
        aligned_image = cv2.resize(
            image,
            CANONICAL_SPREAD_SIZE,
            interpolation=cv2.INTER_AREA,
        )
        metadata["alignment_method"] = "resize_fallback"
        metadata["alignment_failed"] = True
        metadata["error"] = str(error)

    metadata["aligned_width"] = aligned_image.shape[1]
    metadata["aligned_height"] = aligned_image.shape[0]
    return aligned_image, metadata


def align_team_spread_with_template(image):
    aligned_image, base_metadata = align_team_spread(image)
    metadata = {
        **base_metadata,
        "template_alignment_available": has_template_image(),
        "template_alignment_success": False,
        "template_alignment_method": "none",
        "template_good_matches": 0,
        "template_inliers": 0,
        "template_reason": "No template image available yet.",
        "alignment_status": "No template image available yet",
    }

    template_image = load_template_image()
    if template_image is None:
        return aligned_image, metadata

    template_aligned_image, template_metadata = align_to_template(
        aligned_image,
        template_image,
    )
    metadata.update(
        {
            "template_alignment_method": template_metadata.get("method"),
            "template_alignment_success": template_metadata.get("success", False),
            "template_good_matches": template_metadata.get("good_matches", 0),
            "template_inliers": template_metadata.get("inliers", 0),
            "template_reason": template_metadata.get("reason", ""),
            "template_keypoints_input": template_metadata.get("keypoints_input", 0),
            "template_keypoints_template": template_metadata.get(
                "keypoints_template",
                0,
            ),
        }
    )

    if template_metadata.get("success"):
        metadata["alignment_method"] = "template_homography"
        metadata["alignment_failed"] = False
        metadata["alignment_status"] = "Using template homography alignment"
        metadata["aligned_width"] = template_aligned_image.shape[1]
        metadata["aligned_height"] = template_aligned_image.shape[0]
        return template_aligned_image, metadata

    metadata["alignment_status"] = "Using fallback alignment"
    return aligned_image, metadata
