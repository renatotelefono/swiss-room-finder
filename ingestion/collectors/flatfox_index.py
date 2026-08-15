import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


SOURCE_URL = (
    "https://flatfox.ch/fr/search/"
    "?object_category=SHARED"
    "&offer_type=RENT"
    "&query=Lausanne"
)

OUTPUT_FILE = Path(
    "data/raw/flatfox/lausanne-shared-index.json"
)


WAIT_AFTER_LOAD_MS = 4000
SCROLL_WAIT_MS = 1200
MAX_SCROLLS = 15


def clean(value):
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
    parsed = urlparse(url)

    path = parsed.path.lower()

    return any(
        marker in path
        for marker in [
            "/fr/flat/",
            "/en/flat/",
            "/de/flat/",
            "/it/flat/",
        ]
    )


def get_source_id(url):
    path = urlparse(
        url
    ).path.rstrip("/")

    last_part = (
        path.split("/")[-1]
    )

    if re.fullmatch(
        r"\d+",
        last_part,
    ):
        return last_part

    return None


def parse_location(text):
    """
    Esempi:

    Chambre en colocation 1020 Renens
    Chambre en colocation 1004 Lausanne
    Chambre en colocation 1024 Ecublens VD
    """

    match = re.search(
        r"\b(\d{4})\s+(.+)$",
        text,
    )

    if not match:
        return {
            "postal_code": None,
            "city": None,
        }

    return {
        "postal_code":
            match.group(1),

        "city":
            clean(
                match.group(2)
            ),
    }


def get_card_text(anchor):
    """
    Cerca un contenitore superiore che possa
    contenere prezzo, località e altre
    informazioni del risultato.
    """

    try:
        result = anchor.evaluate(
            """
            (a) => {
                let element = a;
                let best = (
                    a.innerText || ""
                ).trim();

                for (
                    let i = 0;
                    i < 7 && element;
                    i++
                ) {
                    const text = (
                        element.innerText || ""
                    ).trim();

                    if (
                        text.length > best.length
                        &&
                        text.length < 3000
                    ) {
                        best = text;
                    }

                    if (
                        /CHF/i.test(text)
                        &&
                        /\\b\\d{4}\\b/.test(text)
                        &&
                        text.length < 1500
                    ) {
                        return text;
                    }

                    element =
                        element.parentElement;
                }

                return best;
            }
            """
        )

        return clean(
            result
        )

    except Exception:
        return ""


def extract_price(text):
    if not text:
        return None

    patterns = [
        r"CHF\s*([\d'’\s]+)",
        r"([\d'’\s]+)\s*CHF",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = (
            match.group(1)
            .replace(" ", "")
            .replace("'", "")
            .replace("’", "")
        )

        try:
            price = float(
                value
            )

            if price >= 100:
                return price

        except ValueError:
            pass

    return None


def main():
    collected = {}

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            },

            locale="fr-CH",
        )

        print()
        print("======================")
        print("FLATFOX INDEX")
        print("======================")
        print()

        print(
            "Opening:",
            SOURCE_URL,
        )

        response = page.goto(
            SOURCE_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        print(
            "HTTP:",
            (
                response.status
                if response
                else None
            ),
        )

        page.wait_for_timeout(
            WAIT_AFTER_LOAD_MS
        )

        print(
            "Title:",
            page.title(),
        )

        #
        # Scroll per eventuali risultati
        # caricati progressivamente.
        #
        previous_height = None

        for step in range(
            1,
            MAX_SCROLLS + 1,
        ):

            page.evaluate(
                """
                window.scrollTo(
                    0,
                    document.body.scrollHeight
                )
                """
            )

            page.wait_for_timeout(
                SCROLL_WAIT_MS
            )

            current_height = (
                page.evaluate(
                    "document.body.scrollHeight"
                )
            )

            print(
                f"Scroll {step}:",
                current_height,
            )

            if (
                previous_height
                == current_height
            ):
                break

            previous_height = (
                current_height
            )

        #
        # Recupera tutti i link annuncio.
        #
        anchors = page.locator(
            "a[href]"
        )

        for index in range(
            anchors.count()
        ):

            anchor = anchors.nth(
                index
            )

            try:
                href = (
                    anchor.get_attribute(
                        "href"
                    )
                )

            except Exception:
                continue

            if not href:
                continue

            absolute_url = urljoin(
                SOURCE_URL,
                href,
            )

            if not is_listing_url(
                absolute_url
            ):
                continue

            url = clean_url(
                absolute_url
            )

            source_id = (
                get_source_id(
                    url
                )
            )

            #
            # Ignora URL strani che non
            # terminano con l'ID numerico.
            #
            if not source_id:
                continue

            try:
                anchor_text = clean(
                    anchor.inner_text(
                        timeout=500
                    )
                )

            except Exception:
                anchor_text = ""

            card_text = (
                get_card_text(
                    anchor
                )
            )

            location = (
                parse_location(
                    anchor_text
                )
            )

            price = (
                extract_price(
                    card_text
                )
            )

            candidate = {
                "source":
                    "flatfox",

                "source_id":
                    source_id,

                "url":
                    url,

                "title":
                    anchor_text
                    or None,

                "price_chf":
                    price,

                "postal_code":
                    location[
                        "postal_code"
                    ],

                "city":
                    location[
                        "city"
                    ],

                "card_text":
                    card_text
                    or None,
            }

            existing = (
                collected.get(
                    url
                )
            )

            if existing is None:
                collected[
                    url
                ] = candidate
                continue

            #
            # Se lo stesso annuncio compare
            # più volte, conserva la versione
            # con più informazioni.
            #
            if (
                len(
                    candidate.get(
                        "card_text"
                    )
                    or ""
                )
                >
                len(
                    existing.get(
                        "card_text"
                    )
                    or ""
                )
            ):
                collected[
                    url
                ] = candidate

        browser.close()

    listings = list(
        collected.values()
    )

    listings.sort(
        key=lambda item: (
            item.get(
                "postal_code"
            )
            or "9999",

            item.get(
                "city"
            )
            or "",

            item.get(
                "source_id"
            )
            or "",
        )
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source":
            "flatfox",

        "source_section":
            "lausanne_shared",

        "source_url":
            SOURCE_URL,

        "collected_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(
                listings
            ),

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
        item.get(
            "price_chf"
        )
        is not None

        for item in listings
    )

    with_postal = sum(
        bool(
            item.get(
                "postal_code"
            )
        )

        for item in listings
    )

    with_city = sum(
        bool(
            item.get(
                "city"
            )
        )

        for item in listings
    )

    print()
    print("======================")
    print("FLATFOX INDEX RESULT")
    print("======================")

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

    print(
        "With city:",
        with_city,
    )

    print()
    print("First 15:")

    for index, item in enumerate(
        listings[:15],
        start=1,
    ):

        print()
        print(
            f"{index}."
        )

        print(
            "  CAP:",
            item[
                "postal_code"
            ],
        )

        print(
            "  City:",
            item[
                "city"
            ],
        )

        print(
            "  Price:",
            item[
                "price_chf"
            ],
        )

        print(
            "  Title:",
            item[
                "title"
            ],
        )

        print(
            "  URL:",
            item[
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