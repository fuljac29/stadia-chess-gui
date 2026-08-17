\
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chess


DEFAULT_DB_PATH = Path(os.getenv("STADIA_DB_PATH", "data/stadia_chess.db"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection(db_path: Path | str = DEFAULT_DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                white_name TEXT NOT NULL,
                black_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                fen TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT '',
                time_control TEXT NOT NULL DEFAULT 'rapid_15_10',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                black_joined_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                archived INTEGER NOT NULL DEFAULT 0,
                premium_source TEXT NOT NULL DEFAULT '',
                premium_until TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                ply INTEGER NOT NULL,
                uci TEXT NOT NULL,
                san TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(game_id, ply),
                FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_games_status_updated
                ON games(status, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_moves_game
                ON moves(game_id, ply);
            """
        )


def create_game(
    white_name: str,
    black_name: str,
    time_control: str = "rapid_15_10",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> str:
    game_id = uuid.uuid4().hex
    now = utc_now()
    board = chess.Board()
    with connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO games (
                id, white_name, black_name, status, fen, result,
                time_control, created_at, updated_at
            ) VALUES (?, ?, ?, 'waiting', ?, '', ?, ?, ?)
            """,
            (
                game_id,
                (white_name or "White").strip()[:60],
                (black_name or "Friend").strip()[:60],
                board.fen(),
                time_control,
                now,
                now,
            ),
        )
    return game_id


def get_game(game_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return dict(row) if row else None


def mark_black_joined(game_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    now = utc_now()
    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None
        if row["status"] == "waiting":
            conn.execute(
                """
                UPDATE games
                SET black_joined_at = COALESCE(black_joined_at, ?),
                    status = 'ready',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, game_id),
            )
        conn.execute("COMMIT")
    return get_game(game_id, db_path)


def start_game(game_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any]:
    now = utc_now()
    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            raise ValueError("Game not found")
        if row["status"] == "active":
            conn.execute("COMMIT")
            return dict(row)
        if row["status"] != "ready":
            conn.execute("ROLLBACK")
            raise ValueError("Friend has not joined yet")
        conn.execute(
            """
            UPDATE games
            SET status = 'active',
                started_at = COALESCE(started_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, game_id),
        )
        conn.execute("COMMIT")
    return get_game(game_id, db_path)  # type: ignore[return-value]


def get_moves(game_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY ply",
            (game_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def make_move(game_id: str, uci: str, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any]:
    now = utc_now()
    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            raise ValueError("Game not found")
        if row["status"] != "active":
            conn.execute("ROLLBACK")
            raise ValueError("Game is not active")

        board = chess.Board(row["fen"])
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            conn.execute("ROLLBACK")
            raise ValueError("Invalid move") from exc

        if move not in board.legal_moves:
            conn.execute("ROLLBACK")
            raise ValueError("Move is no longer legal. The other player may have moved.")

        san = board.san(move)
        ply = conn.execute(
            "SELECT COUNT(*) AS c FROM moves WHERE game_id = ?",
            (game_id,),
        ).fetchone()["c"] + 1

        board.push(move)
        status = "active"
        result = ""
        finished_at = None
        if board.is_game_over(claim_draw=True):
            status = "finished"
            result = board.result(claim_draw=True)
            finished_at = now

        conn.execute(
            """
            INSERT INTO moves (game_id, ply, uci, san, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_id, ply, uci, san, now),
        )
        conn.execute(
            """
            UPDATE games
            SET fen = ?, status = ?, result = ?, updated_at = ?, finished_at = ?
            WHERE id = ?
            """,
            (board.fen(), status, result, now, finished_at, game_id),
        )
        conn.execute("COMMIT")
    return get_game(game_id, db_path)  # type: ignore[return-value]


def legal_moves(game_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, str]]:
    game = get_game(game_id, db_path)
    if not game:
        return []
    board = chess.Board(game["fen"])
    items = []
    for move in board.legal_moves:
        items.append({"uci": move.uci(), "san": board.san(move)})
    return items


def list_games(
    include_archived: bool = False,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    where = "" if include_archived else "WHERE archived = 0"
    with connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT g.*,
                   (SELECT COUNT(*) FROM moves m WHERE m.game_id = g.id) AS move_count
            FROM games g
            {where}
            ORDER BY updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def archive_game(game_id: str, archived: bool = True, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "UPDATE games SET archived = ?, updated_at = ? WHERE id = ?",
            (1 if archived else 0, utc_now(), game_id),
        )


def delete_game(game_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
