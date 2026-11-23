"""Read-only database access for the agent."""
from __future__ import annotations

import os

from desk_copilot.params import to_psycopg


def run_query(sql: str, params: dict | None = None, timeout_ms: int = 5_000) -> list[dict]:
    """Execute an already-guarded query on a read-only connection."""
    import psycopg
    from psycopg.rows import dict_row

    url = os.environ["READONLY_DATABASE_URL"]  # a role with SELECT on the marts only
    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
            cur.execute(to_psycopg(sql), params or {})
            return cur.fetchall()
