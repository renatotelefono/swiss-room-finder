# Swiss Room Finder — Struttura e logica del progetto

## 1. Obiettivo

Il progetto **Swiss Room Finder** ha lo scopo di raccogliere annunci immobiliari disponibili online in Svizzera, normalizzarli in un formato JSON comune e prepararli per una futura applicazione con mappa geografica e filtri.

In questa fase il progetto è pensato per **uso personale** e non per la pubblicazione dei dati.

L'approccio scelto è volutamente semplice:

1. raccogliere gli annunci da una fonte reale;
2. salvare gli URL e i dati principali in un file JSON;
3. aprire i singoli annunci;
4. estrarre e normalizzare i dettagli;
5. salvare il risultato in un secondo JSON;
6. in una fase successiva aggiungere geocoding, coordinate e visualizzazione su mappa.

## 2. Sito attualmente utilizzato

La fonte attualmente integrata è:

**Ron Orp — Market / Housing**

Pagina utilizzata per la ricerca degli annunci:

`https://ronorp.net/zurich-en/market/housing`

Gli annunci individuali utilizzano URL del tipo:

`https://ronorp.net/market/posts/...`

Il collector attuale è configurato sulla sezione immobiliare dell'area di Zurigo.

La pagina carica gli annunci dinamicamente tramite JavaScript. Per questo motivo il progetto utilizza **Playwright** con Chromium anziché una semplice richiesta HTTP con `requests`.

Durante i test, il collector è riuscito a individuare circa **121 annunci reali** nella pagina Housing di Zurigo.

## 3. Struttura utile del progetto

La struttura essenziale da mantenere è:

```text
swiss-room-finder/
│
├── .venv/
│
├── data/
│   ├── raw/
│   │   └── ronorp/
│   │       └── zurich-housing-index.json
│   │
│   └── processed/
│       └── ronorp-listings.json
│
├── ingestion/
│   └── collectors/
│       ├── ronorp_index.py
│       └── ronorp_details.py
│
├── .gitignore
├── requirements.txt
│
└── .vscode/
    └── settings.json
```

La cartella `.vscode/` è opzionale, ma utile per fare in modo che Visual Studio Code utilizzi il Python presente nel virtual environment `.venv`.

## 4. File principali

### `ingestion/collectors/ronorp_index.py`

È il primo stadio della pipeline.

Responsabilità:

- apre la pagina Housing di Ron Orp;
- utilizza Playwright e Chromium;
- aspetta l'esecuzione del JavaScript;
- scorre progressivamente la pagina;
- individua i link degli annunci;
- elimina i link duplicati o non rilevanti;
- estrae già alcune informazioni semplici, come il prezzo;
- salva l'indice degli annunci in JSON.

Input principale:

`https://ronorp.net/zurich-en/market/housing`

Output:

`data/raw/ronorp/zurich-housing-index.json`

Schema semplificato dell'output:

```json
{
  "source": "ronorp",
  "area": "zurich",
  "source_url": "https://ronorp.net/zurich-en/market/housing",
  "count": 121,
  "listings": [
    {
      "url": "https://ronorp.net/market/posts/...",
      "link_text": "CHF 2'640.00 / Monthly 3.5 Zürich",
      "price_chf": 2640.0
    }
  ]
}
```

Questo file rappresenta il **dataset grezzo dell'indice**.

### `ingestion/collectors/ronorp_details.py`

È il secondo stadio della pipeline.

Legge:

`data/raw/ronorp/zurich-housing-index.json`

Per ogni annuncio:

1. apre l'URL con Playwright;
2. legge il contenuto renderizzato della pagina;
3. identifica il titolo;
4. isola il contenuto dell'annuncio principale;
5. estrae i principali dati strutturati;
6. conserva anche il testo originale;
7. salva gli annunci normalizzati.

Output:

`data/processed/ronorp-listings.json`

Campi attualmente estratti o normalizzati:

- fonte;
- URL originale;
- titolo;
- prezzo mensile;
- valuta;
- città;
- CAP;
- numero di locali;
- superficie in m²;
- piano, quando disponibile;
- appartamento arredato;
- tipologia di immobile;
- tipo di contratto;
- data di disponibilità iniziale;
- data di disponibilità finale;
- durata minima del contratto;
- eventuali restrizioni;
- descrizione sintetica;
- testo originale dell'annuncio;
- eventuale URL esterno;
- data di acquisizione;
- stato dell'annuncio.

Esempio semplificato:

```json
{
  "source": "ronorp",
  "source_url": "https://ronorp.net/market/posts/...",
  "title": "3½ ROOM APARTMENT IN ZÜRICH...",
  "price": {
    "monthly": 2640.0,
    "currency": "CHF"
  },
  "location": {
    "address": null,
    "postal_code": "8003",
    "city": "Zürich",
    "country": "CH",
    "latitude": null,
    "longitude": null
  },
  "property": {
    "type": "apartment",
    "rooms": 3.5,
    "size_m2": 65.0,
    "furnished": true
  },
  "contract": {
    "type": "temporary",
    "available_from": "2026-09-19",
    "available_to": "2027-01-09",
    "minimum_months": 3
  }
}
```

## 5. Cartella `data/raw`

Percorso:

`data/raw/ronorp/`

Contiene i dati raccolti direttamente dalla fonte, prima della normalizzazione completa.

File principale:

### `zurich-housing-index.json`

Contiene:

- URL degli annunci;
- testo sintetico del link;
- prezzo eventualmente ricavato dall'indice;
- informazioni sulla fonte;
- data di acquisizione.

Questo file è importante perché permette di separare la fase di **discovery degli annunci** dalla fase di **estrazione dei dettagli**.

## 6. Cartella `data/processed`

Percorso:

`data/processed/`

File principale:

### `ronorp-listings.json`

Contiene gli annunci elaborati e normalizzati.

È il file che in futuro verrà utilizzato dalla parte grafica dell'applicazione.

Il frontend non dovrà conoscere la struttura originale di Ron Orp: dovrà leggere solamente il formato normalizzato prodotto dal collector.

## 7. `requirements.txt`

Contiene le dipendenze Python del progetto.

Le librerie principali utilizzate sono:

- `playwright`
- `beautifulsoup4`
- `requests`

Attualmente Playwright è la libreria più importante perché Ron Orp carica gli annunci tramite JavaScript.

Per aggiornare il file:

```powershell
.\.venv\Scripts\python.exe -m pip freeze > requirements.txt
```

## 8. `.venv`

È il virtual environment Python del progetto.

Contiene:

- Python utilizzato dal progetto;
- Playwright;
- Requests;
- BeautifulSoup;
- altre dipendenze.

Per attivarlo in PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Per verificare quale Python viene utilizzato:

```powershell
python -c "import sys; print(sys.executable)"
```

Il percorso corretto deve essere simile a:

```text
C:\Users\HP\Desktop\swiss-room-finder\.venv\Scripts\python.exe
```

## 9. `.vscode/settings.json`

File opzionale ma consigliato.

Serve a dire a Visual Studio Code di utilizzare il Python del virtual environment.

Esempio:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
  "python.terminal.activateEnvironment": true
}
```

## 10. Logica completa di funzionamento

La pipeline attuale è:

```text
Ron Orp
https://ronorp.net/zurich-en/market/housing
        │
        ▼
ronorp_index.py
        │
        │ Playwright apre Chromium
        │ esegue JavaScript
        │ scorre la pagina
        │ trova gli annunci
        ▼
data/raw/ronorp/
zurich-housing-index.json
        │
        ▼
ronorp_details.py
        │
        │ apre ogni annuncio
        │ estrae i dettagli
        │ normalizza i dati
        │ conserva description_raw
        ▼
data/processed/
ronorp-listings.json
        │
        ▼
futuro geocoding
        │
        ▼
latitude / longitude
        │
        ▼
futura applicazione web
        │
        ▼
mappa + poligono + filtri
```

## 11. Perché vengono mantenuti due JSON

Il progetto separa intenzionalmente i dati in due livelli.

### RAW

`zurich-housing-index.json`

Rappresenta ciò che è stato raccolto dalla sorgente.

### PROCESSED

`ronorp-listings.json`

Rappresenta ciò che l'applicazione utilizzerà.

Questa separazione permette di migliorare in futuro il parser senza dover necessariamente ricostruire tutto il processo da zero.

## 12. Stato attuale del progetto

Al momento sono già stati verificati:

- funzionamento del virtual environment;
- funzionamento di Playwright;
- avvio di Chromium;
- caricamento dinamico di Ron Orp;
- scrolling automatico;
- individuazione di circa 121 annunci;
- estrazione degli URL;
- estrazione del prezzo;
- apertura dei singoli annunci;
- estrazione di città e CAP;
- estrazione del numero di locali;
- estrazione della superficie;
- riconoscimento dei contratti `temporary` e `permanent`;
- riconoscimento di varie date di disponibilità;
- riconoscimento di alcune durate minime;
- distinzione iniziale tra appartamento e appartamento condiviso.

## 13. Limiti attuali

### Indirizzo

In alcuni annunci Ron Orp espone un indirizzo completo nel campo che oggi viene interpretato come città.

Esempio:

```text
Badenerstrasse 356, 8004 Zürich
```

In futuro dovrà diventare:

```json
{
  "address": "Badenerstrasse 356",
  "postal_code": "8004",
  "city": "Zürich"
}
```

### Disponibilità

Alcuni annunci esprimono la disponibilità nel testo libero e il parser attuale non riconosce ancora tutti i formati.

### Restrizioni

Campi come:

- solo studenti;
- solo donne;
- solo uomini;
- animali non ammessi;
- fumatori non ammessi;
- limiti di età;

devono essere ulteriormente affinati.

### Coordinate

`latitude` e `longitude` non sono ancora presenti.

Saranno aggiunte nella futura fase di geocoding.

## 14. Prossime fasi previste

La sequenza consigliata è:

1. completare la raccolta dei dettagli dei 121 annunci;
2. verificare la qualità dei dati;
3. separare correttamente indirizzo, CAP e città;
4. migliorare il parser delle date;
5. migliorare il parser delle restrizioni;
6. aggiungere geocoding;
7. salvare latitudine e longitudine;
8. produrre un dataset JSON definitivo;
9. aggiungere una seconda fonte;
10. sviluppare la visualizzazione su mappa.

## 15. File temporanei già eliminabili

I seguenti file erano utilizzati esclusivamente durante i test e non fanno parte della pipeline definitiva:

```text
check_python.py
ronorp_probe.py
ronorp_detail_probe.py
ronorp_index_old.py
wgzimmer_index.py
```

Possono essere eliminati una volta verificato che:

- `ronorp_index.py` funziona;
- `ronorp_details.py` funziona;
- Playwright è configurato correttamente.

## 16. Nota su WGZimmer

WGZimmer è stato analizzato come possibile fonte iniziale.

La pagina restituiva però il messaggio:

```text
The processing of the request was stopped by Google reCaptcha
```

Per questo motivo WGZimmer è stato momentaneamente escluso dalla pipeline.

Il progetto attuale fa quindi riferimento **solamente a Ron Orp**.

WGZimmer potrà eventualmente essere rivalutato in una fase successiva con una strategia diversa e nel rispetto delle condizioni di utilizzo del sito.

## 17. Principio del progetto

La filosofia attuale è:

```text
raccogliere prima dati reali
        ↓
capire cosa è realmente disponibile
        ↓
normalizzare
        ↓
affinare progressivamente
        ↓
aggiungere geocoding
        ↓
costruire la mappa
```

Non viene introdotto un database finché il volume dei dati non lo rende realmente necessario.

Per il momento la persistenza è basata su file JSON.
