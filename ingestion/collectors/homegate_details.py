"""
Collector Homegate — fase DETAILS.

I dati raccolti da homegate_index.py sono già molto ricchi (indirizzo,
coordinate, prezzo, caratteristiche, descrizione completa), ma un campo
importante manca dall'indice di ricerca: la data di disponibilità
("availableFrom"), presente solo nello stato interno (Pinia) della
pagina di dettaglio del singolo annuncio.

Questo script legge data/raw/homegate/lausanne-index.json, apre ogni
annuncio con Playwright, estrae "availableFrom" (quando presente) e
produce un file "processed" con i campi principali già rinominati in
uno schema semplice e piatto, pronto per la normalizzazione.

Per ridurre il carico sul sito (ed il rischio di essere bloccati da
DataDome, il sistema anti-bot di Homegate), questo script apre SOLO la
pagina di dettaglio, non rifà lo scraping di tutto ciò che è già
disponibile dall'indice.

Se noti blocchi DataDome (pagine vuote, HTTP 403, titolo "Un instant..."):
vedi le note dettagliate in homegate_index.py. Qui usiamo la stessa
strategia: browser visibile, Chrome reale invece del Chromium interno
di Playwright, e caricamento di cookies.json se presente.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


INPUT_FILE = Path(
    "data/raw/homegate/lausanne-index.json"
)

OUTPUT_FILE = Path(
    "data/processed/homegate-lausanne-listings.json"
)

COOKIES_FILE = Path("cookies.json")

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

HEADLESS = False
USE_REAL_CHROME = True
PAGE_WAIT_MS = 1800

# Limite di sicurezza per non aprire migliaia di pagine per errore.
MAX_LISTINGS = 500


def load_cookies():
    if not COOKIES_FILE.exists():
        return []

    try:
        return json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print("Impossibile leggere cookies.json:", repr(exc))
        return []


def launch_browser(playwright, headless, use_real_chrome):
    launch_args = ["--disable-blink-features=AutomationControlled"]

    if use_real_chrome:
        try:
            return playwright.chromium.launch(
                headless=headless,
                channel="chrome",
                args=launch_args,
            )
        except Exception as exc:
            print(
                "Chrome reale non disponibile "
                f"({exc!r}), uso Chromium interno."
            )

    return playwright.chromium.launch(
        headless=headless,
        args=launch_args,
    )


def listing_url(listing_id):
    return f"https://www.homegate.ch/louer/{listing_id}"


def extract_available_from(page):
    """
    Legge window.__PINIA_INITIAL_STATE__.listing.listing._rawValue
    .availableFrom evitando di incappare in riferimenti circolari
    (lo stato Pinia è reattivo e contiene oggetti che si richiamano
    a vicenda).
    """

    return page.evaluate(
        """
        () => {
            try {
                const state = window.__PINIA_INITIAL_STATE__;

                const raw =
                    state
                    && state.listing
                    && state.listing.listing
                    && (
                        state.listing.listing._rawValue
                        || state.listing.listing._value
                    );

                if (!raw) {
                    return null;
                }

                return raw.availableFrom || null;
            } catch (error) {
                return null;
            }
        }
        """
    )


def flatten_listing(entry, available_from):
    listing = entry.get("listing") or {}

    address = listing.get("address") or {}
    geo = address.get("geoCoordinates") or {}
    prices = listing.get("prices") or {}
    rent = prices.get("rent") or {}
    characteristics = listing.get("characteristics") or {}
    categories = listing.get("categories") or []

    localization = listing.get("localization") or {}
    primary_lang = localization.get("primary")
    text = (localization.get(primary_lang) or {}).get("text") or {}

    return {
        "source": "homegate",
        "source_id": entry.get("id"),
        "url": listing_url(entry.get("id")),
        "title": text.get("title"),
        "description_raw": text.get("description"),
        "categories": categories,
        "price_chf": rent.get("gross"),
        "price_net_chf": rent.get("net"),
        "price_charges_chf": rent.get("extra"),
        "currency": prices.get("currency") or "CHF",
        "address": address.get("street"),
        "postal_code": address.get("postalCode"),
        "city": address.get("locality"),
        "country": address.get("country") or "CH",
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "geo_accuracy": geo.get("accuracy"),
        "rooms": characteristics.get("numberOfRooms"),
        "bathrooms": characteristics.get("numberOfBathrooms"),
        "size_m2": characteristics.get("livingSpace"),
        "floor": characteristics.get("floor"),
        "year_built": characteristics.get("yearBuilt"),
        "has_elevator": characteristics.get("hasElevator"),
        "available_from": available_from,
        "created_at": (listing.get("meta") or {}).get("createdAt"),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    if not INPUT_FILE.exists():
        print("File non trovato:", INPUT_FILE)
        print("Esegui prima homegate_index.py")
        return

    raw = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    entries = raw.get("listings") or []

    total = min(len(entries), MAX_LISTINGS)

    print()
    print("======================")
    print("HOMEGATE DETAILS")
    print("======================")
    print()
    print("Annunci da processare:", total)

    processed = []

    with sync_playwright() as playwright:
        browser = launch_browser(
            playwright,
            headless=HEADLESS,
            use_real_chrome=USE_REAL_CHROME,
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="fr-CH",
            user_agent=REALISTIC_USER_AGENT,
        )

        cookies = load_cookies()

        if cookies:
            context.add_cookies(cookies)
            print("Cookie caricati da cookies.json:", len(cookies))

        page = context.new_page()

        for index, entry in enumerate(entries[:total], start=1):
            listing_id = entry.get("id")

            if not listing_id:
                continue

            url = listing_url(listing_id)

            print()
            print(f"[{index}/{total}] {url}")

            available_from = None

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(PAGE_WAIT_MS)

                available_from = extract_available_from(page)

                print("  available_from:", available_from)

            except Exception as exc:
                print("  ERRORE:", repr(exc))

            processed.append(
                flatten_listing(entry, available_from)
            )

        browser.close()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "source": "homegate",
        "source_section": "lausanne",
        "input_count": len(entries),
        "count": len(processed),
        "listings": processed,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with_available_from = sum(
        1 for item in processed if item.get("available_from")
    )

    print()
    print("======================")
    print("HOMEGATE DETAILS RESULT")
    print("======================")
    print("Processed:", len(processed))
    print("With available_from:", with_available_from)
    print()
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
