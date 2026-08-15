import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.homegate.ch/"
    "louer/appartement/sc-chambre/"
    "region-lausanne/liste-annonces"
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
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )

    print()
    print("======================")
    print("HOMEGATE PROBE")
    print("======================")

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


    lower = response.text.lower()


    tests = [
        "70 résultats",
        "lausanne",
        "CHF",
        "surface habitable",
        "avenue",
        "chambre",
        "400",
        "application/ld+json",
        "__NEXT_DATA__",
    ]


    print()
    print("RAW HTML SEARCH")
    print("----------------------")


    for value in tests:
        print(
            f"{value!r}:",
            value.lower()
            in lower,
        )


    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )


    print()
    print("TITLE:")
    print(
        soup.title.get_text(
            " ",
            strip=True,
        )
        if soup.title
        else None
    )


    #
    # Cerchiamo link ai singoli immobili.
    #
    listing_links = []


    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor.get(
            "href"
        )

        if not href:
            continue


        if (
            "/rent/"
            in href
            or
            "/louer/"
            in href
        ):

            text = " ".join(
                anchor.get_text(
                    " ",
                    strip=True,
                ).split()
            )


            if (
                "CHF"
                in text
                or
                len(text) > 40
            ):

                listing_links.append(
                    (
                        href,
                        text,
                    )
                )


    print()
    print(
        "Possible listing links:",
        len(listing_links),
    )


    print()
    print("FIRST 10")
    print("----------------------")


    for index, (
        href,
        text,
    ) in enumerate(
        listing_links[:10],
        start=1,
    ):

        print()
        print(
            f"{index}."
        )

        print(
            "URL:",
            href,
        )

        print(
            "TEXT:",
            text[:500],
        )


    #
    # Salviamo l'HTML per eventuale debug.
    #
    output = (
        "data/raw/homegate/"
        "homegate-probe.html"
    )


    from pathlib import Path


    path = Path(
        output
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    path.write_text(
        response.text,
        encoding="utf-8",
    )


    print()
    print(
        "Saved:",
        path,
    )


if __name__ == "__main__":
    main()