import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


SOURCE_URL = "https://ronorp.net/romandie/market/housing"

OUTPUT_FILE = Path(
    "data/raw/ronorp_romandie/romandie-housing-index.json"
)

SCROLL_COUNT = 15
SCROLL_WAIT_MS = 1500


def normalize_text(value):
    if not value:
        return ""

    return " ".join(
        value.replace("\xa0", " ").split()
    )


def extract_price(text):
    """
    Cerca prezzi del tipo:

    CHF 2'640
    CHF2'640.00
    CHF 1380
    """

    if not text:
        return None

    match = re.search(
        r"CHF\s*([\d'’.,]+)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = match.group(1)

    value = (
        value
        .replace("'", "")
        .replace("’", "")
        .replace(",", "")
    )

    try:
        return float(value)

    except ValueError:
        return None


def is_listing_url(url):
    """
    Mantiene solo gli URL reali degli annunci.

    Ron Orp espone anche URL numerici come:
    /market/posts/3721256

    che eliminiamo perché normalmente esiste
    anche la versione slug più utile.
    """

    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    if not path.startswith(
        "/market/posts/"
    ):
        return False

    last_part = path.split("/")[-1]

    if re.fullmatch(
        r"\d+",
        last_part,
    ):
        return False

    return True


def collect_listings():
    listings = []

    seen_urls = set()

    with sync_playwright() as playwright:

        print(
            "Opening:",
            SOURCE_URL,
        )

        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            }
        )

        page.goto(
            SOURCE_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(
            3000
        )

        print(
            "Title:",
            page.title(),
        )

        print()
        print(
            "Scrolling page..."
        )

        previous_height = 0

        for index in range(
            SCROLL_COUNT
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

            current_height = page.evaluate(
                "document.body.scrollHeight"
            )

            print(
                f"Scroll {index + 1}: "
                f"{current_height}"
            )

            if (
                current_height
                == previous_height
            ):
                #
                # Facciamo comunque un secondo
                # tentativo prima di terminare.
                #
                page.wait_for_timeout(
                    1000
                )

            previous_height = (
                current_height
            )

        print()
        print(
            "Reading links..."
        )

        anchors = page.locator(
            "a"
        )

        count = anchors.count()

        for index in range(
            count
        ):
            anchor = anchors.nth(
                index
            )

            try:
                href = anchor.get_attribute(
                    "href"
                )

                text = anchor.inner_text(
                    timeout=2000
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

            #
            # Elimina query string e frammenti.
            #
            parsed = urlparse(
                absolute_url
            )

            clean_url = (
                f"{parsed.scheme}://"
                f"{parsed.netloc}"
                f"{parsed.path}"
            ).rstrip("/")

            if clean_url in seen_urls:
                continue

            normalized_text = (
                normalize_text(
                    text
                )
            )

            #
            # Gli URL slug hanno normalmente
            # testo utile. Evitiamo link vuoti.
            #
            if not normalized_text:
                continue

            seen_urls.add(
                clean_url
            )

            listings.append(
                {
                    "url": clean_url,

                    "link_text":
                        normalized_text,

                    "price_chf":
                        extract_price(
                            normalized_text
                        ),
                }
            )

        browser.close()

    return listings


def main():
    listings = (
        collect_listings()
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source": "ronorp",

        "source_section":
            "romandie",

        "source_url":
            SOURCE_URL,

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

    print()
    print(
        "----------------------"
    )

    print(
        "RON ORP ROMANDIE"
    )

    print(
        "----------------------"
    )

    print(
        "Found:",
        len(listings),
        "real listings",
    )

    print()

    for index, listing in enumerate(
        listings[:10],
        start=1,
    ):
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
            "  Text:",
            listing[
                "link_text"
            ][:150],
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