from __future__ import annotations

import logging
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import connection, reset_queries

SQL_LOGGER = logging.getLogger("sql")
SQL_DIR = Path(__file__).resolve().parent / "sql"
PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _split_named_queries(content: str) -> dict[str, str]:
    named_queries: dict[str, list[str]] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if current_name is not None:
                named_queries[current_name] = current_lines
            current_name = stripped.split(":", 1)[1].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_name is not None:
        named_queries[current_name] = current_lines

    if not named_queries:
        raise ValueError("No named SQL found. Use '-- name: query_id' blocks.")

    return {k: "\n".join(v).strip() for k, v in named_queries.items()}


@lru_cache(maxsize=16)
def load_named_queries(sql_filename: str) -> dict[str, str]:
    sql_path = SQL_DIR / sql_filename
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    return _split_named_queries(sql_path.read_text(encoding="utf-8"))


def _compile_template_sql(sql_template: str, params: dict[str, Any]) -> tuple[str, list[Any]]:
    values: list[Any] = []

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        values.append(params.get(key))
        return "%s"

    compiled_sql = PLACEHOLDER_PATTERN.sub(repl, sql_template)
    return compiled_sql, values


def _rewrite_limit_for_pg(sql_template: str) -> str:
    return re.sub(
        r"LIMIT\s*\{offset\}\s*,\s*\{count\}",
        "LIMIT {count} OFFSET {offset}",
        sql_template,
        flags=re.IGNORECASE,
    )


def run_named_query(
    *,
    sql_filename: str,
    query_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    all_queries = load_named_queries(sql_filename)
    if query_id not in all_queries:
        raise KeyError(f"Unknown query_id '{query_id}' in {sql_filename}")

    raw_sql = all_queries[query_id]
    sql_template = raw_sql

    if settings.DB_TARGET == "pg" and sql_filename == "txns.sql":
        sql_template = _rewrite_limit_for_pg(sql_template)

    exec_sql, exec_params = _compile_template_sql(sql_template, params)
    pre_sql = "SET mysql_mode=true;" if settings.DB_TARGET == "pgx" else None

    started_at = time.perf_counter()
    final_pre_sql = pre_sql
    final_sql = exec_sql
    columns: list[str] = []
    rows: list[tuple[Any, ...]] = []

    connection.force_debug_cursor = True
    reset_queries()

    try:
        with connection.cursor() as cursor:
            if pre_sql:
                cursor.execute(pre_sql)
            cursor.execute(exec_sql, exec_params)
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = list(cursor.fetchall())

        queries = connection.queries
        if pre_sql and len(queries) >= 2:
            final_pre_sql = queries[-2].get("sql", pre_sql)
            final_sql = queries[-1].get("sql", exec_sql)
        elif len(queries) >= 1:
            final_sql = queries[-1].get("sql", exec_sql)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        SQL_LOGGER.info(
            "query_id=%s db_target=%s pre_sql=%s raw_sql=%s final_sql=%s params=%s rows=%s elapsed_ms=%.2f",
            query_id,
            settings.DB_TARGET,
            final_pre_sql,
            raw_sql,
            final_sql,
            exec_params,
            len(rows),
            elapsed_ms,
        )
        return {
            "raw_sql": raw_sql,
            "pre_sql": final_pre_sql,
            "final_sql": final_sql,
            "columns": columns,
            "rows": rows,
            "params": exec_params,
            "error": None,
        }
    except Exception:
        queries = connection.queries
        if pre_sql and len(queries) >= 2:
            final_pre_sql = queries[-2].get("sql", pre_sql)
            final_sql = queries[-1].get("sql", exec_sql)
        elif len(queries) >= 1:
            final_sql = queries[-1].get("sql", exec_sql)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        SQL_LOGGER.exception(
            "query_id=%s db_target=%s pre_sql=%s raw_sql=%s final_sql=%s params=%s elapsed_ms=%.2f",
            query_id,
            settings.DB_TARGET,
            final_pre_sql,
            raw_sql,
            final_sql,
            exec_params,
            elapsed_ms,
        )
        return {
            "raw_sql": raw_sql,
            "pre_sql": final_pre_sql,
            "final_sql": final_sql,
            "columns": [],
            "rows": [],
            "params": exec_params,
            "error": "SQL execution failed. Check log/sql.log for details.",
        }
    finally:
        connection.force_debug_cursor = False
