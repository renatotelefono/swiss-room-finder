import re
from pathlib import Path
from playwright.sync_api import sync_playwright


URL = "https://fr.comparis.ch/immobilien/marktplatz/lausanne/wohnung/mieten"


def main():
    print()
    print("======================")
    print("COMPARIS PLAYWRIGHT PROBE")
    print("======================")
    print()

    output_dir = Path("data/raw/comparis/debug")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

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

        page.wait_for_timeout(5000)

        print(f"HTTP: {response.status if response else 'None'}")
        print(f"Final URL: {page.url}")
        print(f"Title: {page.title()}")

        # Scroll per caricare eventuali contenuti dinamici
        for i in range(3):
            page.evaluate(
                "window.scrollBy(0, window.innerHeight)"
            )

            page.wait_for_timeout(1500)

            scroll_y = page.evaluate("window.scrollY")

            print(f"Scroll {i + 1}: {scroll_y}")

        html = page.content()

        text = page.locator("body").inner_text()

        print()
        print("----------------------")
        print("VISIBLE TEXT SEARCH")
        print("----------------------")

        search_terms = [
            "Lausanne",
            "CHF",
            "Appartement",
            "Chambre",
            "Colocation",
            "Loyer",
            "m²",
        ]

        lower_text = text.lower()

        for term in search_terms:
            found = term.lower() in lower_text
            print(f"{term!r}: {found}")

        print()
        print("----------------------")
        print("LINK ANALYSIS")
        print("----------------------")

        links = page.locator("a").evaluate_all(
            """
            links => links.map(a => ({
                href: a.href,
                text: (a.innerText || '').trim()
            }))
            """
        )

        possible_links = []

        for link in links:
            href = link.get("href", "")
            label = link.get("text", "")

            if (
                href
                and "comparis.ch" in href
                and href != URL
            ):
                possible_links.append(
                    {
                        "url": href,
                        "text": label,
                    }
                )

        # Deduplicazione
        unique = {}

        for item in possible_links:
            unique[item["url"]] = item

        possible_links = list(unique.values())

        print(f"Unique Comparis links: {len(possible_links)}")

        print()
        print("FIRST 30")
        print("----------------------")

        for i, item in enumerate(
            possible_links[:30],
            start=1,
        ):
            print()
            print(f"{i}.")
            print(f"URL: {item['url']}")
            print(f"TEXT: {item['text']}")

        # Salvataggio debug
        html_path = (
            output_dir
            / "comparis-search-rendered.html"
        )

        text_path = (
            output_dir
            / "comparis-search-rendered.txt"
        )

        screenshot_path = (
            output_dir
            / "comparis-search-rendered.png"
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
        print(f"SCREENSHOT: {screenshot_path}")

        browser.close()


if __name__ == "__main__":
    main()