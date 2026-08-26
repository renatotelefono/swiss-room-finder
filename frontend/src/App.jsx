import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Map,
  NavigationControl,
  Popup,
  setWorkerUrl,
} from "maplibre-gl";

import workerUrl
  from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

import "maplibre-gl/dist/maplibre-gl.css";
import "./App.css";


setWorkerUrl(workerUrl);


/*
 * ============================================================
 * MAP STYLE
 * ============================================================
 */

const mapStyle = {
  version: 8,

  sources: {
    osm: {
      type: "raster",

      tiles: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],

      tileSize: 256,

      attribution:
        "© OpenStreetMap contributors",
    },
  },

  layers: [
    {
      id: "osm",

      type: "raster",

      source: "osm",
    },
  ],
};


/*
 * ============================================================
 * AREA VIEW
 * ============================================================
 */

const AREA_VIEW = {
  all: {
    center: [
      7.6,
      47.0,
    ],

    zoom: 7,
  },

  zurich: {
    center: [
      8.5417,
      47.3769,
    ],

    zoom: 9,
  },

  lausanne: {
    center: [
      6.6323,
      46.5197,
    ],

    zoom: 9,
  },
};


/*
 * ============================================================
 * FILTER BAR STYLE
 *
 * Usiamo stile inline per evitare di dover modificare
 * App.css in questa prima versione dei filtri.
 * ============================================================
 */

const filterStyles = {
  container: {
    background: "#ffffff",
    borderBottom: "1px solid #e5e7eb",
    padding: "14px 18px",
  },

  grid: {
    display: "grid",
    gridTemplateColumns:
      "repeat(auto-fit, minmax(150px, 1fr))",
    gap: "12px",
    alignItems: "end",
  },

  control: {
    display: "flex",
    flexDirection: "column",
    gap: "5px",
  },

  label: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#374151",
  },

  input: {
    width: "100%",
    minHeight: "38px",
    padding: "8px 10px",
    border: "1px solid #d1d5db",
    borderRadius: "6px",
    background: "#ffffff",
    color: "#111827",
    boxSizing: "border-box",
  },

  resetButton: {
    minHeight: "38px",
    padding: "8px 14px",
    border: "1px solid #d1d5db",
    borderRadius: "6px",
    background: "#f9fafb",
    color: "#111827",
    cursor: "pointer",
    fontWeight: "600",
  },

  statusRow: {
    marginTop: "10px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
    fontSize: "13px",
    color: "#6b7280",
  },

  activeBadge: {
    padding: "3px 8px",
    borderRadius: "999px",
    background: "#eff6ff",
    color: "#1d4ed8",
    fontWeight: "600",
  },
};


/*
 * ============================================================
 * HELPERS
 * ============================================================
 */

function normalizeString(value) {
  if (
    value === null
    || value === undefined
  ) {
    return "";
  }

  return String(value)
    .trim()
    .toLowerCase();
}


function toNumber(value) {
  if (
    value === null
    || value === undefined
    || value === ""
  ) {
    return null;
  }

  if (
    typeof value === "number"
  ) {
    return Number.isFinite(value)
      ? value
      : null;
  }

  const cleaned = String(value)
    .replace(/\s/g, "")
    .replace(/[^\d.,-]/g, "")
    .replace(",", ".");

  const parsed =
    Number.parseFloat(cleaned);

  return Number.isFinite(parsed)
    ? parsed
    : null;
}


function normalizeBoolean(value) {
  if (
    value === true
    || value === false
  ) {
    return value;
  }

  const normalized =
    normalizeString(value);

  if (
    [
      "true",
      "yes",
      "y",
      "1",
      "si",
      "sì",
      "oui",
      "ja",
      "furnished",
      "meuble",
      "meublé",
      "möbliert",
      "arredato",
    ].includes(normalized)
  ) {
    return true;
  }

  if (
    [
      "false",
      "no",
      "n",
      "0",
      "non",
      "unfurnished",
      "non meuble",
      "non meublé",
      "unmöbliert",
      "non arredato",
    ].includes(normalized)
  ) {
    return false;
  }

  return null;
}


function parseListingDate(value) {
  if (!value) {
    return null;
  }

  const raw =
    String(value).trim();

  if (!raw) {
    return null;
  }


  /*
   * ISO YYYY-MM-DD
   */

  const isoMatch =
    raw.match(
      /^(\d{4})-(\d{2})-(\d{2})/
    );

  if (isoMatch) {
    const year =
      Number(isoMatch[1]);

    const month =
      Number(isoMatch[2]) - 1;

    const day =
      Number(isoMatch[3]);

    const date =
      new Date(
        year,
        month,
        day
      );

    if (
      !Number.isNaN(
        date.getTime()
      )
    ) {
      return date;
    }
  }


  /*
   * DD.MM.YYYY
   * DD/MM/YYYY
   */

  const europeanMatch =
    raw.match(
      /^(\d{1,2})[./](\d{1,2})[./](\d{4})$/
    );

  if (europeanMatch) {
    const day =
      Number(europeanMatch[1]);

    const month =
      Number(europeanMatch[2]) - 1;

    const year =
      Number(europeanMatch[3]);

    const date =
      new Date(
        year,
        month,
        day
      );

    if (
      !Number.isNaN(
        date.getTime()
      )
    ) {
      return date;
    }
  }


  /*
   * Ultimo tentativo tramite parser JS.
   */

  const parsed =
    new Date(raw);

  if (
    !Number.isNaN(
      parsed.getTime()
    )
  ) {
    return parsed;
  }

  return null;
}


function propertyTypeLabel(value) {
  const normalized =
    normalizeString(value);

  const labels = {
    apartment:
      "Appartamento",

    private_room:
      "Stanza privata",

    shared_room:
      "Stanza condivisa",

    room:
      "Stanza",

    studio:
      "Studio",

    house:
      "Casa",

    other:
      "Altro",
  };

  return labels[normalized]
    || value
    || "Non specificato";
}


function sourceLabel(value) {
  const normalized =
    normalizeString(value);

  const labels = {
    flatfox:
      "Flatfox",

    "immobilier.ch":
      "immobilier.ch",

    immobilier:
      "immobilier.ch",

    ronorp:
      "Ron Orp",

    "ron orp":
      "Ron Orp",

    anibis:
      "Anibis",

    homegate:
      "Homegate",

    wgzimmer:
      "WGZimmer",
  };

  return labels[normalized]
    || value
    || "Sconosciuta";
}


function getPropertyValue(
  properties,
  candidates
) {
  for (
    const key
    of candidates
  ) {
    if (
      properties?.[key]
      !== undefined
      && properties?.[key]
      !== null
      && properties?.[key]
      !== ""
    ) {
      return properties[key];
    }
  }

  return null;
}


/*
 * ============================================================
 * FILTRO GEOJSON
 * ============================================================
 */

function filterGeoJSON(
  originalGeoJSON,
  filters
) {
  if (!originalGeoJSON) {
    return null;
  }


  const {
    selectedArea,
    minPrice,
    maxPrice,
    propertyType,
    furnished,
    source,
    precision,
    availableBy,
    search,
  } = filters;


  const targetAvailabilityDate =
    availableBy
      ? parseListingDate(
          availableBy
        )
      : null;


  const features =
    originalGeoJSON.features.filter(
      (feature) => {
        const properties =
          feature.properties || {};


        /*
         * RICERCA TESTUALE
         *
         * Cerca nel titolo, città e indirizzo
         * dell'annuncio.
         *
         * La ricerca è limitata agli annunci
         * dell'area di Losanna, indipendentemente
         * dal filtro "Area" selezionato.
         */

        if (search) {
          if (properties.area !== "lausanne") {
            return false;
          }

          const query =
            normalizeString(search);

          const haystack =
            [
              properties.title,
              properties.city,
              properties.address,
              properties.postal_code,
            ]
              .filter(Boolean)
              .map(
                (value) =>
                  normalizeString(value)
              )
              .join(" ");

          if (
            !haystack.includes(query)
          ) {
            return false;
          }
        }


        /*
         * AREA
         */

        if (
          selectedArea !== "all"
          && normalizeString(
            properties.area
          )
          !== normalizeString(
            selectedArea
          )
        ) {
          return false;
        }


        /*
         * PREZZO
         */

        const price =
          toNumber(
            getPropertyValue(
              properties,
              [
                "price_monthly",
                "monthly_price",
                "price",
              ]
            )
          );


        if (
          minPrice !== ""
        ) {
          const minimum =
            toNumber(minPrice);

          if (
            minimum !== null
            && (
              price === null
              || price < minimum
            )
          ) {
            return false;
          }
        }


        if (
          maxPrice !== ""
        ) {
          const maximum =
            toNumber(maxPrice);

          if (
            maximum !== null
            && (
              price === null
              || price > maximum
            )
          ) {
            return false;
          }
        }


        /*
         * PROPERTY TYPE
         */

        if (
          propertyType !== "all"
        ) {
          const listingType =
            normalizeString(
              properties.property_type
            );

          if (
            listingType
            !== normalizeString(
              propertyType
            )
          ) {
            return false;
          }
        }


        /*
         * ARREDATO
         *
         * Se il filtro è attivo ma il dato
         * è sconosciuto, l'annuncio viene escluso.
         */

        if (
          furnished !== "all"
        ) {
          const listingFurnished =
            normalizeBoolean(
              properties.furnished
            );

          if (
            listingFurnished
            === null
          ) {
            return false;
          }


          if (
            furnished === "yes"
            && listingFurnished
            !== true
          ) {
            return false;
          }


          if (
            furnished === "no"
            && listingFurnished
            !== false
          ) {
            return false;
          }
        }


        /*
         * SOURCE
         */

        if (
          source !== "all"
        ) {
          const listingSource =
            normalizeString(
              getPropertyValue(
                properties,
                [
                  "source",
                  "source_name",
                ]
              )
            );

          if (
            listingSource
            !== normalizeString(
              source
            )
          ) {
            return false;
          }
        }


        /*
         * PRECISIONE POSIZIONE
         */

        if (
          precision !== "all"
        ) {
          const listingPrecision =
            normalizeString(
              properties
                .location_precision
            );

          if (
            listingPrecision
            !== normalizeString(
              precision
            )
          ) {
            return false;
          }
        }


        /*
         * DISPONIBILE ENTRO
         *
         * Un annuncio passa se la sua data
         * available_from è <= data scelta.
         *
         * Se non abbiamo una data leggibile,
         * viene escluso quando questo filtro
         * è attivo.
         */

        if (
          targetAvailabilityDate
        ) {
          const listingDate =
            parseListingDate(
              getPropertyValue(
                properties,
                [
                  "available_from",
                  "availability_date",
                  "available",
                ]
              )
            );

          if (!listingDate) {
            return false;
          }


          if (
            listingDate.getTime()
            > targetAvailabilityDate
              .getTime()
          ) {
            return false;
          }
        }


        return true;
      }
    );


  return {
    ...originalGeoJSON,

    features,
  };
}


/*
 * ============================================================
 * APP
 * ============================================================
 */

function App() {
  const mapContainerRef =
    useRef(null);

  const mapRef =
    useRef(null);

  const originalGeoJSONRef =
    useRef(null);


  /*
   * ============================================================
   * FILTER STATES
   * ============================================================
   */

  const [
    search,
    setSearch,
  ] = useState("");


  const [
    selectedArea,
    setSelectedArea,
  ] = useState("all");


  const [
    minPrice,
    setMinPrice,
  ] = useState("");


  const [
    maxPrice,
    setMaxPrice,
  ] = useState("");


  const [
    propertyType,
    setPropertyType,
  ] = useState("all");


  const [
    furnished,
    setFurnished,
  ] = useState("all");


  const [
    selectedSource,
    setSelectedSource,
  ] = useState("all");


  const [
    precision,
    setPrecision,
  ] = useState("all");


  const [
    availableBy,
    setAvailableBy,
  ] = useState("");


  /*
   * ============================================================
   * UI / DATA STATES
   * ============================================================
   */

  const [
    visibleCount,
    setVisibleCount,
  ] = useState(0);


  const [
    totalCount,
    setTotalCount,
  ] = useState(0);


  const [
    dataLoaded,
    setDataLoaded,
  ] = useState(false);


  const [
    propertyTypes,
    setPropertyTypes,
  ] = useState([]);


  const [
    sources,
    setSources,
  ] = useState([]);


  /*
   * ============================================================
   * CREA MAPPA
   * ============================================================
   */

  useEffect(() => {
    if (mapRef.current) {
      return;
    }


    const map =
      new Map({
        container:
          mapContainerRef.current,

        style:
          mapStyle,

        center:
          AREA_VIEW.all.center,

        zoom:
          AREA_VIEW.all.zoom,
      });


    mapRef.current =
      map;


    map.addControl(
      new NavigationControl(),
      "top-right"
    );


    map.on(
      "error",
      (event) => {
        console.error(
          "MAPLIBRE ERROR:",
          event.error
        );
      }
    );


    map.on(
      "load",
      async () => {
        try {
          const response =
            await fetch(
              "/data/swiss-listings.geojson"
            );


          if (!response.ok) {
            throw new Error(
              `GeoJSON HTTP ${response.status}`
            );
          }


          const geojson =
            await response.json();


          originalGeoJSONRef.current =
            geojson;


          const features =
            Array.isArray(
              geojson.features
            )
              ? geojson.features
              : [];


          setVisibleCount(
            features.length
          );


          setTotalCount(
            features.length
          );


          /*
           * ====================================================
           * OPZIONI DINAMICHE PROPERTY TYPE
           * ====================================================
           */

          const detectedPropertyTypes =
            [
              ...new Set(
                features
                  .map(
                    (feature) =>
                      feature
                        .properties
                        ?.property_type
                  )
                  .filter(Boolean)
                  .map(
                    (value) =>
                      String(value)
                        .trim()
                  )
              ),
            ]
              .sort(
                (a, b) =>
                  propertyTypeLabel(a)
                    .localeCompare(
                      propertyTypeLabel(b),
                      "it"
                    )
              );


          setPropertyTypes(
            detectedPropertyTypes
          );


          /*
           * ====================================================
           * OPZIONI DINAMICHE SOURCES
           * ====================================================
           */

          const detectedSources =
            [
              ...new Set(
                features
                  .map(
                    (feature) =>
                      getPropertyValue(
                        feature.properties,
                        [
                          "source",
                          "source_name",
                        ]
                      )
                  )
                  .filter(Boolean)
                  .map(
                    (value) =>
                      String(value)
                        .trim()
                  )
              ),
            ]
              .sort(
                (a, b) =>
                  sourceLabel(a)
                    .localeCompare(
                      sourceLabel(b),
                      "it"
                    )
              );


          setSources(
            detectedSources
          );


          /*
           * ====================================================
           * SOURCE GEOJSON
           * ====================================================
           */

          map.addSource(
            "listings",
            {
              type: "geojson",

              data: geojson,

              cluster: true,

              clusterRadius: 50,

              clusterMaxZoom: 14,
            }
          );


          /*
           * ====================================================
           * CLUSTER
           * ====================================================
           */

          map.addLayer({
            id: "clusters",

            type: "circle",

            source: "listings",

            filter: [
              "has",
              "point_count",
            ],

            paint: {
              "circle-color": [
                "step",

                [
                  "get",
                  "point_count",
                ],

                "#2563eb",

                10,
                "#f59e0b",

                30,
                "#dc2626",
              ],

              "circle-radius": [
                "step",

                [
                  "get",
                  "point_count",
                ],

                18,

                10,
                23,

                30,
                29,
              ],

              "circle-stroke-color":
                "#ffffff",

              "circle-stroke-width":
                2,
            },
          });


          /*
           * ====================================================
           * NUMERO NEL CLUSTER
           * ====================================================
           */

          map.addLayer({
            id: "cluster-count",

            type: "symbol",

            source: "listings",

            filter: [
              "has",
              "point_count",
            ],

            layout: {
              "text-field":
                "{point_count_abbreviated}",

              "text-size":
                13,
            },

            paint: {
              "text-color":
                "#ffffff",
            },
          });


          /*
           * ====================================================
           * PUNTI SINGOLI
           * ====================================================
           */

          map.addLayer({
            id: "unclustered-point",

            type: "circle",

            source: "listings",

            filter: [
              "!",
              [
                "has",
                "point_count",
              ],
            ],

            paint: {
              "circle-color": [
                "case",

                [
                  "==",

                  [
                    "get",
                    "location_precision",
                  ],

                  "address",
                ],

                "#16a34a",

                "#f97316",
              ],

              "circle-radius":
                7,

              "circle-stroke-color":
                "#ffffff",

              "circle-stroke-width":
                2,
            },
          });


          /*
           * ====================================================
           * CLICK CLUSTER
           * ====================================================
           */

          map.on(
            "click",
            "clusters",
            async (event) => {
              const renderedFeatures =
                map.queryRenderedFeatures(
                  event.point,
                  {
                    layers: [
                      "clusters",
                    ],
                  }
                );


              if (
                renderedFeatures.length
                === 0
              ) {
                return;
              }


              const feature =
                renderedFeatures[0];


              const clusterId =
                feature
                  .properties
                  .cluster_id;


              const source =
                map.getSource(
                  "listings"
                );


              if (!source) {
                return;
              }


              try {
                const zoom =
                  await source
                    .getClusterExpansionZoom(
                      clusterId
                    );


                map.easeTo({
                  center:
                    feature
                      .geometry
                      .coordinates,

                  zoom,
                });
              } catch (error) {
                console.error(
                  "ERRORE CLUSTER:",
                  error
                );
              }
            }
          );


          /*
           * ====================================================
           * CLICK ANNUNCIO
           * ====================================================
           */

          map.on(
            "click",
            "unclustered-point",
            (event) => {
              const feature =
                event.features?.[0];


              if (!feature) {
                return;
              }


              const properties =
                feature.properties || {};


              const coordinates =
                feature
                  .geometry
                  .coordinates
                  .slice();


              const popup =
                document.createElement(
                  "div"
                );


              popup.className =
                "listing-popup";


              /*
               * TITOLO
               */

              const title =
                document.createElement(
                  "h3"
                );


              title.textContent =
                properties.title
                || "Annuncio";


              popup.appendChild(
                title
              );


              /*
               * AREA
               */

              const area =
                document.createElement(
                  "p"
                );


              area.className =
                "popup-area";


              if (
                properties.area
                === "lausanne"
              ) {
                area.textContent =
                  "Area Losanna";
              } else if (
                properties.area
                === "zurich"
              ) {
                area.textContent =
                  "Area Zurigo";
              }


              if (
                area.textContent
              ) {
                popup.appendChild(
                  area
                );
              }


              /*
               * PREZZO
               */

              const price =
                document.createElement(
                  "p"
                );


              price.className =
                "popup-price";


              const monthlyPrice =
                toNumber(
                  getPropertyValue(
                    properties,
                    [
                      "price_monthly",
                      "monthly_price",
                      "price",
                    ]
                  )
                );


              if (
                monthlyPrice
                !== null
              ) {
                price.textContent =
                  `${monthlyPrice.toLocaleString(
                    "it-CH"
                  )} CHF / mese`;
              } else {
                price.textContent =
                  "Prezzo non disponibile";
              }


              popup.appendChild(
                price
              );


              /*
               * TIPO IMMOBILE
               */

              if (
                properties
                  .property_type
              ) {
                const typeElement =
                  document.createElement(
                    "p"
                  );


                typeElement.textContent =
                  propertyTypeLabel(
                    properties
                      .property_type
                  );


                popup.appendChild(
                  typeElement
                );
              }


              /*
               * LOCALI + SUPERFICIE
               */

              const details = [];


              if (
                properties.rooms
              ) {
                details.push(
                  `${properties.rooms} locali`
                );
              }


              if (
                properties.size_m2
              ) {
                details.push(
                  `${properties.size_m2} m²`
                );
              }


              if (
                properties
                  .usable_area_m2
              ) {
                details.push(
                  `${properties.usable_area_m2} m² utili`
                );
              }


              if (
                details.length
              ) {
                const detailElement =
                  document.createElement(
                    "p"
                  );


                detailElement.textContent =
                  details.join(" · ");


                popup.appendChild(
                  detailElement
                );
              }


              /*
               * LOCALITÀ
               */

              const locationText =
                [
                  properties
                    .postal_code,

                  properties.city,
                ]
                  .filter(Boolean)
                  .join(" ");


              if (
                locationText
              ) {
                const location =
                  document.createElement(
                    "p"
                  );


                location.textContent =
                  locationText;


                popup.appendChild(
                  location
                );
              }


              /*
               * ARREDATO
               */

              const furnishedValue =
                normalizeBoolean(
                  properties.furnished
                );


              if (
                furnishedValue
                !== null
              ) {
                const furnishedElement =
                  document.createElement(
                    "p"
                  );


                furnishedElement
                  .textContent =
                    furnishedValue
                      ? "Arredato: sì"
                      : "Arredato: no";


                popup.appendChild(
                  furnishedElement
                );
              }


              /*
               * PRECISIONE
               */

              const precisionElement =
                document.createElement(
                  "p"
                );


              precisionElement.className =
                "popup-precision";


              if (
                properties
                  .location_precision
                === "address"
              ) {
                precisionElement
                  .textContent =
                    "● Posizione precisa";
              } else {
                precisionElement
                  .textContent =
                    "○ Posizione approssimativa";
              }


              popup.appendChild(
                precisionElement
              );


              /*
               * DISPONIBILITÀ
               */

              if (
                properties
                  .available_from
              ) {
                const availability =
                  document.createElement(
                    "p"
                  );


                availability.textContent =
                  `Disponibile dal: ${properties.available_from}`;


                popup.appendChild(
                  availability
                );
              }


              /*
               * FONTE
               */

              const listingSource =
                getPropertyValue(
                  properties,
                  [
                    "source",
                    "source_name",
                  ]
                );


              if (
                listingSource
              ) {
                const sourceElement =
                  document.createElement(
                    "p"
                  );


                sourceElement.textContent =
                  `Fonte: ${sourceLabel(
                    listingSource
                  )}`;


                popup.appendChild(
                  sourceElement
                );
              }


              /*
               * LINK
               */

              if (
                properties
                  .source_url
              ) {
                const link =
                  document.createElement(
                    "a"
                  );


                link.href =
                  properties
                    .source_url;


                link.target =
                  "_blank";


                link.rel =
                  "noopener noreferrer";


                link.textContent =
                  "Apri l'annuncio";


                popup.appendChild(
                  link
                );
              }


              new Popup({
                offset: 12,
              })
                .setLngLat(
                  coordinates
                )
                .setDOMContent(
                  popup
                )
                .addTo(
                  map
                );
            }
          );


          /*
           * ====================================================
           * POINTER
           * ====================================================
           */

          [
            "clusters",
            "unclustered-point",
          ].forEach(
            (layerId) => {
              map.on(
                "mouseenter",
                layerId,
                () => {
                  map.getCanvas()
                    .style.cursor =
                    "pointer";
                }
              );


              map.on(
                "mouseleave",
                layerId,
                () => {
                  map.getCanvas()
                    .style.cursor =
                    "";
                }
              );
            }
          );


          setDataLoaded(true);


          console.log(
            "Swiss listings:",
            features.length
          );
        } catch (error) {
          console.error(
            "ERRORE CARICAMENTO:",
            error
          );
        }
      }
    );


    return () => {
      map.remove();

      mapRef.current =
        null;
    };
  }, []);


  /*
   * ============================================================
   * APPLICA TUTTI I FILTRI
   * ============================================================
   */

  useEffect(() => {
    if (
      !dataLoaded
      || !mapRef.current
      || !originalGeoJSONRef.current
    ) {
      return;
    }


    const filtered =
      filterGeoJSON(
        originalGeoJSONRef.current,
        {
          selectedArea,
          minPrice,
          maxPrice,
          propertyType,
          furnished,
          source:
            selectedSource,
          precision,
          availableBy,
          search,
        }
      );


    const source =
      mapRef.current
        .getSource(
          "listings"
        );


    if (source) {
      source.setData(
        filtered
      );
    }


    setVisibleCount(
      filtered.features.length
    );
  }, [
    selectedArea,
    minPrice,
    maxPrice,
    propertyType,
    furnished,
    selectedSource,
    precision,
    availableBy,
    search,
    dataLoaded,
  ]);


  /*
   * ============================================================
   * CAMBIO AREA = SPOSTAMENTO MAPPA
   *
   * Gli altri filtri NON cambiano automaticamente zoom.
   * ============================================================
   */

  useEffect(() => {
    if (
      !dataLoaded
      || !mapRef.current
    ) {
      return;
    }


    const view =
      AREA_VIEW[selectedArea];


    if (!view) {
      return;
    }


    mapRef.current.easeTo({
      center:
        view.center,

      zoom:
        view.zoom,

      duration:
        800,
    });
  }, [
    selectedArea,
    dataLoaded,
  ]);


  /*
   * ============================================================
   * RESET
   * ============================================================
   */

  function resetFilters() {
    setSearch("");

    setSelectedArea("all");

    setMinPrice("");

    setMaxPrice("");

    setPropertyType("all");

    setFurnished("all");

    setSelectedSource("all");

    setPrecision("all");

    setAvailableBy("");
  }


  /*
   * ============================================================
   * NUMERO FILTRI ATTIVI
   * ============================================================
   */

  const activeFilterCount =
    [
      search !== "",

      selectedArea !== "all",

      minPrice !== "",

      maxPrice !== "",

      propertyType !== "all",

      furnished !== "all",

      selectedSource !== "all",

      precision !== "all",

      availableBy !== "",
    ].filter(Boolean).length;


  /*
   * ============================================================
   * RENDER
   * ============================================================
   */

  return (
    <div className="app">

      <header className="header">

        <div>
          <h1>
            Swiss Room Finder
          </h1>

          <p>
            Annunci immobiliari in Svizzera
          </p>
        </div>


        <div className="header-controls">

          <div className="header-stats">
            {visibleCount} annunci
          </div>

        </div>

      </header>


      {/*
       * ========================================================
       * FILTRI
       * ========================================================
       */}

      <section
        style={
          filterStyles.container
        }
      >

        <div
          style={
            filterStyles.grid
          }
        >

          {/*
           * RICERCA
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Cerca
            </span>

            <input
              style={
                filterStyles.input
              }

              type="text"

              placeholder="Titolo, città, indirizzo..."

              value={
                search
              }

              onChange={
                (event) =>
                  setSearch(
                    event.target.value
                  )
              }
            />
          </label>


          {/*
           * AREA
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Area
            </span>

            <select
              style={
                filterStyles.input
              }

              value={
                selectedArea
              }

              onChange={
                (event) =>
                  setSelectedArea(
                    event.target.value
                  )
              }
            >
              <option value="all">
                Tutte
              </option>

              <option value="zurich">
                Zurigo
              </option>

              <option value="lausanne">
                Losanna
              </option>
            </select>
          </label>


          {/*
           * PREZZO MINIMO
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Prezzo min. CHF
            </span>

            <input
              style={
                filterStyles.input
              }

              type="number"

              min="0"

              step="50"

              placeholder="es. 500"

              value={
                minPrice
              }

              onChange={
                (event) =>
                  setMinPrice(
                    event.target.value
                  )
              }
            />
          </label>


          {/*
           * PREZZO MASSIMO
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Prezzo max. CHF
            </span>

            <input
              style={
                filterStyles.input
              }

              type="number"

              min="0"

              step="50"

              placeholder="es. 1500"

              value={
                maxPrice
              }

              onChange={
                (event) =>
                  setMaxPrice(
                    event.target.value
                  )
              }
            />
          </label>


          {/*
           * PROPERTY TYPE
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Tipo
            </span>

            <select
              style={
                filterStyles.input
              }

              value={
                propertyType
              }

              onChange={
                (event) =>
                  setPropertyType(
                    event.target.value
                  )
              }
            >
              <option value="all">
                Tutti
              </option>

              {
                propertyTypes.map(
                  (type) => (
                    <option
                      key={type}
                      value={type}
                    >
                      {
                        propertyTypeLabel(
                          type
                        )
                      }
                    </option>
                  )
                )
              }
            </select>
          </label>


          {/*
           * ARREDATO
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Arredato
            </span>

            <select
              style={
                filterStyles.input
              }

              value={
                furnished
              }

              onChange={
                (event) =>
                  setFurnished(
                    event.target.value
                  )
              }
            >
              <option value="all">
                Tutti
              </option>

              <option value="yes">
                Sì
              </option>

              <option value="no">
                No
              </option>
            </select>
          </label>


          {/*
           * FONTE
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Fonte
            </span>

            <select
              style={
                filterStyles.input
              }

              value={
                selectedSource
              }

              onChange={
                (event) =>
                  setSelectedSource(
                    event.target.value
                  )
              }
            >
              <option value="all">
                Tutte
              </option>

              {
                sources.map(
                  (source) => (
                    <option
                      key={source}
                      value={source}
                    >
                      {
                        sourceLabel(
                          source
                        )
                      }
                    </option>
                  )
                )
              }
            </select>
          </label>


          {/*
           * PRECISIONE
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Posizione
            </span>

            <select
              style={
                filterStyles.input
              }

              value={
                precision
              }

              onChange={
                (event) =>
                  setPrecision(
                    event.target.value
                  )
              }
            >
              <option value="all">
                Tutte
              </option>

              <option value="address">
                Precisa
              </option>

              <option value="postal_code_city">
                Approssimativa
              </option>
            </select>
          </label>


          {/*
           * DISPONIBILE ENTRO
           */}

          <label
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Disponibile entro
            </span>

            <input
              style={
                filterStyles.input
              }

              type="date"

              value={
                availableBy
              }

              onChange={
                (event) =>
                  setAvailableBy(
                    event.target.value
                  )
              }
            />
          </label>


          {/*
           * RESET
           */}

          <div
            style={
              filterStyles.control
            }
          >
            <span
              style={
                filterStyles.label
              }
            >
              Filtri
            </span>

            <button
              type="button"

              style={
                filterStyles.resetButton
              }

              onClick={
                resetFilters
              }
            >
              Reset filtri
            </button>
          </div>

        </div>


        {/*
         * STATUS FILTRI
         */}

        <div
          style={
            filterStyles.statusRow
          }
        >

          <div>
            Mostrati{" "}
            <strong>
              {visibleCount}
            </strong>
            {" "}di{" "}
            <strong>
              {totalCount}
            </strong>
            {" "}annunci
          </div>


          {
            activeFilterCount > 0
              ? (
                  <div
                    style={
                      filterStyles.activeBadge
                    }
                  >
                    {
                      activeFilterCount
                    }{" "}
                    {
                      activeFilterCount
                      === 1
                        ? "filtro attivo"
                        : "filtri attivi"
                    }
                  </div>
                )
              : (
                  <div>
                    Nessun filtro attivo
                  </div>
                )
          }

        </div>

      </section>


      {/*
       * ========================================================
       * MAPPA
       * ========================================================
       */}

      <div className="map-wrapper">

        <div
          ref={
            mapContainerRef
          }

          className="map"
        />


        {/*
         * ======================================================
         * LEGENDA
         * ======================================================
         */}

        <div className="legend">

          <div>
            <span
              className="dot precise"
            />

            Posizione precisa
          </div>


          <div>
            <span
              className="dot approximate"
            />

            Posizione approssimativa
          </div>

        </div>

      </div>

    </div>
  );
}


export default App;