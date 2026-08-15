import json
import math
from pathlib import Path


INPUT_FILE = Path(
    "data/geocoded/ronorp-romandie-listings-geocoded.json"
)

OUTPUT_FILE = Path(
    "data/normalized/lausanne-area-analysis.json"
)


# Centro approssimativo di Losanna
LAUSANNE_LAT = 46.5197
LAUSANNE_LON = 6.6323


RADII_KM = [
    10,
    20,
    30,
    40,
]


def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Distanza tra due coordinate
    sulla superficie terrestre.
    """

    earth_radius_km = 6371.0088

    lat1_rad = math.radians(
        lat1
    )

    lat2_rad = math.radians(
        lat2
    )

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
        math.cos(
            lat1_rad
        )
        *
        math.cos(
            lat2_rad
        )
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

    analyzed = []


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
            continue


        distance = haversine_km(
            LAUSANNE_LAT,
            LAUSANNE_LON,
            latitude,
            longitude,
        )


        analyzed.append(
            {
                "title":
                    listing.get(
                        "title"
                    ),

                "city":
                    location.get(
                        "city"
                    ),

                "postal_code":
                    location.get(
                        "postal_code"
                    ),

                "distance_km":
                    round(
                        distance,
                        2,
                    ),

                "price_monthly":
                    listing.get(
                        "price",
                        {}
                    ).get(
                        "monthly"
                    ),

                "source_url":
                    listing.get(
                        "source_url"
                    ),
            }
        )


    #
    # Ordina dal più vicino
    # al più lontano.
    #
    analyzed.sort(
        key=lambda item:
            item["distance_km"]
    )


    radius_counts = {}


    for radius in RADII_KM:

        radius_counts[
            str(radius)
        ] = sum(
            item[
                "distance_km"
            ] <= radius

            for item in analyzed
        )


    output = {
        "center": {
            "name":
                "Lausanne",

            "latitude":
                LAUSANNE_LAT,

            "longitude":
                LAUSANNE_LON,
        },

        "input_count":
            len(listings),

        "analyzed_count":
            len(analyzed),

        "radius_counts":
            radius_counts,

        "listings":
            analyzed,
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
        "----------------------"
    )

    print(
        "LAUSANNE AREA ANALYSIS"
    )

    print(
        "----------------------"
    )


    print(
        "Romandie listings:",
        len(listings),
    )


    print()
    print(
        "Annunci entro:"
    )


    for radius in RADII_KM:

        print(
            f"  {radius:>2} km: "
            f"{radius_counts[str(radius)]}"
        )


    print()
    print(
        "15 annunci più vicini:"
    )

    print()


    for index, item in enumerate(
        analyzed[:15],
        start=1,
    ):

        print(
            f"{index}. "
            f"{item['distance_km']} km"
        )

        print(
            "   City:",
            item["city"],
        )

        print(
            "   CAP:",
            item["postal_code"],
        )

        print(
            "   Price:",
            item["price_monthly"],
        )

        print(
            "   Title:",
            (
                item["title"]
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