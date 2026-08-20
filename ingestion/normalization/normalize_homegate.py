"""
Normalizzazione Homegate.

Legge data/processed/homegate-lausanne-listings.json (già abbastanza
pulito, perché i dati Homegate arrivano strutturati e non da parsing di
testo libero) e lo converte nello schema comune del progetto, lo stesso
prodotto da normalize_romandie.py / normalize_listings.py, così che
geocode_homegate.py e generate_lausanne_combined_geojson.py possano
trattarlo esattamente come le altre fonti.
"""

import json
import re
from pathlib import Path


INPUT_FILE = Path(
    "data/processed/homegate-lausanne-listings.json"
)

OUTPUT_FILE = Path(
    "data/normalized/homegate-listings-normalized.json"
)


FURNISHED_PATTERN = re.compile(
    r"\b(meublé|meublée|furnished|möbliert)\b",
    re.IGNORECASE,
)

PETS_NOT_ALLOWED_PATTERN = re.compile(
    r"(pas d.animaux|animaux non admis|no pets|keine haustiere)",
    re.IGNORECASE,
)

SMOKING_NOT_ALLOWED_PATTERN = re.compile(
    r"(non.fumeur|non fumeur|no smoking|nichtraucher)",
    re.IGNORECASE,
)

STUDENT_ONLY_PATTERN = re.compile(
    r"(uniquement.*(étudiant|etudiant)|students? only|nur.*student)",
    re.IGNORECASE,
)


def clean(value):
    if value is None:
        return None

    value = " ".join(str(value).replace("\xa0", " ").split())

    return value or None


def map_property_type(categories):
    categories = categories or []

    if "SINGLE_ROOM" in categories:
        return "private_room"

    if "STUDIO" in categories:
        return "studio"

    if "HOUSE" in categories:
        return "house"

    if "APARTMENT" in categories:
        return "apartment"

    return None


def detect_furnished(text, categories):
    # Gli annunci "sc-chambre" (stanza in colocation) su Homegate sono
    # quasi sempre arredati; se il testo lo conferma esplicitamente
    # usiamo True, altrimenti lasciamo None invece di indovinare.
    if text and FURNISHED_PATTERN.search(text):
        return True

    return None


def detect_restrictions(text):
    if not text:
        return {
            "pets": None,
            "smoking": None,
            "student_only": None,
            "gender": None,
            "minimum_age": None,
            "maximum_age": None,
        }

    return {
        "pets": (
            False if PETS_NOT_ALLOWED_PATTERN.search(text) else None
        ),
        "smoking": (
            False if SMOKING_NOT_ALLOWED_PATTERN.search(text) else None
        ),
        "student_only": (
            True if STUDENT_ONLY_PATTERN.search(text) else None
        ),
        "gender": None,
        "minimum_age": None,
        "maximum_age": None,
    }


def normalize_listing(item):
    description = clean(item.get("description_raw"))

    return {
        "source": "homegate",
        "source_section": "lausanne",
        "source_id": item.get("source_id"),
        "source_url": item.get("url"),
        "title": clean(item.get("title")),
        "price": {
            "monthly": item.get("price_chf"),
            "net": item.get("price_net_chf"),
            "charges": item.get("price_charges_chf"),
            "currency": item.get("currency") or "CHF",
        },
        "location": {
            "address": clean(item.get("address")),
            "postal_code": clean(item.get("postal_code")),
            "city": clean(item.get("city")),
            "country": item.get("country") or "CH",
            # Homegate fornisce già coordinate proprie: le passiamo
            # attraverso la normalizzazione, geocode_homegate.py le userà
            # direttamente senza richiamare un servizio di geocoding
            # esterno.
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "precision": (
                "source_exact"
                if item.get("geo_accuracy") == "HIGH"
                else "source_approximate"
                if item.get("latitude") is not None
                else None
            ),
        },
        "property": {
            "type": map_property_type(item.get("categories")),
            "rooms": item.get("rooms"),
            "bathrooms": item.get("bathrooms"),
            "size_m2": item.get("size_m2"),
            "floor": item.get("floor"),
            "furnished": detect_furnished(
                description, item.get("categories")
            ),
        },
        "contract": {
            "type": None,
            "available_from": item.get("available_from"),
            "available_to": None,
            "minimum_months": None,
            "maximum_months": None,
        },
        "offer_type": "RENT",
        "restrictions": detect_restrictions(description),
        "description": description,
        "description_raw": description,
    }


def main():
    if not INPUT_FILE.exists():
        print("File non trovato:", INPUT_FILE)
        print("Esegui prima homegate_index.py e homegate_details.py")
        return

    source = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    items = source.get("listings") or []

    normalized = []
    excluded = []

    for item in items:
        if not item.get("latitude") or not item.get("longitude"):
            excluded.append(item)
            continue

        normalized.append(normalize_listing(item))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "source": "homegate",
        "source_section": "lausanne",
        "input_count": len(items),
        "count": len(normalized),
        "listings": normalized,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("======================")
    print("HOMEGATE NORMALIZE")
    print("======================")
    print("Input:", len(items))
    print("Normalized:", len(normalized))
    print("Excluded (no coordinates):", len(excluded))
    print()
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
