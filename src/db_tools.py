"""
db_tools.py

Two things live here, and only two:
1. get_schema()  -> lets the agent discover what tables/columns exist
2. run_query()   -> lets the agent execute a SELECT and get rows back

Both are deliberately narrow. The agent should never be able to do
anything to the database except read from it.
"""

import re
import sqlite3
from typing import Any


MAX_ROWS = 200  # hard cap so one bad query can't dump the whole table


def get_schema(db_path: str) -> str:
    """Return a plain-text description of every table and its columns.

    This is the first tool the agent should call in a session -- it has
    no idea what your EPL database looks like until it asks.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]

        lines = []
        for table in tables:
            cur.execute(f"PRAGMA table_info({table});")
            cols = cur.fetchall()  # (cid, name, type, notnull, dflt, pk)
            col_desc = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
            lines.append(f"- {table}: {col_desc}")

        return "\n".join(lines) if lines else "No tables found."
    finally:
        conn.close()


def _is_safe_select(sql: str) -> bool:
    """Very deliberately restrictive: one SELECT statement, nothing else.

    This is not a general-purpose SQL sanitizer -- it's a tripwire.
    The goal is to make write/DDL statements and statement-stacking
    obviously fail rather than to be clever about it.
    """
    cleaned = sql.strip().rstrip(";")

    if ";" in cleaned:
        return False  # no stacked statements

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        return False

    forbidden = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|PRAGMA|REPLACE)\b"
    if re.search(forbidden, cleaned, re.IGNORECASE):
        return False

    return True


def run_query(db_path: str, sql: str) -> dict[str, Any]:
    """Execute a read-only SELECT and return rows + column names.

    Returns a dict so it serializes cleanly as a tool result:
        {"columns": [...], "rows": [[...], [...]], "truncated": bool}
    or {"error": "..."} if the query was rejected or failed.
    """
    if not _is_safe_select(sql):
        return {"error": "Only single SELECT statements are allowed."}

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "truncated": truncated,
        }
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()
