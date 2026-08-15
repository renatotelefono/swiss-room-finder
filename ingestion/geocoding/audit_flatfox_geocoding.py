import json
import re
import unicodedata
from pathlib import Path


INPUT_FILE = Path(
    "data/geocoded/flatfox-lausanne-listings-geocoded.json"
)


def clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )


def normalize(value):
    value = clean(
        value
    ).lower()

    value = (
        value
        .replace("’", "'")
        .replace("œ", "oe")
    )

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(
            char
        )
    )

    return value


def extract_house_number_from_address(
    address,
):
    """
    Estrae il numero civico dall'indirizzo
    originale Flatfox.

    Esempi:
        Rue de Lausanne 49       -> 49
        Avenue des Baumettes 72B -> 72b
        Avenue de Chailly 1      -> 1
    """

    if not address:
        return None

    matches = re.findall(
        r"\b"
        r"\d+"
        r"(?:\.\d+)?"
        r"[A-Za-z]?"
        r"\b",
        address,
    )

    if not matches:
        return None

    return (
        matches[-1]
        .lower()
    )


def extract_house_number_from_match(
    label,
):
    """
    Estrae il numero civico dal risultato
    swisstopo SENZA confonderlo con il CAP.

    Esempi:
        Chemin des Retraites 11 1004 Lausanne
        -> 11

        Rue de Lausanne 49d 1020 Renens VD
        -> 49d

        Avenue de Chailly 9.1 1012 Lausanne
        -> 9.1
    """

    if not label:
        return None

    text = clean(
        label
    )

    #
    # Rimuove CAP e tutto ciò che segue.
    #
    match = re.search(
        r"^(.*?)\s+\d{4}\b",
        text,
    )

    if match:
        before_postal = (
            match.group(1)
        )

    else:
        before_postal = text


    numbers = re.findall(
        r"\b"
        r"\d+"
        r"(?:\.\d+)?"
        r"[A-Za-z]?"
        r"\b",
        before_postal,
    )

    if not numbers:
        return None

    return (
        numbers[-1]
        .lower()
    )


def split_house_number(
    value,
):
    """
    Divide:

        72b  -> ("72", "b")
        49d  -> ("49", "d")
        9.1  -> ("9.1", "")
        11   -> ("11", "")
    """

    if not value:
        return (
            None,
            None,
        )

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)"
        r"([a-z]?)",
        value.lower(),
    )

    if not match:
        return (
            value.lower(),
            "",
        )

    return (
        match.group(1),
        match.group(2),
    )


def compare_house_numbers(
    input_number,
    match_number,
):
    """
    Restituisce:

        exact
        variant
        mismatch
        unknown

    "variant" significa che il numero principale
    coincide ma cambia/manca il suffisso.

    Esempio:
        72b vs 72
        49 vs 49d
    """

    if (
        not input_number
        or not match_number
    ):
        return "unknown"


    if (
        input_number.lower()
        == match_number.lower()
    ):
        return "exact"


    input_base, input_suffix = (
        split_house_number(
            input_number
        )
    )

    match_base, match_suffix = (
        split_house_number(
            match_number
        )
    )


    if (
        input_base
        == match_base
        and input_suffix
        != match_suffix
    ):
        return "variant"


    return "mismatch"


def extract_street_words(
    address,
):
    if not address:
        return set()


    value = normalize(
        address
    )


    #
    # Rimuove numeri civici.
    #
    value = re.sub(
        r"\b"
        r"\d+"
        r"(?:\.\d+)?"
        r"[a-z]?"
        r"\b",
        " ",
        value,
    )


    #
    # Abbreviazioni comuni.
    #
    replacements = {
        "chem.": "chemin",
        "chem ": "chemin ",
        "av.": "avenue",
        "av ": "avenue ",
        "rte.": "route",
        "rte ": "route ",
    }


    for old, new in replacements.items():
        value = value.replace(
            old,
            new,
        )


    ignored = {
        "de",
        "du",
        "des",
        "la",
        "le",
        "les",
        "l",
        "d",
        "rue",
        "route",
        "avenue",
        "chemin",
        "place",
        "allee",
        "boulevard",
    }


    return {
        word
        for word
        in re.findall(
            r"[a-z]{2,}",
            value,
        )
        if word
        not in ignored
    }


def main():
    data = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )


    listings = data.get(
        "listings",
        []
    )


    address_count = 0

    exact = []
    variants = []
    suspicious = []


    for listing in listings:

        location = listing.get(
            "location",
            {}
        )


        if (
            location.get(
                "precision"
            )
            != "address"
        ):
            continue


        address_count += 1


        input_address = clean(
            location.get(
                "address"
            )
        )


        geocoder = (
            location.get(
                "geocoder"
            )
            or {}
        )


        match_label = clean(
            geocoder.get(
                "label"
            )
        )


        input_number = (
            extract_house_number_from_address(
                input_address
            )
        )


        match_number = (
            extract_house_number_from_match(
                match_label
            )
        )


        number_status = (
            compare_house_numbers(
                input_number,
                match_number,
            )
        )


        input_words = (
            extract_street_words(
                input_address
            )
        )


        match_words = (
            extract_street_words(
                match_label
            )
        )


        if input_words:

            street_overlap = (
                len(
                    input_words
                    & match_words
                )
                /
                len(
                    input_words
                )
            )

        else:
            street_overlap = 1.0


        record = {
            "title":
                listing.get(
                    "title"
                ),

            "source_url":
                listing.get(
                    "source_url"
                ),

            "input_address":
                input_address,

            "postal_code":
                location.get(
                    "postal_code"
                ),

            "city":
                location.get(
                    "city"
                ),

            "match":
                match_label,

            "input_number":
                input_number,

            "match_number":
                match_number,

            "number_status":
                number_status,

            "street_overlap":
                street_overlap,
        }


        #
        # Mismatch vero:
        # 1 vs 9.1
        # 1 vs 13.1
        #
        if (
            number_status
            == "mismatch"
            or street_overlap < 0.5
        ):

            reasons = []


            if (
                number_status
                == "mismatch"
            ):
                reasons.append(
                    (
                        "house_number_mismatch: "
                        f"{input_number} "
                        f"!= "
                        f"{match_number}"
                    )
                )


            if street_overlap < 0.5:
                reasons.append(
                    (
                        "street_mismatch: "
                        f"overlap="
                        f"{street_overlap:.2f}"
                    )
                )


            record[
                "reasons"
            ] = reasons


            suspicious.append(
                record
            )


        #
        # Numero principale uguale,
        # ma suffisso diverso.
        #
        elif (
            number_status
            == "variant"
        ):

            variants.append(
                record
            )


        else:

            exact.append(
                record
            )


    print()
    print(
        "======================"
    )

    print(
        "FLATFOX GEOCODING AUDIT"
    )

    print(
        "======================"
    )


    print(
        "Address precision:",
        address_count,
    )


    print(
        "Exact matches:",
        len(
            exact
        ),
    )


    print(
        "House-number variants:",
        len(
            variants
        ),
    )


    print(
        "Suspicious:",
        len(
            suspicious
        ),
    )


    if variants:

        print()
        print(
            "HOUSE-NUMBER VARIANTS"
        )

        print(
            "----------------------"
        )


        for index, item in enumerate(
            variants,
            start=1,
        ):

            print()
            print(
                f"{index}."
            )

            print(
                "  Input:",
                item[
                    "input_address"
                ],
            )

            print(
                "  Match:",
                item[
                    "match"
                ],
            )

            print(
                "  Number:",
                (
                    f"{item['input_number']} "
                    f"vs "
                    f"{item['match_number']}"
                ),
            )

            print(
                "  URL:",
                item[
                    "source_url"
                ],
            )


    if suspicious:

        print()
        print(
            "SUSPICIOUS MATCHES"
        )

        print(
            "----------------------"
        )


        for index, item in enumerate(
            suspicious,
            start=1,
        ):

            print()
            print(
                f"{index}."
            )

            print(
                "  Input:",
                item[
                    "input_address"
                ],
                "|",
                item[
                    "postal_code"
                ],
                item[
                    "city"
                ],
            )


            print(
                "  Match:",
                item[
                    "match"
                ],
            )


            print(
                "  Number:",
                (
                    f"{item['input_number']} "
                    f"vs "
                    f"{item['match_number']}"
                ),
            )


            print(
                "  Reason:",
                "; ".join(
                    item[
                        "reasons"
                    ]
                ),
            )


            print(
                "  URL:",
                item[
                    "source_url"
                ],
            )


if __name__ == "__main__":
    main()