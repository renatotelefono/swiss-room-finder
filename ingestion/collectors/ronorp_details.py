import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


INDEX_FILE = Path(
    "data/raw/ronorp/zurich-housing-index.json"
)

OUTPUT_FILE = Path(
    "data/processed/ronorp-listings.json"
)

# Per il test elaboriamo 10 annunci.
# Quando siamo soddisfatti metteremo None.
MAX_LISTINGS = None


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def load_index():
    data = json.loads(
        INDEX_FILE.read_text(
            encoding="utf-8"
        )
    )

    return data.get("listings", [])


def clean_text(value):
    if value is None:
        return None

    value = " ".join(
        str(value).split()
    )

    return value or None


def extract_price(text):
    match = re.search(
        r"CHF\s*([\d'’]+(?:[.,]\d+)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    value = (
        match.group(1)
        .replace("'", "")
        .replace("’", "")
        .replace(",", "")
    )

    try:
        return float(value)
    except ValueError:
        return None


def extract_postal_code(text):
    match = re.search(
        r"\bPLZ\s+(\d{4})\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    match = re.search(
        r"\b(\d{4})\s+[A-ZÄÖÜ][A-Za-zÀ-ÿ-]+",
        text,
    )

    if match:
        return match.group(1)

    return None


def extract_rooms(text):
    match = re.search(
        r"Räume\s+([0-9]+(?:[.,][0-9]+)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1).replace(",", ".")
        )
    except ValueError:
        return None


def extract_size_m2(text):
    match = re.search(
        r"Quadratmeter\s+([0-9]+(?:[.,][0-9]+)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1).replace(",", ".")
        )
    except ValueError:
        return None


def extract_contract_type(text):
    match = re.search(
        r"Vertrag\s+(Temporary|Permanent)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).lower()

    lower = text.lower()

    if (
        "unbefristet" in lower
        or "permanent" in lower
        or "indefinite" in lower
    ):
        return "permanent"

    if (
        "temporary" in lower
        or "befristet" in lower
        or "short term" in lower
        or "short-term" in lower
    ):
        return "temporary"

    return None


def extract_offer_type(text):
    match = re.search(
        r"Typ\s+(BIETE|SUCHE|OFFER|WANTED)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    value = match.group(1).lower()

    if value in {"biete", "offer"}:
        return "offer"

    if value in {"suche", "wanted"}:
        return "wanted"

    return value


def extract_city(text):
    match = re.search(
        r"Adresse\s+(.+?)\s+City/Agglo",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    city = clean_text(
        match.group(1)
    )

    if city == "--":
        return None

    return city


def extract_floor(text):
    match = re.search(
        r"Böden\s+(.+?)\s+Quadratmeter",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    value = clean_text(
        match.group(1)
    )

    if value == "--":
        return None

    return value


def extract_external_url(text):
    match = re.search(
        r"Verknüpfung\s+(https?://\S+)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1)


def parse_english_date(
    month_name,
    day,
    year,
):
    month = MONTHS.get(
        month_name.lower()
    )

    if month is None:
        return None

    try:
        value = datetime(
            int(year),
            month,
            int(day),
        )

        return value.date().isoformat()

    except ValueError:
        return None


def extract_availability(text):
    result = {
        "available_from": None,
        "available_to": None,
        "minimum_months": None,
        "maximum_months": None,
    }

    #
    # Esempio:
    # RENTAL PERIOD from September 19, 2026
    # to January 9, 2027
    #
    match = re.search(
        r"from\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})"
        r"\s+to\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})",
        text,
        re.IGNORECASE,
    )

    if match:
        result["available_from"] = (
            parse_english_date(
                match.group(1),
                match.group(2),
                match.group(3),
            )
        )

        result["available_to"] = (
            parse_english_date(
                match.group(4),
                match.group(5),
                match.group(6),
            )
        )

    #
    # min. 3 months
    # minimum 2 months
    # minimum rental 2 months
    #
    min_match = re.search(
        r"(?:min\.?|minimum(?:\s+rental)?)"
        r"\s*(\d+)"
        r"\s*months?",
        text,
        re.IGNORECASE,
    )

    if min_match:
        result["minimum_months"] = int(
            min_match.group(1)
        )

    #
    # German:
    # Mindestmietdauer 12 Monate
    #
    if result["minimum_months"] is None:
        min_match = re.search(
            r"Mindestmietdauer\s*"
            r"(\d+)\s*Monate?",
            text,
            re.IGNORECASE,
        )

        if min_match:
            result["minimum_months"] = int(
                min_match.group(1)
            )

    return result


def infer_property_type(
    title,
    text,
):
    combined = (
        f"{title} {text}"
    ).lower()

    if (
        "flatshare" in combined
        or "shared apartment" in combined
        or "wg-zimmer" in combined
        or "wg zimmer" in combined
    ):
        return "shared_apartment"

    if (
        "private room" in combined
        or re.search(
            r"\bzimmer\b",
            combined,
        )
    ):
        return "private_room"

    if (
        "studio" in combined
        or "atelier" in combined
    ):
        return "studio"

    if (
        "apartment" in combined
        or "wohnung" in combined
        or "appartement" in combined
    ):
        return "apartment"

    return "other"


def extract_restrictions(text):
    lower = text.lower()

    pets_allowed = None
    smoking_allowed = None
    students_only = None
    gender = None

    pets_negative = [
        "animals not permitted",
        "pets not allowed",
        "no pets",
        "keine haustiere",
        "keine tiere",
        "animaux interdits",
        "animali non ammessi",
    ]

    pets_positive = [
        "pets allowed",
        "animals allowed",
        "haustiere erlaubt",
        "animaux acceptés",
        "animali ammessi",
    ]

    smoking_negative = [
        "smoking not permitted",
        "no smoking",
        "non-smoking",
        "nichtraucher",
        "rauchen nicht erlaubt",
        "non fumeur",
        "vietato fumare",
    ]

    smoking_positive = [
        "smoking allowed",
        "rauchen erlaubt",
        "fumeur accepté",
        "fumatori ammessi",
    ]

    student_patterns = [
        "students only",
        "student only",
        "nur studenten",
        "nur studentinnen",
        "étudiants uniquement",
        "solo studenti",
    ]

    female_patterns = [
        "women only",
        "female only",
        "woman only",
        "nur frauen",
        "nur weiblich",
        "studentin gesucht",
        "solo donne",
    ]

    male_patterns = [
        "men only",
        "male only",
        "man only",
        "nur männer",
        "nur männlich",
        "solo uomini",
    ]

    if any(
        value in lower
        for value in pets_negative
    ):
        pets_allowed = False

    elif any(
        value in lower
        for value in pets_positive
    ):
        pets_allowed = True

    if any(
        value in lower
        for value in smoking_negative
    ):
        smoking_allowed = False

    elif any(
        value in lower
        for value in smoking_positive
    ):
        smoking_allowed = True

    if any(
        value in lower
        for value in student_patterns
    ):
        students_only = True

    if any(
        value in lower
        for value in female_patterns
    ):
        gender = "female"

    elif any(
        value in lower
        for value in male_patterns
    ):
        gender = "male"

    age_min = None
    age_max = None

    age_match = re.search(
        r"(?:between|zwischen)"
        r"\s*(\d{2})"
        r"\s*(?:and|und|-)"
        r"\s*(\d{2})",
        lower,
    )

    if age_match:
        age_min = int(
            age_match.group(1)
        )

        age_max = int(
            age_match.group(2)
        )

    return {
        "students_only": students_only,
        "gender": gender,
        "minimum_age": age_min,
        "maximum_age": age_max,
        "pets_allowed": pets_allowed,
        "smoking_allowed": smoking_allowed,
    }


def isolate_main_listing(
    body_text,
    title,
):
    text = body_text

    title_position = text.find(
        title
    )

    if title_position >= 0:
        text = text[
            title_position:
        ]

    stop_markers = [
        "Wichtige Information!",
        "MEHR HOUSING",
    ]

    positions = []

    for marker in stop_markers:
        position = text.find(
            marker
        )

        if position >= 0:
            positions.append(
                position
            )

    if positions:
        text = text[
            :min(positions)
        ]

    return text.strip()


def parse_listing(
    page,
    index_listing,
):
    page_title = clean_text(
        page.title()
    )

    h1 = page.locator(
        "h1"
    ).all_inner_texts()

    if h1:
        title = clean_text(
            h1[0]
        )
    else:
        title = page_title

    body_text = page.locator(
        "body"
    ).inner_text()

    main_text = isolate_main_listing(
        body_text,
        title,
    )

    meta_description = None

    meta_locator = page.locator(
        'meta[name="description"]'
    )

    if meta_locator.count() > 0:
        meta_description = (
            meta_locator
            .first
            .get_attribute(
                "content"
            )
        )

    price = extract_price(
        main_text
    )

    if price is None:
        price = index_listing.get(
            "price_chf"
        )

    postal_code = extract_postal_code(
        main_text
    )

    rooms = extract_rooms(
        main_text
    )

    size_m2 = extract_size_m2(
        main_text
    )

    contract_type = extract_contract_type(
        main_text
    )

    offer_type = extract_offer_type(
        main_text
    )

    city = extract_city(
        main_text
    )

    floor = extract_floor(
        main_text
    )

    external_url = extract_external_url(
        main_text
    )

    availability = extract_availability(
        main_text
    )

    restrictions = extract_restrictions(
        main_text
    )

    property_type = infer_property_type(
        title,
        main_text,
    )

    title_lower = title.lower()

    furnished = (
        "furnished" in title_lower
        or "möbl" in title_lower
        or "meublé" in title_lower
        or "arredato" in title_lower
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "source": "ronorp",

        "source_url": index_listing[
            "url"
        ],

        "title": title,

        "price": {
            "monthly": price,
            "currency": "CHF",
        },

        "location": {
            "address": None,
            "postal_code": postal_code,
            "city": city,
            "country": "CH",
            "latitude": None,
            "longitude": None,
            "precision": (
                "postal_code"
                if postal_code
                else "city"
            ),
        },

        "property": {
            "type": property_type,
            "rooms": rooms,
            "size_m2": size_m2,
            "floor": floor,
            "furnished": furnished,
        },

        "contract": {
            "type": contract_type,
            "available_from": availability[
                "available_from"
            ],
            "available_to": availability[
                "available_to"
            ],
            "minimum_months": availability[
                "minimum_months"
            ],
            "maximum_months": availability[
                "maximum_months"
            ],
        },

        "offer_type": offer_type,

        "restrictions": restrictions,

        "description": clean_text(
            meta_description
        ),

        "description_raw": main_text,

        "external_url": external_url,

        "dates": {
            "first_seen_at": now,
            "last_seen_at": now,
        },

        "status": "active",
    }


def main():
    index_listings = load_index()

    print(
        f"Listings available in index: "
        f"{len(index_listings)}"
    )

    if MAX_LISTINGS is not None:
        index_listings = (
            index_listings[
                :MAX_LISTINGS
            ]
        )

    print(
        f"Listings to process: "
        f"{len(index_listings)}"
    )

    print()

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1400,
                "height": 1200,
            }
        )

        total = len(
            index_listings
        )

        for index, listing in enumerate(
            index_listings,
            start=1,
        ):

            url = listing["url"]

            print(
                f"[{index}/{total}]"
            )

            print(
                f"Opening: {url}"
            )

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(
                    2000
                )

                parsed = parse_listing(
                    page,
                    listing,
                )

                results.append(
                    parsed
                )

                print(
                    "  Title:",
                    parsed["title"],
                )

                print(
                    "  Price:",
                    parsed["price"]["monthly"],
                )

                print(
                    "  City:",
                    parsed["location"]["city"],
                )

                print(
                    "  Postal code:",
                    parsed["location"]["postal_code"],
                )

                print(
                    "  Type:",
                    parsed["property"]["type"],
                )

                print(
                    "  Rooms:",
                    parsed["property"]["rooms"],
                )

                print(
                    "  Size:",
                    parsed["property"]["size_m2"],
                )

                print(
                    "  Contract:",
                    parsed["contract"]["type"],
                )

                print(
                    "  From:",
                    parsed["contract"]["available_from"],
                )

                print(
                    "  To:",
                    parsed["contract"]["available_to"],
                )

                print(
                    "  Min months:",
                    parsed["contract"]["minimum_months"],
                )

                print(
                    "  Pets:",
                    parsed["restrictions"]["pets_allowed"],
                )

                print(
                    "  Smoking:",
                    parsed["restrictions"]["smoking_allowed"],
                )

            except Exception as exc:

                print(
                    "  ERROR:",
                    repr(exc),
                )

            print()

            time.sleep(
                0.5
            )

        browser.close()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source": "ronorp",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "count": len(
            results
        ),
        "listings": results,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"Processed: "
        f"{len(results)} listings"
    )

    print(
        f"Saved to: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()