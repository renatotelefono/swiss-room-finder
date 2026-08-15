import json
from pathlib import Path

from playwright.sync_api import sync_playwright


INPUT_FILE = Path(
    "data/raw/immobilier/lausanne-index.json"
)

DEBUG_DIR = Path(
    "data/raw/immobilier/debug"
)


def main():
    source = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    listing = source[
        "listings"
    ][0]

    url = listing["url"]

    print()
    print("======================")
    print("IMMOBILIER PLAYWRIGHT")
    print("======================")
    print()
    print("URL:", url)

    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        #
        # Aspettiamo che l'app JavaScript
        # abbia avuto il tempo di caricare
        # i dettagli.
        #
        try:
            page.locator(
                "h1"
            ).wait_for(
                state="visible",
                timeout=15000,
            )

        except Exception:
            print(
                "H1 non trovato entro 15 secondi"
            )

        page.wait_for_timeout(
            4000
        )

        title = page.title()

        body_text = page.locator(
            "body"
        ).inner_text()

        rendered_html = page.content()

        print()
        print("PAGE TITLE:")
        print(title)

        print()
        print("RENDERED HTML SEARCH")
        print("----------------------")

        tests = [
            "idObject",
            "gpsLatitude",
            "gpsLongitude",
            "1004 Lausanne",
            "23, avenue de Riant-Mont",
            "51 m",
            "1.5 pièce",
            "Disponible de suite",
        ]

        for value in tests:
            print(
                f"{value!r}:",
                value.lower()
                in rendered_html.lower(),
            )

        print()
        print("VISIBLE TEXT SEARCH")
        print("----------------------")

        for value in tests:
            print(
                f"{value!r}:",
                value.lower()
                in body_text.lower(),
            )

        print()
        print("FIRST 100 BODY LINES")
        print("----------------------")

        lines = [
            line.strip()
            for line
            in body_text.splitlines()
            if line.strip()
        ]

        for index, line in enumerate(
            lines[:100],
            start=1,
        ):
            print(
                f"{index:03d}: "
                f"{line[:200]}"
            )

        html_file = (
            DEBUG_DIR
            / "first-detail-rendered.html"
        )

        text_file = (
            DEBUG_DIR
            / "first-detail-rendered.txt"
        )

        html_file.write_text(
            rendered_html,
            encoding="utf-8",
        )

        text_file.write_text(
            body_text,
            encoding="utf-8",
        )

        #
        # Screenshot utile per capire
        # cosa vede effettivamente Chromium.
        #
        screenshot_file = (
            DEBUG_DIR
            / "first-detail-rendered.png"
        )

        page.screenshot(
            path=str(
                screenshot_file
            ),
            full_page=True,
        )

        browser.close()

    print()
    print("Saved HTML:", html_file)
    print("Saved text:", text_file)
    print(
        "Saved screenshot:",
        screenshot_file,
    )


if __name__ == "__main__":
    main()