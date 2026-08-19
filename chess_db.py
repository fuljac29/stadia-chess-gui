from __future__ import annotations

import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chess


DEFAULT_DB_PATH = Path(
    os.getenv("STADIA_DB_PATH", "data/stadia_chess.db")
)

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_CODE_LENGTH = 6

CLOCK_CONTROLS: dict[str, tuple[int, int] | None] = {
    "rapid_15_10": (15 * 60_000, 10_000),
    "blitz_5_3": (5 * 60_000, 3_000),
    "relaxed": None,
}


def clock_config(
    time_control: str,
) -> tuple[int, int] | None:
    return CLOCK_CONTROLS.get(
        str(time_control or "").strip(),
        None,
    )


def _clock_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _clock_now_iso(
    now_dt: datetime | None = None,
) -> str:
    current = now_dt or _clock_now_dt()
    return current.isoformat(
        timespec="milliseconds"
    )


def _parse_clock_time(
    value: str | None,
) -> datetime | None:
    raw = str(value or "").strip()

    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _elapsed_ms(
    started_at: str | None,
    now_dt: datetime,
) -> int:
    started = _parse_clock_time(
        started_at
    )

    if not started:
        return 0

    elapsed = (
        now_dt - started
    ).total_seconds()

    return max(
        0,
        int(elapsed * 1000),
    )


def _timeout_result(
    active_color: str,
) -> str:
    return (
        "0-1"
        if active_color == "white"
        else "1-0"
    )


def _clock_snapshot(
    row: sqlite3.Row | dict[str, Any],
    now_dt: datetime,
) -> dict[str, Any]:
    config = clock_config(
        row["time_control"]
    )

    board = chess.Board(
        row["fen"]
    )

    active_color = (
        "white"
        if board.turn == chess.WHITE
        else "black"
    )

    finish_reason = (
        row["finish_reason"]
        if "finish_reason" in row.keys()
        else ""
    )

    if config is None:
        return {
            "enabled": False,
            "time_control": row["time_control"],
            "increment_ms": 0,
            "white_ms": None,
            "black_ms": None,
            "active_color": active_color,
            "running": False,
            "status": row["status"],
            "result": row["result"],
            "finish_reason": finish_reason,
        }

    base_ms, increment_ms = config

    white_ms = (
        int(row["white_clock_ms"])
        if row["white_clock_ms"] is not None
        else base_ms
    )

    black_ms = (
        int(row["black_clock_ms"])
        if row["black_clock_ms"] is not None
        else base_ms
    )

    running = (
        row["status"] == "active"
        and bool(row["clock_started_at"])
    )

    if running:
        elapsed = _elapsed_ms(
            row["clock_started_at"],
            now_dt,
        )

        if active_color == "white":
            white_ms = max(
                0,
                white_ms - elapsed,
            )
        else:
            black_ms = max(
                0,
                black_ms - elapsed,
            )

    return {
        "enabled": True,
        "time_control": row["time_control"],
        "increment_ms": increment_ms,
        "white_ms": white_ms,
        "black_ms": black_ms,
        "active_color": active_color,
        "running": running,
        "status": row["status"],
        "result": row["result"],
        "finish_reason": finish_reason,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_invite_code(value: str) -> str:
    return "".join(
        ch
        for ch in (value or "").upper()
        if ch.isalnum()
    )


@contextmanager
def connection(
    db_path: Path | str = DEFAULT_DB_PATH
):
    db_path = Path(db_path)
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    conn = sqlite3.connect(
        db_path,
        timeout=15,
        isolation_level=None,
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    try:
        yield conn
    finally:
        conn.close()


def _generate_invite_code(
    conn: sqlite3.Connection
) -> str:
    for _ in range(200):
        code = "".join(
            secrets.choice(INVITE_ALPHABET)
            for _ in range(INVITE_CODE_LENGTH)
        )

        exists = conn.execute(
            "SELECT 1 FROM games WHERE invite_code = ? LIMIT 1",
            (code,),
        ).fetchone()

        if not exists:
            return code

    raise RuntimeError(
        "Could not generate a unique invitation code"
    )


def init_db(
    db_path: Path | str = DEFAULT_DB_PATH
) -> None:
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
                premium_until TEXT NOT NULL DEFAULT '',
                invite_code TEXT,
                white_clock_ms INTEGER,
                black_clock_ms INTEGER,
                clock_started_at TEXT,
                finish_reason TEXT NOT NULL DEFAULT '',
                white_player_id TEXT NOT NULL DEFAULT '',
                black_player_id TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                ply INTEGER NOT NULL,
                uci TEXT NOT NULL,
                san TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(game_id, ply),
                FOREIGN KEY(game_id)
                    REFERENCES games(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_games_status_updated
                ON games(status, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_moves_game
                ON moves(game_id, ply);
            """
        )

        # Migration from v0.7 and earlier:
        # add invite_code if the existing DB does not have it.
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(games)"
            ).fetchall()
        }

        if "invite_code" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN invite_code TEXT"
            )


        if "white_clock_ms" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN white_clock_ms INTEGER"
            )

        if "black_clock_ms" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN black_clock_ms INTEGER"
            )

        if "clock_started_at" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN clock_started_at TEXT"
            )

        if "finish_reason" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN finish_reason TEXT NOT NULL DEFAULT ''"
            )


        if "white_player_id" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN white_player_id TEXT NOT NULL DEFAULT ''"
            )

        if "black_player_id" not in columns:
            conn.execute(
                "ALTER TABLE games ADD COLUMN black_player_id TEXT NOT NULL DEFAULT ''"
            )

        # v0.9.0 migration:
        # older timed games receive a full clock. Active games begin timing
        # from this migration moment, so no time is charged retroactively.
        migration_now = _clock_now_iso()

        clock_rows = conn.execute(
            """
            SELECT
                id,
                status,
                time_control,
                white_clock_ms,
                black_clock_ms,
                clock_started_at
            FROM games
            """
        ).fetchall()

        for clock_row in clock_rows:
            config = clock_config(
                clock_row["time_control"]
            )

            if config is None:
                conn.execute(
                    """
                    UPDATE games
                    SET white_clock_ms = NULL,
                        black_clock_ms = NULL,
                        clock_started_at = NULL
                    WHERE id = ?
                    """,
                    (clock_row["id"],),
                )
                continue

            base_ms, _ = config

            white_ms = (
                clock_row["white_clock_ms"]
                if clock_row["white_clock_ms"] is not None
                else base_ms
            )

            black_ms = (
                clock_row["black_clock_ms"]
                if clock_row["black_clock_ms"] is not None
                else base_ms
            )

            if clock_row["status"] == "active":
                clock_started_at = (
                    clock_row["clock_started_at"]
                    or migration_now
                )
            else:
                clock_started_at = None

            conn.execute(
                """
                UPDATE games
                SET white_clock_ms = ?,
                    black_clock_ms = ?,
                    clock_started_at = ?
                WHERE id = ?
                """,
                (
                    white_ms,
                    black_ms,
                    clock_started_at,
                    clock_row["id"],
                ),
            )

        # Empty values are treated as missing.
        conn.execute(
            """
            UPDATE games
            SET invite_code = NULL
            WHERE TRIM(COALESCE(invite_code, '')) = ''
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_games_invite_code
            ON games(invite_code)
            WHERE invite_code IS NOT NULL
            """
        )

        # Give old games a short code too, so migration is seamless.
        rows = conn.execute(
            """
            SELECT id
            FROM games
            WHERE invite_code IS NULL
            """
        ).fetchall()

        for row in rows:
            code = _generate_invite_code(conn)
            conn.execute(
                """
                UPDATE games
                SET invite_code = ?
                WHERE id = ?
                """,
                (code, row["id"]),
            )


def create_game(
    white_name: str,
    black_name: str,
    time_control: str = "rapid_15_10",
    db_path: Path | str = DEFAULT_DB_PATH,
    white_player_id: str = "",
) -> str:
    game_id = uuid.uuid4().hex
    now = utc_now()
    board = chess.Board()

    config = clock_config(
        time_control
    )

    initial_clock_ms = (
        config[0]
        if config is not None
        else None
    )

    player_id = str(
        white_player_id or ""
    ).strip()[:80]

    with connection(db_path) as conn:
        invite_code = _generate_invite_code(
            conn
        )

        conn.execute(
            """
            INSERT INTO games (
                id,
                white_name,
                black_name,
                status,
                fen,
                result,
                time_control,
                created_at,
                updated_at,
                invite_code,
                white_clock_ms,
                black_clock_ms,
                clock_started_at,
                finish_reason,
                white_player_id,
                black_player_id
            )
            VALUES (
                ?, ?, ?, 'waiting', ?, '', ?, ?, ?, ?, ?, ?, NULL, '', ?, ''
            )
            """,
            (
                game_id,
                (white_name or "White").strip()[:60],
                (black_name or "Friend").strip()[:60],
                board.fen(),
                time_control,
                now,
                now,
                invite_code,
                initial_clock_ms,
                initial_clock_ms,
                player_id,
            ),
        )

    return game_id

def get_game(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    with connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

        return dict(row) if row else None


def get_latest_finished_game_by_player_id(
    player_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    player_id = str(
        player_id or ""
    ).strip()

    if not player_id:
        return None

    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM games
            WHERE archived = 0
              AND status = 'finished'
              AND (
                    white_player_id = ?
                 OR black_player_id = ?
              )
            ORDER BY COALESCE(finished_at, updated_at) DESC
            LIMIT 1
            """,
            (player_id, player_id),
        ).fetchone()

        return dict(row) if row else None


def get_open_game_by_white_player_id(
    player_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    player_id = str(
        player_id or ""
    ).strip()

    if not player_id:
        return None

    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM games
            WHERE white_player_id = ?
              AND archived = 0
              AND status IN ('waiting', 'ready', 'active')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()

        return dict(row) if row else None


def get_game_by_invite_code(
    invite_code: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    code = normalize_invite_code(invite_code)

    if not code:
        return None

    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM games
            WHERE invite_code = ?
              AND archived = 0
            LIMIT 1
            """,
            (code,),
        ).fetchone()

        return dict(row) if row else None


def accept_invite(
    invite_code: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    black_player_id: str = "",
) -> dict[str, Any]:
    """
    The invited player accepts by short code.

    v0.9.0:
    timed games start their authoritative server clock at the exact moment
    the invitation becomes active.
    """
    code = normalize_invite_code(
        invite_code
    )

    if not code:
        raise ValueError(
            "Invitation code is required"
        )

    now = utc_now()
    clock_now = _clock_now_iso()
    player_id = str(
        black_player_id or ""
    ).strip()[:80]

    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT *
            FROM games
            WHERE invite_code = ?
              AND archived = 0
            LIMIT 1
            """,
            (code,),
        ).fetchone()

        if not row:
            conn.execute("ROLLBACK")
            raise ValueError(
                "Invitation code not found"
            )

        if row["status"] in {
            "waiting",
            "ready",
        }:
            conn.execute(
                """
                UPDATE games
                SET black_joined_at =
                        COALESCE(black_joined_at, ?),
                    started_at =
                        COALESCE(started_at, ?),
                    status = 'active',
                    updated_at = ?,
                    clock_started_at =
                        CASE
                            WHEN time_control = 'relaxed'
                            THEN NULL
                            ELSE ?
                        END,
                    black_player_id =
                        CASE
                            WHEN TRIM(COALESCE(black_player_id, '')) = ''
                            THEN ?
                            ELSE black_player_id
                        END
                WHERE id = ?
                """,
                (
                    now,
                    now,
                    now,
                    clock_now,
                    player_id,
                    row["id"],
                ),
            )

        elif row["status"] not in {
            "active",
            "finished",
        }:
            conn.execute("ROLLBACK")
            raise ValueError(
                "This game cannot be opened"
            )

        conn.execute("COMMIT")

    game = get_game(
        row["id"],
        db_path,
    )

    if not game:
        raise ValueError(
            "Game not found"
        )

    return game

def mark_black_joined(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    now = utc_now()

    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

        if not row:
            conn.execute("ROLLBACK")
            return None

        if row["status"] == "waiting":
            conn.execute(
                """
                UPDATE games
                SET black_joined_at =
                        COALESCE(black_joined_at, ?),
                    status = 'ready',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    now,
                    game_id,
                ),
            )

        conn.execute("COMMIT")

    return get_game(game_id, db_path)


def join_black(
    game_id: str,
    black_name: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """
    Backward-compatible v0.7 join method.
    v0.8 normally uses accept_invite().
    """

    name = (black_name or "").strip()[:60]

    if not name:
        raise ValueError(
            "Please enter your name"
        )

    now = utc_now()

    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

        if not row:
            conn.execute("ROLLBACK")
            raise ValueError("Game not found")

        if row["status"] in {
            "ready",
            "active",
            "finished",
        }:
            conn.execute("COMMIT")
            return dict(row)

        if row["status"] != "waiting":
            conn.execute("ROLLBACK")
            raise ValueError(
                "This game cannot be joined"
            )

        conn.execute(
            """
            UPDATE games
            SET black_name = ?,
                black_joined_at =
                    COALESCE(black_joined_at, ?),
                status = 'ready',
                updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                now,
                now,
                game_id,
            ),
        )

        conn.execute("COMMIT")

    game = get_game(game_id, db_path)

    if not game:
        raise ValueError("Game not found")

    return game


def start_game(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    now = utc_now()
    clock_now = _clock_now_iso()

    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

        if not row:
            conn.execute("ROLLBACK")
            raise ValueError(
                "Game not found"
            )

        if row["status"] == "active":
            conn.execute("COMMIT")
            return dict(row)

        if row["status"] != "ready":
            conn.execute("ROLLBACK")
            raise ValueError(
                "Friend has not joined yet"
            )

        conn.execute(
            """
            UPDATE games
            SET status = 'active',
                started_at =
                    COALESCE(started_at, ?),
                updated_at = ?,
                clock_started_at =
                    CASE
                        WHEN time_control = 'relaxed'
                        THEN NULL
                        ELSE ?
                    END
            WHERE id = ?
            """,
            (
                now,
                now,
                clock_now,
                game_id,
            ),
        )

        conn.execute("COMMIT")

    game = get_game(
        game_id,
        db_path,
    )

    if not game:
        raise ValueError(
            "Game not found"
        )

    return game

def get_moves(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM moves
            WHERE game_id = ?
            ORDER BY ply
            """,
            (game_id,),
        ).fetchall()

        return [dict(r) for r in rows]


def make_move(
    game_id: str,
    uci: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    now_dt = _clock_now_dt()
    now = utc_now()
    clock_now = _clock_now_iso(
        now_dt
    )

    timeout_detected = False

    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

        if not row:
            conn.execute("ROLLBACK")
            raise ValueError(
                "Game not found"
            )

        if row["status"] != "active":
            conn.execute("ROLLBACK")
            raise ValueError(
                "Game is not active"
            )

        board = chess.Board(
            row["fen"]
        )

        turn_role = (
            "white"
            if board.turn == chess.WHITE
            else "black"
        )

        config = clock_config(
            row["time_control"]
        )

        if config is not None:
            base_ms, increment_ms = config

            white_clock_ms = (
                int(row["white_clock_ms"])
                if row["white_clock_ms"] is not None
                else base_ms
            )

            black_clock_ms = (
                int(row["black_clock_ms"])
                if row["black_clock_ms"] is not None
                else base_ms
            )

            elapsed = _elapsed_ms(
                row["clock_started_at"],
                now_dt,
            )

            if turn_role == "white":
                remaining_before_move = max(
                    0,
                    white_clock_ms - elapsed,
                )
            else:
                remaining_before_move = max(
                    0,
                    black_clock_ms - elapsed,
                )

            if remaining_before_move <= 0:
                timeout_detected = True

                result = _timeout_result(
                    turn_role
                )

                if turn_role == "white":
                    white_clock_ms = 0
                else:
                    black_clock_ms = 0

                conn.execute(
                    """
                    UPDATE games
                    SET status = 'finished',
                        result = ?,
                        updated_at = ?,
                        finished_at = ?,
                        white_clock_ms = ?,
                        black_clock_ms = ?,
                        clock_started_at = NULL,
                        finish_reason = 'timeout'
                    WHERE id = ?
                    """,
                    (
                        result,
                        now,
                        now,
                        white_clock_ms,
                        black_clock_ms,
                        game_id,
                    ),
                )

                conn.execute("COMMIT")

            else:
                try:
                    move = chess.Move.from_uci(
                        uci
                    )
                except ValueError as exc:
                    conn.execute("ROLLBACK")
                    raise ValueError(
                        "Invalid move"
                    ) from exc

                if move not in board.legal_moves:
                    conn.execute("ROLLBACK")
                    raise ValueError(
                        "Move is no longer legal. "
                        "The other player may have moved."
                    )

                san = board.san(
                    move
                )

                ply = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM moves
                    WHERE game_id = ?
                    """,
                    (game_id,),
                ).fetchone()["c"] + 1

                board.push(
                    move
                )

                if turn_role == "white":
                    white_clock_ms = (
                        remaining_before_move
                        + increment_ms
                    )
                else:
                    black_clock_ms = (
                        remaining_before_move
                        + increment_ms
                    )

                status = "active"
                result = ""
                finished_at = None
                finish_reason = ""
                next_clock_started_at = clock_now

                if board.is_game_over(
                    claim_draw=True
                ):
                    status = "finished"
                    result = board.result(
                        claim_draw=True
                    )
                    finished_at = now
                    finish_reason = "board"
                    next_clock_started_at = None

                conn.execute(
                    """
                    INSERT INTO moves (
                        game_id,
                        ply,
                        uci,
                        san,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        game_id,
                        ply,
                        uci,
                        san,
                        now,
                    ),
                )

                conn.execute(
                    """
                    UPDATE games
                    SET fen = ?,
                        status = ?,
                        result = ?,
                        updated_at = ?,
                        finished_at = ?,
                        white_clock_ms = ?,
                        black_clock_ms = ?,
                        clock_started_at = ?,
                        finish_reason = ?
                    WHERE id = ?
                    """,
                    (
                        board.fen(),
                        status,
                        result,
                        now,
                        finished_at,
                        white_clock_ms,
                        black_clock_ms,
                        next_clock_started_at,
                        finish_reason,
                        game_id,
                    ),
                )

                conn.execute("COMMIT")

        else:
            # Relaxed mode uses the proven no-clock move path.
            try:
                move = chess.Move.from_uci(
                    uci
                )
            except ValueError as exc:
                conn.execute("ROLLBACK")
                raise ValueError(
                    "Invalid move"
                ) from exc

            if move not in board.legal_moves:
                conn.execute("ROLLBACK")
                raise ValueError(
                    "Move is no longer legal. "
                    "The other player may have moved."
                )

            san = board.san(
                move
            )

            ply = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM moves
                WHERE game_id = ?
                """,
                (game_id,),
            ).fetchone()["c"] + 1

            board.push(
                move
            )

            status = "active"
            result = ""
            finished_at = None
            finish_reason = ""

            if board.is_game_over(
                claim_draw=True
            ):
                status = "finished"
                result = board.result(
                    claim_draw=True
                )
                finished_at = now
                finish_reason = "board"

            conn.execute(
                """
                INSERT INTO moves (
                    game_id,
                    ply,
                    uci,
                    san,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    game_id,
                    ply,
                    uci,
                    san,
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE games
                SET fen = ?,
                    status = ?,
                    result = ?,
                    updated_at = ?,
                    finished_at = ?,
                    clock_started_at = NULL,
                    finish_reason = ?
                WHERE id = ?
                """,
                (
                    board.fen(),
                    status,
                    result,
                    now,
                    finished_at,
                    finish_reason,
                    game_id,
                ),
            )

            conn.execute("COMMIT")

    if timeout_detected:
        raise ValueError(
            "Time expired"
        )

    game = get_game(
        game_id,
        db_path,
    )

    if not game:
        raise ValueError(
            "Game not found"
        )

    return game


def get_clock_state(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    """
    Return a synchronized clock snapshot without writing every second.

    Only an actual timeout causes a write. A second locked check prevents
    a stale clock read from overwriting a move that arrived at the same time.
    """
    now_dt = _clock_now_dt()

    with connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

    if not row:
        return None

    snapshot = _clock_snapshot(
        row,
        now_dt,
    )

    if (
        not snapshot["enabled"]
        or snapshot["status"] != "active"
    ):
        return snapshot

    active_color = snapshot[
        "active_color"
    ]

    active_ms = (
        snapshot["white_ms"]
        if active_color == "white"
        else snapshot["black_ms"]
    )

    if (
        active_ms is None
        or active_ms > 0
    ):
        return snapshot

    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        fresh = conn.execute(
            "SELECT * FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()

        if not fresh:
            conn.execute("ROLLBACK")
            return None

        fresh_snapshot = _clock_snapshot(
            fresh,
            _clock_now_dt(),
        )

        if (
            fresh_snapshot["enabled"]
            and fresh_snapshot["status"] == "active"
        ):
            fresh_color = fresh_snapshot[
                "active_color"
            ]

            fresh_active_ms = (
                fresh_snapshot["white_ms"]
                if fresh_color == "white"
                else fresh_snapshot["black_ms"]
            )

            if (
                fresh_active_ms is not None
                and fresh_active_ms <= 0
            ):
                result = _timeout_result(
                    fresh_color
                )

                white_ms = fresh_snapshot[
                    "white_ms"
                ]
                black_ms = fresh_snapshot[
                    "black_ms"
                ]

                if fresh_color == "white":
                    white_ms = 0
                else:
                    black_ms = 0

                now_text = utc_now()

                conn.execute(
                    """
                    UPDATE games
                    SET status = 'finished',
                        result = ?,
                        updated_at = ?,
                        finished_at = ?,
                        white_clock_ms = ?,
                        black_clock_ms = ?,
                        clock_started_at = NULL,
                        finish_reason = 'timeout'
                    WHERE id = ?
                    """,
                    (
                        result,
                        now_text,
                        now_text,
                        white_ms,
                        black_ms,
                        game_id,
                    ),
                )

        conn.execute("COMMIT")

    updated = get_game(
        game_id,
        db_path,
    )

    if not updated:
        return None

    return _clock_snapshot(
        updated,
        _clock_now_dt(),
    )

def legal_moves(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, str]]:
    game = get_game(
        game_id,
        db_path,
    )

    if not game:
        return []

    board = chess.Board(
        game["fen"]
    )

    items = []

    for move in board.legal_moves:
        items.append(
            {
                "uci": move.uci(),
                "san": board.san(move),
            }
        )

    return items


def list_games(
    include_archived: bool = False,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    where = (
        ""
        if include_archived
        else "WHERE archived = 0"
    )

    with connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                g.*,
                (
                    SELECT COUNT(*)
                    FROM moves m
                    WHERE m.game_id = g.id
                ) AS move_count
            FROM games g
            {where}
            ORDER BY updated_at DESC
            """
        ).fetchall()

        return [dict(r) for r in rows]


def archive_game(
    game_id: str,
    archived: bool = True,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with connection(db_path) as conn:
        conn.execute(
            """
            UPDATE games
            SET archived = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                1 if archived else 0,
                utc_now(),
                game_id,
            ),
        )


def delete_game(
    game_id: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "DELETE FROM games WHERE id = ?",
            (game_id,),
        )
