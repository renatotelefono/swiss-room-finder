from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


SOURCE_URL = (
    "https://flatfox.ch/fr/search/"
    "?object_category=SHARED"
    "&offer_type=RENT"
    "&query=Lausanne"
)

DEBUG_DIR = Path(
    "data/raw/flatfox/debug"
)


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

    #
    # Flatfox può cambiare lingua:
    # /fr/flat/
    # /en/flat/
    # /de/flat/
    # /it/flat/
    #
    return any(
        marker in path
        for marker in [
            "/fr/flat/",
            "/en/flat/",
            "/de/flat/",
            "/it/flat/",
        ]
    )


def main():
    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    listings = {}


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
        print("FLATFOX PLAYWRIGHT")
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
            4000
        )


        print(
            "Title:",
            page.title(),
        )


        #
        # Scroll progressivo:
        # la lista può caricare altri risultati
        # man mano che scendiamo.
        #
        previous_height = 0

        for step in range(
            1,
            16,
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
                1200
            )


            current_height = page.evaluate(
                "document.body.scrollHeight"
            )


            print(
                f"Scroll {step}:",
                current_height,
            )


            if (
                current_height
                == previous_height
            ):
                #
                # Facciamo comunque un ultimo
                # tentativo prima di fermarci.
                #
                page.wait_for_timeout(
                    1000
                )

                second_height = (
                    page.evaluate(
                        "document.body.scrollHeight"
                    )
                )

                if (
                    second_height
                    == current_height
                ):
                    break


            previous_height = (
                current_height
            )


        #
        # Ritorniamo in cima.
        #
        page.evaluate(
            """
            window.scrollTo(0, 0)
            """
        )

        page.wait_for_timeout(
            500
        )


        body_text = page.locator(
            "body"
        ).inner_text()


        print()
        print("VISIBLE TEXT SEARCH")
        print("----------------------")


        tests = [
            "Lausanne",
            "CHF",
            "Chambre",
            "colocation",
            "louer",
            "meublé",
        ]


        for value in tests:
            print(
                f"{value!r}:",
                value.lower()
                in body_text.lower(),
            )


        #
        # Recuperiamo tutti i link presenti
        # nel DOM renderizzato.
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


            try:
                text = clean(
                    anchor.inner_text(
                        timeout=500
                    )
                )

            except Exception:
                text = ""


            existing = listings.get(
                url
            )


            if (
                existing is None
                or len(text)
                > len(existing)
            ):
                listings[url] = text


        print()
        print(
            "Unique listing URLs:",
            len(listings),
        )


        print()
        print("FIRST 20")
        print("----------------------")


        for index, (
            url,
            text,
        ) in enumerate(
            list(
                listings.items()
            )[:20],
            start=1,
        ):

            print()
            print(
                f"{index}."
            )

            print(
                "URL:",
                url,
            )

            print(
                "TEXT:",
                text[:500],
            )


        #
        # Salviamo DOM renderizzato e testo,
        # utili per costruire il collector vero.
        #
        html_file = (
            DEBUG_DIR
            / "flatfox-search-rendered.html"
        )

        text_file = (
            DEBUG_DIR
            / "flatfox-search-rendered.txt"
        )

        screenshot_file = (
            DEBUG_DIR
            / "flatfox-search-rendered.png"
        )


        html_file.write_text(
            page.content(),
            encoding="utf-8",
        )

        text_file.write_text(
            body_text,
            encoding="utf-8",
        )

        page.screenshot(
            path=str(
                screenshot_file
            ),
            full_page=True,
        )


        browser.close()


    print()
    print(
        "Saved HTML:",
        html_file,
    )

    print(
        "Saved text:",
        text_file,
    )

    print(
        "Saved screenshot:",
        screenshot_file,
    )


if __name__ == "__main__":
    main()