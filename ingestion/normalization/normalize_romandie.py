import json
import re
from pathlib import Path


INPUT_FILE = Path(
    "data/processed/ronorp-romandie-listings.json"
)

OUTPUT_FILE = Path(
    "data/normalized/ronorp-romandie-listings-normalized.json"
)

EXCLUDED_FILE = Path(
    "data/normalized/ronorp-romandie-listings-excluded.json"
)


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


def combined_text(listing):
    return " ".join(
        [
            clean(
                listing.get("title")
            )
            or "",

            clean(
                listing.get("description")
            )
            or "",

            clean(
                listing.get("description_raw")
            )
            or "",
        ]
    ).lower()


def is_wanted_listing(listing):
    """
    Individua annunci di persone che cercano
    casa invece di offrire un alloggio.
    """

    offer_type = (
        listing.get("offer_type")
        or ""
    ).lower()

    if offer_type == "wanted":
        return True

    title = (
        listing.get("title")
        or ""
    ).lower()

    title_patterns = [
        "je cherche",
        "je recherche",
        "cherche appartement",
        "cherche une chambre",
        "cherche chambre",
        "recherche appartement",
        "recherche chambre",
        "looking for",
        "searching for",
        "suche wohnung",
        "suche zimmer",
        "suche wg",
    ]

    return any(
        pattern in title
        for pattern in title_patterns
    )


def normalize_full_address(listing):
    """
    Se il parser ha salvato un indirizzo completo
    dentro city, lo separa.

    Esempio:

    Rue Exemple 10, 1004 Lausanne

    diventa:

    address: Rue Exemple 10
    postal_code: 1004
    city: Lausanne
    """

    location = listing.get(
        "location",
        {}
    )

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

    location["address"] = clean(
        match.group(1)
    )

    location["postal_code"] = (
        match.group(2)
    )

    location["city"] = clean(
        match.group(3)
    )

    location["precision"] = (
        "address"
    )


def normalize_existing_address(listing):
    """
    Se address contiene anche CAP e città,
    prova a separare i tre elementi.
    """

    location = listing.get(
        "location",
        {}
    )

    address = clean(
        location.get("address")
    )

    if not address:
        return

    match = re.match(
        r"^(.+?),\s*(\d{4})\s+(.+)$",
        address,
    )

    if not match:
        return

    location["address"] = clean(
        match.group(1)
    )

    if not clean(
        location.get("postal_code")
    ):
        location["postal_code"] = (
            match.group(2)
        )

    if not clean(
        location.get("city")
    ):
        location["city"] = clean(
            match.group(3)
        )

    location["precision"] = (
        "address"
    )


def normalize_country(listing):
    location = listing.get(
        "location",
        {}
    )

    location["country"] = "CH"


def normalize_size(listing):
    """
    Se la superficie estratta è palesemente
    impossibile, prova a recuperarla dal titolo.

    Non inventa valori mancanti.
    """

    property_data = listing.get(
        "property",
        {}
    )

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
        flags=re.IGNORECASE,
    )

    if not match:
        property_data["size_m2"] = None
        return

    candidate = float(
        match.group(1)
    )

    if 5 <= candidate <= 1000:
        property_data["size_m2"] = (
            candidate
        )

    else:
        property_data["size_m2"] = None


def add_quality_flags(listing):
    location = listing.get(
        "location",
        {}
    )

    price = listing.get(
        "price",
        {}
    )

    property_data = listing.get(
        "property",
        {}
    )

    contract = listing.get(
        "contract",
        {}
    )

    flags = []

    if price.get(
        "monthly"
    ) is None:
        flags.append(
            "missing_price"
        )

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

    if property_data.get(
        "size_m2"
    ) is None:
        flags.append(
            "missing_size"
        )

    if contract.get(
        "available_from"
    ) is None:
        flags.append(
            "missing_availability"
        )

    if contract.get(
        "type"
    ) is None:
        flags.append(
            "missing_contract_type"
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

    listings = source.get(
        "listings",
        []
    )

    normalized = []
    excluded = []


    for listing in listings:

        #
        # Copia profonda semplice
        #
        listing = json.loads(
            json.dumps(
                listing,
                ensure_ascii=False,
            )
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


        normalize_full_address(
            listing
        )

        normalize_existing_address(
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


    output = {
        "source": "ronorp",

        "source_section":
            "romandie",

        "input_count":
            len(listings),

        "count":
            len(normalized),

        "listings":
            normalized,
    }


    excluded_output = {
        "source": "ronorp",

        "source_section":
            "romandie",

        "count":
            len(excluded),

        "listings":
            excluded,
    }


    OUTPUT_FILE.write_text(
        json.dumps(
            output,
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


    print()
    print(
        "----------------------"
    )

    print(
        "ROMANDIE NORMALIZATION"
    )

    print(
        "----------------------"
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
    print(
        "Excluded reasons:"
    )


    reasons = {}

    for listing in excluded:

        reason = listing.get(
            "excluded_reason",
            "unknown",
        )

        reasons[reason] = (
            reasons.get(
                reason,
                0,
            )
            + 1
        )


    for reason, count in reasons.items():
        print(
            f"  {reason}: {count}"
        )


    print()


    missing_price = sum(
        x["price"].get(
            "monthly"
        )
        is None

        for x in normalized
    )


    missing_city = sum(
        not clean(
            x["location"].get(
                "city"
            )
        )

        for x in normalized
    )


    missing_postal = sum(
        not clean(
            x["location"].get(
                "postal_code"
            )
        )

        for x in normalized
    )


    missing_address = sum(
        not clean(
            x["location"].get(
                "address"
            )
        )

        for x in normalized
    )


    missing_size = sum(
        x["property"].get(
            "size_m2"
        )
        is None

        for x in normalized
    )


    missing_availability = sum(
        x["contract"].get(
            "available_from"
        )
        is None

        for x in normalized
    )


    print(
        "Missing price:",
        missing_price,
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

    print(
        "Missing size:",
        missing_size,
    )

    print(
        "Missing availability:",
        missing_availability,
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