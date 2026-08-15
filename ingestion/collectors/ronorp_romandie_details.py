import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


INPUT_FILE = Path(
    "data/raw/ronorp_romandie/romandie-housing-index.json"
)

OUTPUT_FILE = Path(
    "data/processed/ronorp-romandie-listings.json"
)

MAX_LISTINGS = None


MONTHS = {
    # Francese
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,

    # Inglese
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


def clean(value):
    if value is None:
        return None

    value = " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )

    if value in {
        "",
        "--",
        "\\--",
    }:
        return None

    return value


def extract_price(text):
    if not text:
        return None

    patterns = [
        r"CHF\s*([\d'’.,]+)",
        r"Preis\s+CHF\s*([\d'’.,]+)",
        r"Prix\s+CHF\s*([\d'’.,]+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = (
            match.group(1)
            .replace("'", "")
            .replace("’", "")
            .replace(",", "")
        )

        try:
            number = float(value)

            #
            # Evitiamo numeri palesemente non plausibili
            # per un affitto mensile.
            #
            if number >= 100:
                return number

        except ValueError:
            pass

    return None


def extract_postal_code(text):
    if not text:
        return None

    patterns = [
        r"\bPLZ\s+(\d{4})\b",
        r"\bNPA\s+(\d{4})\b",
        r"\b(\d{4})\s+[A-Za-zÀ-ÿ]",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def extract_rooms(text):
    patterns = [
        r"Räume\s+([\d.,]+)",
        r"Pièces\s+([\d.,]+)",
        r"Pieces\s+([\d.,]+)",
        r"(\d+[½]?)\s+PIÈCES",
        r"(\d+[½]?)\s+PIECES",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = match.group(1)

        value = value.replace(",", ".")

        if "½" in value:
            value = value.replace("½", ".5")

        try:
            return float(value)

        except ValueError:
            continue

    return None


def extract_size_m2(text):
    patterns = [
        r"Quadratmeter\s+([\d.,]+)",
        r"Surface\s+([\d.,]+)",
        r"([\d.,]+)\s*m[²2]",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = (
            match.group(1)
            .replace(",", ".")
        )

        try:
            number = float(value)

            if 5 <= number <= 1000:
                return number

        except ValueError:
            continue

    return None


def extract_floor(text):
    patterns = [
        r"Böden\s+(.+?)(?:\n|Quadratmeter|Surface)",
        r"Étage\s+(.+?)(?:\n|Surface|Quadratmeter)",
        r"Etage\s+(.+?)(?:\n|Surface|Quadratmeter)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:
            return clean(
                match.group(1)
            )

    return None


def extract_contract_type(text):
    lower = text.lower()

    if any(
        value in lower
        for value in [
            "durée déterminée",
            "duree determinee",
            "temporary",
            "temporär",
            "befristet",
        ]
    ):
        return "temporary"

    if any(
        value in lower
        for value in [
            "durée indéterminée",
            "duree indeterminee",
            "permanent",
            "unbefristet",
        ]
    ):
        return "permanent"

    patterns = [
        r"Vertrag\s+(Temporary|Permanent)",
        r"Contrat\s+(.+?)(?:\n|Email|E-mail)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = clean(
            match.group(1)
        )

        if not value:
            continue

        lower_value = value.lower()

        if (
            "temporary" in lower_value
            or "détermin" in lower_value
            or "determin" in lower_value
        ):
            return "temporary"

        if (
            "permanent" in lower_value
            or "indétermin" in lower_value
            or "indetermin" in lower_value
        ):
            return "permanent"

    return None


def extract_offer_type(text):
    lower = text.lower()

    wanted_patterns = [
        "je cherche",
        "recherche appartement",
        "recherche chambre",
        "cherche appartement",
        "cherche une chambre",
        "looking for",
        "suche wohnung",
        "suche zimmer",
    ]

    if any(
        pattern in lower
        for pattern in wanted_patterns
    ):
        return "wanted"

    if any(
        pattern in lower
        for pattern in [
            "typ biete",
            "type offre",
            "à louer",
            "a louer",
            "sublease",
            "sous-location",
        ]
    ):
        return "offer"

    return None


def extract_address_city(text):
    address = None
    city = None

    address_patterns = [
        r"Adresse\s+(.+?)(?:\nCity/Agglo|\nPLZ|\nNPA)",
        r"Address\s+(.+?)(?:\nCity/Agglo|\nPLZ|\nNPA)",
    ]

    for pattern in address_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:
            address = clean(
                match.group(1)
            )
            break

    if address:
        match = re.match(
            r"^(.+?),\s*(\d{4})\s+(.+)$",
            address,
        )

        if match:
            return {
                "address": clean(
                    match.group(1)
                ),
                "postal_code": match.group(2),
                "city": clean(
                    match.group(3)
                ),
            }

    #
    # Cerca città dopo Adresse, quando Ron Orp
    # mette solo il nome della località.
    #
    if address:
        if not re.search(
            r"\d{4}",
            address,
        ):
            city = address
            address = None

    return {
        "address": address,
        "postal_code": None,
        "city": city,
    }


def parse_french_date(day, month, year):
    month_number = MONTHS.get(
        month.lower()
    )

    if not month_number:
        return None

    try:
        return (
            datetime(
                int(year),
                month_number,
                int(day),
            )
            .date()
            .isoformat()
        )

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
    # Francese:
    # dès le 1 janvier 2027 au 30 juin 2027
    #
    range_pattern = re.search(
        r"d[èe]s\s+le\s+"
        r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})"
        r"\s+au\s+"
        r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )

    if range_pattern:
        result["available_from"] = (
            parse_french_date(
                range_pattern.group(1),
                range_pattern.group(2),
                range_pattern.group(3),
            )
        )

        result["available_to"] = (
            parse_french_date(
                range_pattern.group(4),
                range_pattern.group(5),
                range_pattern.group(6),
            )
        )

    #
    # Francese: dès le 14 septembre 2026
    #
    if not result["available_from"]:
        start_pattern = re.search(
            r"d[èe]s\s+le\s+"
            r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})",
            text,
            flags=re.IGNORECASE,
        )

        if start_pattern:
            result["available_from"] = (
                parse_french_date(
                    start_pattern.group(1),
                    start_pattern.group(2),
                    start_pattern.group(3),
                )
            )

    #
    # "dès maintenant"
    #
    if re.search(
        r"d[èe]s\s+maintenant",
        text,
        flags=re.IGNORECASE,
    ):
        result["available_from"] = (
            datetime.now(
                timezone.utc
            )
            .date()
            .isoformat()
        )

    #
    # minimo 3 mesi / au minimum 3 mois
    #
    minimum_patterns = [
        r"au\s+minimum\s+(\d+)\s+mois",
        r"minimum\s+(\d+)\s+mois",
        r"min\.\s*(\d+)\s+mois",
        r"mindestens\s+(\d+)\s+monate",
        r"min\.?\s*(\d+)\s+months?",
    ]

    for pattern in minimum_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            result["minimum_months"] = int(
                match.group(1)
            )
            break

    return result


def infer_property_type(title, text):
    combined = (
        f"{title} {text}"
    ).lower()

    if any(
        word in combined
        for word in [
            "colocation",
            "flatshare",
            "wg",
            "chambre en colocation",
        ]
    ):
        return "shared_apartment"

    if any(
        word in combined
        for word in [
            "chambre",
            "room",
            "zimmer",
        ]
    ):
        return "private_room"

    if any(
        word in combined
        for word in [
            "studio",
            "atelier",
        ]
    ):
        return "studio"

    if any(
        word in combined
        for word in [
            "appartement",
            "apartment",
            "wohnung",
        ]
    ):
        return "apartment"

    return "other"


def extract_restrictions(text):
    lower = text.lower()

    pets = None
    smoking = None
    student_only = None
    gender = None

    if any(
        phrase in lower
        for phrase in [
            "animaux non admis",
            "animaux interdits",
            "pets not allowed",
            "animals not permitted",
            "keine haustiere",
        ]
    ):
        pets = False

    elif any(
        phrase in lower
        for phrase in [
            "animaux admis",
            "animaux acceptés",
            "pets allowed",
            "haustiere erlaubt",
        ]
    ):
        pets = True

    if any(
        phrase in lower
        for phrase in [
            "non-fumeur",
            "non fumeur",
            "smoking not permitted",
            "no smoking",
            "nichtraucher",
        ]
    ):
        smoking = False

    if any(
        phrase in lower
        for phrase in [
            "étudiant uniquement",
            "étudiants uniquement",
            "student only",
            "students only",
        ]
    ):
        student_only = True

    if any(
        phrase in lower
        for phrase in [
            "femme uniquement",
            "femmes uniquement",
            "female only",
            "women only",
        ]
    ):
        gender = "female"

    elif any(
        phrase in lower
        for phrase in [
            "homme uniquement",
            "hommes uniquement",
            "male only",
            "men only",
        ]
    ):
        gender = "male"

    return {
        "pets": pets,
        "smoking": smoking,
        "student_only": student_only,
        "gender": gender,
        "minimum_age": None,
        "maximum_age": None,
    }


def isolate_main_listing(body_text):
    text = body_text

    separators = [
        "PLUS DE LOGEMENTS",
        "MEHR HOUSING",
        "Wichtige Information!",
        "Informations importantes",
    ]

    for separator in separators:
        position = text.find(
            separator
        )

        if position != -1:
            text = text[:position]

    return text.strip()


def parse_listing(page, source_url):
    body_text = page.locator(
        "body"
    ).inner_text()

    main_text = isolate_main_listing(
        body_text
    )

    title = None

    try:
        title = clean(
            page.locator(
                "h1"
            ).first.inner_text(
                timeout=2000
            )
        )

    except Exception:
        pass

    if not title:
        title = clean(
            page.title()
        )

    price = extract_price(
        main_text
    )

    postal_code = extract_postal_code(
        main_text
    )

    location_data = extract_address_city(
        main_text
    )

    if not postal_code:
        postal_code = location_data[
            "postal_code"
        ]

    city = location_data[
        "city"
    ]

    address = location_data[
        "address"
    ]

    #
    # Se l'indirizzo contiene CAP+città ma
    # non è stato separato prima.
    #
    if address and not city:
        match = re.search(
            r"\b(\d{4})\s+(.+)$",
            address,
        )

        if match:
            if not postal_code:
                postal_code = match.group(1)

            city = clean(
                match.group(2)
            )

    availability = extract_availability(
        main_text
    )

    property_type = infer_property_type(
        title,
        main_text,
    )

    restrictions = extract_restrictions(
        main_text
    )

    furnished = None

    lower = main_text.lower()

    if any(
        word in lower
        for word in [
            "meublé",
            "meuble",
            "furnished",
            "möbliert",
        ]
    ):
        furnished = True

    elif any(
        word in lower
        for word in [
            "non meublé",
            "non meuble",
            "unfurnished",
            "unmöbliert",
        ]
    ):
        furnished = False

    return {
        "source": "ronorp",

        "source_section": "romandie",

        "source_url": source_url,

        "title": title,

        "price": {
            "monthly": price,
            "currency": "CHF",
        },

        "location": {
            "address": address,
            "postal_code": postal_code,
            "city": city,
            "country": "CH",
            "latitude": None,
            "longitude": None,
            "precision": None,
        },

        "property": {
            "type": property_type,
            "rooms": extract_rooms(
                main_text
            ),
            "size_m2": extract_size_m2(
                main_text
            ),
            "floor": extract_floor(
                main_text
            ),
            "furnished": furnished,
        },

        "contract": {
            "type": extract_contract_type(
                main_text
            ),
            **availability,
        },

        "offer_type": extract_offer_type(
            main_text
        ),

        "restrictions": restrictions,

        "description": clean(
            main_text[:1000]
        ),

        "description_raw": main_text,

        "dates": {
            "first_seen_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "last_seen_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        },

        "status": "active",
    }


def main():
    source = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    listings = source.get(
        "listings",
        []
    )

    if MAX_LISTINGS is not None:
        listings = listings[
            :MAX_LISTINGS
        ]

    processed = []

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            }
        )

        total = len(
            listings
        )

        for index, listing in enumerate(
            listings,
            start=1,
        ):
            url = listing[
                "url"
            ]

            print()
            print(
                f"[{index}/{total}]"
            )

            print(
                url
            )

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(
                    1800
                )

                parsed = parse_listing(
                    page,
                    url,
                )

                processed.append(
                    parsed
                )

                print(
                    "  Price:",
                    parsed[
                        "price"
                    ][
                        "monthly"
                    ],
                )

                print(
                    "  City:",
                    parsed[
                        "location"
                    ][
                        "city"
                    ],
                )

                print(
                    "  CAP:",
                    parsed[
                        "location"
                    ][
                        "postal_code"
                    ],
                )

                print(
                    "  Rooms:",
                    parsed[
                        "property"
                    ][
                        "rooms"
                    ],
                )

                print(
                    "  Available:",
                    parsed[
                        "contract"
                    ][
                        "available_from"
                    ],
                )

            except Exception as exc:
                print(
                    "  ERROR:",
                    repr(exc),
                )

        browser.close()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source": "ronorp",

        "source_section": "romandie",

        "input_count": len(
            listings
        ),

        "count": len(
            processed
        ),

        "listings": processed,
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
        "----------------------"
    )

    print(
        "ROMANDIE DETAILS"
    )

    print(
        "----------------------"
    )

    print(
        "Input:",
        len(listings),
    )

    print(
        "Processed:",
        len(processed),
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()