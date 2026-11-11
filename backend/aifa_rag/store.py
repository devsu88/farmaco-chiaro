"""Indice vettoriale su Qdrant.

Si collega al server Qdrant (``QDRANT_URL``, eventualmente con
``QDRANT_API_KEY``); se il valore è un percorso, usa la modalità embedded di
``qdrant-client`` (utile nei test, sconsigliata in produzione).
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient, models

from aifa_rag import config

COLLECTION_NAME = config.QDRANT_COLLECTION


def _is_url(location: str) -> bool:
    return location.startswith(("http://", "https://"))


def connect(location: str, api_key: str = "") -> QdrantClient:
    """Apre un client Qdrant su URL (server) o su percorso (modalità embedded)."""
    if _is_url(location):
        return QdrantClient(url=location, api_key=api_key or None, timeout=60)
    return QdrantClient(path=location)


class VectorStore:
    """Wrapper minimo sulla collection Qdrant dei chunk."""

    def __init__(self, client: QdrantClient, name: str = COLLECTION_NAME):
        self.client = client
        self.name = name

    @classmethod
    def open(
        cls,
        location: str,
        name: str = COLLECTION_NAME,
        api_key: str = "",
    ) -> "VectorStore":
        if not _is_url(location) and not Path(location).exists():
            raise FileNotFoundError(
                f"indice assente in {location}: esegui prima `python -m aifa_rag.cli index`"
            )
        client = connect(location, api_key)
        try:
            client.get_collection(name)
        except Exception as exc:
            client.close()
            raise FileNotFoundError(
                f"collezione `{name}` assente in {location}: esegui prima `index`"
            ) from exc
        return cls(client, name)

    def count(self) -> int:
        return int(self.client.count(collection_name=self.name, exact=True).count)

    def search(
        self,
        query_vector: list[float],
        k: int = 5,
        filters: dict[str, str] | None = None,
    ) -> list[dict]:
        """Top-k per coseno, con filtri esatti sui campi del payload."""
        query_filter = None
        if filters:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in filters.items()
                ]
            )

        points = self.client.query_points(
            collection_name=self.name,
            query=list(query_vector),
            limit=k,
            query_filter=query_filter,
            with_payload=True,
        ).points

        hits: list[dict] = []
        for point in points:
            payload = dict(point.payload or {})
            payload.setdefault("chunk_id", str(point.id))
            payload["score"] = float(point.score)
            hits.append(payload)
        return hits

    def close(self) -> None:
        self.client.close()
