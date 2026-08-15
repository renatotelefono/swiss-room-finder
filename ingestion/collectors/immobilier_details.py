import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


INPUT_FILE = Path(
    "data/raw/immobilier/lausanne-index.json"
)

OUTPUT_FILE = Path(
    "data/processed/immobilier-lausanne-listings.json"
)

DEBUG_DIR = Path(
    "data/raw/immobilier/debug/errors"
)


# Prima testiamo 5.
# Dopo il test positivo:
# MAX_LISTINGS = None
MAX_LISTINGS = None


WAIT_MS = 800


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

    if not value:
        return None

    return value


def get_source_id(url):
    match = re.search(
        r"-(\d+)$",
        url.rstrip("/"),
    )

    if match:
        return match.group(1)

    return None


def cut_main_listing(body_text):
    """
    Rimuove la sezione con gli altri immobili
    consigliati, evitando di estrarre dati
    dagli annunci correlati.
    """

    markers = [
        "Ces autres biens peuvent vous intéresser",
        "Ces autres biens pourraient vous intéresser",
    ]

    text = body_text

    for marker in markers:
        if marker in text:
            text = text.split(
                marker,
                1,
            )[0]

    return text


def get_lines(text):
    return [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]


def extract_price(text):
    patterns = [
        r"CHF\s*([\d'’\s]+)\.-\s*/\s*mois",
        r"CHF\s*([\d'’\s]+)\.-",
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


def extract_location(text):
    """
    La sezione Localisation contiene tipicamente:

    De : 1004 Lausanne, 23, avenue de Riant-Mont

    È il punto più affidabile da cui leggere
    CAP, città e indirizzo.
    """

    patterns = [
        (
            r"De\s*:\s*"
            r"(\d{4})\s+"
            r"([^,\n]+),\s*"
            r"([^\n]+)"
        ),
        (
            r"(\d{4})\s+"
            r"([^,\n]+),\s*\n"
            r"([^\n]+)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        postal_code = clean(
            match.group(1)
        )

        city = clean(
            match.group(2)
        )

        address = clean(
            match.group(3)
        )

        #
        # Il primo pattern può catturare
        # troppo testo dopo l'indirizzo.
        #
        if address:
            address = address.split(
                "À :",
                1,
            )[0]

            address = clean(
                address
            )

        return {
            "postal_code":
                postal_code,

            "city":
                city,

            "address":
                address,
        }

    #
    # Fallback: cerchiamo almeno CAP + città.
    #
    match = re.search(
        r"\b(\d{4})\s+"
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’ .-]+)",
        text,
    )

    if match:
        return {
            "postal_code":
                clean(
                    match.group(1)
                ),

            "city":
                clean(
                    match.group(2)
                ),

            "address":
                None,
        }

    return {
        "postal_code":
            None,

        "city":
            None,

        "address":
            None,
    }


def extract_size(text):
    match = re.search(
        r"\b([\d.,]+)\s*m[²2]\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1)
            .replace(
                ",",
                ".",
            )
        )

    except ValueError:
        return None


def extract_rooms(text):
    match = re.search(
        r"\b([\d.,]+)\s*pi[eè]ces?\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1)
            .replace(
                ",",
                ".",
            )
        )

    except ValueError:
        return None


def extract_bedrooms(text):
    match = re.search(
        r"\b([\d.,]+)\s*chambres?\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1)
            .replace(
                ",",
                ".",
            )
        )

    except ValueError:
        return None


def extract_bathrooms(text):
    match = re.search(
        r"\b([\d.,]+)\s*"
        r"salles?\s+de\s+bain\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1)
            .replace(
                ",",
                ".",
            )
        )

    except ValueError:
        return None


def extract_floor(text):
    patterns = [
        r"\b\d+(?:er|ère|e|ème)\s+étage\b",
        r"\brez-de-chaussée\b",
        r"\brez supérieur\b",
        r"\brez inférieur\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return clean(
                match.group(0)
            )

    return None


def parse_numeric_date(
    day,
    month,
    year,
):
    try:
        return (
            datetime(
                int(year),
                int(month),
                int(day),
            )
            .date()
            .isoformat()
        )

    except ValueError:
        return None


def parse_french_date(
    day,
    month,
    year,
):
    month_number = MONTHS_FR.get(
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
    """
    Restituisce sia il testo originale sia,
    quando possibile, una data ISO.

    "Disponible de suite" non viene trasformato
    artificialmente nella data di oggi.
    """

    lines = get_lines(
        text
    )

    availability_text = None

    for line in lines:
        if line.lower().startswith(
            "disponible"
        ):
            availability_text = line
            break

    if not availability_text:
        return {
            "text":
                None,

            "available_from":
                None,

            "available_now":
                None,
        }

    lower = (
        availability_text.lower()
    )

    available_now = (
        "de suite" in lower
        or "immédiatement" in lower
        or "immediatement" in lower
    )

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
        availability_text,
    )

    if match:
        return {
            "text":
                availability_text,

            "available_from":
                parse_numeric_date(
                    match.group(1),
                    match.group(2),
                    match.group(3),
                ),

            "available_now":
                available_now,
        }

    #
    # 1 septembre 2026
    #
    match = re.search(
        r"\b"
        r"(\d{1,2})\s+"
        r"([A-Za-zÀ-ÿ]+)\s+"
        r"(\d{4})"
        r"\b",
        availability_text,
    )

    if match:
        return {
            "text":
                availability_text,

            "available_from":
                parse_french_date(
                    match.group(1),
                    match.group(2),
                    match.group(3),
                ),

            "available_now":
                available_now,
        }

    return {
        "text":
            availability_text,

        "available_from":
            None,

        "available_now":
            available_now,
    }


def infer_property_type(
    title,
    text,
):
    combined = (
        f"{title or ''} "
        f"{text or ''}"
    ).lower()

    if (
        "chambre" in combined
        and (
            "colocation" in combined
            or "coliving" in combined
        )
    ):
        return "private_room"

    if "chambre" in (
        title or ""
    ).lower():
        return "private_room"

    if "studio" in combined:
        return "studio"

    if "maison" in combined:
        return "house"

    if (
        "attique" in combined
        or "appartement" in combined
    ):
        return "apartment"

    return "other"


def extract_furnished(
    text,
):
    lower = (
        text
        or ""
    ).lower()

    if (
        "non meublé" in lower
        or "non meublée" in lower
    ):
        return False

    if (
        "meublé" in lower
        or "meublée" in lower
    ):
        return True

    return None


def extract_restrictions(
    text,
):
    lower = (
        text
        or ""
    ).lower()

    pets = None
    smoking = None
    student_only = None
    gender = None

    if any(
        value in lower
        for value in [
            "animaux interdits",
            "animaux non admis",
            "animaux non acceptés",
            "sans animaux",
        ]
    ):
        pets = False

    elif any(
        value in lower
        for value in [
            "animaux acceptés",
            "animaux admis",
        ]
    ):
        pets = True

    if any(
        value in lower
        for value in [
            "non-fumeur",
            "non fumeur",
            "non-fumeurs",
            "non fumeurs",
        ]
    ):
        smoking = False

    if any(
        value in lower
        for value in [
            "réservé aux étudiants",
            "réservée aux étudiants",
            "étudiants uniquement",
            "étudiant uniquement",
        ]
    ):
        student_only = True

    if any(
        value in lower
        for value in [
            "femme uniquement",
            "femmes uniquement",
            "réservé aux femmes",
            "réservée aux femmes",
        ]
    ):
        gender = "female"

    elif any(
        value in lower
        for value in [
            "homme uniquement",
            "hommes uniquement",
            "réservé aux hommes",
            "réservée aux hommes",
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


def extract_description(
    text,
):
    """
    Cerca la sezione compresa tra il riepilogo
    m²/pièces e "Informations complémentaires".

    In genere contiene:
    - titolo descrittivo
    - paragrafi dell'annuncio
    """

    lines = get_lines(
        text
    )

    summary_index = None
    info_index = None

    for index, line in enumerate(
        lines
    ):
        if (
            summary_index is None
            and (
                "m²" in line
                or " m2" in line.lower()
            )
            and re.search(
                r"\bpi[eè]ces?\b",
                line,
                flags=re.IGNORECASE,
            )
        ):
            summary_index = index

        if (
            line.lower()
            == "informations complémentaires"
        ):
            info_index = index
            break

    if (
        summary_index is None
        or info_index is None
        or info_index
        <= summary_index + 1
    ):
        return {
            "description_title":
                None,

            "description":
                None,
        }

    content = lines[
        summary_index + 1:
        info_index
    ]

    #
    # Filtra elementi UI che possono
    # comparire nel mezzo.
    #
    ignored = {
        "afficher plus",
        "afficher moins",
    }

    content = [
        line
        for line in content
        if line.lower()
        not in ignored
    ]

    if not content:
        return {
            "description_title":
                None,

            "description":
                None,
        }

    description_title = (
        content[0]
    )

    description = clean(
        " ".join(
            content[1:]
        )
    )

    return {
        "description_title":
            description_title,

        "description":
            description,
    }


def extract_equipments(
    text,
):
    lines = get_lines(
        text
    )

    start = None

    for index, line in enumerate(
        lines
    ):
        if line.lower() == "équipements":
            start = index + 1
            break

    if start is None:
        return []

    stop_markers = [
        "votre garantie",
        "localisation",
        "ce bien est proposé",
    ]

    equipments = []

    for line in lines[start:]:

        lower = line.lower()

        if any(
            lower.startswith(
                marker
            )
            for marker
            in stop_markers
        ):
            break

        if len(line) <= 80:
            equipments.append(
                line
            )

    return equipments


def get_title(
    page,
    index_listing,
):
    try:
        locator = page.locator(
            "h1"
        ).first

        title = clean(
            locator.inner_text(
                timeout=3000
            )
        )

        if title:
            return title

    except Exception:
        pass

    page_title = clean(
        page.title()
    )

    if page_title:
        match = re.search(
            r"Location\s+(.+?)\s+-\s+CHF",
            page_title,
            flags=re.IGNORECASE,
        )

        if match:
            return clean(
                match.group(1)
            )

    return clean(
        index_listing.get(
            "title"
        )
    )


def parse_listing(
    page,
    item,
):
    url = item[
        "url"
    ]

    body_text = (
        page.locator(
            "body"
        ).inner_text()
    )

    main_text = (
        cut_main_listing(
            body_text
        )
    )

    title = get_title(
        page,
        item,
    )

    price = extract_price(
        main_text
    )

    if price is None:
        price = item.get(
            "price_chf"
        )

    location = (
        extract_location(
            main_text
        )
    )

    size_m2 = extract_size(
        main_text
    )

    rooms = extract_rooms(
        main_text
    )

    bedrooms = extract_bedrooms(
        main_text
    )

    bathrooms = extract_bathrooms(
        main_text
    )

    floor = extract_floor(
        main_text
    )

    availability = (
        extract_availability(
            main_text
        )
    )

    description_data = (
        extract_description(
            main_text
        )
    )

    description = (
        description_data[
            "description"
        ]
    )

    restrictions = (
        extract_restrictions(
            main_text
        )
    )

    equipments = (
        extract_equipments(
            main_text
        )
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

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    return {
        "source":
            "immobilier.ch",

        "source_section":
            "lausanne",

        "source_id":
            get_source_id(
                url
            ),

        "source_url":
            url,

        "title":
            title,

        "description_title":
            description_data[
                "description_title"
            ],

        "price": {
            "monthly":
                price,

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

            #
            # Le coordinate verranno aggiunte
            # dal geocoder swisstopo.
            #
            "latitude":
                None,

            "longitude":
                None,

            "precision":
                None,
        },

        "property": {
            "type":
                infer_property_type(
                    title,
                    main_text,
                ),

            "rooms":
                rooms,

            "bedrooms":
                bedrooms,

            "bathrooms":
                bathrooms,

            "size_m2":
                size_m2,

            "floor":
                floor,

            "furnished":
                extract_furnished(
                    main_text
                ),
        },

        "contract": {
            "type":
                None,

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
            restrictions,

        "description":
            description,

        "equipments":
            equipments,

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

                status = (
                    response.status
                    if response
                    else None
                )

                print(
                    "  HTTP:",
                    status,
                )

                #
                # Aspettiamo che appaia il
                # contenuto dell'annuncio.
                #
                try:
                    page.locator(
                        "body"
                    ).wait_for(
                        state="visible",
                        timeout=10000,
                    )

                except Exception:
                    pass

                page.wait_for_timeout(
                    WAIT_MS
                )

                body_text = (
                    page.locator(
                        "body"
                    ).inner_text()
                )

                if (
                    "Just a moment"
                    in page.title()
                    or
                    "checking your browser"
                    in body_text.lower()
                ):
                    raise RuntimeError(
                        "Anti-bot challenge detected"
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
                    "  City:",
                    listing[
                        "location"
                    ][
                        "city"
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
                    "  Size:",
                    listing[
                        "property"
                    ][
                        "size_m2"
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

                #
                # Salva il contenuto solo
                # quando qualcosa fallisce.
                #
                try:
                    source_id = (
                        get_source_id(
                            url
                        )
                        or str(index)
                    )

                    debug_file = (
                        DEBUG_DIR
                        / (
                            f"{source_id}.html"
                        )
                    )

                    debug_file.write_text(
                        page.content(),
                        encoding="utf-8",
                    )

                except Exception:
                    pass

            time.sleep(
                0.2
            )

        browser.close()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source":
            "immobilier.ch",

        "source_section":
            "lausanne",

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

    with_rooms = sum(
        x["property"].get(
            "rooms"
        )
        is not None
        for x in processed
    )

    with_size = sum(
        x["property"].get(
            "size_m2"
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
    print(
        "======================"
    )

    print(
        "IMMOBILIER.CH DETAILS"
    )

    print(
        "======================"
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
        "With rooms:",
        with_rooms,
    )

    print(
        "With size:",
        with_size,
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