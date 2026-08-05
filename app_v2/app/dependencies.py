from __future__ import annotations

from collections.abc import Iterator
from sqlite3 import Connection

from app_v2.app.config import get_settings
from app_v2.app.db.connection import connect, init_db


def get_db() -> Iterator[Connection]:
    settings = get_settings()
    conn = connect(settings.db_path)
    init_db(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
