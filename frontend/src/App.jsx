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


function filterGeoJSON(
  originalGeoJSON,
  selectedArea
) {
  if (!originalGeoJSON) {
    return null;
  }


  if (selectedArea === "all") {
    return originalGeoJSON;
  }


  return {
    ...originalGeoJSON,

    features:
      originalGeoJSON.features.filter(
        (feature) =>
          feature.properties?.area
          === selectedArea
      ),
  };
}


function App() {
  const mapContainerRef =
    useRef(null);

  const mapRef =
    useRef(null);

  const originalGeoJSONRef =
    useRef(null);


  const [
    selectedArea,
    setSelectedArea,
  ] = useState("all");


  const [
    visibleCount,
    setVisibleCount,
  ] = useState(0);


  const [
    dataLoaded,
    setDataLoaded,
  ] = useState(false);


  /*
   * CREA LA MAPPA UNA SOLA VOLTA
   */
  useEffect(() => {
    if (mapRef.current) {
      return;
    }


    const map = new Map({
      container:
        mapContainerRef.current,

      style:
        mapStyle,

      center:
        AREA_VIEW.all.center,

      zoom:
        AREA_VIEW.all.zoom,
    });


    mapRef.current = map;


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


          setVisibleCount(
            geojson.features.length
          );


          /*
           * SOURCE GEOJSON
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
           * CLUSTER
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
           * NUMERO NEL CLUSTER
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
           * PUNTI SINGOLI
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
           * CLICK SU CLUSTER
           */
          map.on(
            "click",
            "clusters",
            async (event) => {
              const features =
                map.queryRenderedFeatures(
                  event.point,
                  {
                    layers: [
                      "clusters",
                    ],
                  }
                );


              if (
                features.length === 0
              ) {
                return;
              }


              const feature =
                features[0];


              const clusterId =
                feature
                  .properties
                  .cluster_id;


              const source =
                map.getSource(
                  "listings"
                );


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
            }
          );


          /*
           * CLICK SU ANNUNCIO
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
                feature.properties;


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
                Number(
                  properties
                    .price_monthly
                );


              if (
                Number.isFinite(
                  monthlyPrice
                )
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
                  properties.postal_code,
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
               * PRECISIONE
               */
              const precision =
                document.createElement(
                  "p"
                );


              precision.className =
                "popup-precision";


              if (
                properties
                  .location_precision
                === "address"
              ) {
                precision.textContent =
                  "● Posizione precisa";
              } else {
                precision.textContent =
                  "○ Posizione approssimativa";
              }


              popup.appendChild(
                precision
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
                  "Apri annuncio ";


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
           * POINTER
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
            geojson.features.length
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

      mapRef.current = null;
    };
  }, []);


  /*
   * CAMBIO AREA
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
        selectedArea
      );


    const source =
      mapRef.current.getSource(
        "listings"
      );


    if (source) {
      /*
       * Aggiorniamo direttamente i dati
       * della source GeoJSON.
       */
      source.setData(
        filtered
      );
    }


    setVisibleCount(
      filtered.features.length
    );


    const view =
      AREA_VIEW[selectedArea];


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


  return (
    <div className="app">

      <header className="header">

        <div>
          <h1>
            Swiss Room Finder
          </h1>

          <p>
            Annunci 
          </p>
        </div>


        <div className="header-controls">

          <label
            className="area-control"
          >
            <span>
              Area
            </span>

            <select
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


          <div className="header-stats">
            {visibleCount} annunci
          </div>

        </div>

      </header>


      <div className="map-wrapper">

        <div
          ref={mapContainerRef}
          className="map"
        />


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