from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL = (
    "https://flatfox.ch/fr/search/"
    "?east=6.720815"
    "&north=46.601862"
    "&query=Lausanne"
    "&south=46.494140"
    "&west=6.560625"
    "&offerType=RENT"
)


OUTPUT_FILE = Path(
    "data/raw/flatfox/flatfox-probe.html"
)


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


def clean(value):
    if not value:
        return ""

    return " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    )


def main():
    print()
    print("======================")
    print("FLATFOX PROBE")
    print("======================")
    print()

    print(
        "Opening:",
        URL,
    )

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )

    print(
        "HTTP:",
        response.status_code,
    )

    print(
        "Final URL:",
        response.url,
    )

    print(
        "HTML length:",
        len(response.text),
    )

    print()

    lower_html = (
        response.text.lower()
    )

    tests = [
        "lausanne",
        "chambre",
        "colocation",
        "location",
        "chf",
        "/fr/flat/",
        "meublé",
        "disponibilité",
    ]

    print(
        "RAW HTML SEARCH"
    )

    print(
        "----------------------"
    )

    for value in tests:
        print(
            f"{value!r}:",
            value.lower()
            in lower_html,
        )


    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )


    print()
    print(
        "TITLE:"
    )

    print(
        clean(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )
        if soup.title
        else None
    )


    #
    # Cerchiamo link ai singoli annunci.
    #
    listings = {}

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor.get(
            "href"
        )

        if not href:
            continue

        if "/fr/flat/" not in href:
            continue

        absolute_url = urljoin(
            URL,
            href,
        )

        absolute_url = (
            absolute_url
            .split("#")[0]
            .split("?")[0]
            .rstrip("/")
        )

        text = clean(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        existing = listings.get(
            absolute_url
        )

        if (
            existing is None
            or len(text)
            > len(existing)
        ):
            listings[
                absolute_url
            ] = text


    print()
    print(
        "Unique listing URLs:",
        len(listings),
    )


    print()
    print(
        "FIRST 15"
    )

    print(
        "----------------------"
    )


    for index, (
        url,
        text,
    ) in enumerate(
        list(
            listings.items()
        )[:15],
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
    # Salviamo l'HTML per debug.
    #
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        response.text,
        encoding="utf-8",
    )

    print()
    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()