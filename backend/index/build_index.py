"""Indicizzazione dei markdown FI in blocchi strutturati.

Uso:
    uv run python index/build_index.py
    uv run python index/build_index.py --check

Il registro dei farmaci (``data/farmaci.json``) è l'unica fonte per il
mapping id -> file. Lo script fallisce se un file manca o se un farmaco non
produce blocchi, così un errore nei dati non passa silenziosamente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import INDEX_META_FILE
from app.farmaci import all as all_farmaci
from app.farmaci import tieni_primo_foglio, valida_file

DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "index"
FI_DIR = DATA_DIR / "markdown" / "FI"
OUTPUT_FILE = INDEX_DIR / "blocchi.json"

# Pulizia artefatti OCR ricorrenti nei markdown AIFA
OCR_ARTIFACTS = {"Ita", "Ag", "rm", "Fa", "del", "enz", "lia", "na", "aco", "ia"}

# Footer legale ripetuto in quasi tutti i blocchi: non è contenuto informativo
# e non deve mai diventare una fonte citata.
LEGAL_FOOTER_RE = re.compile(
    r"medicinali e, pertanto, l[’']Agenzia non può essere ritenuta responsabile.*?\(o titolare AIC\)\.",
    re.IGNORECASE | re.DOTALL,
)


def clean_text(text: str) -> str:
    """Rimuove artefatti OCR, footer legali e spazi superflui."""
    text = LEGAL_FOOTER_RE.sub("", text)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped in OCR_ARTIFACTS:
            continue
        if re.fullmatch(r"\d{1,3}", stripped):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_blocks(markdown_text: str, farmaco_id: str, documento: str) -> list[dict]:
    """Divide il markdown in blocchi basandosi su header ## e ###."""
    lines = markdown_text.split("\n")
    blocks: list[dict] = []
    current_section = "Introduzione"
    current_subsection = None
    current_text_lines: list[str] = []
    block_counter = 0
    offset_acc = 0

    def flush_block() -> None:
        nonlocal block_counter, offset_acc
        if not current_text_lines:
            return
        testo = "\n".join(current_text_lines).strip()
        if not testo:
            return
        testo_pulito = clean_text(testo)
        if not testo_pulito:
            return
        # Il titolo del paragrafo è contenuto del foglio illustrativo: lo
        # includiamo nel blocco, così è visibile nell'originale e citabile
        # anche quando il corpo è breve o generico. Non creiamo però blocchi
        # nuovi per i paragrafi che prima erano vuoti: gli id restano stabili.
        if current_subsection and current_subsection != "1":
            intestazione = clean_text(current_subsection)
            if intestazione and not testo_pulito.lower().startswith(
                intestazione.lower()
            ):
                testo_pulito = f"{intestazione}\n{testo_pulito}"
        if not testo_pulito:
            return
        block_id = f"{farmaco_id}_sec{block_counter}"
        blocks.append(
            {
                "id": block_id,
                "farmaco_id": farmaco_id,
                "tipo": "FI",
                "documento": documento,
                "sezione": current_section,
                "paragrafo": current_subsection or "1",
                "testo": testo_pulito,
                "offset_inizio": offset_acc,
                "offset_fine": offset_acc + len(testo_pulito),
                "header_padre": current_section,
            }
        )
        offset_acc += len(testo_pulito) + 1
        block_counter += 1
        current_text_lines.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush_block()
            current_section = stripped.replace("## ", "").strip()
            current_subsection = None
            continue
        if stripped.startswith("### "):
            flush_block()
            current_subsection = stripped.replace("### ", "").strip()
            continue
        current_text_lines.append(line)

    flush_block()
    return blocks


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_blocks() -> tuple[list[dict], dict]:
    mancanti = valida_file()
    if mancanti:
        raise FileNotFoundError("File markdown mancanti:\n" + "\n".join(mancanti))

    blocchi: list[dict] = []
    sorgenti: dict[str, str] = {}
    for farmaco in all_farmaci():
        path = farmaco.path_fi
        print(f"Indicizzazione {path.name} -> {farmaco.id}")
        testo = tieni_primo_foglio(path.read_text(encoding="utf-8"))
        farmaco_blocks = split_into_blocks(testo, farmaco.id, farmaco.documento)
        if not farmaco_blocks:
            raise ValueError(f"Nessun blocco generato per {farmaco.id}")
        print(f"  -> {len(farmaco_blocks)} blocchi generati")
        blocchi.extend(farmaco_blocks)
        sorgenti[farmaco.id] = _hash_file(path)

    ids = [b["id"] for b in blocchi]
    if len(ids) != len(set(ids)):
        raise ValueError("Blocchi con id duplicati: l'indice non è deterministico")

    meta = {
        "versione": 1,
        "generato_il": datetime.now(UTC).isoformat(),
        "farmaci": len({b["farmaco_id"] for b in blocchi}),
        "blocchi": len(blocchi),
        "sorgenti": sorgenti,
    }
    return blocchi, meta


def _serializza(blocchi: list[dict]) -> str:
    return json.dumps(blocchi, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce l'indice dei blocchi FI")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verifica che l'indice committato sia aggiornato, senza scrivere",
    )
    args = parser.parse_args()

    blocchi, meta = build_blocks()
    nuovo = _serializza(blocchi)

    if args.check:
        if not OUTPUT_FILE.exists():
            print(f"ERRORE: indice mancante in {OUTPUT_FILE}")
            return 1
        attuale = _serializza(json.loads(OUTPUT_FILE.read_text(encoding="utf-8")))
        if attuale != nuovo:
            print("ERRORE: l'indice non è aggiornato. Esegui build_index.py.")
            return 1
        print("Indice aggiornato.")
        return 0

    OUTPUT_FILE.write_text(nuovo, encoding="utf-8")
    INDEX_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nIndice salvato in {OUTPUT_FILE} ({len(blocchi)} blocchi totali)")
    print(f"Metadati salvati in {INDEX_META_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
