import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


INPUT_FILE = Path(
    "data/final/lausanne-listings.geojson"
)

OUTPUT_FILE = Path(
    "data/normalized/lausanne-duplicate-audit.json"
)


MIN_SCORE = 60
HIGH_SCORE = 85


def clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )


def normalize_text(value):
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

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def normalize_address(value):
    value = normalize_text(
        value
    )

    replacements = {
        " av ": " avenue ",
        " av. ": " avenue ",
        " chem ": " chemin ",
        " chem. ": " chemin ",
        " rte ": " route ",
        " rte. ": " route ",
        " bd ": " boulevard ",
    }

    padded = (
        f" {value} "
    )

    for old, new in replacements.items():

        padded = padded.replace(
            old,
            new,
        )

    return " ".join(
        padded.split()
    )


def normalize_city(value):
    value = normalize_text(
        value
    )

    replacements = {
        "lausanne vd":
            "lausanne",

        "renens vd":
            "renens",

        "ecublens vd":
            "ecublens",
    }

    return replacements.get(
        value,
        value,
    )


def as_float(value):
    try:

        if (
            value is None
            or value == ""
        ):
            return None

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def haversine_m(
    lat1,
    lon1,
    lat2,
    lon2,
):
    values = [
        lat1,
        lon1,
        lat2,
        lon2,
    ]

    if any(
        value is None
        for value in values
    ):
        return None


    radius = 6371008.8


    lat1 = math.radians(
        float(lat1)
    )

    lon1 = math.radians(
        float(lon1)
    )

    lat2 = math.radians(
        float(lat2)
    )

    lon2 = math.radians(
        float(lon2)
    )


    dlat = (
        lat2 - lat1
    )

    dlon = (
        lon2 - lon1
    )


    a = (
        math.sin(
            dlat / 2
        ) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(
            dlon / 2
        ) ** 2
    )


    return (
        radius
        *
        2
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )
    )


def text_similarity(
    a,
    b,
):
    a = normalize_text(
        a
    )

    b = normalize_text(
        b
    )


    if (
        not a
        or not b
    ):
        return None


    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def value_difference(
    a,
    b,
):
    a = as_float(
        a
    )

    b = as_float(
        b
    )


    if (
        a is None
        or b is None
    ):
        return None


    return abs(
        a - b
    )


def listing_summary(
    feature,
    index,
):
    props = (
        feature.get(
            "properties"
        )
        or {}
    )


    geometry = (
        feature.get(
            "geometry"
        )
        or {}
    )


    coordinates = (
        geometry.get(
            "coordinates"
        )
        or [
            None,
            None,
        ]
    )


    longitude = (
        coordinates[0]
        if len(
            coordinates
        ) >= 1
        else None
    )


    latitude = (
        coordinates[1]
        if len(
            coordinates
        ) >= 2
        else None
    )


    return {
        "index":
            index,

        "source":
            props.get(
                "source"
            ),

        "source_id":
            props.get(
                "source_id"
            ),

        "source_url":
            props.get(
                "source_url"
            ),

        "title":
            props.get(
                "title"
            ),

        "description_title":
            props.get(
                "description_title"
            ),

        "price_monthly":
            props.get(
                "price_monthly"
            ),

        "address":
            props.get(
                "address"
            ),

        "postal_code":
            props.get(
                "postal_code"
            ),

        "city":
            props.get(
                "city"
            ),

        "location_precision":
            props.get(
                "location_precision"
            ),

        "latitude":
            latitude,

        "longitude":
            longitude,

        "property_type":
            props.get(
                "property_type"
            ),

        "rooms":
            props.get(
                "rooms"
            ),

        "size_m2":
            props.get(
                "size_m2"
            ),

        "usable_area_m2":
            props.get(
                "usable_area_m2"
            ),

        "furnished":
            props.get(
                "furnished"
            ),

        "available_from":
            props.get(
                "available_from"
            ),
    }


def compare_pair(
    a,
    b,
):
    reasons = []

    score = 0


    #
    # Non ci interessa trovare doppioni
    # all'interno della stessa fonte.
    #
    if (
        a["source"]
        == b["source"]
    ):
        return None


    address_a = normalize_address(
        a["address"]
    )

    address_b = normalize_address(
        b["address"]
    )


    postal_a = clean(
        a["postal_code"]
    )

    postal_b = clean(
        b["postal_code"]
    )


    city_a = normalize_city(
        a["city"]
    )

    city_b = normalize_city(
        b["city"]
    )


    price_diff = value_difference(
        a["price_monthly"],
        b["price_monthly"],
    )


    #
    # Per Flatfox, quando disponibile,
    # usable_area_m2 può essere più utile
    # della superficie dell'intero appartamento.
    #
    size_a = (
        a["usable_area_m2"]
        if a["usable_area_m2"]
        is not None
        else a["size_m2"]
    )

    size_b = (
        b["usable_area_m2"]
        if b["usable_area_m2"]
        is not None
        else b["size_m2"]
    )


    size_diff = value_difference(
        size_a,
        size_b,
    )


    rooms_diff = value_difference(
        a["rooms"],
        b["rooms"],
    )


    title_sim = text_similarity(
        a["title"],
        b["title"],
    )


    exact_a = (
        a[
            "location_precision"
        ]
        == "address"
    )

    exact_b = (
        b[
            "location_precision"
        ]
        == "address"
    )


    distance_m = haversine_m(
        a["latitude"],
        a["longitude"],
        b["latitude"],
        b["longitude"],
    )


    same_address = (
        bool(
            address_a
        )
        and
        bool(
            address_b
        )
        and
        address_a
        == address_b
    )


    same_postal = (
        bool(
            postal_a
        )
        and
        bool(
            postal_b
        )
        and
        postal_a
        == postal_b
    )


    same_city = (
        bool(
            city_a
        )
        and
        bool(
            city_b
        )
        and
        city_a
        == city_b
    )


    #
    # STESSO INDIRIZZO
    #
    if same_address:

        score += 55

        reasons.append(
            "same_normalized_address"
        )


    #
    # COORDINATE
    #
    # Usiamo la distanza come segnale forte
    # solo quando ENTRAMBI i punti sono
    # realmente geocodificati a indirizzo.
    #
    if (
        exact_a
        and exact_b
        and distance_m
        is not None
    ):

        if distance_m <= 20:

            score += 25

            reasons.append(
                (
                    "exact_coordinates_"
                    f"within_{distance_m:.0f}m"
                )
            )

        elif distance_m <= 50:

            score += 18

            reasons.append(
                (
                    "exact_coordinates_"
                    f"within_{distance_m:.0f}m"
                )
            )

        elif distance_m <= 100:

            score += 8

            reasons.append(
                (
                    "exact_coordinates_"
                    f"within_{distance_m:.0f}m"
                )
            )


    #
    # PREZZO
    #
    if price_diff is not None:

        if price_diff == 0:

            score += 25

            reasons.append(
                "same_price"
            )

        elif price_diff <= 20:

            score += 20

            reasons.append(
                (
                    "price_difference_"
                    f"{price_diff:.0f}_chf"
                )
            )

        elif price_diff <= 50:

            score += 14

            reasons.append(
                (
                    "price_difference_"
                    f"{price_diff:.0f}_chf"
                )
            )

        elif price_diff <= 100:

            score += 6

            reasons.append(
                (
                    "price_difference_"
                    f"{price_diff:.0f}_chf"
                )
            )


    #
    # SUPERFICIE
    #
    if size_diff is not None:

        if size_diff == 0:

            score += 12

            reasons.append(
                "same_size"
            )

        elif size_diff <= 2:

            score += 10

            reasons.append(
                (
                    "size_difference_"
                    f"{size_diff:.1f}_m2"
                )
            )

        elif size_diff <= 5:

            score += 5

            reasons.append(
                (
                    "size_difference_"
                    f"{size_diff:.1f}_m2"
                )
            )


    #
    # NUMERO DI LOCALI
    #
    if rooms_diff is not None:

        if rooms_diff == 0:

            score += 8

            reasons.append(
                "same_rooms"
            )

        elif rooms_diff <= 0.5:

            score += 4

            reasons.append(
                (
                    "rooms_difference_"
                    f"{rooms_diff:.1f}"
                )
            )


    #
    # TITOLO
    #
    if title_sim is not None:

        if title_sim >= 0.90:

            score += 12

            reasons.append(
                (
                    "title_similarity_"
                    f"{title_sim:.2f}"
                )
            )

        elif title_sim >= 0.75:

            score += 8

            reasons.append(
                (
                    "title_similarity_"
                    f"{title_sim:.2f}"
                )
            )

        elif title_sim >= 0.60:

            score += 4

            reasons.append(
                (
                    "title_similarity_"
                    f"{title_sim:.2f}"
                )
            )


    #
    # CAP / CITTÀ
    #
    if same_postal:

        score += 5

        reasons.append(
            "same_postal_code"
        )


    if same_city:

        score += 3

        reasons.append(
            "same_city"
        )


    #
    # Penalità:
    # CAP chiaramente diverso.
    #
    if (
        postal_a
        and postal_b
        and postal_a
        != postal_b
    ):

        score -= 30

        reasons.append(
            "different_postal_code"
        )


    #
    # Tipologia diversa.
    #
    if (
        a["property_type"]
        and b["property_type"]
        and a["property_type"]
        != b["property_type"]
    ):

        score -= 8

        reasons.append(
            "different_property_type"
        )


    #
    # Se entrambi hanno indirizzo preciso
    # ma gli indirizzi sono diversi,
    # penalizziamo molto.
    #
    if (
        address_a
        and address_b
        and not same_address
        and exact_a
        and exact_b
    ):

        score -= 25

        reasons.append(
            "different_exact_addresses"
        )


    if score < MIN_SCORE:
        return None


    if score >= HIGH_SCORE:

        confidence = "high"

    else:

        confidence = "review"


    return {
        "score":
            score,

        "confidence":
            confidence,

        "reasons":
            reasons,

        "metrics": {
            "distance_m":
                (
                    round(
                        distance_m,
                        1,
                    )
                    if distance_m
                    is not None
                    else None
                ),

            "price_difference_chf":
                price_diff,

            "size_difference_m2":
                size_diff,

            "rooms_difference":
                rooms_diff,

            "title_similarity":
                (
                    round(
                        title_sim,
                        3,
                    )
                    if title_sim
                    is not None
                    else None
                ),
        },

        "a":
            a,

        "b":
            b,
    }


def main():
    data = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )


    features = data.get(
        "features",
        []
    )


    listings = [
        listing_summary(
            feature,
            index,
        )

        for index, feature
        in enumerate(
            features
        )
    ]


    candidates = []


    #
    # 144 annunci sono pochi:
    # possiamo confrontare tutte le coppie.
    #
    for i in range(
        len(listings)
    ):

        for j in range(
            i + 1,
            len(listings),
        ):

            result = compare_pair(
                listings[i],
                listings[j],
            )


            if result:

                candidates.append(
                    result
                )


    candidates.sort(
        key=lambda item: (
            -item[
                "score"
            ],
            item[
                "a"
            ][
                "source"
            ]
            or "",
            item[
                "b"
            ][
                "source"
            ]
            or "",
        )
    )


    high = [
        candidate

        for candidate
        in candidates

        if candidate[
            "confidence"
        ]
        == "high"
    ]


    review = [
        candidate

        for candidate
        in candidates

        if candidate[
            "confidence"
        ]
        == "review"
    ]


    output = {
        "input_file":
            str(
                INPUT_FILE
            ),

        "listing_count":
            len(
                listings
            ),

        "thresholds": {
            "minimum_candidate_score":
                MIN_SCORE,

            "high_confidence_score":
                HIGH_SCORE,
        },

        "candidate_count":
            len(
                candidates
            ),

        "high_confidence_count":
            len(
                high
            ),

        "review_count":
            len(
                review
            ),

        "candidates":
            candidates,
    }


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


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
        "======================"
    )

    print(
        "LAUSANNE DUPLICATE AUDIT"
    )

    print(
        "======================"
    )


    print(
        "Listings:",
        len(
            listings
        ),
    )


    print(
        "Candidates:",
        len(
            candidates
        ),
    )


    print(
        "High confidence:",
        len(
            high
        ),
    )


    print(
        "Review:",
        len(
            review
        ),
    )


    print()


    if not candidates:

        print(
            "No cross-source duplicate "
            "candidates found."
        )

    else:

        print(
            "TOP CANDIDATES"
        )

        print(
            "----------------------"
        )


        for index, candidate in enumerate(
            candidates[:30],
            start=1,
        ):

            a = candidate[
                "a"
            ]

            b = candidate[
                "b"
            ]


            print()


            print(
                f"{index}. "
                f"Score "
                f"{candidate['score']} "
                f"[{candidate['confidence']}]"
            )


            print(
                "  A:",
                a["source"],
                "|",
                a["price_monthly"],
                "CHF |",
                a["address"]
                or "",
                a["postal_code"]
                or "",
                a["city"]
                or "",
            )


            print(
                "     ",
                a["source_url"],
            )


            print(
                "  B:",
                b["source"],
                "|",
                b["price_monthly"],
                "CHF |",
                b["address"]
                or "",
                b["postal_code"]
                or "",
                b["city"]
                or "",
            )


            print(
                "     ",
                b["source_url"],
            )


            print(
                "  Reasons:",
                ", ".join(
                    candidate[
                        "reasons"
                    ]
                ),
            )


    print()


    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()