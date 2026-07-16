import re

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "merge", "replace", "attach", "pragma", "vacuum",
]

SYSTEM_TABLE_HINTS = ["sqlite_master", "sqlite_temp_master", "information_schema", "pg_", "mysql."]


class SQLRejectedError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def validate_sql(
    sql: str,
    allowed_tables: list[str],
    allowed_columns: list[str] | None = None,
    max_rows: int = 100,
) -> tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "empty"

    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    if ";" in cleaned:
        return False, "multiple_statements"

    lowered = cleaned.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
            return False, "forbidden_keyword"

    if not lowered.startswith("select") or lowered.startswith("select into"):
        return False, "not_select"

    tables = re.findall(r"\b(?:from|join)\s+([\w.]+)", lowered)
    for table in tables:
        base = table.split(".")[-1]
        if any(base.startswith(h) for h in SYSTEM_TABLE_HINTS):
            return False, "system_table"
        if base not in allowed_tables:
            return False, "table_not_allowed"

    if allowed_columns is not None:
        cols = re.findall(r"select\s+(.*?)\s+from", lowered, flags=re.DOTALL)
        selected = cols[0] if cols else "*"
        if selected.strip() != "*":
            for col in re.split(r",", selected):
                name = col.strip().split(" as ")[0].split(".")[-1].strip()
                if name and name not in allowed_columns:
                    return False, "column_not_allowed"

    if max_rows is not None and max_rows <= 0:
        return False, "invalid_row_limit"

    return True, "ok"
