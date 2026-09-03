"""One-time transfer of Stadia Chess data from SQLite to PostgreSQL.

Usage:
    DATABASE_URL='postgresql://...' python migrate_sqlite_to_postgres.py

Set STADIA_DB_PATH only when the SQLite file is not data/stadia_chess.db.
The script never deletes records from SQLite.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import chess_db


GAME_COLUMNS = (
    "id", "white_name", "black_name", "status", "fen", "result",
    "time_control", "created_at", "updated_at", "black_joined_at",
    "started_at", "finished_at", "archived", "premium_source",
    "premium_until", "invite_code", "white_clock_ms", "black_clock_ms",
    "clock_started_at", "finish_reason", "white_player_id",
    "black_player_id", "variant",
)

MOVE_COLUMNS = (
    "id", "game_id", "ply", "uci", "san", "created_at", "position_key",
)


def source_rows(connection: sqlite3.Connection, table: str, columns: tuple[str, ...]):
    available = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
    }
    selected = [column for column in columns if column in available]
    return selected, connection.execute(
        f"SELECT {', '.join(selected)} FROM {table} ORDER BY rowid"
    ).fetchall()


def copy_table(target, table: str, columns: list[str], rows) -> int:
    if not rows:
        return 0
    placeholders = ", ".join("?" for _ in columns)
    conflict = "id" if table == "games" else "game_id, ply"
    statement = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) ON CONFLICT ({conflict}) DO NOTHING"
    )
    for row in rows:
        target.execute(statement, tuple(row[column] for column in columns))
    return len(rows)


def main() -> None:
    if not chess_db.DATABASE_URL:
        raise SystemExit("DATABASE_URL is required")
    source_path = Path(os.getenv("STADIA_DB_PATH", "data/stadia_chess.db"))
    if not source_path.exists():
        raise SystemExit(f"SQLite database not found: {source_path}")

    chess_db._init_postgres()
    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    try:
        game_columns, games = source_rows(source, "games", GAME_COLUMNS)
        move_columns, moves = source_rows(source, "moves", MOVE_COLUMNS)
        with chess_db.connection() as target:
            target.execute("BEGIN")
            copied_games = copy_table(target, "games", game_columns, games)
            copied_moves = copy_table(target, "moves", move_columns, moves)
            target.execute(
                "SELECT setval(pg_get_serial_sequence('moves','id'), "
                "COALESCE((SELECT MAX(id) FROM moves), 1), true)"
            )
            target.execute("COMMIT")
    except Exception:
        try:
            target.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        source.close()
    print(f"Migration complete: {copied_games} games, {copied_moves} moves processed.")


if __name__ == "__main__":
    main()
