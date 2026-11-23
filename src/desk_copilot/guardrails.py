"""SQL guardrails: nothing reaches the database unless it is a single, read-only
SELECT over allow-listed tables, wrapped in a row limit.

Defence in depth: the agent also connects with a read-only database role, so a
query that slipped past these checks still could not write.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from desk_copilot.params import null_placeholders, placeholders, to_psycopg  # noqa: F401  (re-exported)

_FORBIDDEN_NAMES = ["Insert", "Update", "Delete", "Drop", "Create", "Alter", "AlterTable",
                    "Command", "Merge", "TruncateTable", "Grant"]
FORBIDDEN_NODES = tuple(t for t in (getattr(exp, n, None) for n in _FORBIDDEN_NAMES) if t is not None)


class GuardrailError(ValueError):
    """Raised when a query is refused."""


def _nodes(root: exp.Expression):
    for item in root.walk():
        # older sqlglot versions yield (node, parent, key) tuples
        yield item[0] if isinstance(item, tuple) else item


def validate_sql(sql: str, allowed_tables: set[str], max_rows: int = 200) -> str:
    """Return a guarded version of ``sql`` or raise :class:`GuardrailError`."""
    try:
        statements = [s for s in sqlglot.parse(null_placeholders(sql), read="postgres") if s is not None]
    except sqlglot.errors.ParseError as err:
        raise GuardrailError(f"could not parse SQL: {err}") from err

    if len(statements) != 1:
        raise GuardrailError("exactly one statement is allowed")
    root = statements[0]
    if not isinstance(root, exp.Select):
        raise GuardrailError("only SELECT statements are allowed")
    if any(isinstance(node, FORBIDDEN_NODES) for node in _nodes(root)):
        raise GuardrailError("data-changing statements are not allowed")

    cte_names = {cte.alias.lower() for cte in root.find_all(exp.CTE)}
    allowed = {t.lower() for t in allowed_tables}
    for table in root.find_all(exp.Table):
        name = f"{table.db}.{table.name}" if table.db else table.name
        if name.lower() in allowed or table.name.lower() in cte_names:
            continue
        raise GuardrailError(f"table not allowed: {name}")

    body = sql.strip().rstrip(";")
    return f"SELECT * FROM ({body}) AS guarded LIMIT {int(max_rows)}"
