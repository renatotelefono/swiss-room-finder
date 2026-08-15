import json
import re
import time
from pathlib import Path

import requests


INPUT_FILE = Path(
    "data/processed/immobilier-lausanne-listings.json"
)

OUTPUT_FILE = Path(
    "data/geocoded/immobilier-lausanne-listings-geocoded.json"
)

CACHE_FILE = Path(
    "data/geocoded/immobilier-geocoding-cache.json"
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
        return None

    value = " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )

    return value or None


def strip_html(value):
    if not value:
        return None

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
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

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    CACHE_FILE.write_text(
        json.dumps(
            cache,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_queries(location):
    address = clean(
        location.get(
            "address"
        )
    )

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

    queries = []


    #
    # 1. Indirizzo completo:
    #    migliore possibilità di ottenere
    #    coordinate esatte.
    #
    if (
        address
        and postal_code
        and city
    ):
        queries.append(
            {
                "query":
                    f"{address}, "
                    f"{postal_code} "
                    f"{city}",

                "origins":
                    "address",

                "expected_precision":
                    "address",
            }
        )


    #
    # 2. Variante senza virgola.
    #
    if (
        address
        and postal_code
        and city
    ):
        queries.append(
            {
                "query":
                    f"{address} "
                    f"{postal_code} "
                    f"{city}",

                "origins":
                    "address",

                "expected_precision":
                    "address",
            }
        )


    #
    # 3. CAP + città.
    #
    if postal_code and city:
        queries.append(
            {
                "query":
                    f"{postal_code} "
                    f"{city}",

                "origins":
                    None,

                "expected_precision":
                    "postal_code_city",
            }
        )


    #
    # 4. Solo CAP.
    #
    if postal_code:
        queries.append(
            {
                "query":
                    postal_code,

                "origins":
                    "zipcode",

                "expected_precision":
                    "postal_code",
            }
        )


    #
    # 5. Solo città.
    #
    if city:
        queries.append(
            {
                "query":
                    city,

                "origins":
                    None,

                "expected_precision":
                    "city",
            }
        )


    #
    # Rimuove query duplicate.
    #
    unique = []

    seen = set()


    for item in queries:
        key = (
            item["query"],
            item["origins"],
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            item
        )


    return unique


def search_location(
    session,
    query,
    origins,
    cache,
):
    cache_key = json.dumps(
        {
            "query":
                query,

            "origins":
                origins,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


    if cache_key in cache:
        return cache[
            cache_key
        ]


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


    if origins:
        params[
            "origins"
        ] = origins


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


    return data


def score_result(
    result,
    location,
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


    address = (
        clean(
            location.get(
                "address"
            )
        )
        or ""
    ).lower()

    postal_code = (
        clean(
            location.get(
                "postal_code"
            )
        )
        or ""
    ).lower()

    city = (
        clean(
            location.get(
                "city"
            )
        )
        or ""
    ).lower()


    score = 0


    origin = attrs.get(
        "origin"
    )


    #
    # Un risultato proveniente dall'origine
    # address è fortemente preferito.
    #
    if origin == "address":
        score += 100


    if postal_code:
        if postal_code in combined:
            score += 40
        else:
            score -= 20


    if city:
        city_parts = [
            part
            for part
            in re.split(
                r"[\s\-/]+",
                city,
            )
            if len(part) >= 3
        ]

        matches = sum(
            part in combined
            for part
            in city_parts
        )

        score += (
            matches * 10
        )


    if address:
        #
        # Confrontiamo le parole significative
        # dell'indirizzo.
        #
        address_parts = [
            part
            for part
            in re.split(
                r"[\s,.'’\-/]+",
                address,
            )
            if len(part) >= 2
        ]


        for part in address_parts:
            if part in combined:
                score += 5


        #
        # Numero civico:
        # molto utile per scegliere
        # l'indirizzo corretto.
        #
        house_number_match = re.search(
            r"\b\d+[A-Za-z]?\b",
            address,
        )


        if house_number_match:
            house_number = (
                house_number_match
                .group(0)
                .lower()
            )


            if house_number in combined:
                score += 30


    #
    # Il SearchServer fornisce anche
    # un peso/ranking.
    #
    weight = result.get(
        "weight"
    )


    if isinstance(
        weight,
        (int, float),
    ):
        score += min(
            weight / 100,
            10,
        )


    return score


def choose_result(
    results,
    location,
):
    valid = []


    for result in results:
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


        valid.append(
            (
                score_result(
                    result,
                    location,
                ),
                result,
            )
        )


    if not valid:
        return None


    valid.sort(
        key=lambda item:
            item[0],
        reverse=True,
    )


    return valid[0]


def result_to_location(
    result,
    query_info,
):
    score, result_data = result


    attrs = result_data.get(
        "attrs",
        {}
    )


    origin = attrs.get(
        "origin"
    )


    #
    # Precisione reale.
    #
    if origin == "address":
        precision = "address"

    elif origin == "zipcode":
        precision = "postal_code"

    else:
        precision = (
            query_info[
                "expected_precision"
            ]
        )


    return {
        "latitude":
            attrs.get(
                "lat"
            ),

        "longitude":
            attrs.get(
                "lon"
            ),

        "precision":
            precision,

        "geocoder": {
            "provider":
                "geo.admin.ch",

            "origin":
                origin,

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
                query_info[
                    "query"
                ],

            "score":
                round(
                    score,
                    2,
                ),
        },
    }


def geocode_listing(
    session,
    listing,
    cache,
):
    location = listing.get(
        "location",
        {}
    )


    queries = build_queries(
        location
    )


    for query_info in queries:

        try:
            response = (
                search_location(
                    session,
                    query_info[
                        "query"
                    ],
                    query_info[
                        "origins"
                    ],
                    cache,
                )
            )

        except Exception as exc:
            print(
                "    Search error:",
                repr(exc),
            )

            continue


        results = response.get(
            "results",
            []
        )


        chosen = choose_result(
            results,
            location,
        )


        if chosen is None:
            continue


        geocoded = (
            result_to_location(
                chosen,
                query_info,
            )
        )


        #
        # Se stiamo cercando un indirizzo,
        # non accettiamo un risultato
        # completamente scollegato.
        #
        if (
            query_info[
                "expected_precision"
            ]
            == "address"
            and geocoded[
                "geocoder"
            ][
                "origin"
            ]
            != "address"
        ):
            continue


        return geocoded


    return None


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


    cache = load_cache()


    session = requests.Session()


    output_listings = []

    geocoded_count = 0

    failed_count = 0

    precision_counts = {}


    total = len(
        listings
    )


    for index, listing in enumerate(
        listings,
        start=1,
    ):

        print()
        print(
            f"[{index}/{total}]"
        )

        print(
            listing.get(
                "title"
            )
        )


        location = listing.setdefault(
            "location",
            {}
        )


        print(
            "  Input:",
            location.get(
                "address"
            ),
            "|",
            location.get(
                "postal_code"
            ),
            location.get(
                "city"
            ),
        )


        result = geocode_listing(
            session,
            listing,
            cache,
        )


        if result is None:

            failed_count += 1


            location[
                "geocoding_status"
            ] = "failed"


            print(
                "  Geocoding: FAILED"
            )


        else:

            geocoded_count += 1


            location[
                "latitude"
            ] = result[
                "latitude"
            ]


            location[
                "longitude"
            ] = result[
                "longitude"
            ]


            location[
                "precision"
            ] = result[
                "precision"
            ]


            location[
                "geocoding_status"
            ] = "success"


            location[
                "geocoder"
            ] = result[
                "geocoder"
            ]


            precision = result[
                "precision"
            ]


            precision_counts[
                precision
            ] = (
                precision_counts.get(
                    precision,
                    0,
                )
                + 1
            )


            print(
                "  Geocoding: SUCCESS"
            )

            print(
                "  Coordinates:",
                result[
                    "latitude"
                ],
                result[
                    "longitude"
                ],
            )

            print(
                "  Precision:",
                precision,
            )

            print(
                "  Match:",
                result[
                    "geocoder"
                ][
                    "label"
                ],
            )


        output_listings.append(
            listing
        )


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
            total,

        "geocoded":
            geocoded_count,

        "failed":
            failed_count,

        "precision":
            precision_counts,

        "listings":
            output_listings,
    }


    OUTPUT_FILE.write_text(
        json.dumps(
            output,
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
        "IMMOBILIER GEOCODING"
    )

    print(
        "======================"
    )

    print(
        "Input:",
        total,
    )

    print(
        "Geocoded:",
        geocoded_count,
    )

    print(
        "Failed:",
        failed_count,
    )


    print()
    print(
        "Precision:"
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
        "Cache:",
        CACHE_FILE,
    )


if __name__ == "__main__":
    main()