\
from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class Seat:
    game_id: str
    role: str  # "white" or "black"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def make_seat_token(game_id: str, role: str, secret: str) -> str:
    if role not in {"white", "black"}:
        raise ValueError("Invalid role")
    payload = _b64encode(f"{game_id}|{role}".encode("utf-8"))
    signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_seat_token(token: str, secret: str) -> Seat | None:
    try:
        payload, signature = token.split(".", 1)
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        decoded = _b64decode(payload).decode("utf-8")
        game_id, role = decoded.split("|", 1)
        if role not in {"white", "black"}:
            return None
        if not game_id:
            return None
        return Seat(game_id=game_id, role=role)
    except Exception:
        return None
