import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


INPUT_FILE = Path(
    "data/raw/flatfox/lausanne-shared-index.json"
)

OUTPUT_FILE = Path(
    "data/processed/flatfox-lausanne-listings.json"
)

DEBUG_DIR = Path(
    "data/raw/flatfox/debug/errors"
)


# Prima testiamo 5.
# Se il risultato è buono:
# MAX_LISTINGS = None
MAX_LISTINGS = None


WAIT_MS = 700


MONTHS_FR = {
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
}


def clean(value):
    if value is None:
        return None

    value = " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )

    return value or None


def get_source_id(url):
    match = re.search(
        r"/(\d+)/?$",
        url,
    )

    if match:
        return match.group(1)

    return None


def get_lines(text):
    return [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]


def extract_price(text):
    patterns = [
        r"CHF\s*([\d'’\s]+)\s+charges\s+incluses",
        r"CHF\s*([\d'’\s]+)\s+par\s+mois",
        r"CHF\s*([\d'’\s]+)",
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
            .replace(" ", "")
            .replace("'", "")
            .replace("’", "")
        )

        try:
            price = float(value)

            if price >= 100:
                return price

        except ValueError:
            pass

    return None


def extract_net_rent(text):
    match = re.search(
        r"Loyer net\s*"
        r"\(hors charges\)\s*:\s*"
        r"(?:\|\s*)?"
        r"CHF\s*([\d'’\s]+)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = (
        match.group(1)
        .replace(" ", "")
        .replace("'", "")
        .replace("’", "")
    )

    try:
        return float(value)

    except ValueError:
        return None


def extract_charges(text):
    match = re.search(
        r"\bCharges\s*:\s*"
        r"(?:\|\s*)?"
        r"CHF\s*([\d'’\s]+)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = (
        match.group(1)
        .replace(" ", "")
        .replace("'", "")
        .replace("’", "")
    )

    try:
        return float(value)

    except ValueError:
        return None


def extract_location(text):
    """
    Cerca righe tipo:

    Rue de Lausanne 49, 1020 Renens - CHF 870 ...
    1018 Lausanne - CHF 750 ...
    """

    lines = get_lines(text)

    for line in lines:

        if (
            "CHF" not in line
            or not re.search(
                r"\b\d{4}\b",
                line,
            )
        ):
            continue

        before_price = re.split(
            r"\s+-\s+CHF",
            line,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        before_price = clean(
            before_price
        )

        if not before_price:
            continue

        #
        # Con indirizzo:
        # Rue de Lausanne 49, 1020 Renens
        #
        match = re.match(
            r"(.+?),\s*"
            r"(\d{4})\s+"
            r"(.+)$",
            before_price,
        )

        if match:
            return {
                "address":
                    clean(
                        match.group(1)
                    ),

                "postal_code":
                    match.group(2),

                "city":
                    clean(
                        match.group(3)
                    ),
            }

        #
        # Senza indirizzo:
        # 1018 Lausanne
        #
        match = re.match(
            r"(\d{4})\s+"
            r"(.+)$",
            before_price,
        )

        if match:
            return {
                "address":
                    None,

                "postal_code":
                    match.group(1),

                "city":
                    clean(
                        match.group(2)
                    ),
            }

    return {
        "address":
            None,

        "postal_code":
            None,

        "city":
            None,
    }


def extract_number_field(
    text,
    label,
):
    pattern = (
        rf"{re.escape(label)}"
        rf"\s*:\s*"
        rf"(?:\|\s*)?"
        rf"([\d.,]+)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1)
            .replace(",", ".")
        )

    except ValueError:
        return None


def extract_area_field(
    text,
    label,
):
    pattern = (
        rf"{re.escape(label)}"
        rf"\s*:\s*"
        rf"(?:\|\s*)?"
        rf"([\d.,]+)\s*m[²2]"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1)
            .replace(",", ".")
        )

    except ValueError:
        return None


def extract_floor(text):
    match = re.search(
        r"Étage\s*:\s*"
        r"(?:\|\s*)?"
        r"([^\n]+)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return clean(
        match.group(1)
    )


def extract_field(
    text,
    label,
):
    pattern = (
        rf"{re.escape(label)}"
        rf"\s*:\s*"
        rf"(?:\|\s*)?"
        rf"([^\n]+)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return clean(
        match.group(1)
    )


def parse_french_date(value):
    if not value:
        return None

    #
    # 01.09.2026
    #
    match = re.search(
        r"\b"
        r"(\d{1,2})"
        r"[./]"
        r"(\d{1,2})"
        r"[./]"
        r"(\d{4})"
        r"\b",
        value,
    )

    if match:

        try:
            return (
                datetime(
                    int(
                        match.group(3)
                    ),
                    int(
                        match.group(2)
                    ),
                    int(
                        match.group(1)
                    ),
                )
                .date()
                .isoformat()
            )

        except ValueError:
            return None

    #
    # 1. septembre 2026
    # 1 septembre 2026
    #
    match = re.search(
        r"\b"
        r"(\d{1,2})"
        r"\.?\s+"
        r"([A-Za-zÀ-ÿ]+)"
        r"\s+"
        r"(\d{4})"
        r"\b",
        value,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    month = MONTHS_FR.get(
        match.group(2).lower()
    )

    if not month:
        return None

    try:
        return (
            datetime(
                int(
                    match.group(3)
                ),
                month,
                int(
                    match.group(1)
                ),
            )
            .date()
            .isoformat()
        )

    except ValueError:
        return None


def extract_availability(text):
    value = extract_field(
        text,
        "Disponibilité",
    )

    if not value:
        return {
            "text":
                None,

            "available_from":
                None,

            "available_now":
                None,
        }

    lower = value.lower()

    available_now = any(
        marker in lower
        for marker in [
            "immédiatement",
            "immediatement",
            "de suite",
            "dès maintenant",
            "des maintenant",
        ]
    )

    return {
        "text":
            value,

        "available_from":
            parse_french_date(
                value
            ),

        "available_now":
            available_now,
    }


def extract_features(text):
    value = extract_field(
        text,
        "Caractéristiques",
    )

    if not value:
        return []

    return [
        clean(part)
        for part in value.split(",")
        if clean(part)
    ]


def extract_furnished(text):
    lower = text.lower()

    if any(
        marker in lower
        for marker in [
            "non meublé",
            "non meublée",
        ]
    ):
        return False

    if any(
        marker in lower
        for marker in [
            "meublé",
            "meublée",
        ]
    ):
        return True

    return None


def extract_contract_type(
    text,
):
    lower = text.lower()

    if any(
        marker in lower
        for marker in [
            "temporaire",
            "durée déterminée",
            "duree determinee",
            "sous-location",
            "sous location",
        ]
    ):
        return "temporary"

    return None


def extract_description(text):
    lines = get_lines(
        text
    )

    start = None
    end = None

    for index, line in enumerate(
        lines
    ):

        if (
            line.lower()
            == "description"
        ):
            start = index + 1
            continue

        if (
            start is not None
            and (
                line == "Flatfox AG"
                or line.startswith(
                    "Flatfox AG"
                )
            )
        ):
            end = index
            break

    if start is None:
        return {
            "title":
                None,

            "description":
                None,
        }

    if end is None:
        end = len(
            lines
        )

    content = lines[
        start:end
    ]

    if not content:
        return {
            "title":
                None,

            "description":
                None,
        }

    #
    # In molti annunci la prima riga della
    # descrizione è un titolo libero.
    #
    description_title = (
        content[0]
    )

    description = clean(
        " ".join(
            content[1:]
        )
    )

    return {
        "title":
            description_title,

        "description":
            description,
    }


def extract_restrictions(
    text,
):
    lower = text.lower()

    pets = None
    smoking = None
    student_only = None
    gender = None

    if any(
        marker in lower
        for marker in [
            "animaux interdits",
            "animaux non admis",
            "animaux non acceptés",
            "sans animaux",
            "pas d'animaux",
            "pas d’animaux",
        ]
    ):
        pets = False

    elif any(
        marker in lower
        for marker in [
            "animaux acceptés",
            "animaux admis",
        ]
    ):
        pets = True

    if any(
        marker in lower
        for marker in [
            "non-fumeur",
            "non fumeur",
            "non-fumeurs",
            "non fumeurs",
        ]
    ):
        smoking = False

    if any(
        marker in lower
        for marker in [
            "réservé aux étudiants",
            "réservée aux étudiants",
            "étudiants uniquement",
            "étudiant uniquement",
            "student only",
        ]
    ):
        student_only = True

    if any(
        marker in lower
        for marker in [
            "femme uniquement",
            "femmes uniquement",
            "réservé aux femmes",
            "réservée aux femmes",
            "female only",
        ]
    ):
        gender = "female"

    elif any(
        marker in lower
        for marker in [
            "homme uniquement",
            "hommes uniquement",
            "réservé aux hommes",
            "réservée aux hommes",
            "male only",
        ]
    ):
        gender = "male"

    return {
        "pets":
            pets,

        "smoking":
            smoking,

        "student_only":
            student_only,

        "gender":
            gender,

        "minimum_age":
            None,

        "maximum_age":
            None,
    }


def get_title(
    page,
    item,
):
    try:
        h1 = page.locator(
            "h1"
        ).first

        title = clean(
            h1.inner_text(
                timeout=3000
            )
        )

        if title:
            return title

    except Exception:
        pass

    return clean(
        item.get(
            "title"
        )
    )


def parse_listing(
    page,
    item,
):
    body_text = (
        page.locator(
            "body"
        ).inner_text()
    )

    title = get_title(
        page,
        item,
    )

    location = extract_location(
        body_text
    )

    price = extract_price(
        body_text
    )

    if price is None:
        price = item.get(
            "price_chf"
        )

    availability = (
        extract_availability(
            body_text
        )
    )

    description_data = (
        extract_description(
            body_text
        )
    )

    rooms = extract_number_field(
        body_text,
        "Nombre de pièces",
    )

    surface_m2 = extract_area_field(
        body_text,
        "Surface",
    )

    usable_area_m2 = (
        extract_area_field(
            body_text,
            "Domaine utile",
        )
    )

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    quality_flags = []

    if not location[
        "postal_code"
    ]:
        quality_flags.append(
            "missing_postal_code"
        )

    if not location[
        "city"
    ]:
        quality_flags.append(
            "missing_city"
        )

    if not location[
        "address"
    ]:
        quality_flags.append(
            "missing_address"
        )

    if price is None:
        quality_flags.append(
            "missing_price"
        )

    return {
        "source":
            "flatfox",

        "source_section":
            "lausanne_shared",

        "source_id":
            get_source_id(
                item[
                    "url"
                ]
            ),

        "source_url":
            item[
                "url"
            ],

        "title":
            title,

        "description_title":
            description_data[
                "title"
            ],

        "price": {
            "monthly":
                price,

            "net":
                extract_net_rent(
                    body_text
                ),

            "charges":
                extract_charges(
                    body_text
                ),

            "currency":
                "CHF",
        },

        "location": {
            "address":
                location[
                    "address"
                ],

            "postal_code":
                location[
                    "postal_code"
                ],

            "city":
                location[
                    "city"
                ],

            "country":
                "CH",

            "latitude":
                None,

            "longitude":
                None,

            "precision":
                None,
        },

        "property": {
            "type":
                "private_room",

            "rooms":
                rooms,

            "size_m2":
                surface_m2,

            #
            # Flatfox può distinguere tra
            # superficie dell'appartamento
            # e superficie utile della stanza.
            #
            "usable_area_m2":
                usable_area_m2,

            "floor":
                extract_floor(
                    body_text
                ),

            "furnished":
                extract_furnished(
                    body_text
                ),

            "features":
                extract_features(
                    body_text
                ),
        },

        "contract": {
            "type":
                extract_contract_type(
                    body_text
                ),

            "availability_text":
                availability[
                    "text"
                ],

            "available_from":
                availability[
                    "available_from"
                ],

            "available_now":
                availability[
                    "available_now"
                ],

            "available_to":
                None,

            "minimum_months":
                None,

            "maximum_months":
                None,
        },

        "offer_type":
            "offer",

        "restrictions":
            extract_restrictions(
                body_text
            ),

        "description":
            description_data[
                "description"
            ],

        "quality_flags":
            quality_flags,

        "dates": {
            "first_seen_at":
                now,

            "last_seen_at":
                now,
        },

        "status":
            "active",
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
    errors = []

    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sync_playwright() as playwright:

        browser = (
            playwright.chromium.launch(
                headless=True
            )
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 1000,
            },

            locale="fr-CH",
        )

        page = context.new_page()

        total = len(
            listings
        )

        for index, item in enumerate(
            listings,
            start=1,
        ):

            url = item[
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
                response = page.goto(
                    url,
                    wait_until=
                        "domcontentloaded",
                    timeout=60000,
                )

                print(
                    "  HTTP:",
                    (
                        response.status
                        if response
                        else None
                    ),
                )

                page.wait_for_timeout(
                    WAIT_MS
                )

                listing = (
                    parse_listing(
                        page,
                        item,
                    )
                )

                processed.append(
                    listing
                )

                print(
                    "  Price:",
                    listing[
                        "price"
                    ][
                        "monthly"
                    ],
                )

                print(
                    "  CAP:",
                    listing[
                        "location"
                    ][
                        "postal_code"
                    ],
                )

                print(
                    "  City:",
                    listing[
                        "location"
                    ][
                        "city"
                    ],
                )

                print(
                    "  Address:",
                    listing[
                        "location"
                    ][
                        "address"
                    ],
                )

                print(
                    "  Rooms:",
                    listing[
                        "property"
                    ][
                        "rooms"
                    ],
                )

                print(
                    "  Surface:",
                    listing[
                        "property"
                    ][
                        "size_m2"
                    ],
                )

                print(
                    "  Usable area:",
                    listing[
                        "property"
                    ][
                        "usable_area_m2"
                    ],
                )

                print(
                    "  Furnished:",
                    listing[
                        "property"
                    ][
                        "furnished"
                    ],
                )

                print(
                    "  Availability:",
                    listing[
                        "contract"
                    ][
                        "availability_text"
                    ],
                )

            except Exception as exc:

                print(
                    "  ERROR:",
                    repr(exc),
                )

                errors.append(
                    {
                        "url":
                            url,

                        "error":
                            repr(exc),
                    }
                )

                try:
                    source_id = (
                        get_source_id(
                            url
                        )
                        or str(index)
                    )

                    debug_file = (
                        DEBUG_DIR
                        / f"{source_id}.html"
                    )

                    debug_file.write_text(
                        page.content(),
                        encoding="utf-8",
                    )

                except Exception:
                    pass

            time.sleep(
                0.15
            )

        browser.close()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source":
            "flatfox",

        "source_section":
            "lausanne_shared",

        "input_count":
            len(listings),

        "count":
            len(processed),

        "error_count":
            len(errors),

        "errors":
            errors,

        "listings":
            processed,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with_price = sum(
        x["price"].get(
            "monthly"
        )
        is not None
        for x in processed
    )

    with_postal = sum(
        bool(
            x["location"].get(
                "postal_code"
            )
        )
        for x in processed
    )

    with_city = sum(
        bool(
            x["location"].get(
                "city"
            )
        )
        for x in processed
    )

    with_address = sum(
        bool(
            x["location"].get(
                "address"
            )
        )
        for x in processed
    )

    with_size = sum(
        x["property"].get(
            "size_m2"
        )
        is not None
        for x in processed
    )

    with_usable_area = sum(
        x["property"].get(
            "usable_area_m2"
        )
        is not None
        for x in processed
    )

    with_availability = sum(
        bool(
            x["contract"].get(
                "availability_text"
            )
        )
        for x in processed
    )

    print()
    print("======================")
    print("FLATFOX DETAILS")
    print("======================")

    print(
        "Input:",
        len(listings),
    )

    print(
        "Processed:",
        len(processed),
    )

    print(
        "Errors:",
        len(errors),
    )

    print()
    print(
        "With price:",
        with_price,
    )

    print(
        "With postal code:",
        with_postal,
    )

    print(
        "With city:",
        with_city,
    )

    print(
        "With address:",
        with_address,
    )

    print(
        "With size:",
        with_size,
    )

    print(
        "With usable area:",
        with_usable_area,
    )

    print(
        "With availability:",
        with_availability,
    )

    print()
    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()