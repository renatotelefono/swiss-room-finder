import re
from pathlib import Path
from playwright.sync_api import sync_playwright


URL = (
    "https://www.newhome.ch/fr/louer/"
    "appartement/region-lausanne"
)


def main():
    print()
    print("======================")
    print("NEWHOME PLAYWRIGHT PROBE")
    print("======================")
    print()

    output_dir = Path("data/raw/newhome/debug")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        print(f"Opening: {URL}")

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(3000)

        print(
            f"HTTP: {response.status if response else 'None'}"
        )

        print(
            f"Final URL: {page.url}"
        )

        print(
            f"Title: {page.title()}"
        )

        # Scroll per caricare eventuali annunci dinamici
        for i in range(3):
            page.evaluate(
                "window.scrollBy(0, window.innerHeight)"
            )

            page.wait_for_timeout(1500)

            print(
                f"Scroll {i + 1}: "
                f"{page.evaluate('window.scrollY')}"
            )

        html = page.content()

        text = page.locator("body").inner_text()

        print()
        print("----------------------")
        print("VISIBLE TEXT SEARCH")
        print("----------------------")

        search_terms = [
            "Lausanne",
            "CHF",
            "louer",
            "appartement",
            "chambre",
            "colocation",
            "pièce",
            "m²",
        ]

        lower_text = text.lower()

        for term in search_terms:
            found = term.lower() in lower_text

            print(
                f"{term!r}: {found}"
            )

        # Cerca tutti i link
        links = page.locator("a").evaluate_all(
            """
            links => links.map(a => ({
                href: a.href,
                text: (a.innerText || '').trim()
            }))
            """
        )

        listing_urls = []

        for link in links:
            href = link.get("href", "")
            label = link.get("text", "")

            # Filtriamo URL potenzialmente relativi agli annunci
            if (
                href
                and "newhome.ch" in href
                and href != URL
            ):
                if re.search(
                    r"/fr/.*(louer|objet|immobilier|appartement|studio|chambre)",
                    href,
                    re.IGNORECASE,
                ):
                    listing_urls.append(
                        {
                            "url": href,
                            "text": label,
                        }
                    )

        # Deduplicazione
        unique = {}

        for item in listing_urls:
            unique[item["url"]] = item

        listing_urls = list(unique.values())

        print()
        print("----------------------")
        print("POSSIBLE LISTING URLS")
        print("----------------------")

        print(
            f"Unique listing URLs: {len(listing_urls)}"
        )

        print()
        print("FIRST 20")
        print("----------------------")

        for i, item in enumerate(
            listing_urls[:20],
            start=1,
        ):
            print()
            print(f"{i}.")
            print(f"URL: {item['url']}")
            print(f"TEXT: {item['text']}")

        # Salvataggi debug
        html_path = (
            output_dir
            / "newhome-search-rendered.html"
        )

        text_path = (
            output_dir
            / "newhome-search-rendered.txt"
        )

        screenshot_path = (
            output_dir
            / "newhome-search-rendered.png"
        )

        html_path.write_text(
            html,
            encoding="utf-8",
        )

        text_path.write_text(
            text,
            encoding="utf-8",
        )

        page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )

        print()
        print("----------------------")
        print("SAVED DEBUG FILES")
        print("----------------------")

        print(f"HTML: {html_path}")
        print(f"TEXT: {text_path}")
        print(
            f"SCREENSHOT: {screenshot_path}"
        )

        browser.close()


if __name__ == "__main__":
    main()