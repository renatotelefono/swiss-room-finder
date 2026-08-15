import json
import re
import time
import unicodedata
from pathlib import Path

import requests


INPUT_FILE = Path(
    "data/geocoded/flatfox-lausanne-listings-geocoded.json"
)

OUTPUT_FILE = Path(
    "data/geocoded/flatfox-lausanne-listings-geocoded.json"
)

BACKUP_FILE = Path(
    "data/geocoded/flatfox-lausanne-listings-geocoded-before-fix.json"
)

CACHE_FILE = Path(
    "data/geocoded/flatfox-geocoding-cache.json"
)


SEARCH_URL = (
    "https://api3.geo.admin.ch/"
    "rest/services/ech/SearchServer"
)


WAIT_SECONDS = 0.25


HEADERS = {
    "User-Agent": (
        "SwissRoomFinder/1.0 "
        "(personal project)"
    ),
}


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


def strip_html(value):
    if not value:
        return ""

    value = re.sub(
        r"<[^>]+>",
        "",
        str(value),
    )

    return clean(value)


def load_cache():
    if not CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(
            CACHE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data,
            dict,
        ):
            return data

    except Exception:
        pass

    return {}


def save_cache(cache):
    CACHE_FILE.write_text(
        json.dumps(
            cache,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def extract_input_house_number(
    address,
):
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


def extract_match_house_number(
    label,
):
    if not label:
        return None

    text = clean(
        label
    )

    #
    # Elimina CAP e tutto ciò che segue.
    #
    match = re.search(
        r"^(.*?)\s+\d{4}\b",
        text,
    )

    if match:
        text = match.group(1)

    numbers = re.findall(
        r"\b"
        r"\d+"
        r"(?:\.\d+)?"
        r"[A-Za-z]?"
        r"\b",
        text,
    )

    if not numbers:
        return None

    return (
        numbers[-1]
        .lower()
    )


def street_words(
    address,
):
    if not address:
        return set()

    value = normalize(
        address
    )

    value = (
        value
        .replace(
            "chem.",
            "chemin",
        )
        .replace(
            "av.",
            "avenue",
        )
        .replace(
            "rte.",
            "route",
        )
    )

    value = re.sub(
        r"\b"
        r"\d+"
        r"(?:\.\d+)?"
        r"[a-z]?"
        r"\b",
        " ",
        value,
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
        for word in re.findall(
            r"[a-z]{2,}",
            value,
        )
        if word not in ignored
    }


def is_exact_address_match(
    location,
):
    """
    Un punto resta "address" soltanto se:

    1. l'annuncio contiene un civico;
    2. swisstopo restituisce lo stesso civico;
    3. la strada coincide sufficientemente.

    Varianti tipo:
        49 -> 49d
        72b -> 72

    vengono volutamente considerate
    non esatte.
    """

    address = clean(
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

    label = clean(
        geocoder.get(
            "label"
        )
    )

    input_number = (
        extract_input_house_number(
            address
        )
    )

    match_number = (
        extract_match_house_number(
            label
        )
    )


    if (
        not input_number
        or not match_number
    ):
        return False


    if (
        input_number.lower()
        != match_number.lower()
    ):
        return False


    source_words = street_words(
        address
    )

    match_words = street_words(
        label
    )


    if not source_words:
        return False


    overlap = (
        len(
            source_words
            & match_words
        )
        /
        len(
            source_words
        )
    )


    return overlap >= 0.5


def search_postal_city(
    session,
    postal_code,
    city,
    cache,
):
    query = (
        f"{postal_code} "
        f"{city}"
    )

    cache_key = json.dumps(
        {
            "query":
                query,

            "origins":
                None,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


    if cache_key in cache:
        return (
            query,
            cache[
                cache_key
            ]
        )


    params = {
        "searchText":
            query,

        "type":
            "locations",

        "limit":
            10,

        "returnGeometry":
            "true",
    }


    response = session.get(
        SEARCH_URL,
        params=params,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()


    cache[
        cache_key
    ] = data


    save_cache(
        cache
    )


    time.sleep(
        WAIT_SECONDS
    )


    return (
        query,
        data,
    )


def score_postal_city_result(
    result,
    postal_code,
    city,
):
    attrs = result.get(
        "attrs",
        {}
    )

    label = (
        strip_html(
            attrs.get(
                "label"
            )
        )
        or ""
    ).lower()

    detail = (
        clean(
            attrs.get(
                "detail"
            )
        )
        or ""
    ).lower()

    combined = (
        f"{label} {detail}"
    )

    score = 0


    if (
        postal_code
        and postal_code
        in combined
    ):
        score += 100


    city_parts = [
        part
        for part in re.split(
            r"[\s\-/]+",
            normalize(
                city
            ),
        )
        if len(part) >= 3
    ]


    normalized_combined = (
        normalize(
            combined
        )
    )


    for part in city_parts:

        if part in normalized_combined:
            score += 20


    origin = attrs.get(
        "origin"
    )


    #
    # Per una posizione approssimativa
    # preferiamo CAP/parcella rispetto
    # a un indirizzo arbitrario.
    #
    if origin == "zipcode":
        score += 30

    elif origin == "parcel":
        score += 20

    elif origin == "address":
        score -= 5


    return score


def choose_postal_city_result(
    data,
    postal_code,
    city,
):
    candidates = []


    for result in data.get(
        "results",
        []
    ):

        attrs = result.get(
            "attrs",
            {}
        )

        latitude = attrs.get(
            "lat"
        )

        longitude = attrs.get(
            "lon"
        )


        if (
            latitude is None
            or longitude is None
        ):
            continue


        score = (
            score_postal_city_result(
                result,
                postal_code,
                city,
            )
        )


        candidates.append(
            (
                score,
                result,
            )
        )


    if not candidates:
        return None


    candidates.sort(
        key=lambda item:
            item[0],
        reverse=True,
    )


    return candidates[0]


def fallback_to_postal_city(
    session,
    location,
    cache,
):
    postal_code = clean(
        location.get(
            "postal_code"
        )
    )

    city = clean(
        location.get(
            "city"
        )
    )


    if (
        not postal_code
        or not city
    ):
        return False


    query, data = (
        search_postal_city(
            session,
            postal_code,
            city,
            cache,
        )
    )


    chosen = (
        choose_postal_city_result(
            data,
            postal_code,
            city,
        )
    )


    if chosen is None:
        return False


    score, result = chosen


    attrs = result.get(
        "attrs",
        {}
    )


    location[
        "latitude"
    ] = attrs.get(
        "lat"
    )


    location[
        "longitude"
    ] = attrs.get(
        "lon"
    )


    location[
        "precision"
    ] = "postal_code_city"


    location[
        "geocoding_status"
    ] = "success"


    location[
        "geocoder"
    ] = {
        "provider":
            "geo.admin.ch",

        "origin":
            attrs.get(
                "origin"
            ),

        "label":
            strip_html(
                attrs.get(
                    "label"
                )
            ),

        "detail":
            clean(
                attrs.get(
                    "detail"
                )
            ),

        "query":
            query,

        "score":
            round(
                score,
                2,
            ),
    }


    flags = location.setdefault(
        "quality_flags",
        []
    )


    if (
        "address_match_downgraded"
        not in flags
    ):
        flags.append(
            "address_match_downgraded"
        )


    return True


def main():
    data = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )


    #
    # Salva una copia del dataset
    # prima della correzione.
    #
    BACKUP_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


    listings = data.get(
        "listings",
        []
    )


    cache = load_cache()

    session = requests.Session()


    exact_count = 0
    already_approximate = 0
    downgraded_count = 0
    fallback_failed = 0


    print()
    print(
        "======================"
    )

    print(
        "FIX FLATFOX GEOCODING"
    )

    print(
        "======================"
    )


    for index, listing in enumerate(
        listings,
        start=1,
    ):

        location = listing.get(
            "location",
            {}
        )


        precision = location.get(
            "precision"
        )


        if precision != "address":

            already_approximate += 1
            continue


        if is_exact_address_match(
            location
        ):

            exact_count += 1
            continue


        print()
        print(
            f"[{index}] DOWNGRADE"
        )

        print(
            "  Address:",
            location.get(
                "address"
            ),
        )

        print(
            "  Old match:",
            (
                location.get(
                    "geocoder"
                )
                or {}
            ).get(
                "label"
            ),
        )


        try:
            success = (
                fallback_to_postal_city(
                    session,
                    location,
                    cache,
                )
            )

        except Exception as exc:

            print(
                "  ERROR:",
                repr(exc),
            )

            success = False


        if success:

            downgraded_count += 1

            print(
                "  New precision:",
                location[
                    "precision"
                ],
            )

            print(
                "  New match:",
                location[
                    "geocoder"
                ][
                    "label"
                ],
            )

        else:

            fallback_failed += 1

            #
            # Anche in caso di errore non
            # lasciamo il punto marcato come
            # preciso.
            #
            location[
                "precision"
            ] = "postal_code_city"

            print(
                "  Fallback FAILED"
            )


    #
    # Ricalcola il riepilogo.
    #
    precision_counts = {}


    for listing in listings:

        precision = (
            listing.get(
                "location",
                {}
            ).get(
                "precision"
            )
            or "unknown"
        )


        precision_counts[
            precision
        ] = (
            precision_counts.get(
                precision,
                0,
            )
            + 1
        )


    data[
        "precision"
    ] = precision_counts


    OUTPUT_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


    save_cache(
        cache
    )


    print()
    print(
        "======================"
    )

    print(
        "RESULT"
    )

    print(
        "======================"
    )


    print(
        "Exact addresses kept:",
        exact_count,
    )


    print(
        "Already approximate:",
        already_approximate,
    )


    print(
        "Downgraded:",
        downgraded_count,
    )


    print(
        "Fallback failed:",
        fallback_failed,
    )


    print()
    print(
        "Final precision:"
    )


    for precision, count in sorted(
        precision_counts.items()
    ):

        print(
            f"  {precision}: "
            f"{count}"
        )


    print()
    print(
        "Saved:",
        OUTPUT_FILE,
    )


    print(
        "Backup:",
        BACKUP_FILE,
    )


if __name__ == "__main__":
    main()