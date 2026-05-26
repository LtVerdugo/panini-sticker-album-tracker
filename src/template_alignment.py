import cv2

from pathlib import Path

from src.layout_template import ensure_config_dir


TEMPLATE_IMAGE_PATH = Path("config") / "aligned_template.png"
MIN_MATCH_COUNT = 20
HOMOGRAPHY_REPROJ_THRESHOLD = 5.0


def has_template_image() -> bool:
    return load_template_image() is not None


def save_template_image(aligned_image):
    ensure_config_dir()
    if not cv2.imwrite(str(TEMPLATE_IMAGE_PATH), aligned_image):
        raise OSError(f"Could not save template image to {TEMPLATE_IMAGE_PATH}")
    return str(TEMPLATE_IMAGE_PATH)


def load_template_image():
    image = cv2.imread(str(TEMPLATE_IMAGE_PATH))
    if image is None or image.size == 0:
        return None
    return image


def _base_metadata(method: str) -> dict:
    return {
        "success": False,
        "method": method,
        "keypoints_input": 0,
        "keypoints_template": 0,
        "good_matches": 0,
        "inliers": 0,
        "reason": "",
    }


def _align_with_orb(input_image, template_image):
    metadata = _base_metadata("orb_homography")
    input_gray = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=3000)
    input_keypoints, input_descriptors = orb.detectAndCompute(input_gray, None)
    template_keypoints, template_descriptors = orb.detectAndCompute(
        template_gray,
        None,
    )
    metadata["keypoints_input"] = len(input_keypoints or [])
    metadata["keypoints_template"] = len(template_keypoints or [])

    if input_descriptors is None or template_descriptors is None:
        metadata["reason"] = "Missing ORB descriptors."
        return input_image, metadata

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(
        matcher.match(input_descriptors, template_descriptors),
        key=lambda match: match.distance,
    )
    good_matches = matches[: max(MIN_MATCH_COUNT, min(100, len(matches)))]
    metadata["good_matches"] = len(good_matches)

    if len(good_matches) < MIN_MATCH_COUNT:
        metadata["reason"] = (
            f"Only {len(good_matches)} good ORB matches; "
            f"{MIN_MATCH_COUNT} required."
        )
        return input_image, metadata

    input_points = cv2.KeyPoint_convert(
        input_keypoints,
        [match.queryIdx for match in good_matches],
    )
    template_points = cv2.KeyPoint_convert(
        template_keypoints,
        [match.trainIdx for match in good_matches],
    )
    homography, mask = cv2.findHomography(
        input_points,
        template_points,
        cv2.RANSAC,
        HOMOGRAPHY_REPROJ_THRESHOLD,
    )
    if homography is None:
        metadata["reason"] = "ORB homography could not be computed."
        return input_image, metadata

    metadata["inliers"] = int(mask.sum()) if mask is not None else 0
    template_height, template_width = template_image.shape[:2]
    aligned_image = cv2.warpPerspective(
        input_image,
        homography,
        (template_width, template_height),
    )
    metadata["success"] = True
    metadata["reason"] = "Template alignment succeeded."
    return aligned_image, metadata


def align_to_template(input_image, template_image):
    if input_image is None or template_image is None:
        metadata = _base_metadata("orb_homography")
        metadata["reason"] = "Input image or template image is missing."
        return input_image, metadata

    try:
        return _align_with_orb(input_image, template_image)
    except cv2.error as error:
        metadata = _base_metadata("orb_homography")
        metadata["reason"] = f"OpenCV alignment error: {error}"
        return input_image, metadata
