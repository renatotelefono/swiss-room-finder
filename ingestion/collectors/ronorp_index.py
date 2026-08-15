import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


URL = "https://ronorp.net/zurich-en/market/housing"

OUTPUT_FILE = Path(
    "data/raw/ronorp/zurich-housing-index.json"
)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def is_real_listing(url: str, text: str) -> bool:
    parsed = urlparse(url)

    # Deve appartenere a Ron Orp
    if parsed.hostname not in {
        "ronorp.net",
        "www.ronorp.net",
    }:
        return False

    # Deve essere un annuncio
    if not parsed.path.startswith("/market/posts/"):
        return False

    # Ron Orp espone anche link numerici duplicati:
    # /market/posts/3721256
    # Li scartiamo.
    if re.fullmatch(
        r"/market/posts/\d+/?",
        parsed.path,
    ):
        return False

    # Deve avere del testo utile
    if not text.strip():
        return False

    return True


def extract_price(text: str):
    match = re.search(
        r"CHF\s*([\d'’]+(?:[.,]\d+)?)",
        text,
        re.IGNORECASE,
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


def collect_listings():
    print("Starting Ron Orp collector...")

    with sync_playwright() as p:

        print("Launching Chromium...")

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1400,
                "height": 1200,
            }
        )

        print(f"Opening: {URL}")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(5000)

        print()
        print("Page title:")
        print(page.title())
        print()

        # Scrolliamo per permettere alla pagina
        # di caricare eventuali altri annunci.
        previous_height = 0

        for step in range(15):

            current_height = page.evaluate(
                "document.body.scrollHeight"
            )

            print(
                f"Scroll {step + 1}: "
                f"height={current_height}"
            )

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(1500)

            new_height = page.evaluate(
                "document.body.scrollHeight"
            )

            if (
                new_height == current_height
                and current_height == previous_height
            ):
                break

            previous_height = current_height

        print()
        print("Reading links...")

        links = page.locator("a").evaluate_all(
            """
            elements => elements.map(a => ({
                href: a.href,
                text: (a.innerText || '').trim()
            }))
            """
        )

        browser.close()

    listings = {}

    for link in links:

        url = link.get("href", "")

        text = normalize_text(
            link.get("text", "")
        )

        if not is_real_listing(
            url,
            text,
        ):
            continue

        listings[url] = {
            "url": url,
            "link_text": text,
            "price_chf": extract_price(text),
        }

    return list(listings.values())


def save_listings(listings):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "source": "ronorp",
        "area": "zurich",
        "source_url": URL,
        "fetched_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "count": len(listings),
        "listings": listings,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main():

    listings = collect_listings()

    print()
    print(
        f"Found {len(listings)} real listings."
    )

    print()

    for index, listing in enumerate(
        listings[:10],
        start=1,
    ):

        print(
            f"{index:02d}. "
            f"Price: {listing['price_chf']} CHF"
        )

        print(
            f"    {listing['link_text'][:120]}"
        )

        print(
            f"    {listing['url']}"
        )

        print()

    save_listings(listings)

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()