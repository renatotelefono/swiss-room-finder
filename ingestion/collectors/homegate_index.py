"""
Collector Homegate — fase INDEX.

A differenza di Ron Orp, Flatfox e immobilier.ch, Homegate non richiede
di aprire ogni singolo annuncio per ottenere i dati principali: la pagina
dei risultati di ricerca (server-rendered da un'app Vue) espone già un
oggetto JavaScript globale

    window.__INITIAL_STATE__.resultList.search.fullSearch.result

che contiene, per ciascun annuncio, indirizzo completo, coordinate GPS
(precisione "HIGH" quando disponibile), prezzo, caratteristiche
strutturate (locali, superficie, piano, ecc.) e descrizione completa
nella lingua originale dell'inserzione.

Questo script raccoglie quindi direttamente questi oggetti "grezzi" per
tutte le pagine dei risultati e li salva in data/raw/homegate/. La
normalizzazione nello schema comune del progetto avviene in un secondo
momento (vedi ingestion/normalization/normalize_homegate.py), mentre
homegate_details.py si occupa solo di recuperare il campo "availableFrom"
(disponibile solo nella pagina di dettaglio del singolo annuncio).

NOTA SU DATADOME:
Homegate è protetto da DataDome, un sistema anti-bot che riconosce i
browser guidati via CDP (il protocollo usato da Playwright/Selenium),
indipendentemente dalla modalità headless. Se ricevi un HTTP 403 con
titolo pagina "Un instant..." o simili, è DataDome che ha bloccato la
richiesta. Contromisure, in ordine di efficacia crescente:

  1. HEADLESS = False (già impostato di default) per usare un browser
     visibile, più simile a una sessione reale;
  2. USE_REAL_CHROME = True (default) per pilotare il tuo Chrome
     installato invece del Chromium interno di Playwright — richiede
     Google Chrome già installato sul sistema;
  3. se nonostante tutto vieni ancora bloccato, prova a navigare
     manualmente su Homegate nel tuo Chrome normale (superando
     l'eventuale verifica "non sono un robot"), poi esporta il cookie
     "datadome" con un'estensione tipo "Cookie-Editor" e salvalo in
     un file cookies.json nella cartella del progetto nel formato
     [{"name": "datadome", "value": "...", "domain": ".homegate.ch",
     "path": "/"}] — lo script lo caricherà automaticamente se presente;
  4. aumenta PAGE_WAIT_MS per rallentare le richieste ed evita di
     rilanciare lo script troppe volte a distanza ravvicinata.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


COOKIES_FILE = Path("cookies.json")

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


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


# URL di ricerca: stanze/camere in affitto nella regione di Losanna.
# Homegate pagina i risultati con il parametro di query "ep" (numero di
# pagina, a partire da 1), 20 annunci per pagina.
SOURCE_URL = (
    "https://www.homegate.ch/louer/appartement/"
    "sc-chambre/region-lausanne/liste-annonces"
)

OUTPUT_FILE = Path(
    "data/raw/homegate/lausanne-index.json"
)

HEADLESS = False
USE_REAL_CHROME = True
PAGE_WAIT_MS = 2500
MAX_PAGES_SAFETY = 30  # limite di sicurezza, non dovrebbe mai servire


def build_page_url(page_number):
    if page_number <= 1:
        return SOURCE_URL

    return f"{SOURCE_URL}?ep={page_number}"


def extract_result(page):
    """
    Legge window.__INITIAL_STATE__.resultList.search.fullSearch.result
    dalla pagina corrente. Restituisce None se la struttura non è quella
    attesa (es. pagina di verifica DataDome, layout cambiato, ecc.).
    """

    return page.evaluate(
        """
        () => {
            try {
                const state = window.__INITIAL_STATE__;
                const result =
                    state
                    && state.resultList
                    && state.resultList.search
                    && state.resultList.search.fullSearch
                    && state.resultList.search.fullSearch.result;

                if (!result) {
                    return null;
                }

                return {
                    page: result.page,
                    pageCount: result.pageCount,
                    resultCount: result.resultCount,
                    itemsPerPage: result.itemsPerPage,
                    listings: result.listings || [],
                };
            } catch (error) {
                return null;
            }
        }
        """
    )


def main():
    collected = {}

    print()
    print("======================")
    print("HOMEGATE INDEX")
    print("======================")
    print()
    print("Opening:", SOURCE_URL)

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

        response = page.goto(
            SOURCE_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        print("HTTP:", response.status if response else None)

        page.wait_for_timeout(PAGE_WAIT_MS)

        first_result = extract_result(page)

        if first_result is None:
            print()
            print("ATTENZIONE: non ho trovato __INITIAL_STATE__.")
            print("Possibile blocco DataDome o layout cambiato.")
            print("Titolo pagina:", page.title())

            browser.close()

            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_FILE.write_text(
                json.dumps(
                    {
                        "source": "homegate",
                        "area": "lausanne",
                        "source_url": SOURCE_URL,
                        "collected_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "count": 0,
                        "listings": [],
                        "error": "initial_state_not_found",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            return

        page_count = first_result.get("pageCount") or 1
        result_count = first_result.get("resultCount")

        print("Total results (dichiarati):", result_count)
        print("Total pages:", page_count)

        page_count = min(page_count, MAX_PAGES_SAFETY)

        for page_number in range(1, page_count + 1):

            print()
            print("----------------------")
            print(f"PAGE {page_number}/{page_count}")
            print("----------------------")

            if page_number > 1:
                page.goto(
                    build_page_url(page_number),
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(PAGE_WAIT_MS)

            result = extract_result(page)

            if result is None:
                print("Nessun dato trovato su questa pagina, salto.")
                continue

            page_listings = result.get("listings") or []

            print("Annunci in questa pagina:", len(page_listings))

            for entry in page_listings:
                listing_id = entry.get("id")

                if not listing_id:
                    continue

                # Se lo stesso annuncio compare più volte (es. annunci
                # "TOP" ripetuti su più pagine), teniamo la prima
                # occorrenza.
                if listing_id not in collected:
                    collected[listing_id] = entry

        browser.close()

    listings = list(collected.values())

    listings.sort(
        key=lambda item: (
            (item.get("listing") or {}).get("address", {}).get(
                "postalCode"
            )
            or "9999",
            item.get("id") or "",
        )
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "source": "homegate",
        "area": "lausanne",
        "source_url": SOURCE_URL,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "count": len(listings),
        "listings": listings,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with_coords = sum(
        bool(
            ((item.get("listing") or {}).get("address") or {}).get(
                "geoCoordinates"
            )
        )
        for item in listings
    )

    with_price = sum(
        bool(((item.get("listing") or {}).get("prices") or {}).get("rent"))
        for item in listings
    )

    print()
    print("======================")
    print("HOMEGATE INDEX RESULT")
    print("======================")
    print("Unique listings:", len(listings))
    print("With coordinates:", with_coords)
    print("With price:", with_price)
    print()
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
