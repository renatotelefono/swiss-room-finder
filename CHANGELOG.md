# Changelog

Tutte le modifiche importanti di Swiss Room Finder vengono registrate qui.

Il progetto utilizza Semantic Versioning:

- MAJOR: modifiche incompatibili o grandi cambiamenti architetturali
- MINOR: nuove funzionalità
- PATCH: correzioni e piccoli miglioramenti


## [0.1.0] - 2026-08-15

### Added

- Mappa interattiva della Svizzera con MapLibre.
- Area Zurigo.
- Area Losanna.
- Clustering degli annunci.
- Distinzione tra posizione precisa e approssimativa.
- Popup degli annunci.
- Link alla fonte originale.
- Collector Ron Orp.
- Collector immobilier.ch.
- Collector Flatfox.
- Geocoding tramite geo.admin.ch / swisstopo.
- Dataset combinato Zurigo + Losanna.
- Audit dei duplicati cross-source.
- Deploy statico tramite Netlify.

### Data

- Zurigo: 118 annunci.
- Losanna: 144 annunci.
- Dataset complessivo: 262 annunci.
- Flatfox Losanna: 48 annunci.

### Notes

Questa versione rappresenta la baseline stabile prima
dell'introduzione del sistema avanzato di filtri.