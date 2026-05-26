from rapidfuzz import fuzz, process


MATCH_FIELDS = (
    "matched_sticker_id",
    "matched_display_code",
    "matched_player_name",
)


def _normalize_catalog_value(value) -> str:
    return str(value).strip().upper()


def _suggestion(
    cleaned_result: dict,
    sticker=None,
    match_type="no_match",
    score=0,
    match_reason="no catalog match",
):
    suggestion = {
        "raw_text": cleaned_result["raw_text"],
        "cleaned_text": cleaned_result["cleaned_text"],
        "match_type": match_type,
        "score": score,
        "match_reason": match_reason,
    }

    if sticker is None:
        suggestion.update({field: "" for field in MATCH_FIELDS})
        return suggestion

    suggestion.update(
        {
            "matched_sticker_id": sticker["sticker_id"],
            "matched_display_code": sticker["display_code"],
            "matched_player_name": sticker["player_name"],
        }
    )
    return suggestion


def suggest_sticker_matches(
    cleaned_ocr_results: list[dict],
    catalog_df,
    min_score: int = 85,
) -> list[dict]:
    if catalog_df.empty:
        return [_suggestion(result) for result in cleaned_ocr_results]

    catalog = catalog_df.to_dict("records")
    display_codes = {
        _normalize_catalog_value(sticker["display_code"]): sticker
        for sticker in catalog
    }
    sticker_ids = {
        _normalize_catalog_value(sticker["sticker_id"]): sticker
        for sticker in catalog
    }
    team_codes = {
        _normalize_catalog_value(sticker["team_code"])
        for sticker in catalog
    }
    player_names = {
        _normalize_catalog_value(sticker["player_name"]): sticker
        for sticker in catalog
    }

    suggestions = []
    for cleaned_result in cleaned_ocr_results:
        cleaned_text = cleaned_result["cleaned_text"]

        exact_sticker = None
        for sticker_code in cleaned_result.get("possible_sticker_codes", []):
            exact_sticker = display_codes.get(sticker_code)
            if exact_sticker is not None:
                suggestions.append(
                    _suggestion(
                        cleaned_result,
                        exact_sticker,
                        "display_code",
                        100,
                        "exact display_code",
                    )
                )
                break
        if exact_sticker is not None:
            continue

        exact_sticker = display_codes.get(cleaned_text)
        if exact_sticker is not None:
            suggestions.append(
                _suggestion(
                    cleaned_result,
                    exact_sticker,
                    "display_code",
                    100,
                    "exact display_code",
                )
            )
            continue

        exact_sticker = sticker_ids.get(cleaned_text)
        if exact_sticker is not None:
            suggestions.append(
                _suggestion(
                    cleaned_result,
                    exact_sticker,
                    "sticker_id",
                    100,
                    "exact sticker_id",
                )
            )
            continue

        if cleaned_text in team_codes:
            suggestions.append(
                _suggestion(
                    cleaned_result,
                    match_type="team_context",
                    score=100,
                    match_reason="exact team_code",
                )
            )
            continue

        if len(cleaned_text) < 4:
            suggestions.append(
                _suggestion(cleaned_result, match_reason="too short for fuzzy matching")
            )
            continue

        if " " not in cleaned_text and len(cleaned_text) < 5:
            suggestions.append(
                _suggestion(cleaned_result, match_reason="no catalog match")
            )
            continue

        fuzzy_match = process.extractOne(
            cleaned_text,
            player_names.keys(),
            scorer=fuzz.WRatio,
            score_cutoff=min_score,
        )
        if fuzzy_match is None:
            suggestions.append(
                _suggestion(cleaned_result, match_reason="below fuzzy threshold")
            )
            continue

        matched_name, score, _ = fuzzy_match
        suggestions.append(
            _suggestion(
                cleaned_result,
                player_names[matched_name],
                "player_name",
                score,
                "fuzzy player_name above threshold",
            )
        )

    return suggestions


def aggregate_match_suggestions(match_suggestions: list[dict]) -> list[dict]:
    aggregated = {}
    for suggestion in match_suggestions:
        sticker_id = suggestion.get("matched_sticker_id", "")
        if not sticker_id:
            continue

        row = aggregated.setdefault(
            sticker_id,
            {
                "matched_sticker_id": sticker_id,
                "matched_display_code": suggestion["matched_display_code"],
                "matched_player_name": suggestion["matched_player_name"],
                "best_score": suggestion.get("score", 0),
                "evidence_texts": [],
            },
        )
        row["best_score"] = max(row["best_score"], suggestion.get("score", 0))

        evidence_text = suggestion.get("cleaned_text", "")
        if evidence_text and evidence_text not in row["evidence_texts"]:
            row["evidence_texts"].append(evidence_text)

    for row in aggregated.values():
        row["evidence_texts"] = ", ".join(row["evidence_texts"])

    return list(aggregated.values())
