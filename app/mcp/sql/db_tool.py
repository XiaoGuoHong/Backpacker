import sqlite3

from app.core.config import Settings
from app.mcp.sql.validator import SQLRejectedError, validate_sql


def make_db_query_tool(settings: Settings):
    def handler(params: dict) -> dict:
        sql = params.get("sql")
        ok, reason = validate_sql(
            sql,
            allowed_tables=settings.db_allowed_tables,
            max_rows=settings.db_max_rows,
        )
        if not ok:
            raise SQLRejectedError(reason)

        db_path = settings.db_path or ":memory:"
        conn = sqlite3.connect(db_path, timeout=settings.db_query_timeout_ms / 1000.0)
        try:
            conn.execute("PRAGMA query_only = ON")
            cursor = conn.execute(sql)
            cols = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(settings.db_max_rows + 1)
            truncated = len(rows) > settings.db_max_rows
            rows = rows[: settings.db_max_rows]
            data = [dict(zip(cols, r)) for r in rows]
            return {
                "sql": sql,
                "columns": cols,
                "rows": data,
                "truncated": truncated,
                "source": "db(read-only)",
                "is_demo": False,
            }
        finally:
            conn.close()

    return handler
