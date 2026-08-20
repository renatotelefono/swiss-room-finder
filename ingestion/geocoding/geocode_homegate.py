"""
"Geocoding" Homegate.

A differenza delle altre fonti del progetto, gli annunci Homegate
arrivano già con latitude/longitude proprie (spesso con precisione
"HIGH", cioè geocodifica dell'indirizzo esatto fatta direttamente da
Homegate). Non ha quindi senso richiamare geo.admin.ch: questo script si
limita a validare i dati e a scrivere l'output nello stesso formato
"geocoded" usato dalle altre fonti, in modo che
generate_lausanne_combined_geojson.py possa leggerlo allo stesso modo.
"""

import json
from pathlib import Path


INPUT_FILE = Path(
    "data/normalized/homegate-listings-normalized.json"
)

OUTPUT_FILE = Path(
    "data/geocoded/homegate-listings-geocoded.json"
)


def main():
    if not INPUT_FILE.exists():
        print("File non trovato:", INPUT_FILE)
        print("Esegui prima normalize_homegate.py")
        return

    source = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    listings = source.get("listings") or []

    success = 0
    failed = 0
    precision_counts = {}

    for listing in listings:
        location = listing.setdefault("location", {})

        latitude = location.get("latitude")
        longitude = location.get("longitude")

        if latitude is None or longitude is None:
            failed += 1
            location["geocoding_status"] = "failed"
            continue

        success += 1
        location["geocoding_status"] = "source"
        location["geocoder_origin"] = "homegate"

        precision = location.get("precision") or "source_exact"
        location["precision"] = precision

        precision_counts[precision] = (
            precision_counts.get(precision, 0) + 1
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "source": "homegate",
        "source_section": "lausanne",
        "input_count": len(listings),
        "geocoded": success,
        "failed": failed,
        "precision": precision_counts,
        "listings": listings,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("======================")
    print("HOMEGATE GEOCODING")
    print("======================")
    print("Input:", len(listings))
    print("Geocoded (from source):", success)
    print("Failed:", failed)
    print()
    print("Precision:")
    for precision, count in sorted(precision_counts.items()):
        print(f"  {precision}: {count}")
    print()
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
