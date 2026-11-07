"""Ingestion separata dell'indice vettoriale ChromaDB.

Uso:
    uv run python scripts/ingest_vector_index.py
    uv run python scripts/ingest_vector_index.py --reset
    uv run python scripts/ingest_vector_index.py --dry-run

Prerequisiti:
    uv run python index/build_index.py   # produce blocchi.json
    OPENROUTER_API_KEY nel .env

Lo script non fa parte dell'app: il backend legge solo l'indice prodotto.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.config import Settings

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import BLOCCHI_FILE, INDEX_DIR  # noqa: E402
from services.embeddings import EMBEDDING_MODEL, embed_texts  # noqa: E402
from services.vector_store import CHROMA_DIR, COLLECTION_NAME  # noqa: E402

VECTOR_META_FILE = INDEX_DIR / "vector_meta.json"


def _split_parts(testo: str) -> list[str]:
    parti = re.split(r"(?<=[.!?])\s+|\n{2,}", testo)
    return [parte.strip() for parte in parti if parte.strip()]


def chunk_text(testo: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Divide un blocco in chunk con un piccolo overlap."""
    testo = testo.strip()
    if len(testo) <= max_chars:
        return [testo] if testo else []

    parti = _split_parts(testo)
    chunks: list[str] = []
    corrente = ""

    for parte in parti:
        if len(parte) > max_chars:
            if corrente:
                chunks.append(corrente)
                corrente = ""
            passo = max(1, max_chars - overlap)
            for inizio in range(0, len(parte), passo):
                pezzo = parte[inizio : inizio + max_chars].strip()
                if pezzo:
                    chunks.append(pezzo)
            continue

        candidato = f"{corrente}\n\n{parte}".strip()
        if len(candidato) > max_chars and corrente:
            chunks.append(corrente)
            coda = corrente[-overlap:].strip() if overlap else ""
            corrente = f"{coda}\n\n{parte}".strip() if coda else parte
        else:
            corrente = candidato

    if corrente:
        chunks.append(corrente)
    return chunks


def build_records(
    max_chars: int,
    overlap: int,
    farmaco_filtro: str | None = None,
) -> list[dict]:
    if not BLOCCHI_FILE.exists():
        raise FileNotFoundError(
            f"Indice blocchi non trovato: {BLOCCHI_FILE}. Esegui index/build_index.py"
        )

    blocchi = json.loads(BLOCCHI_FILE.read_text(encoding="utf-8"))
    records: list[dict] = []
    for blocco in blocchi:
        if farmaco_filtro and blocco["farmaco_id"] != farmaco_filtro:
            continue
        chunks = chunk_text(blocco["testo"], max_chars=max_chars, overlap=overlap)
        for indice, chunk in enumerate(chunks):
            records.append(
                {
                    "id": f"{blocco['id']}__chunk_{indice}",
                    "testo": chunk,
                    "metadata": {
                        "blocco_id": blocco["id"],
                        "farmaco_id": blocco["farmaco_id"],
                        "documento": blocco["documento"],
                        "sezione": blocco["sezione"],
                        "paragrafo": blocco["paragrafo"],
                        "chunk_index": indice,
                    },
                }
            )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestion ChromaDB dei blocchi FI")
    parser.add_argument("--reset", action="store_true", help="Ricrea la collezione")
    parser.add_argument("--dry-run", action="store_true", help="Non chiama embeddings")
    parser.add_argument("--farmaco", default=None, help="Limita a un farmaco_id")
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=150)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    records = build_records(
        max_chars=args.max_chars,
        overlap=args.overlap,
        farmaco_filtro=args.farmaco,
    )
    if not records:
        print("Nessun chunk da indicizzare.")
        return 1

    farmaci = sorted({record["metadata"]["farmaco_id"] for record in records})
    print(f"Chunk da indicizzare: {len(records)}")
    print(f"Farmaci: {', '.join(farmaci)}")
    print(f"Modello embeddings: {EMBEDDING_MODEL}")

    if args.dry_run:
        return 0

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    if args.reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Collezione {COLLECTION_NAME} eliminata.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    dimensione = 0
    for inizio in range(0, len(records), args.batch_size):
        batch = records[inizio : inizio + args.batch_size]
        testi = [record["testo"] for record in batch]
        vettori = embed_texts(testi, batch_size=args.batch_size)
        if vettori:
            dimensione = len(vettori[0])

        collection.upsert(
            ids=[record["id"] for record in batch],
            documents=testi,
            embeddings=vettori,
            metadatas=[record["metadata"] for record in batch],
        )
        print(
            f"  indicizzati {min(inizio + len(batch), len(records))}/{len(records)}"
        )

    meta = {
        "versione": 1,
        "creato_il": datetime.now(timezone.utc).isoformat(),
        "modello_embedding": EMBEDDING_MODEL,
        "dimensione": dimensione,
        "collezione": COLLECTION_NAME,
        "chunk": len(records),
        "farmaci": farmaci,
        "max_chars": args.max_chars,
        "overlap": args.overlap,
        "path": str(CHROMA_DIR),
    }
    VECTOR_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nIndice vettoriale salvato in {CHROMA_DIR}")
    print(f"Chunk nella collezione: {collection.count()}")
    print(f"Metadati salvati in {VECTOR_META_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
