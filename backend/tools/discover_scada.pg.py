from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row


OUTPUT_FILE = Path("pg_archive_discovery.json")


def redact_row(row: dict[str, Any]) -> dict[str, Any]:
    """Redact fields that may contain sensitive values."""
    redacted: dict[str, Any] = {}

    sensitive_patterns = [
        "password",
        "secret",
        "token",
        "key",
        "connectionstring",
        "connstr",
    ]

    for key, value in row.items():
        key_text = str(key).lower()

        if any(pattern in key_text for pattern in sensitive_patterns):
            redacted[key] = "***"
        else:
            redacted[key] = value

    return redacted


def load_pg_settings() -> dict[str, Any]:
    """Load PostgreSQL connection settings from the backend .env file."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)

    required_vars = [
        "SCADA_PG_HOST",
        "SCADA_PG_PORT",
        "SCADA_PG_DATABASE",
        "SCADA_PG_USERNAME",
        "SCADA_PG_PASSWORD",
    ]

    missing = [name for name in required_vars if not os.getenv(name)]

    if missing:
        raise RuntimeError(
            "Missing required .env variables: " + ", ".join(missing)
        )

    return {
        "host": os.getenv("SCADA_PG_HOST"),
        "port": int(os.getenv("SCADA_PG_PORT", "5432")),
        "dbname": os.getenv("SCADA_PG_DATABASE"),
        "user": os.getenv("SCADA_PG_USERNAME"),
        "password": os.getenv("SCADA_PG_PASSWORD"),
        "connect_timeout": 5,
        "application_name": "rapid_scada_dashboard_readonly_discovery",
        "options": "-c default_transaction_read_only=on -c statement_timeout=10000",
    }


def fetch_all(cur: psycopg.Cursor, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Run a SELECT query and return all rows as dictionaries."""
    cur.execute(query, params)
    return list(cur.fetchall())


def is_candidate_archive_table(table_name: str, columns: list[dict[str, Any]]) -> bool:
    """Guess if a table may contain archive/history data."""
    text = table_name.lower() + " " + " ".join(
        str(column["column_name"]).lower()
        for column in columns
    )

    keywords = [
        "archive",
        "arc",
        "hist",
        "history",
        "trend",
        "data",
        "min",
        "hour",
        "day",
        "event",
        "cnl",
        "channel",
        "time",
        "timestamp",
        "val",
        "value",
        "stat",
        "status",
    ]

    return any(keyword in text for keyword in keywords)


def sample_table(
    cur: psycopg.Cursor,
    table_schema: str,
    table_name: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Read a tiny sample from a table using SELECT only."""
    query = sql.SQL("SELECT * FROM {}.{} LIMIT {}").format(
        sql.Identifier(table_schema),
        sql.Identifier(table_name),
        sql.Literal(limit),
    )

    cur.execute(query)
    rows = cur.fetchall()

    return [redact_row(dict(row)) for row in rows]


def main() -> None:
    """Discover PostgreSQL archive schema using read-only queries."""
    settings = load_pg_settings()

    safe_settings = {
        key: ("***" if key == "password" else value)
        for key, value in settings.items()
    }

    result: dict[str, Any] = {
        "ok": False,
        "mode": "postgresql_read_only_schema_discovery",
        "connection": safe_settings,
        "server_info": {},
        "schemas": [],
        "tables": [],
        "columns": [],
        "candidate_tables": [],
        "candidate_samples": [],
        "errors": [],
    }

    try:
        with psycopg.connect(**settings, row_factory=dict_row) as conn:
            # Force read-only behavior at the session level.
            conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;")
            conn.execute("SET statement_timeout = '10s';")

            with conn.cursor() as cur:
                cur.execute("BEGIN READ ONLY;")

                result["server_info"] = fetch_all(
                    cur,
                    """
                    SELECT
                        current_database() AS database,
                        current_user AS current_user,
                        inet_server_addr()::text AS server_addr,
                        inet_server_port() AS server_port,
                        version() AS version
                    """
                )[0]

                result["schemas"] = fetch_all(
                    cur,
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY schema_name
                    """
                )

                result["tables"] = fetch_all(
                    cur,
                    """
                    SELECT
                        t.table_schema,
                        t.table_name,
                        COALESCE(c.reltuples::bigint, 0) AS estimated_rows,
                        pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
                    FROM information_schema.tables t
                    LEFT JOIN pg_namespace n
                        ON n.nspname = t.table_schema
                    LEFT JOIN pg_class c
                        ON c.relname = t.table_name
                        AND c.relnamespace = n.oid
                    WHERE t.table_type = 'BASE TABLE'
                      AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY
                        pg_total_relation_size(c.oid) DESC NULLS LAST,
                        t.table_schema,
                        t.table_name
                    """
                )

                result["columns"] = fetch_all(
                    cur,
                    """
                    SELECT
                        table_schema,
                        table_name,
                        ordinal_position,
                        column_name,
                        data_type,
                        udt_name,
                        is_nullable
                    FROM information_schema.columns
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name, ordinal_position
                    """
                )

                columns_by_table: dict[tuple[str, str], list[dict[str, Any]]] = {}

                for column in result["columns"]:
                    key = (column["table_schema"], column["table_name"])
                    columns_by_table.setdefault(key, []).append(column)

                for table in result["tables"]:
                    key = (table["table_schema"], table["table_name"])
                    table_columns = columns_by_table.get(key, [])

                    if is_candidate_archive_table(table["table_name"], table_columns):
                        result["candidate_tables"].append(
                            {
                                "table_schema": table["table_schema"],
                                "table_name": table["table_name"],
                                "estimated_rows": table["estimated_rows"],
                                "total_size": table["total_size"],
                                "columns": [
                                    {
                                        "column_name": column["column_name"],
                                        "data_type": column["data_type"],
                                        "udt_name": column["udt_name"],
                                    }
                                    for column in table_columns
                                ],
                            }
                        )

                for candidate in result["candidate_tables"][:15]:
                    try:
                        rows = sample_table(
                            cur,
                            candidate["table_schema"],
                            candidate["table_name"],
                            limit=3,
                        )

                        result["candidate_samples"].append(
                            {
                                "table_schema": candidate["table_schema"],
                                "table_name": candidate["table_name"],
                                "sample_rows": rows,
                            }
                        )
                    except Exception as exc:
                        result["candidate_samples"].append(
                            {
                                "table_schema": candidate["table_schema"],
                                "table_name": candidate["table_name"],
                                "error": str(exc),
                            }
                        )

                cur.execute("ROLLBACK;")

        result["ok"] = True

    except Exception as exc:
        result["errors"].append(str(exc))

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"Wrote discovery output to: {OUTPUT_FILE.resolve()}")
    print(f"OK: {result['ok']}")
    print(f"Tables found: {len(result['tables'])}")
    print(f"Candidate archive tables: {len(result['candidate_tables'])}")

    if result["errors"]:
        print("Errors:")
        for error in result["errors"]:
            print(f"- {error}")


if __name__ == "__main__":
    main()