import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup


INPUT_FILE = Path(
    "data/raw/immobilier/lausanne-index.json"
)

DEBUG_DIR = Path(
    "data/raw/immobilier/debug"
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
    print(
        "======================"
    )
    print(
        "IMMOBILIER PROBE"
    )
    print(
        "======================"
    )
    print()
    print(
        "URL:",
        url,
    )

    response = requests.get(
        url,
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
        "Content-Type:",
        response.headers.get(
            "content-type"
        ),
    )

    print(
        "HTML length:",
        len(response.text),
    )

    raw_html = response.text

    tests = [
        "idObject",
        "gpsLatitude",
        "gpsLongitude",
        "__NEXT_DATA__",
        "application/ld+json",
        "1004 Lausanne",
        "Disponible",
        "51 m",
        "Attique",
    ]

    print()
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
            in raw_html.lower(),
        )

    soup = BeautifulSoup(
        raw_html,
        "html.parser",
    )

    print()
    print(
        "TITLE TAG:"
    )

    print(
        soup.title.get_text(
            " ",
            strip=True,
        )
        if soup.title
        else None
    )

    print()
    print(
        "H1:"
    )

    h1 = soup.find("h1")

    print(
        h1.get_text(
            " ",
            strip=True,
        )
        if h1
        else None
    )

    #
    # Test JSON-LD
    #
    json_ld = soup.find_all(
        "script",
        attrs={
            "type":
                "application/ld+json"
        },
    )

    print()
    print(
        "JSON-LD scripts:",
        len(json_ld),
    )

    for index, script in enumerate(
        json_ld[:5],
        start=1,
    ):
        content = (
            script.string
            or script.get_text()
            or ""
        )

        print()
        print(
            f"JSON-LD #{index}:"
        )

        print(
            content[:1000]
        )

    #
    # Cerca script che contengano
    # parole interessanti.
    #
    interesting_scripts = []

    for script in soup.find_all(
        "script"
    ):
        content = (
            script.string
            or script.get_text()
            or ""
        )

        lower = content.lower()

        if any(
            key.lower() in lower
            for key in [
                "idObject",
                "gpsLatitude",
                "gpsLongitude",
                "zipcode",
            ]
        ):
            interesting_scripts.append(
                content
            )

    print()
    print(
        "Interesting scripts:",
        len(
            interesting_scripts
        ),
    )

    for index, content in enumerate(
        interesting_scripts[:3],
        start=1,
    ):
        print()
        print(
            f"SCRIPT #{index}:"
        )

        print(
            content[:2000]
        )

    #
    # Testo visibile.
    #
    text = soup.get_text(
        "\n",
        strip=True,
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    print()
    print(
        "VISIBLE TEXT LINES:",
        len(lines),
    )

    print()
    print(
        "FIRST 80 TEXT LINES"
    )
    print(
        "----------------------"
    )

    for index, line in enumerate(
        lines[:80],
        start=1,
    ):
        print(
            f"{index:03d}: "
            f"{line[:200]}"
        )

    #
    # Salviamo tutto per debugging.
    #
    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_file = (
        DEBUG_DIR
        / "first-detail.html"
    )

    text_file = (
        DEBUG_DIR
        / "first-detail-text.txt"
    )

    html_file.write_text(
        raw_html,
        encoding="utf-8",
    )

    text_file.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print()
    print(
        "Saved HTML:",
        html_file,
    )

    print(
        "Saved text:",
        text_file,
    )


if __name__ == "__main__":
    main()