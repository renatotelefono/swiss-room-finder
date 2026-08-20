import json
import math
from collections import Counter
from pathlib import Path


RONORP_FILE = Path(
    "data/geocoded/ronorp-romandie-listings-geocoded.json"
)

IMMOBILIER_FILE = Path(
    "data/geocoded/immobilier-lausanne-listings-geocoded.json"
)

FLATFOX_FILE = Path(
    "data/geocoded/flatfox-lausanne-listings-geocoded.json"
)

HOMEGATE_FILE = Path(
    "data/geocoded/homegate-listings-geocoded.json"
)

OUTPUT_FILE = Path(
    "data/final/lausanne-listings.geojson"
)


LAUSANNE_LAT = 46.5197
LAUSANNE_LON = 6.6323
RADIUS_KM = 20


def load_json(path, default=None):
    if not path.exists():
        if default is not None:
            return default

        raise FileNotFoundError(path)

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    radius = 6371.0088

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

    dlat = lat2 - lat1
    dlon = lon2 - lon1

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


def make_feature(
    listing,
):
    location = (
        listing.get(
            "location"
        )
        or {}
    )

    latitude = location.get(
        "latitude"
    )

    longitude = location.get(
        "longitude"
    )


    if (
        latitude is None
        or longitude is None
    ):
        return None


    latitude = float(
        latitude
    )

    longitude = float(
        longitude
    )


    price = (
        listing.get(
            "price"
        )
        or {}
    )

    property_data = (
        listing.get(
            "property"
        )
        or {}
    )

    contract = (
        listing.get(
            "contract"
        )
        or {}
    )

    restrictions = (
        listing.get(
            "restrictions"
        )
        or {}
    )


    distance = haversine_km(
        LAUSANNE_LAT,
        LAUSANNE_LON,
        latitude,
        longitude,
    )


    return {
        "type":
            "Feature",

        "geometry": {
            "type":
                "Point",

            "coordinates": [
                longitude,
                latitude,
            ],
        },

        "properties": {
            "source":
                listing.get(
                    "source"
                ),

            "source_section":
                listing.get(
                    "source_section"
                ),

            "source_id":
                listing.get(
                    "source_id"
                ),

            "source_url":
                listing.get(
                    "source_url"
                ),

            "area":
                "lausanne",

            "title":
                listing.get(
                    "title"
                ),

            "description_title":
                listing.get(
                    "description_title"
                ),

            "price_monthly":
                price.get(
                    "monthly"
                ),

            "price_net":
                price.get(
                    "net"
                ),

            "charges":
                price.get(
                    "charges"
                ),

            "currency":
                (
                    price.get(
                        "currency"
                    )
                    or "CHF"
                ),

            "address":
                location.get(
                    "address"
                ),

            "postal_code":
                location.get(
                    "postal_code"
                ),

            "city":
                location.get(
                    "city"
                ),

            "country":
                (
                    location.get(
                        "country"
                    )
                    or "CH"
                ),

            "latitude":
                latitude,

            "longitude":
                longitude,

            "location_precision":
                location.get(
                    "precision"
                ),

            "distance_from_lausanne_km":
                round(
                    distance,
                    2,
                ),

            "property_type":
                property_data.get(
                    "type"
                ),

            "rooms":
                property_data.get(
                    "rooms"
                ),

            "bedrooms":
                property_data.get(
                    "bedrooms"
                ),

            "bathrooms":
                property_data.get(
                    "bathrooms"
                ),

            "size_m2":
                property_data.get(
                    "size_m2"
                ),

            "usable_area_m2":
                property_data.get(
                    "usable_area_m2"
                ),

            "floor":
                property_data.get(
                    "floor"
                ),

            "furnished":
                property_data.get(
                    "furnished"
                ),

            "contract_type":
                contract.get(
                    "type"
                ),

            "availability_text":
                contract.get(
                    "availability_text"
                ),

            "available_from":
                contract.get(
                    "available_from"
                ),

            "available_now":
                contract.get(
                    "available_now"
                ),

            "available_to":
                contract.get(
                    "available_to"
                ),

            "minimum_months":
                contract.get(
                    "minimum_months"
                ),

            "maximum_months":
                contract.get(
                    "maximum_months"
                ),

            "pets":
                restrictions.get(
                    "pets"
                ),

            "smoking":
                restrictions.get(
                    "smoking"
                ),

            "student_only":
                restrictions.get(
                    "student_only"
                ),

            "gender":
                restrictions.get(
                    "gender"
                ),

            "minimum_age":
                restrictions.get(
                    "minimum_age"
                ),

            "maximum_age":
                restrictions.get(
                    "maximum_age"
                ),

            "description":
                listing.get(
                    "description"
                ),
        },
    }


def add_source(
    listings,
    features,
    source_name,
):
    stats = {
        "source":
            source_name,

        "input":
            len(
                listings
            ),

        "added":
            0,

        "outside_radius":
            0,

        "missing_coordinates":
            0,
    }


    for listing in listings:

        feature = make_feature(
            listing
        )


        if feature is None:

            stats[
                "missing_coordinates"
            ] += 1

            continue


        distance = (
            feature[
                "properties"
            ][
                "distance_from_lausanne_km"
            ]
        )


        if distance > RADIUS_KM:

            stats[
                "outside_radius"
            ] += 1

            continue


        features.append(
            feature
        )

        stats[
            "added"
        ] += 1


    return stats


def deduplicate_by_url(
    features,
):
    unique = []

    seen = set()

    duplicates = 0


    for feature in features:

        properties = (
            feature.get(
                "properties"
            )
            or {}
        )


        source = (
            properties.get(
                "source"
            )
            or ""
        )


        source_url = (
            properties.get(
                "source_url"
            )
            or ""
        )


        #
        # Per ora deduplica solo:
        # stessa fonte + stesso URL.
        #
        # La deduplicazione vera
        # tra portali diversi la faremo dopo.
        #
        if source_url:

            key = (
                source,
                source_url,
            )

        else:

            key = None


        if (
            key
            and key in seen
        ):

            duplicates += 1

            continue


        if key:
            seen.add(
                key
            )


        unique.append(
            feature
        )


    return (
        unique,
        duplicates,
    )


def main():

    ronorp_data = load_json(
        RONORP_FILE
    )

    immobilier_data = load_json(
        IMMOBILIER_FILE
    )

    flatfox_data = load_json(
        FLATFOX_FILE
    )

    #
    # Homegate è opzionale: se la pipeline non è ancora
    # stata eseguita per questa fonte, procediamo comunque
    # con le altre invece di far fallire lo script.
    #
    homegate_data = load_json(
        HOMEGATE_FILE,
        default={"listings": []},
    )


    ronorp_listings = (
        ronorp_data.get(
            "listings",
            []
        )
    )

    immobilier_listings = (
        immobilier_data.get(
            "listings",
            []
        )
    )

    flatfox_listings = (
        flatfox_data.get(
            "listings",
            []
        )
    )

    homegate_listings = (
        homegate_data.get(
            "listings",
            []
        )
    )


    raw_features = []


    ronorp_stats = add_source(
        ronorp_listings,
        raw_features,
        "ronorp",
    )


    immobilier_stats = add_source(
        immobilier_listings,
        raw_features,
        "immobilier.ch",
    )


    flatfox_stats = add_source(
        flatfox_listings,
        raw_features,
        "flatfox",
    )


    homegate_stats = add_source(
        homegate_listings,
        raw_features,
        "homegate",
    )


    features, duplicate_urls = (
        deduplicate_by_url(
            raw_features
        )
    )


    features.sort(
        key=lambda feature:
            feature[
                "properties"
            ].get(
                "distance_from_lausanne_km",
                9999,
            )
    )


    source_counts = Counter(
        (
            feature.get(
                "properties"
            )
            or {}
        ).get(
            "source"
        )
        or "unknown"

        for feature in features
    )


    precision_counts = Counter(
        (
            feature.get(
                "properties"
            )
            or {}
        ).get(
            "location_precision"
        )
        or "unknown"

        for feature in features
    )


    property_counts = Counter(
        (
            feature.get(
                "properties"
            )
            or {}
        ).get(
            "property_type"
        )
        or "unknown"

        for feature in features
    )


    output = {
        "type":
            "FeatureCollection",

        "metadata": {
            "area":
                "lausanne",

            "center": {
                "latitude":
                    LAUSANNE_LAT,

                "longitude":
                    LAUSANNE_LON,
            },

            "radius_km":
                RADIUS_KM,

            "feature_count":
                len(
                    features
                ),

            "duplicate_urls_removed":
                duplicate_urls,

            "sources":
                dict(
                    source_counts
                ),

            "precision":
                dict(
                    precision_counts
                ),

            "property_types":
                dict(
                    property_counts
                ),

            "collection_stats": {
                "ronorp":
                    ronorp_stats,

                "immobilier.ch":
                    immobilier_stats,

                "flatfox":
                    flatfox_stats,

                "homegate":
                    homegate_stats,
            },
        },

        "features":
            features,
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
        "LAUSANNE COMBINED"
    )

    print(
        "======================"
    )


    print(
        "Radius:",
        RADIUS_KM,
        "km",
    )


    print()


    print(
        "Ron Orp:",
        ronorp_stats[
            "added"
        ],
    )


    print(
        "immobilier.ch:",
        immobilier_stats[
            "added"
        ],
    )


    print(
        "Flatfox:",
        flatfox_stats[
            "added"
        ],
    )


    print(
        "Homegate:",
        homegate_stats[
            "added"
        ],
    )


    print()


    print(
        "Duplicates removed:",
        duplicate_urls,
    )


    print(
        "Total:",
        len(
            features
        ),
    )


    print()
    print(
        "Sources:"
    )


    for source, count in sorted(
        source_counts.items()
    ):

        print(
            f"  {source}: "
            f"{count}"
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
        "Property types:"
    )


    for property_type, count in sorted(
        property_counts.items()
    ):

        print(
            f"  {property_type}: "
            f"{count}"
        )


    print()
    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()