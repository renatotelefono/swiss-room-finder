"""
update_all_data.py

Script unico per rilanciare l'intera pipeline dati di Swiss Room Finder:

    collector (index)
        -> collector (details)
        -> normalizzazione
        -> geocoding
        -> export GeoJSON finale
        -> copia dentro frontend/public/data

Va eseguito con il Python del virtual environment del progetto,
dalla cartella principale del repository (dove si trova questo file).

Esempio (PowerShell, Windows):

    .\.venv\Scripts\python.exe update_all_data.py

Ogni fase viene eseguita come processo separato: se una fase fallisce
(sito cambiato, blocco anti-bot, rete assente, ecc.) lo script lo segnala
ma prosegue comunque con le fasi successive, così un problema su una
sola fonte non blocca l'aggiornamento delle altre.

Fonti NON incluse in questa pipeline perché non ancora collegate al
dataset finale:
  - Anibis (solo raccolta indice, nessuna normalizzazione/geocoding)
  - WGZimmer (il sito blocca lo scraping automatico con reCAPTCHA)

Alla fine dello script, controlla l'esito con:

    git status
    git diff --stat

e poi fai tu commit/push quando sei soddisfatto dei nuovi dati.
"""

import subprocess
import sys
import shutil
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


# ============================================================
# DEFINIZIONE PIPELINE
# ============================================================
#
# Ogni fonte è una lista di script Python da eseguire in ordine.
# I percorsi sono relativi alla radice del repository.

SOURCES = {
    "Ron Orp - Zurigo": [
        "ingestion/collectors/ronorp_index.py",
        "ingestion/collectors/ronorp_details.py",
        "ingestion/normalization/normalize_listings.py",
        "ingestion/geocoding/geocode.py",
    ],
    "Ron Orp - Romandie (Losanna)": [
        "ingestion/collectors/ronorp_romandie_index.py",
        "ingestion/collectors/ronorp_romandie_details.py",
        "ingestion/normalization/normalize_romandie.py",
        "ingestion/geocoding/geocode_romandie.py",
    ],
    "immobilier.ch - Losanna": [
        "ingestion/collectors/immobilier_index.py",
        "ingestion/collectors/immobilier_details.py",
        "ingestion/geocoding/geocode_immobilier.py",
    ],
    "Flatfox - Losanna": [
        "ingestion/collectors/flatfox_index.py",
        "ingestion/collectors/flatfox_details.py",
        "ingestion/geocoding/geocode_flatfox.py",
    ],
    "Homegate - Losanna": [
        "ingestion/collectors/homegate_index.py",
        "ingestion/collectors/homegate_details.py",
        "ingestion/normalization/normalize_homegate.py",
        "ingestion/geocoding/geocode_homegate.py",
    ],
}


# Script di export, da eseguire DOPO che tutte le fonti sopra
# sono state processate (combinano i dati di più fonti).

EXPORT_STEPS = [
    "ingestion/export/generate_lausanne_combined_geojson.py",
    "ingestion/export/merge_geojson.py",
]


# Copie finali dentro il frontend, usate direttamente dalla mappa.

FRONTEND_COPIES = [
    (
        "data/final/listings.geojson",
        "frontend/public/data/listings.geojson",
    ),
    (
        "data/final/swiss-listings.geojson",
        "frontend/public/data/swiss-listings.geojson",
    ),
]


# ============================================================
# ESECUZIONE
# ============================================================

def run_script(relative_path):
    """
    Esegue uno script Python della pipeline come processo separato,
    mostrando l'output in tempo reale.

    Ritorna True se lo script è terminato con successo, False altrimenti.
    """

    script_path = REPO_ROOT / relative_path

    if not script_path.exists():
        print(f"  [SALTATO] File non trovato: {relative_path}")
        return False

    print(f"\n{'-' * 60}")
    print(f"  Eseguo: {relative_path}")
    print(f"{'-' * 60}")

    started = time.time()

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
    )

    elapsed = time.time() - started

    if result.returncode == 0:
        print(f"  OK ({elapsed:.1f}s): {relative_path}")
        return True

    print(
        f"  ERRORE (codice {result.returncode}, "
        f"{elapsed:.1f}s): {relative_path}"
    )
    return False


def run_source(name, scripts):
    print(f"\n{'=' * 60}")
    print(f"FONTE: {name}")
    print(f"{'=' * 60}")

    results = []

    for script in scripts:
        ok = run_script(script)
        results.append((script, ok))

        if not ok:
            print(
                f"  Proseguo comunque con le fasi successive "
                f"di '{name}' (i dati potrebbero essere incompleti)."
            )

    return results


def copy_to_frontend():
    print(f"\n{'=' * 60}")
    print("COPIA DEI FILE FINALI NEL FRONTEND")
    print(f"{'=' * 60}")

    copied = []

    for source_rel, dest_rel in FRONTEND_COPIES:
        source = REPO_ROOT / source_rel
        dest = REPO_ROOT / dest_rel

        if not source.exists():
            print(f"  [SALTATO] Manca: {source_rel}")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)

        print(f"  Copiato: {source_rel} -> {dest_rel}")
        copied.append(dest_rel)

    return copied


def main():
    print("Swiss Room Finder - Aggiornamento completo dei dati")
    print(f"Repository: {REPO_ROOT}")
    print(f"Python: {sys.executable}")

    all_results = {}

    for name, scripts in SOURCES.items():
        all_results[name] = run_source(name, scripts)

    print(f"\n{'=' * 60}")
    print("EXPORT FINALE (combina tutte le fonti)")
    print(f"{'=' * 60}")

    export_results = []

    for script in EXPORT_STEPS:
        ok = run_script(script)
        export_results.append((script, ok))

    copied_files = copy_to_frontend()

    # ========================================================
    # RIEPILOGO
    # ========================================================

    print(f"\n{'=' * 60}")
    print("RIEPILOGO")
    print(f"{'=' * 60}\n")

    for name, results in all_results.items():
        failed = [script for script, ok in results if not ok]

        if failed:
            print(f"[PARZIALE] {name}: problemi in {', '.join(failed)}")
        else:
            print(f"[OK] {name}")

    failed_exports = [script for script, ok in export_results if not ok]

    if failed_exports:
        print(f"[PARZIALE] Export: problemi in {', '.join(failed_exports)}")
    else:
        print("[OK] Export GeoJSON")

    if copied_files:
        print(f"[OK] Copiati nel frontend: {', '.join(copied_files)}")
    else:
        print(
            "[ATTENZIONE] Nessun file copiato nel frontend: "
            "controlla gli errori sopra."
        )

    print(
        "\nControlla ora le modifiche con:\n"
        "  git status\n"
        "  git diff --stat\n"
        "e poi fai commit/push quando sei soddisfatto dei nuovi dati."
    )


if __name__ == "__main__":
    main()
