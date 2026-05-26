import re


CODE_PATTERN = re.compile(r"\b([A-Z]{3})[\s_-]+0*(\d{1,3})\b")
TEAM_CODE_PATTERN = re.compile(r"\b([A-Z]{3})\b")


def normalize_ocr_text(text: str) -> str:
    normalized = " ".join(str(text).strip().split())
    normalized = normalized.rstrip(".")
    return normalized.upper()


def extract_possible_team_codes(text: str) -> list[str]:
    normalized = normalize_ocr_text(text)
    return list(dict.fromkeys(TEAM_CODE_PATTERN.findall(normalized)))


def extract_possible_sticker_codes(text: str) -> list[str]:
    normalized = normalize_ocr_text(text)
    return [
        f"{team_code} {number}"
        for team_code, number in dict.fromkeys(CODE_PATTERN.findall(normalized))
    ]


def clean_ocr_results(ocr_results: list[dict]) -> list[dict]:
    cleaned_results = []
    for result in ocr_results:
        raw_text = str(result.get("text", "")).strip()
        cleaned_text = normalize_ocr_text(raw_text)
        if not cleaned_text:
            continue

        cleaned_results.append(
            {
                "raw_text": raw_text,
                "cleaned_text": cleaned_text,
                "confidence": result.get("confidence"),
                "possible_team_codes": extract_possible_team_codes(cleaned_text),
                "possible_sticker_codes": extract_possible_sticker_codes(cleaned_text),
            }
        )

    return cleaned_results
