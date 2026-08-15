import json
import re
import time
from pathlib import Path

import requests


INPUT_FILE = Path(
    "data/processed/flatfox-lausanne-listings.json"
)

OUTPUT_FILE = Path(
    "data/geocoded/flatfox-lausanne-listings-geocoded.json"
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
    """
    Costruisce le query dal dato più preciso
    al meno preciso.

    IMPORTANTE:
    expected_precision rappresenta la precisione
    realmente conosciuta dall'annuncio Flatfox,
    non il tipo di risultato restituito dal geocoder.
    """

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
    # Caso migliore:
    # Flatfox ci ha fornito strada + CAP + città.
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
        # Variante senza virgola.
        #
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
    # Se non abbiamo indirizzo completo,
    # possiamo comunque localizzare
    # CAP + città.
    #
    if (
        postal_code
        and city
    ):
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
    # Fallback: solo CAP.
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
    # Ultimo fallback: solo città.
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
    # Elimina eventuali query duplicate.
    #
    unique = []
    seen = set()


    for item in queries:

        key = (
            item[
                "query"
            ],
            item[
                "origins"
            ],
        )

        if key in seen:
            continue

        seen.add(
            key
        )

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


    #
    # Riutilizza le risposte già scaricate.
    #
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
    """
    Assegna un punteggio ai risultati di swisstopo.

    Un risultato di tipo "address" riceve
    un bonus forte SOLO se l'annuncio Flatfox
    contiene realmente un indirizzo.

    Questo evita di trasformare:
        1018 Lausanne
    in un falso indirizzo preciso.
    """

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
    # Un risultato address è molto utile
    # solamente quando Flatfox ci ha fornito
    # davvero una strada.
    #
    if (
        origin == "address"
        and address
    ):
        score += 100


    #
    # CAP.
    #
    if postal_code:

        if postal_code in combined:
            score += 40

        else:
            score -= 20


    #
    # Città.
    #
    if city:

        city_parts = [
            part
            for part in re.split(
                r"[\s\-/]+",
                city,
            )
            if len(part) >= 3
        ]


        for part in city_parts:

            if part in combined:
                score += 10


    #
    # Indirizzo.
    #
    if address:

        address_parts = [
            part
            for part in re.split(
                r"[\s,.'’\-/]+",
                address,
            )
            if len(part) >= 2
        ]


        for part in address_parts:

            if part in combined:
                score += 5


        #
        # Numero civico.
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
    # Ranking aggiuntivo restituito
    # dal SearchServer.
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
    candidates = []


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


        score = score_result(
            result,
            location,
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


def result_to_location(
    chosen,
    query_info,
):
    """
    ATTENZIONE:

    La precisione NON viene più derivata
    automaticamente da attrs["origin"].

    Se abbiamo cercato soltanto:
        1018 Lausanne

    e swisstopo restituisce accidentalmente
    un singolo indirizzo come primo risultato,
    la precisione resta:

        postal_code_city

    Solo una query costruita da un vero
    indirizzo Flatfox può produrre:

        address
    """

    score, result = chosen


    attrs = result.get(
        "attrs",
        {}
    )


    origin = attrs.get(
        "origin"
    )


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
            response = search_location(
                session,
                query_info[
                    "query"
                ],
                query_info[
                    "origins"
                ],
                cache,
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


        geocoded = result_to_location(
            chosen,
            query_info,
        )


        #
        # Se stiamo tentando una vera query
        # di indirizzo, richiediamo che anche
        # swisstopo abbia trovato un risultato
        # di tipo address.
        #
        if (
            query_info[
                "expected_precision"
            ]
            == "address"
            and
            geocoded[
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


        address = location.get(
            "address"
        )

        postal_code = location.get(
            "postal_code"
        )

        city = location.get(
            "city"
        )


        print(
            "  Input:",
            address,
            "|",
            postal_code,
            city,
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
                "  Query:",
                result[
                    "geocoder"
                ][
                    "query"
                ],
            )


            print(
                "  Origin:",
                result[
                    "geocoder"
                ][
                    "origin"
                ],
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
            "flatfox",

        "source_section":
            "lausanne_shared",

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
        "FLATFOX GEOCODING"
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