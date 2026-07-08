import asyncio
import sqlite3
import os
import json
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Mocking the environment for the exporter
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_legacy.db"

async def setup_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///test_legacy.db")
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS facts"))
        await conn.execute(text("""
            CREATE TABLE facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT,
                entity_id TEXT,
                attribute TEXT,
                value TEXT,
                version TEXT,
                valid_from DATETIME,
                valid_to DATETIME,
                embedding BLOB
            )
        """))

        now = datetime.utcnow()
        v1_time = now - timedelta(days=3)
        v2_time = now - timedelta(days=2)

        # 1. Symbol with multiple versions (my_func)
        await conn.execute(text("INSERT INTO facts (entity_type, entity_id, attribute, value, version, valid_from, valid_to) VALUES (:et, :ei, :attr, :val, :v, :vf, :vt)"),
            [
                {"et": "symbol", "ei": "function:my_func", "attr": "name", "val": "my_func", "v": "v1", "vf": v1_time, "vt": v2_time},
                {"et": "symbol", "ei": "function:my_func", "attr": "file", "val": "main.py", "v": "v1", "vf": v1_time, "vt": v2_time},
                {"et": "symbol", "ei": "function:my_func", "attr": "kind", "val": "function", "v": "v1", "vf": v1_time, "vt": v2_time},

                {"et": "symbol", "ei": "function:my_func", "attr": "name", "val": "my_func", "v": "v2", "vf": v2_time, "vt": None},
                {"et": "symbol", "ei": "function:my_func", "attr": "file", "val": "main.py", "v": "v2", "vf": v2_time, "vt": None},
                {"et": "symbol", "ei": "function:my_func", "attr": "kind", "val": "function", "v": "v2", "vf": v2_time, "vt": None},
                {"et": "symbol", "ei": "function:my_func", "attr": "line", "val": "12", "v": "v2", "vf": v2_time, "vt": None},
            ]
        )

        # 2. Deleted symbol (old_helper)
        await conn.execute(text("INSERT INTO facts (entity_type, entity_id, attribute, value, version, valid_from, valid_to) VALUES (:et, :ei, :attr, :val, :v, :vf, :vt)"),
            [
                {"et": "symbol", "ei": "function:old_helper", "attr": "name", "val": "old_helper", "v": "v1", "vf": v1_time, "vt": v2_time},
                {"et": "symbol", "ei": "function:old_helper", "attr": "file", "val": "utils.py", "v": "v1", "vf": v1_time, "vt": v2_time},
            ]
        )

        # 3. Call (v1, still active)
        await conn.execute(text("INSERT INTO facts (entity_type, entity_id, attribute, value, version, valid_from, valid_to) VALUES (:et, :ei, :attr, :val, :v, :vf, :vt)"),
            [
                {"et": "call", "ei": "call:caller1->my_func", "attr": "caller", "val": "caller1", "v": "v1", "vf": v1_time, "vt": None},
                {"et": "call", "ei": "call:caller1->my_func", "attr": "callee", "val": "my_func", "v": "v1", "vf": v1_time, "vt": None},
            ]
        )

        # 4. Deleted call (caller2->old_helper)
        await conn.execute(text("INSERT INTO facts (entity_type, entity_id, attribute, value, version, valid_from, valid_to) VALUES (:et, :ei, :attr, :val, :v, :vf, :vt)"),
            [
                {"et": "call", "ei": "call:caller2->old_helper", "attr": "caller", "val": "caller2", "v": "v1", "vf": v1_time, "vt": v2_time},
                {"et": "call", "ei": "call:caller2->old_helper", "attr": "callee", "val": "old_helper", "v": "v1", "vf": v1_time, "vt": v2_time},
            ]
        )

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup_test_db())
    print("Test DB setup complete.")
