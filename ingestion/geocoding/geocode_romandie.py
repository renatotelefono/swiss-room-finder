import json
import time
from pathlib import Path

import requests


INPUT_FILE = Path(
    "data/normalized/ronorp-romandie-listings-normalized.json"
)

OUTPUT_FILE = Path(
    "data/geocoded/ronorp-romandie-listings-geocoded.json"
)

# Riutilizziamo la stessa cache usata per Zurigo.
# Se una località è già stata cercata, non rifacciamo
# inutilmente la richiesta.
CACHE_FILE = Path(
    "data/geocoded/geocoding-cache.json"
)


SEARCH_URL = (
    "https://api3.geo.admin.ch/"
    "rest/services/ech/SearchServer"
)


def load_json(path, default):
    if not path.exists():
        return default

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
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


def build_queries(listing):
    """
    Genera query dalla più precisa
    alla meno precisa.
    """

    location = listing.get(
        "location",
        {},
    )

    address = clean(
        location.get("address")
    )

    postal_code = clean(
        location.get("postal_code")
    )

    city = clean(
        location.get("city")
    )

    queries = []


    #
    # 1. Indirizzo completo
    #
    if (
        address
        and postal_code
        and city
    ):
        queries.append(
            {
                "text":
                    f"{address}, "
                    f"{postal_code} "
                    f"{city}",

                "requested_precision":
                    "address",
            }
        )


    #
    # 2. CAP + città
    #
    if (
        postal_code
        and city
    ):
        queries.append(
            {
                "text":
                    f"{postal_code} "
                    f"{city}",

                "requested_precision":
                    "postal_code_city",
            }
        )


    #
    # 3. Solo CAP
    #
    if postal_code:
        queries.append(
            {
                "text":
                    postal_code,

                "requested_precision":
                    "postal_code",
            }
        )


    #
    # 4. Solo città
    #
    if city:
        queries.append(
            {
                "text":
                    city,

                "requested_precision":
                    "city",
            }
        )


    #
    # Elimina duplicati
    #
    unique = []
    seen = set()

    for query in queries:
        key = (
            query["text"]
            .strip()
            .lower()
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            query
        )

    return unique


def search_location(query_text):
    params = {
        "searchText":
            query_text,

        "type":
            "locations",

        "sr":
            4326,

        "limit":
            10,

        "returnGeometry":
            "true",
    }

    response = requests.get(
        SEARCH_URL,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def score_result(
    result,
    listing,
    requested_precision,
):
    attrs = result.get(
        "attrs",
        {},
    )

    origin = (
        attrs.get("origin")
        or ""
    ).lower()

    detail = (
        attrs.get("detail")
        or ""
    ).lower()

    location = listing.get(
        "location",
        {},
    )

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

    address = (
        clean(
            location.get(
                "address"
            )
        )
        or ""
    ).lower()


    score = 0


    #
    # Tipo di risultato
    #
    if (
        requested_precision
        == "address"
        and origin == "address"
    ):
        score += 100


    if (
        requested_precision
        in {
            "postal_code_city",
            "postal_code",
        }
        and origin == "zipcode"
    ):
        score += 80


    if (
        requested_precision
        == "city"
        and origin in {
            "gg25",
            "gazetteer",
        }
    ):
        score += 60


    #
    # CAP coerente
    #
    if (
        postal_code
        and postal_code in detail
    ):
        score += 50


    #
    # Città coerente
    #
    if (
        city
        and city in detail
    ):
        score += 50


    #
    # Indirizzo coerente
    #
    if (
        address
        and address in detail
    ):
        score += 100


    #
    # Peso restituito dal geocoder
    #
    weight = result.get(
        "weight"
    )

    if isinstance(
        weight,
        (int, float),
    ):
        if weight == 100:
            score += 20

        elif weight > 0:
            score += 10


    return score


def choose_result(
    response,
    listing,
    requested_precision,
):
    results = response.get(
        "results",
        [],
    )

    if not results:
        return None


    scored = []


    for result in results:
        attrs = result.get(
            "attrs",
            {},
        )

        lat = attrs.get(
            "lat"
        )

        lon = attrs.get(
            "lon"
        )


        if (
            lat is None
            or lon is None
        ):
            continue


        score = score_result(
            result,
            listing,
            requested_precision,
        )


        scored.append(
            (
                score,
                result,
            )
        )


    if not scored:
        return None


    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )


    best_score, best_result = (
        scored[0]
    )


    if best_score <= 0:
        return None


    return best_result


def geocode_listing(
    listing,
    cache,
):
    queries = build_queries(
        listing
    )


    for query in queries:
        query_text = (
            query["text"]
        )

        requested_precision = (
            query[
                "requested_precision"
            ]
        )


        cache_key = (
            query_text
            .strip()
            .lower()
        )


        print(
            "    Query:",
            query_text,
        )


        if cache_key in cache:
            response = (
                cache[
                    cache_key
                ]
            )

            print(
                "      cache"
            )

        else:
            try:
                response = (
                    search_location(
                        query_text
                    )
                )

                cache[
                    cache_key
                ] = response


                #
                # Piccola pausa tra le richieste.
                #
                time.sleep(
                    0.4
                )

            except Exception as exc:
                print(
                    "      ERROR:",
                    repr(exc),
                )

                continue


        result = choose_result(
            response,
            listing,
            requested_precision,
        )


        if result is None:
            continue


        attrs = result.get(
            "attrs",
            {},
        )


        return {
            "latitude":
                attrs.get("lat"),

            "longitude":
                attrs.get("lon"),

            "precision":
                requested_precision,

            "geocoder_origin":
                attrs.get(
                    "origin"
                ),

            "geocoder_label":
                attrs.get(
                    "label"
                ),

            "geocoder_detail":
                attrs.get(
                    "detail"
                ),

            "geocoder_query":
                query_text,
        }


    return None


def main():
    source = load_json(
        INPUT_FILE,
        {},
    )


    listings = source.get(
        "listings",
        [],
    )


    cache = load_json(
        CACHE_FILE,
        {},
    )


    success = 0
    failed = 0

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
            f"[{index}/{total}] "
            f"{listing.get('title', '')[:90]}"
        )


        result = geocode_listing(
            listing,
            cache,
        )


        location = listing.setdefault(
            "location",
            {},
        )


        if result is None:
            failed += 1

            location[
                "geocoding_status"
            ] = "failed"

            print(
                "    NOT FOUND"
            )

        else:
            success += 1


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
                "geocoder_origin"
            ] = result[
                "geocoder_origin"
            ]


            location[
                "geocoder_label"
            ] = result[
                "geocoder_label"
            ]


            location[
                "geocoder_detail"
            ] = result[
                "geocoder_detail"
            ]


            location[
                "geocoder_query"
            ] = result[
                "geocoder_query"
            ]


            location[
                "geocoding_status"
            ] = "ok"


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
                "    OK:",
                result[
                    "latitude"
                ],
                result[
                    "longitude"
                ],
            )


            print(
                "    Precision:",
                precision,
            )


        #
        # Salvataggio cache periodico
        #
        if index % 10 == 0:
            save_json(
                CACHE_FILE,
                cache,
            )


    save_json(
        CACHE_FILE,
        cache,
    )


    output = {
        "source":
            "ronorp",

        "source_section":
            "romandie",

        "input_count":
            total,

        "geocoded":
            success,

        "failed":
            failed,

        "precision":
            precision_counts,

        "listings":
            listings,
    }


    save_json(
        OUTPUT_FILE,
        output,
    )


    print()
    print(
        "----------------------"
    )

    print(
        "ROMANDIE GEOCODING"
    )

    print(
        "----------------------"
    )


    print(
        "Input:",
        total,
    )

    print(
        "Geocoded:",
        success,
    )

    print(
        "Failed:",
        failed,
    )


    print()
    print(
        "Precision:"
    )


    for precision, count in sorted(
        precision_counts.items()
    ):
        print(
            f"  {precision}: {count}"
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