import json
from pathlib import Path


LAUSANNE_FILE = Path(
    "data/final/lausanne-listings.geojson"
)

OUTPUT_FILE = Path(
    "data/final/swiss-listings.geojson"
)


def load_geojson(path):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def main():
    #
    # Zurigo è stato rimosso dal dataset su richiesta:
    # l'app ora copre solo l'area di Losanna.
    #
    lausanne = load_geojson(
        LAUSANNE_FILE
    )


    lausanne_features = (
        lausanne.get(
            "features",
            []
        )
    )


    #
    # Aggiungiamo un campo "area"
    # uniforme a tutti gli annunci.
    #
    for feature in lausanne_features:

        properties = feature.setdefault(
            "properties",
            {}
        )

        properties["area"] = "lausanne"


    features = lausanne_features


    output = {
        "type":
            "FeatureCollection",

        "metadata": {
            "total":
                len(features),

            "areas": {
                "lausanne":
                    len(
                        lausanne_features
                    ),
            },

            "sources": [
                "ronorp"
            ],
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
        "----------------------"
    )

    print(
        "SWISS GEOJSON (solo Losanna)"
    )

    print(
        "----------------------"
    )

    print(
        "Lausanne:",
        len(
            lausanne_features
        ),
    )

    print(
        "Total:",
        len(
            features
        ),
    )

    print()

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
