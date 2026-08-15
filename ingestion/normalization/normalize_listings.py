import json
import re
from pathlib import Path


INPUT_FILE = Path(
    "data/processed/ronorp-listings.json"
)

OUTPUT_FILE = Path(
    "data/normalized/ronorp-listings-normalized.json"
)

EXCLUDED_FILE = Path(
    "data/normalized/ronorp-listings-excluded.json"
)


def clean(value):
    if value is None:
        return None

    value = " ".join(
        str(value).split()
    )

    if value in {
        "",
        "--",
        "\\--",
    }:
        return None

    return value


def combined_text(listing):
    parts = [
        listing.get("title"),
        listing.get("description"),
        listing.get("description_raw"),
    ]

    return " ".join(
        clean(x) or ""
        for x in parts
    ).lower()


def is_wanted_listing(listing):
    """
    Individua annunci di persone che cercano casa,
    invece di offrire una camera/appartamento.
    """

    offer_type = (
        listing.get("offer_type")
        or ""
    ).lower()

    if offer_type in {
        "wanted",
        "suche",
    }:
        return True

    text = combined_text(listing)

    patterns = [
        "looking for apartment",
        "looking for a room",
        "looking for room",
        "looking for wg",
        "looking for flat",
        "looking for studio",
        "looking for 1 room",
        "searching for apartment",
        "searching for a room",
        "suche eine wohnung",
        "suche ein zimmer",
        "suche wg",
        "cherche appartement",
        "cherche une chambre",
        "cerco appartamento",
        "cerco una camera",
    ]

    return any(
        pattern in text
        for pattern in patterns
    )


def is_foreign_listing(listing):
    """
    Per ora individuiamo casi chiaramente fuori
    dalla Svizzera.
    """

    location = listing.get(
        "location",
        {},
    )

    location_text = " ".join(
        [
            clean(
                location.get("address")
            ) or "",
            clean(
                location.get("city")
            ) or "",
            combined_text(listing),
        ]
    ).lower()

    foreign_markers = [
        "españa",
        "spain",
        "italia",
        "italy",
        "france",
        "deutschland",
        "germany",
        "österreich",
        "austria",
    ]

    return any(
        marker in location_text
        for marker in foreign_markers
    )


def normalize_full_address(listing):
    """
    Alcuni annunci hanno l'indirizzo completo
    erroneamente salvato dentro location.city.

    Esempio:
    Badenerstrasse 356, 8004 Zürich
    """

    location = listing[
        "location"
    ]

    city = clean(
        location.get("city")
    )

    if not city:
        return

    match = re.match(
        r"^(.+?),\s*(\d{4})\s+(.+)$",
        city,
    )

    if not match:
        return

    address = clean(
        match.group(1)
    )

    postal_code = clean(
        match.group(2)
    )

    real_city = clean(
        match.group(3)
    )

    location["address"] = (
        address
    )

    location["postal_code"] = (
        postal_code
    )

    location["city"] = (
        real_city
    )

    location["precision"] = (
        "address"
    )


def infer_zurich_from_title(listing):
    """
    Se manca la città ma il titolo indica
    chiaramente Zürich / Zurich / Kreis,
    impostiamo Zürich.
    """

    location = listing[
        "location"
    ]

    if clean(
        location.get("city")
    ):
        return

    title = (
        listing.get("title")
        or ""
    ).lower()

    indicators = [
        "zürich",
        "zurich",
        "kreis 1",
        "kreis 2",
        "kreis 3",
        "kreis 4",
        "kreis 5",
        "kreis 6",
        "kreis 7",
        "kreis 8",
        "kreis 9",
        "kreis 10",
        "kreis 11",
        "kreis 12",
    ]

    if any(
        indicator in title
        for indicator in indicators
    ):
        location["city"] = (
            "Zürich"
        )


def normalize_size(listing):
    """
    Corregge superfici chiaramente impossibili.

    Esempio reale:
    titolo = 370 m² apartment...
    parser = 4000 m²
    """

    property_data = listing[
        "property"
    ]

    size = property_data.get(
        "size_m2"
    )

    if (
        size is None
        or size <= 1000
    ):
        return

    title = (
        listing.get("title")
        or ""
    )

    match = re.search(
        r"\b(\d{2,4})\s*m[²2]\b",
        title,
        re.IGNORECASE,
    )

    if match:
        title_size = float(
            match.group(1)
        )

        if (
            5
            <= title_size
            <= 1000
        ):
            property_data[
                "size_m2"
            ] = title_size


def normalize_country(listing):
    location = listing[
        "location"
    ]

    # Per il dataset valido lavoriamo
    # solamente sulla Svizzera.
    location["country"] = "CH"


def add_quality_flags(listing):
    location = listing[
        "location"
    ]

    flags = []

    if not clean(
        location.get(
            "postal_code"
        )
    ):
        flags.append(
            "missing_postal_code"
        )

    if not clean(
        location.get(
            "city"
        )
    ):
        flags.append(
            "missing_city"
        )

    if not clean(
        location.get(
            "address"
        )
    ):
        flags.append(
            "missing_address"
        )

    if (
        listing[
            "contract"
        ].get(
            "available_from"
        )
        is None
    ):
        flags.append(
            "missing_availability"
        )

    if (
        listing[
            "property"
        ].get(
            "size_m2"
        )
        is None
    ):
        flags.append(
            "missing_size"
        )

    listing[
        "quality_flags"
    ] = flags


def main():
    source = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    listings = source[
        "listings"
    ]

    normalized = []
    excluded = []

    for listing in listings:

        #
        # Non modifichiamo accidentalmente
        # l'oggetto originale.
        #
        listing = json.loads(
            json.dumps(listing)
        )

        if is_wanted_listing(
            listing
        ):
            listing[
                "excluded_reason"
            ] = "wanted_listing"

            excluded.append(
                listing
            )

            continue

        if is_foreign_listing(
            listing
        ):
            listing[
                "excluded_reason"
            ] = "outside_switzerland"

            excluded.append(
                listing
            )

            continue

        normalize_full_address(
            listing
        )

        infer_zurich_from_title(
            listing
        )

        normalize_size(
            listing
        )

        normalize_country(
            listing
        )

        add_quality_flags(
            listing
        )

        normalized.append(
            listing
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    normalized_output = {
        "source": "ronorp",
        "input_count": len(
            listings
        ),
        "count": len(
            normalized
        ),
        "listings": normalized,
    }

    excluded_output = {
        "source": "ronorp",
        "count": len(
            excluded
        ),
        "listings": excluded,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            normalized_output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    EXCLUDED_FILE.write_text(
        json.dumps(
            excluded_output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "Input:",
        len(listings),
    )

    print(
        "Normalized:",
        len(normalized),
    )

    print(
        "Excluded:",
        len(excluded),
    )

    print()

    reasons = {}

    for listing in excluded:

        reason = listing[
            "excluded_reason"
        ]

        reasons[reason] = (
            reasons.get(
                reason,
                0,
            )
            + 1
        )

    print(
        "Excluded reasons:"
    )

    for reason, count in reasons.items():
        print(
            f"  {reason}: {count}"
        )

    print()

    missing_city = sum(
        not x["location"].get(
            "city"
        )
        for x in normalized
    )

    missing_postal = sum(
        not x["location"].get(
            "postal_code"
        )
        for x in normalized
    )

    missing_address = sum(
        not x["location"].get(
            "address"
        )
        for x in normalized
    )

    print(
        "Missing city:",
        missing_city,
    )

    print(
        "Missing postal code:",
        missing_postal,
    )

    print(
        "Missing address:",
        missing_address,
    )

    print()

    print(
        "Saved:",
        OUTPUT_FILE,
    )

    print(
        "Excluded saved:",
        EXCLUDED_FILE,
    )


if __name__ == "__main__":
    main()