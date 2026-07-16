import os
import sqlite3
import tempfile

from app.core.config import Settings
from app.mcp.connection import InProcessMCPConnection
from app.mcp.registry import build_default_registry
from app.mcp.sql.validator import SQLRejectedError, validate_sql


def test_validate_sql_allowed_select():
    ok, reason = validate_sql("SELECT * FROM city_weather_cache", ["city_weather_cache"])
    assert ok is True
    assert reason == "ok"


def test_validate_sql_rejects_multiple_statements():
    ok, reason = validate_sql("SELECT 1; DROP TABLE x", ["x"])
    assert ok is False
    assert reason == "multiple_statements"


def test_validate_sql_rejects_ddl():
    ok, reason = validate_sql("DROP TABLE city_weather_cache", ["city_weather_cache"])
    assert ok is False
    assert reason == "forbidden_keyword"


def test_validate_sql_rejects_update():
    ok, reason = validate_sql("UPDATE city_weather_cache SET a=1", ["city_weather_cache"])
    assert ok is False
    assert reason == "forbidden_keyword"


def test_validate_sql_rejects_disallowed_table():
    ok, reason = validate_sql("SELECT * FROM secrets", ["city_weather_cache"])
    assert ok is False
    assert reason == "table_not_allowed"


def test_validate_sql_rejects_system_table():
    ok, reason = validate_sql("SELECT * FROM sqlite_master", ["city_weather_cache"])
    assert ok is False
    assert reason == "system_table"


def test_db_tool_runs_read_only_and_rejects_ddl():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE city_weather_cache (city TEXT, t TEXT)")
    conn.execute("INSERT INTO city_weather_cache VALUES ('北京','晴')")
    conn.commit()
    conn.close()

    settings = Settings(db_enabled=True, db_path=path, db_allowed_tables=["city_weather_cache"])
    mcp = InProcessMCPConnection(build_default_registry(settings))
    import anyio

    async def go():
        good = await mcp.call("db_query_tool", {"sql": "SELECT * FROM city_weather_cache"})
        bad = await mcp.call("db_query_tool", {"sql": "DROP TABLE city_weather_cache"})
        return good, bad

    good, bad = anyio.run(go)
    assert good.status == "success"
    assert good.content["rows"][0]["city"] == "北京"
    assert bad.status == "failed"
    assert bad.error_code == "E_SQL_REJECTED"
    os.remove(path)


def test_db_tool_rejects_disallowed_table():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    settings = Settings(db_enabled=True, db_path=path, db_allowed_tables=["city_weather_cache"])
    mcp = InProcessMCPConnection(build_default_registry(settings))
    import anyio

    async def go():
        return await mcp.call("db_query_tool", {"sql": "SELECT * FROM other_table"})

    res = anyio.run(go)
    assert res.status == "failed"
    assert res.error_code == "E_SQL_REJECTED"
    os.remove(path)
