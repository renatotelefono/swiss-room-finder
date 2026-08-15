import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.immobilier.ch"

PAGE_URL = (
    "https://www.immobilier.ch/fr/louer/"
    "appartement-maison/vaud/"
    "lausanne-1004/page-{page}?group=1"
)

OUTPUT_FILE = Path(
    "data/raw/immobilier/lausanne-index.json"
)

MAX_PAGES = 10

WAIT_SECONDS = 1.0


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/127.0 Safari/537.36"
    ),
    "Accept-Language":
        "fr-CH,fr;q=0.9,en;q=0.8",
}


def normalize_text(value):
    if not value:
        return ""

    return " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )


def clean_url(url):
    parsed = urlparse(url)

    return (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
        f"{parsed.path}"
    ).rstrip("/")


def is_listing_url(url):
    """
    Esempio:

    https://www.immobilier.ch/fr/louer/
    appartement/vaud/lausanne/
    room-estate-1443/
    coliving-moderne-...-1552253
    """

    parsed = urlparse(url)

    if (
        parsed.netloc
        not in {
            "www.immobilier.ch",
            "immobilier.ch",
        }
    ):
        return False

    path = parsed.path.rstrip("/")

    if not path.startswith(
        "/fr/louer/"
    ):
        return False

    #
    # Gli annunci finiscono normalmente
    # con un ID numerico.
    #
    if not re.search(
        r"-\d{6,9}$",
        path,
    ):
        return False

    return True


def extract_price(text):
    """
    Esempi:

    CHF 1'290.-/mois
    CHF 795.-/mois (+100.- charges)
    """

    if not text:
        return None

    match = re.search(
        r"CHF\s*([\d'’\s]+)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = (
        match.group(1)
        .replace(" ", "")
        .replace("'", "")
        .replace("’", "")
    )

    try:
        price = float(value)

        if price >= 100:
            return price

    except ValueError:
        pass

    return None


def extract_postal_code(text):
    if not text:
        return None

    match = re.search(
        r"\b([1-9]\d{3})\b",
        text,
    )

    if match:
        return match.group(1)

    return None


def get_card_text(anchor):
    """
    Risale nel DOM cercando un contenitore
    che contenga titolo, prezzo e località.
    """

    current = anchor

    best_text = normalize_text(
        anchor.get_text(
            " ",
            strip=True,
        )
    )

    for _ in range(7):

        current = current.parent

        if current is None:
            break

        text = normalize_text(
            current.get_text(
                " ",
                strip=True,
            )
        )

        if (
            len(text)
            > len(best_text)
            and len(text) < 2500
        ):
            best_text = text

        if (
            "CHF" in text
            and len(text) < 1200
        ):
            return text

    return best_text


def collect_page(
    session,
    page_number,
):
    url = PAGE_URL.format(
        page=page_number
    )

    print()
    print(
        "----------------------"
    )

    print(
        f"PAGE {page_number}"
    )

    print(
        "----------------------"
    )

    print(
        "Opening:",
        url,
    )

    response = session.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    print(
        "HTTP:",
        response.status_code,
    )

    response.raise_for_status()

    html = response.text

    #
    # Evitiamo di continuare in caso
    # di eventuale challenge anti-bot.
    #
    lower_html = html.lower()

    if (
        "just a moment" in lower_html
        or "checking your browser"
        in lower_html
    ):
        raise RuntimeError(
            "Anti-bot challenge detected."
        )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    listings = {}

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor.get(
            "href"
        )

        absolute_url = urljoin(
            BASE_URL,
            href,
        )

        if not is_listing_url(
            absolute_url
        ):
            continue

        listing_url = clean_url(
            absolute_url
        )

        card_text = get_card_text(
            anchor
        )

        anchor_text = normalize_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        price = extract_price(
            card_text
        )

        postal_code = (
            extract_postal_code(
                card_text
            )
        )

        candidate = {
            "url":
                listing_url,

            "title":
                anchor_text
                or None,

            "price_chf":
                price,

            "postal_code":
                postal_code,

            "card_text":
                card_text,
        }

        existing = listings.get(
            listing_url
        )

        if existing is None:
            listings[
                listing_url
            ] = candidate

            continue

        #
        # Se ci sono più link allo stesso
        # annuncio, conserviamo la versione
        # con più informazioni.
        #
        if (
            len(
                candidate[
                    "card_text"
                ]
            )
            >
            len(
                existing[
                    "card_text"
                ]
            )
        ):
            listings[
                listing_url
            ] = candidate

    return list(
        listings.values()
    )


def main():
    session = requests.Session()

    collected = {}

    previous_page_urls = set()


    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):

        try:
            page_listings = (
                collect_page(
                    session,
                    page_number,
                )
            )

        except Exception as exc:
            print(
                "ERROR:",
                repr(exc),
            )

            break


        current_urls = {
            item["url"]
            for item in page_listings
        }


        print(
            "Listings on page:",
            len(page_listings),
        )


        if (
            page_number > 1
            and current_urls
            == previous_page_urls
        ):
            print(
                "Same page detected."
            )

            break


        new_count = 0


        for listing in page_listings:

            url = listing[
                "url"
            ]

            if url not in collected:
                collected[
                    url
                ] = listing

                new_count += 1


        print(
            "New:",
            new_count,
        )

        print(
            "Total unique:",
            len(collected),
        )


        if not page_listings:
            print(
                "No listings found."
            )

            break


        if (
            page_number > 1
            and new_count == 0
        ):
            print(
                "No new listings."
            )

            break


        previous_page_urls = (
            current_urls
        )


        time.sleep(
            WAIT_SECONDS
        )


    listings = list(
        collected.values()
    )


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    output = {
        "source":
            "immobilier.ch",

        "source_section":
            "lausanne",

        "source_url":
            PAGE_URL.format(
                page=1
            ),

        "collected_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(listings),

        "listings":
            listings,
    }


    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


    with_price = sum(
        listing[
            "price_chf"
        ]
        is not None

        for listing in listings
    )


    with_postal = sum(
        bool(
            listing[
                "postal_code"
            ]
        )

        for listing in listings
    )


    print()
    print(
        "======================"
    )

    print(
        "IMMOBILIER.CH LAUSANNE"
    )

    print(
        "======================"
    )


    print(
        "Unique listings:",
        len(listings),
    )

    print(
        "With price:",
        with_price,
    )

    print(
        "With postal code:",
        with_postal,
    )


    print()
    print(
        "First 15:"
    )


    for index, listing in enumerate(
        listings[:15],
        start=1,
    ):

        print()
        print(
            f"{index}."
        )

        print(
            "  Price:",
            listing[
                "price_chf"
            ],
        )

        print(
            "  CAP:",
            listing[
                "postal_code"
            ],
        )

        print(
            "  Title:",
            (
                listing[
                    "title"
                ]
                or ""
            )[:120],
        )

        print(
            "  URL:",
            listing[
                "url"
            ],
        )


    print()

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()