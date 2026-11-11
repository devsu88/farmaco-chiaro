"""Costruisce l'indice Qdrant dei chunk, con cache riprendibile degli embedding.

I vettori sono salvati in ``data/rag/embeddings/`` in append a ogni blocco: se
il processo muore (rate limit, crash) gli embedding già pagati restano su disco
e il run successivo riparte da lì.

La cache è indicizzata per ``chunk_id``, non per posizione: possiamo quindi
filtrare o riordinare i chunk (es. deduplica dei fogli duplicati) senza
richiamare l'API di embedding.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from qdrant_client import models

from aifa_rag import config
from aifa_rag.chunk import contextualize
from aifa_rag.embeddings import embed_texts
from aifa_rag.store import COLLECTION_NAME, connect

WRITE_BATCH = 256
VECTORS_FILE = "vectors.f32"
IDS_FILE = "chunk_ids.jsonl"
MANIFEST_FILE = "index.json"


def _embedding_text(chunk: dict) -> str:
    return contextualize(
        str(chunk.get("nome", "")),
        str(chunk.get("foglio", "")),
        str(chunk.get("sezione_titolo", "")),
        str(chunk.get("sottosezione_titolo", "")),
        str(chunk.get("testo", "")),
    )


def _reset(cache_dir: Path) -> None:
    for name in (VECTORS_FILE, IDS_FILE, MANIFEST_FILE):
        (cache_dir / name).unlink(missing_ok=True)


def _load_cache(cache_dir: Path) -> tuple[list[str], np.ndarray, int] | None:
    """Carica ``(ids, vectors, dim)``; azzera la cache se non è coerente."""
    vectors_path = cache_dir / VECTORS_FILE
    ids_path = cache_dir / IDS_FILE
    manifest_path = cache_dir / MANIFEST_FILE
    if not (vectors_path.exists() and ids_path.exists() and manifest_path.exists()):
        _reset(cache_dir)
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dim = int(manifest["dim"])
        ids = [
            json.loads(line)["chunk_id"]
            for line in ids_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (KeyError, ValueError, json.JSONDecodeError):
        _reset(cache_dir)
        return None

    if manifest.get("model") != config.EMBEDDING_MODEL:
        _reset(cache_dir)
        return None

    expected = len(ids) * dim * 4
    size = vectors_path.stat().st_size
    if size != expected:
        # Un crash durante una scrittura può lasciare una coda parziale.
        if size < expected:
            _reset(cache_dir)
            return None
        with vectors_path.open("r+b") as handle:
            handle.truncate(expected)

    data = np.fromfile(vectors_path, dtype=np.float32)
    return ids, data.reshape(-1, dim), dim


def _ensure_embeddings(
    chunks: list[dict],
    cache_dir: Path,
    batch_size: int = config.EMBED_BATCH_SIZE,
) -> np.ndarray:
    """Restituisce i vettori normalizzati, embeddando solo i chunk mancanti."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = _load_cache(cache_dir)
    if cache is None:
        ids: list[str] = []
        vectors = np.empty((0, 0), dtype=np.float32)
        dim = 0
    else:
        ids, vectors, dim = cache

    position = {chunk_id: index for index, chunk_id in enumerate(ids)}
    missing = [
        chunk for chunk in chunks if str(chunk["chunk_id"]) not in position
    ]

    if missing:
        vectors_path = cache_dir / VECTORS_FILE
        ids_path = cache_dir / IDS_FILE
        manifest_path = cache_dir / MANIFEST_FILE

        with (
            vectors_path.open("ab") as vectors_out,
            ids_path.open("a", encoding="utf-8") as ids_out,
        ):
            for start in range(0, len(missing), WRITE_BATCH):
                batch = missing[start : start + WRITE_BATCH]
                embeddings = embed_texts(
                    [_embedding_text(chunk) for chunk in batch], batch_size=batch_size
                )
                array = np.asarray(embeddings, dtype=np.float32)
                if dim and array.shape[1] != dim:
                    raise ValueError(
                        f"dimensione embedding {array.shape[1]} diversa da {dim}"
                    )
                dim = int(array.shape[1])
                array.tofile(vectors_out)
                vectors_out.flush()

                for chunk in batch:
                    ids_out.write(json.dumps({"chunk_id": str(chunk["chunk_id"])}) + "\n")
                ids_out.flush()

                vectors = np.vstack([vectors, array]) if vectors.size else array
                for offset, chunk in enumerate(batch):
                    position[str(chunk["chunk_id"])] = len(ids) + offset
                ids.extend(str(chunk["chunk_id"]) for chunk in batch)

                manifest_path.write_text(
                    json.dumps(
                        {
                            "dim": dim,
                            "count": len(ids),
                            "model": config.EMBEDDING_MODEL,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

    if not chunks:
        return np.empty((0, max(dim, 0)), dtype=np.float32)

    out = np.empty((len(chunks), dim), dtype=np.float32)
    for row, chunk in enumerate(chunks):
        out[row] = vectors[position[str(chunk["chunk_id"])]]
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    out /= np.maximum(norms, 1e-12)
    return out


def _write_qdrant(
    chunks: list[dict],
    vectors: np.ndarray,
    location: str,
    api_key: str = "",
    collection: str = COLLECTION_NAME,
) -> int:
    client = connect(location, api_key)
    try:
        if client.collection_exists(collection):
            client.delete_collection(collection)
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(
                size=int(vectors.shape[1]), distance=models.Distance.COSINE
            ),
        )
        # Qdrant Cloud rifiuta i filtri sui payload senza indice keyword;
        # la modalità embedded (usata dai test) non supporta gli indici.
        if location.startswith(("http://", "https://")):
            for field in ("farmaco_id", "drug_id", "sezione_key", "tipo"):
                client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        for start in range(0, len(chunks), WRITE_BATCH):
            batch = chunks[start : start + WRITE_BATCH]
            client.upsert(
                collection_name=collection,
                points=[
                    models.PointStruct(
                        id=str(uuid5(NAMESPACE_URL, str(chunk["chunk_id"]))),
                        vector=vectors[start + offset].tolist(),
                        payload=chunk,
                    )
                    for offset, chunk in enumerate(batch)
                ],
            )
    finally:
        client.close()
    return len(chunks)


def _write_meta(
    meta_path: Path,
    chunks_path: Path,
    chunks: list[dict],
    dim: int,
    collection: str,
) -> None:
    digest = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(
            {
                "model": config.EMBEDDING_MODEL,
                "dim": dim,
                "count": len(chunks),
                "chunks_sha256": digest,
                "collection": collection,
                "farmaci": len({chunk.get("farmaco_id") for chunk in chunks}),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def build_index(
    chunks_path: Path,
    cache_dir: Path,
    location: str,
    batch_size: int = config.EMBED_BATCH_SIZE,
    api_key: str = "",
    collection: str = COLLECTION_NAME,
    meta_path: Path | None = None,
) -> int:
    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not chunks:
        return 0

    vectors = _ensure_embeddings(chunks, cache_dir, batch_size)
    written = _write_qdrant(chunks, vectors, location, api_key, collection)
    if meta_path is not None:
        _write_meta(meta_path, chunks_path, chunks, int(vectors.shape[1]), collection)
    return written
