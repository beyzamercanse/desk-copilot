"""Retrieval over ENTSO-E generation-outage notices stored in pgvector."""
from __future__ import annotations

import os
from functools import lru_cache

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")  # 384 dimensions


@lru_cache(maxsize=1)
def _encoder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _encoder().encode(texts, normalize_embeddings=True)]


def search(question: str, k: int = 5) -> list[dict]:
    """Top-k outage notices by cosine similarity."""
    import psycopg
    from pgvector.psycopg import register_vector
    from psycopg.rows import dict_row

    with psycopg.connect(os.environ["READONLY_DATABASE_URL"], row_factory=dict_row) as conn:
        register_vector(conn)
        conn.read_only = True
        rows = conn.execute(
            """
            select notice_id, zone, unit_name, fuel_type, unavailable_mw, start_utc, end_utc, notice_text,
                   1 - (embedding <=> %(q)s::vector) as similarity
            from outage_notices
            order by embedding <=> %(q)s::vector
            limit %(k)s
            """,
            {"q": embed([question])[0], "k": k},
        ).fetchall()
    return rows
