"""Named-parameter helpers shared by the catalogue and the guardrails."""
from __future__ import annotations

import re

# :name placeholders, ignoring Postgres casts such as value::date and times like 10:30
PLACEHOLDER = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")


def placeholders(sql: str) -> set[str]:
    return set(PLACEHOLDER.findall(sql))


def to_psycopg(sql: str) -> str:
    """Convert :name placeholders to psycopg's %(name)s style."""
    return PLACEHOLDER.sub(lambda m: f"%({m.group(1)})s", sql)


def null_placeholders(sql: str) -> str:
    """Replace placeholders with NULL so the SQL can be parsed for validation."""
    return PLACEHOLDER.sub("NULL", sql)
