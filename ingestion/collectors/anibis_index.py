import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


SOURCE_URL = (
    "https://www.anibis.ch/fr/q/"
    "immobilier-vaud-chambres-en-colocation/"
    "Ak8CqcmVhbEVzdGF0ZZSRkqtsaXN0aW5nVHlwZalmbGF0U2hhcmXAwJGTqGxvY2F0aW9ur2dlby1jYW50b24tdmF1ZMA"
)

OUTPUT_FILE = Path(
    "data/raw/anibis/vaud-flatshare-index.json"
)

MAX_PAGES = 20
PAGE_WAIT_MS = 2200


def normalize_text(value):
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
    """
    URL attesi:

    /fr/vi/vaud/immobilier/chambres-en-colocation/
    titolo-annuncio/54716194
    """

    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    if (
        "/fr/vi/vaud/immobilier/"
        "chambres-en-colocation/"
        not in path
    ):
        return False

    last_part = path.split("/")[-1]

    return bool(
        re.fullmatch(
            r"\d+",
            last_part,
        )
    )


def extract_price(text):
    """
    Esempi Anibis:

    850.- par mois
    1 204.- par mois
    CHF 950
    """

    if not text:
        return None

    patterns = [
        r"\b([\d][\d\s'’]*)\.-\s*par\s+mois\b",
        r"\bCHF\s*([\d][\d\s'’]*)",
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
            price = float(value)

            if price >= 100:
                return price

        except ValueError:
            pass

    return None


def extract_location(text):
    """
    Cerca stringhe come:

    Lausanne, 1004
    Renens VD, 1020
    Pully, 1009
    """

    if not text:
        return {
            "city": None,
            "postal_code": None,
        }

    match = re.search(
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'’./-]*?),\s*(\d{4})\b",
        text,
    )

    if not match:
        return {
            "city": None,
            "postal_code": None,
        }

    city = normalize_text(
        match.group(1)
    )

    postal_code = (
        match.group(2)
    )

    return {
        "city": city,
        "postal_code": postal_code,
    }


def get_card_text(anchor):
    """
    Risale alcuni livelli nel DOM per trovare
    il contenitore che include:

    località
    titolo
    descrizione
    prezzo

    Non dipende da una classe CSS specifica,
    quindi è più resistente ai cambiamenti
    grafici del sito.
    """

    try:
        text = anchor.evaluate(
            """
            (a) => {
                let element = a;

                let best = (
                    a.innerText
                    || ""
                ).trim();

                for (
                    let i = 0;
                    i < 7 && element;
                    i++
                ) {
                    const text = (
                        element.innerText
                        || ""
                    ).trim();

                    if (
                        text.length > best.length
                        &&
                        text.length < 5000
                    ) {
                        best = text;
                    }

                    if (
                        /par mois/i.test(text)
                        &&
                        /\\b\\d{4}\\b/.test(text)
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

        return normalize_text(
            text
        )

    except Exception:
        return ""


def collect_visible_listings(
    page,
    collected,
):
    anchors = page.locator(
        'a[href*="/fr/vi/vaud/immobilier/chambres-en-colocation/"]'
    )

    anchor_count = anchors.count()

    found_on_page = set()


    for index in range(
        anchor_count
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


        found_on_page.add(
            url
        )


        try:
            anchor_text = normalize_text(
                anchor.inner_text(
                    timeout=1000
                )
            )

        except Exception:
            anchor_text = ""


        card_text = get_card_text(
            anchor
        )


        location = extract_location(
            card_text
        )


        price = extract_price(
            card_text
        )


        #
        # Potrebbero esserci più link allo stesso
        # annuncio (immagine + titolo).
        #
        # Manteniamo la versione con il testo
        # più utile.
        #
        existing = collected.get(
            url
        )


        candidate = {
            "url": url,

            "title":
                anchor_text
                if (
                    anchor_text
                    and not anchor_text.isdigit()
                )
                else None,

            "price_chf":
                price,

            "city":
                location["city"],

            "postal_code":
                location[
                    "postal_code"
                ],

            "card_text":
                card_text,
        }


        if existing is None:
            collected[url] = (
                candidate
            )

        else:
            #
            # Aggiorna titolo se troviamo
            # un anchor migliore.
            #
            if (
                candidate["title"]
                and (
                    not existing[
                        "title"
                    ]
                    or len(
                        candidate[
                            "title"
                        ]
                    )
                    >
                    len(
                        existing[
                            "title"
                        ]
                    )
                )
            ):
                existing["title"] = (
                    candidate["title"]
                )


            if (
                existing[
                    "price_chf"
                ]
                is None
                and candidate[
                    "price_chf"
                ]
                is not None
            ):
                existing[
                    "price_chf"
                ] = candidate[
                    "price_chf"
                ]


            if (
                not existing[
                    "city"
                ]
                and candidate[
                    "city"
                ]
            ):
                existing[
                    "city"
                ] = candidate[
                    "city"
                ]


            if (
                not existing[
                    "postal_code"
                ]
                and candidate[
                    "postal_code"
                ]
            ):
                existing[
                    "postal_code"
                ] = candidate[
                    "postal_code"
                ]


            if (
                len(
                    candidate[
                        "card_text"
                    ]
                )
                >
                len(
                    existing[
                        "card_text"
                    ]
                )
            ):
                existing[
                    "card_text"
                ] = candidate[
                    "card_text"
                ]


    return found_on_page


def click_page_number(
    page,
    page_number,
):
    """
    Anibis usa pulsanti per la paginazione.

    Cerchiamo il pulsante numerico visibile
    corrispondente e scegliamo l'ultimo:
    normalmente quello nel paginator in fondo.
    """

    page.evaluate(
        """
        window.scrollTo(
            0,
            document.body.scrollHeight
        )
        """
    )

    page.wait_for_timeout(
        800
    )


    buttons = page.locator(
        "button"
    )

    candidates = []


    for index in range(
        buttons.count()
    ):
        button = buttons.nth(
            index
        )

        try:
            if not button.is_visible():
                continue

            text = normalize_text(
                button.inner_text(
                    timeout=500
                )
            )

        except Exception:
            continue


        if text == str(
            page_number
        ):
            candidates.append(
                button
            )


    if not candidates:
        return False


    target = candidates[-1]


    try:
        target.scroll_into_view_if_needed()

        page.wait_for_timeout(
            300
        )

        target.click(
            timeout=5000
        )

        page.wait_for_timeout(
            PAGE_WAIT_MS
        )

        page.evaluate(
            """
            window.scrollTo(
                0,
                0
            )
            """
        )

        page.wait_for_timeout(
            500
        )

        return True

    except Exception as exc:

        print(
            "Pagination click error:",
            repr(exc),
        )

        return False


def main():
    collected = {}


    with sync_playwright() as playwright:

        browser = (
            playwright.chromium.launch(
                headless=True
            )
        )


        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            }
        )


        print(
            "Opening:",
            SOURCE_URL,
        )


        page.goto(
            SOURCE_URL,
            wait_until=
                "domcontentloaded",
            timeout=60000,
        )


        page.wait_for_timeout(
            3000
        )


        print(
            "Title:",
            page.title(),
        )


        previous_page_urls = set()


        for page_number in range(
            1,
            MAX_PAGES + 1,
        ):

            print()
            print(
                "----------------------"
            )

            print(
                f"PAGE {page_number}"
            )

            print(
                "----------------------"
            )


            page.wait_for_timeout(
                1000
            )


            current_urls = (
                collect_visible_listings(
                    page,
                    collected,
                )
            )


            print(
                "Listings on page:",
                len(
                    current_urls
                ),
            )


            print(
                "Total unique:",
                len(
                    collected
                ),
            )


            #
            # Se dopo aver cambiato pagina
            # vediamo esattamente gli stessi URL,
            # qualcosa non ha funzionato.
            #
            if (
                page_number > 1
                and current_urls
                == previous_page_urls
            ):
                print(
                    "Same listings as "
                    "previous page."
                )

                break


            previous_page_urls = (
                current_urls
            )


            next_page = (
                page_number + 1
            )


            clicked = (
                click_page_number(
                    page,
                    next_page,
                )
            )


            if not clicked:

                print()
                print(
                    "No next page button."
                )

                break


        browser.close()


    listings = list(
        collected.values()
    )


    #
    # Ordinamento semplice per località
    # e titolo, solo per rendere il JSON
    # più leggibile.
    #
    listings.sort(
        key=lambda item: (
            item.get("postal_code")
            or "9999",

            item.get("city")
            or "",

            item.get("title")
            or "",
        )
    )


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    output = {
        "source":
            "anibis",

        "source_section":
            "vaud_flatshare",

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


    with_price = sum(
        item[
            "price_chf"
        ]
        is not None

        for item in listings
    )


    with_postal = sum(
        bool(
            item[
                "postal_code"
            ]
        )

        for item in listings
    )


    with_city = sum(
        bool(
            item[
                "city"
            ]
        )

        for item in listings
    )


    print()
    print(
        "======================"
    )

    print(
        "ANIBIS VAUD INDEX"
    )

    print(
        "======================"
    )


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
    print(
        "First 15:"
    )


    for index, item in enumerate(
        listings[:15],
        start=1,
    ):

        print()
        print(
            f"{index}."
        )

        print(
            "  City:",
            item["city"],
        )

        print(
            "  CAP:",
            item[
                "postal_code"
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
            (
                item["title"]
                or ""
            )[:120],
        )

        print(
            "  URL:",
            item["url"],
        )


    print()

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()