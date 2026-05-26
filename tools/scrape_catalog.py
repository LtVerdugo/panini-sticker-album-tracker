import csv
import re
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://www.laststicker.com/cards/panini_world_cup_2026/"
OUTPUT_PATH = Path("data") / "sticker_catalog_full.csv"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

OUTPUT_COLUMNS = [
    "sticker_id",
    "team_code",
    "number",
    "display_code",
    "player_name",
    "category",
    "page_code",
    "slot_position",
    "section",
    "sticker_type",
]

FIFA_CODE_MAP = {
    "Afghanistan": "AFG", "Albania": "ALB", "Algeria": "ALG",
    "Andorra": "AND", "Angola": "ANG", "Argentina": "ARG",
    "Armenia": "ARM", "Australia": "AUS", "Austria": "AUT",
    "Azerbaijan": "AZE", "Bahrain": "BHR", "Bangladesh": "BAN",
    "Belgium": "BEL", "Bolivia": "BOL", "Bosnia": "BIH",
    "Brazil": "BRA", "Bulgaria": "BUL", "Burkina Faso": "BFA",
    "Cameroon": "CMR", "Canada": "CAN", "Chile": "CHI",
    "China": "CHN", "Colombia": "COL", "Congo": "CGO",
    "Costa Rica": "CRC", "Croatia": "CRO", "Cuba": "CUB",
    "Czech Republic": "CZE", "Czechia": "CZE", "Denmark": "DEN",
    "Ecuador": "ECU", "Egypt": "EGY", "England": "ENG",
    "Estonia": "EST", "Ethiopia": "ETH", "Finland": "FIN",
    "France": "FRA", "Georgia": "GEO", "Germany": "GER",
    "Ghana": "GHA", "Greece": "GRE", "Guatemala": "GUA",
    "Honduras": "HON", "Hungary": "HUN", "Iceland": "ISL",
    "India": "IND", "Indonesia": "IDN", "Iran": "IRN",
    "Iraq": "IRQ", "Ireland": "IRL", "Israel": "ISR",
    "Italy": "ITA", "Ivory Coast": "CIV", "Jamaica": "JAM",
    "Japan": "JPN", "Jordan": "JOR", "Kazakhstan": "KAZ",
    "Kenya": "KEN", "Korea Republic": "KOR", "Korea DPR": "PRK",
    "Kosovo": "KVX", "Kuwait": "KUW", "Kyrgyzstan": "KGZ",
    "Latvia": "LVA", "Lebanon": "LIB", "Libya": "LBA",
    "Lithuania": "LTU", "Luxembourg": "LUX", "Malaysia": "MAS",
    "Mali": "MLI", "Malta": "MLT", "Mexico": "MEX",
    "Moldova": "MDA", "Montenegro": "MNE", "Morocco": "MAR",
    "Mozambique": "MOZ", "Netherlands": "NED", "New Zealand": "NZL",
    "Nigeria": "NGA", "North Macedonia": "MKD", "Norway": "NOR",
    "Oman": "OMA", "Pakistan": "PAK", "Panama": "PAN",
    "Paraguay": "PAR", "Peru": "PER", "Philippines": "PHI",
    "Poland": "POL", "Portugal": "POR", "Qatar": "QAT",
    "Romania": "ROU", "Russia": "RUS", "Saudi Arabia": "SAU",
    "Scotland": "SCO", "Senegal": "SEN", "Serbia": "SRB",
    "Slovakia": "SVK", "Slovenia": "SVN", "Somalia": "SOM",
    "South Africa": "RSA", "Spain": "ESP", "Sudan": "SDN",
    "Sweden": "SWE", "Switzerland": "SUI", "Syria": "SYR",
    "Taiwan": "TPE", "Tajikistan": "TJK", "Tanzania": "TAN",
    "Thailand": "THA", "Tunisia": "TUN", "Turkey": "TUR",
    "Turkmenistan": "TKM", "Uganda": "UGA", "Ukraine": "UKR",
    "United States": "USA", "USA": "USA", "Uruguay": "URU",
    "Uzbekistan": "UZB", "Venezuela": "VEN", "Vietnam": "VIE",
    "Wales": "WAL", "Zambia": "ZAM", "Zimbabwe": "ZIM",
    "South Korea": "KOR", "Republic of Ireland": "IRL",
    "DR Congo": "COD", "Congo DR": "COD", "Côte d'Ivoire": "CIV", "Cape Verde": "CPV",
    "Central African Republic": "CAF", "El Salvador": "SLV",
    "Equatorial Guinea": "EQG", "Faroe Islands": "FRO",
    "Guinea-Bissau": "GNB", "Guinea": "GUI",
    "Papua New Guinea": "PNG", "Puerto Rico": "PUR",
    "Trinidad and Tobago": "TRI", "United Arab Emirates": "UAE",
}

EXCLUDED_SECTION_MARKERS = (
    "coca cola / usa",
    "coca-cola usa",
    "coca cola / latin america",
    "coca-cola latin america",
    "coca cola / rest of the world",
    "coca-cola rest of the world",
    "extra",
    "base",
)

SPECIAL_SECTION_CODES = {
    "we are panini": "WP",
    "fifa world cup 2026": "FWC",
    "host countries and cities": "HCC",
    "fifa world cup history": "FWC",
    "coca cola / europe": "CCE",
    "coca-cola europe": "CCE",
}


def clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def extract_integer(value: str) -> int:
    match = re.search(r"\d+", value)
    return int(match.group()) if match else 0


def extract_team_number(value: str) -> int | None:
    match = re.search(r"(?:^|[\s_-])(\d{1,2})(?:$|\D)", value)
    if not match:
        match = re.search(r"(\d{1,2})$", value)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 20 else None


def find_team_code(section: str) -> str | None:
    section_lower = section.lower()
    for team_name, team_code in sorted(FIFA_CODE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if section_lower == team_name.lower() or team_name.lower() in section_lower:
            return team_code
    return None


def should_exclude_section(section: str) -> bool:
    section_lower = section.lower()
    return any(marker in section_lower for marker in EXCLUDED_SECTION_MARKERS)


def special_team_code(section: str) -> str | None:
    section_lower = section.lower()
    for marker, code in SPECIAL_SECTION_CODES.items():
        if marker in section_lower:
            return code
    return None


def is_included_section(section: str, number_text: str) -> bool:
    if should_exclude_section(section):
        return False
    if special_team_code(section):
        return True
    return find_team_code(section) is not None and extract_team_number(number_text) is not None


def find_catalog_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        headers = [clean_text(cell.get_text(" ")) for cell in table.find_all("th")]
        header_text = " | ".join(headers).lower()
        if "no." in header_text and "title" in header_text and "section" in header_text:
            return table
    raise RuntimeError("Could not find the main sticker catalog table")


def table_rows(table) -> list[dict[str, str]]:
    headers = [clean_text(cell.get_text(" ")) for cell in table.find_all("th")]
    header_lookup = {header.lower(): index for index, header in enumerate(headers)}

    def column(cells, name: str) -> str:
        index = header_lookup.get(name.lower())
        if index is None or index >= len(cells):
            return ""
        return clean_text(cells[index].get_text(" "))

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        rows.append(
            {
                "number": column(cells, "No."),
                "title": column(cells, "Title"),
                "section": column(cells, "Section"),
                "type": column(cells, "Type"),
            }
        )
    return rows


def build_team_row(number_text: str, title: str, section: str, sticker_type: str) -> dict:
    team_code = find_team_code(section)
    number = extract_team_number(number_text)
    if team_code is None or number is None:
        raise ValueError(f"Could not map team row: {section} / {number_text}")

    category = "badge" if number == 1 else "team_photo" if number == 13 else "player"
    return {
        "sticker_id": f"{team_code}_{number:03d}",
        "team_code": team_code,
        "number": number,
        "display_code": f"{team_code} {number}",
        "player_name": title,
        "category": category,
        "page_code": team_code.lower(),
        "slot_position": f"slot_{number:02d}",
        "section": section,
        "sticker_type": "player",
    }


def normalize_special_display_code(number_text: str) -> str:
    match = re.match(r"^([A-Za-z]+)[\s_-]*(\d+)$", number_text)
    if match:
        return f"{match.group(1).upper()} {int(match.group(2))}"
    return number_text


def build_special_row(number_text: str, title: str, section: str, sticker_type: str) -> dict:
    team_code = special_team_code(section) or "FWC"
    return {
        "sticker_id": number_text,
        "team_code": team_code,
        "number": extract_integer(number_text),
        "display_code": normalize_special_display_code(number_text),
        "player_name": title,
        "category": "special",
        "page_code": slugify(section),
        "slot_position": number_text,
        "section": section,
        "sticker_type": "special",
    }


def scrape_catalog() -> list[dict]:
    response = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    table = find_catalog_table(soup)
    output_rows = []

    for row in table_rows(table):
        number_text = row["number"].strip()
        title = row["title"].strip()
        section = row["section"].strip()
        if not number_text or not section or not is_included_section(section, number_text):
            continue

        if find_team_code(section) and extract_team_number(number_text) is not None:
            output_rows.append(build_team_row(number_text, title, section, row["type"]))
        else:
            output_rows.append(build_special_row(number_text, title, section, row["type"]))

    unique_rows = {}
    for row in output_rows:
        unique_rows.setdefault(row["sticker_id"], row)

    return list(unique_rows.values())


def save_catalog(rows: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict]) -> None:
    counts = Counter(row["section"] for row in rows)
    for section, count in counts.items():
        print(f"{section}: {count} stickers")
    print(f"TOTAL: {len(rows)} stickers")
    print("\nPreview:")
    for row in rows[:5]:
        print(row)


def main() -> None:
    rows = scrape_catalog()
    save_catalog(rows)
    print_summary(rows)
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
