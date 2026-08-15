import json
from pathlib import Path


INPUT_FILE = Path(
    "data/geocoded/ronorp-listings-geocoded.json"
)

OUTPUT_FILE = Path(
    "data/final/listings.geojson"
)


def main():
    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        source = json.load(f)

    listings = source.get(
        "listings",
        [],
    )

    features = []

    skipped = 0

    precision_counts = {}

    for listing in listings:

        location = listing.get(
            "location",
            {},
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
            skipped += 1
            continue

        precision = (
            location.get("precision")
            or "unknown"
        )

        precision_counts[precision] = (
            precision_counts.get(
                precision,
                0,
            )
            + 1
        )

        price = listing.get(
            "price",
            {},
        )

        property_data = listing.get(
            "property",
            {},
        )

        contract = listing.get(
            "contract",
            {},
        )

        restrictions = listing.get(
            "restrictions",
            {},
        )

        feature = {
            "type": "Feature",

            "geometry": {
                "type": "Point",

                # GeoJSON usa:
                # [longitude, latitude]
                "coordinates": [
                    longitude,
                    latitude,
                ],
            },

            "properties": {
                "source": listing.get(
                    "source"
                ),

                "source_url": listing.get(
                    "source_url"
                ),

                "title": listing.get(
                    "title"
                ),

                "price_monthly": price.get(
                    "monthly"
                ),

                "currency": price.get(
                    "currency"
                ),

                "address": location.get(
                    "address"
                ),

                "postal_code": location.get(
                    "postal_code"
                ),

                "city": location.get(
                    "city"
                ),

                "country": location.get(
                    "country"
                ),

                "location_precision": precision,

                "property_type": property_data.get(
                    "type"
                ),

                "rooms": property_data.get(
                    "rooms"
                ),

                "size_m2": property_data.get(
                    "size_m2"
                ),

                "floor": property_data.get(
                    "floor"
                ),

                "furnished": property_data.get(
                    "furnished"
                ),

                "contract_type": contract.get(
                    "type"
                ),

                "available_from": contract.get(
                    "available_from"
                ),

                "available_to": contract.get(
                    "available_to"
                ),

                "minimum_months": contract.get(
                    "minimum_months"
                ),

                "maximum_months": contract.get(
                    "maximum_months"
                ),

                "pets": restrictions.get(
                    "pets"
                ),

                "smoking": restrictions.get(
                    "smoking"
                ),

                "student_only": restrictions.get(
                    "student_only"
                ),

                "gender": restrictions.get(
                    "gender"
                ),

                "description": listing.get(
                    "description"
                ),

                "external_url": listing.get(
                    "external_url"
                ),
            },
        }

        features.append(
            feature
        )

    geojson = {
        "type": "FeatureCollection",

        "metadata": {
            "source": "ronorp",
            "input_count": len(listings),
            "feature_count": len(features),
            "skipped": skipped,
            "precision": precision_counts,
        },

        "features": features,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            geojson,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("----------------------")
    print("GEOJSON EXPORT")
    print("----------------------")

    print(
        "Input:",
        len(listings),
    )

    print(
        "Features:",
        len(features),
    )

    print(
        "Skipped:",
        skipped,
    )

    print()
    print("Precision:")

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


if __name__ == "__main__":
    main()