import json
import math
from pathlib import Path


INPUT_FILE = Path(
    "data/geocoded/ronorp-romandie-listings-geocoded.json"
)

OUTPUT_FILE = Path(
    "data/final/lausanne-listings.geojson"
)


LAUSANNE_LAT = 46.5197
LAUSANNE_LON = 6.6323

# Puoi cambiare facilmente questo valore in futuro.
RADIUS_KM = 20


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    earth_radius_km = 6371.0088

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(
        lat2 - lat1
    )

    delta_lon = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(
            delta_lat / 2
        ) ** 2
        +
        math.cos(lat1_rad)
        *
        math.cos(lat2_rad)
        *
        math.sin(
            delta_lon / 2
        ) ** 2
    )

    c = (
        2
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )
    )

    return (
        earth_radius_km
        *
        c
    )


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

    features = []

    outside = 0
    missing_coordinates = 0

    precision_counts = {}


    for listing in listings:

        location = listing.get(
            "location",
            {}
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
            missing_coordinates += 1
            continue


        distance_km = haversine_km(
            LAUSANNE_LAT,
            LAUSANNE_LON,
            latitude,
            longitude,
        )


        if distance_km > RADIUS_KM:
            outside += 1
            continue


        precision = (
            location.get("precision")
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

        restrictions = listing.get(
            "restrictions",
            {}
        )


        feature = {
            "type": "Feature",

            "geometry": {
                "type": "Point",

                # GeoJSON usa:
                # longitude, latitude
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
                    "romandie",

                "area":
                    "lausanne",

                "source_url":
                    listing.get(
                        "source_url"
                    ),

                "title":
                    listing.get(
                        "title"
                    ),

                "price_monthly":
                    price.get(
                        "monthly"
                    ),

                "currency":
                    price.get(
                        "currency"
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
                    location.get(
                        "country"
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "distance_from_lausanne_km":
                    round(
                        distance_km,
                        2,
                    ),

                "location_precision":
                    precision,

                "property_type":
                    property_data.get(
                        "type"
                    ),

                "rooms":
                    property_data.get(
                        "rooms"
                    ),

                "size_m2":
                    property_data.get(
                        "size_m2"
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

                "available_from":
                    contract.get(
                        "available_from"
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

                "description":
                    listing.get(
                        "description"
                    ),
            },
        }


        features.append(
            feature
        )


    features.sort(
        key=lambda feature:
            feature[
                "properties"
            ][
                "distance_from_lausanne_km"
            ]
    )


    geojson = {
        "type":
            "FeatureCollection",

        "metadata": {
            "source":
                "ronorp",

            "source_section":
                "romandie",

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

            "input_count":
                len(listings),

            "feature_count":
                len(features),

            "outside_radius":
                outside,

            "missing_coordinates":
                missing_coordinates,

            "precision":
                precision_counts,
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
            geojson,
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
        "LAUSANNE GEOJSON"
    )

    print(
        "----------------------"
    )


    print(
        "Romandie input:",
        len(listings),
    )

    print(
        "Radius:",
        RADIUS_KM,
        "km",
    )

    print(
        "Lausanne listings:",
        len(features),
    )

    print(
        "Outside radius:",
        outside,
    )

    print(
        "Missing coordinates:",
        missing_coordinates,
    )


    print()
    print(
        "Listings:"
    )


    for index, feature in enumerate(
        features,
        start=1,
    ):

        properties = (
            feature[
                "properties"
            ]
        )

        print()
        print(
            f"{index}. "
            f"{properties['distance_from_lausanne_km']} km"
        )

        print(
            "   City:",
            properties["city"],
        )

        print(
            "   CAP:",
            properties["postal_code"],
        )

        print(
            "   Price:",
            properties["price_monthly"],
        )

        print(
            "   Title:",
            (
                properties["title"]
                or ""
            )[:100],
        )


    print()

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()