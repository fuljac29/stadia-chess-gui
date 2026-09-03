from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple


FILES = "abcdefghij"
WIDTH = 10
HEIGHT = 8
WHITE = True
BLACK = False
INITIAL_BACK = "RNTBKQBINR"


def _color(piece: str) -> bool:
    return piece.isupper()


def _kind(piece: str) -> str:
    return piece.upper()


def _inside(x: int, y: int) -> bool:
    return 0 <= x < WIDTH and 0 <= y < HEIGHT


def _square_name(square: Tuple[int, int]) -> str:
    return f"{FILES[square[0]]}{square[1] + 1}"


def _parse_square(value: str) -> Tuple[int, int]:
    if len(value) != 2 or value[0] not in FILES or value[1] not in "12345678":
        raise ValueError("Invalid square")
    return FILES.index(value[0]), int(value[1]) - 1


@dataclass(frozen=True)
class Move:
    src: Tuple[int, int]
    dst: Tuple[int, int]
    piece: str = ""
    captured: Optional[str] = None
    promotion: Optional[str] = None
    en_passant: bool = False
    castle: Optional[str] = None

    @classmethod
    def from_uci(cls, value: str) -> "Move":
        text = str(value or "").strip().lower()
        if len(text) not in (4, 5):
            raise ValueError("Invalid move")
        promotion = text[4].upper() if len(text) == 5 else None
        if promotion and promotion not in "QRBNTI":
            raise ValueError("Invalid promotion")
        return cls(_parse_square(text[:2]), _parse_square(text[2:4]), promotion=promotion)

    def uci(self) -> str:
        return _square_name(self.src) + _square_name(self.dst) + (self.promotion or "").lower()


class Board:
    DIAG = ((-1, -1), (1, -1), (-1, 1), (1, 1))
    ORTHO = ((-1, 0), (1, 0), (0, -1), (0, 1))
    KING = DIAG + ORTHO
    KNIGHT = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))

    def __init__(
        self,
        board: Optional[Dict[Tuple[int, int], str]] = None,
        turn: bool = WHITE,
        castling: str = "KQkq",
        ep: Optional[Tuple[int, int]] = None,
        halfmove: int = 0,
        fullmove: int = 1,
        repetition_count: int = 1,
    ) -> None:
        self.board = dict(board or {})
        self.turn = bool(turn)
        self.castling = "".join(c for c in "KQkq" if c in castling)
        self.ep = ep
        self.halfmove = int(halfmove)
        self.fullmove = int(fullmove)
        self.repetition_count = int(repetition_count)

    @classmethod
    def initial(cls) -> "Board":
        board: Dict[Tuple[int, int], str] = {}
        for x, piece in enumerate(INITIAL_BACK):
            board[(x, 0)] = piece
            board[(x, 1)] = "P"
            board[(x, 6)] = "p"
            board[(x, 7)] = piece.lower()
        return cls(board=board)

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        parts = str(fen or "").split()
        if len(parts) < 4:
            raise ValueError("Invalid 10x8 FEN")
        ranks = parts[0].split("/")
        if len(ranks) != HEIGHT:
            raise ValueError("Invalid 10x8 FEN")
        board: Dict[Tuple[int, int], str] = {}
        for row, encoded in enumerate(ranks):
            x = 0
            index = 0
            while index < len(encoded):
                ch = encoded[index]
                if ch.isdigit():
                    end = index + 1
                    while end < len(encoded) and encoded[end].isdigit():
                        end += 1
                    x += int(encoded[index:end])
                    index = end
                    continue
                if ch.upper() not in "PNBRQKTI" or x >= WIDTH:
                    raise ValueError("Invalid 10x8 FEN")
                board[(x, HEIGHT - 1 - row)] = ch
                x += 1
                index += 1
            if x != WIDTH:
                raise ValueError("Invalid 10x8 FEN")
        ep = None if parts[3] == "-" else _parse_square(parts[3])
        return cls(
            board=board,
            turn=parts[1] == "w",
            castling="" if parts[2] == "-" else parts[2],
            ep=ep,
            halfmove=int(parts[4]) if len(parts) > 4 else 0,
            fullmove=int(parts[5]) if len(parts) > 5 else 1,
        )

    def copy(self) -> "Board":
        return Board(self.board, self.turn, self.castling, self.ep, self.halfmove, self.fullmove, self.repetition_count)

    def fen(self) -> str:
        rows = []
        for y in range(HEIGHT - 1, -1, -1):
            row = []
            empty = 0
            for x in range(WIDTH):
                piece = self.board.get((x, y))
                if piece:
                    if empty:
                        row.append(str(empty))
                        empty = 0
                    row.append(piece)
                else:
                    empty += 1
            if empty:
                row.append(str(empty))
            rows.append("".join(row))
        return " ".join(("/".join(rows), "w" if self.turn else "b", self.castling or "-", _square_name(self.ep) if self.ep else "-", str(self.halfmove), str(self.fullmove)))

    def position_key(self) -> str:
        return " ".join(self.fen().split()[:4])

    def _add_target(self, out: list[Move], src: Tuple[int, int], dst: Tuple[int, int], piece: str) -> None:
        if not _inside(*dst):
            return
        target = self.board.get(dst)
        if not target or _color(target) != _color(piece):
            out.append(Move(src, dst, piece, target))

    def _transparent_neutralized(self, src: Tuple[int, int], side: bool) -> bool:
        x, y = src
        for dx, dy in self.KING:
            piece = self.board.get((x + dx, y + dy))
            if piece and _color(piece) != side and _kind(piece) == "I":
                return True
        return False

    def _transparent_moves(self, src: Tuple[int, int], piece: str) -> list[Move]:
        out: list[Move] = []
        side = _color(piece)
        neutralized = self._transparent_neutralized(src, side)
        for step_x, step_y in self.DIAG:
            jumped = False
            for distance in (1, 2, 3):
                dst = (src[0] + step_x * distance, src[1] + step_y * distance)
                if not _inside(*dst):
                    break
                target = self.board.get(dst)
                if neutralized:
                    if target is None:
                        out.append(Move(src, dst, piece))
                        continue
                    if _color(target) != side:
                        out.append(Move(src, dst, piece, target))
                    break
                if not jumped:
                    if target is None:
                        out.append(Move(src, dst, piece))
                    else:
                        if _color(target) != side:
                            out.append(Move(src, dst, piece, target))
                        jumped = True
                elif target is None:
                    out.append(Move(src, dst, piece))
                else:
                    if _color(target) != side:
                        out.append(Move(src, dst, piece, target))
                    break
        return out

    def _castle_moves(self, side: bool) -> list[Move]:
        y = 0 if side else 7
        king = "K" if side else "k"
        rook = "R" if side else "r"
        if self.board.get((4, y)) != king or self.is_check(side):
            return []
        rights = ("K", "Q") if side else ("k", "q")
        opponent = not side
        out: list[Move] = []
        if rights[1] in self.castling and self.board.get((0, y)) == rook:
            if all((x, y) not in self.board for x in (1, 2, 3)) and not self.is_attacked((3, y), opponent) and not self.is_attacked((2, y), opponent):
                out.append(Move((4, y), (2, y), king, castle="Q"))
        if rights[0] in self.castling and self.board.get((9, y)) == rook:
            if all((x, y) not in self.board for x in (5, 6, 7, 8)) and not self.is_attacked((5, y), opponent) and not self.is_attacked((6, y), opponent):
                out.append(Move((4, y), (6, y), king, castle="K"))
        return out

    def _pseudo(self, src: Tuple[int, int], attacks_only: bool = False) -> list[Move]:
        piece = self.board.get(src)
        if not piece:
            return []
        side = _color(piece)
        kind = _kind(piece)
        x, y = src
        out: list[Move] = []
        if kind == "P":
            dy = 1 if side else -1
            start = 1 if side else 6
            promo = 7 if side else 0
            for dx in (-1, 1):
                dst = (x + dx, y + dy)
                if not _inside(*dst):
                    continue
                target = self.board.get(dst)
                if attacks_only:
                    out.append(Move(src, dst, piece, target))
                    continue
                is_ep = self.ep == dst and target is None
                if (target and _color(target) != side) or is_ep:
                    captured = target or self.board.get((dst[0], dst[1] - dy))
                    if dst[1] == promo:
                        for promotion in "QRBNTI":
                            out.append(Move(src, dst, piece, captured, promotion, is_ep))
                    else:
                        out.append(Move(src, dst, piece, captured, en_passant=is_ep))
            if attacks_only:
                return out
            one = (x, y + dy)
            if _inside(*one) and one not in self.board:
                if one[1] == promo:
                    for promotion in "QRBNTI":
                        out.append(Move(src, one, piece, promotion=promotion))
                else:
                    out.append(Move(src, one, piece))
                two = (x, y + 2 * dy)
                if y == start and two not in self.board:
                    out.append(Move(src, two, piece))
            return out
        if kind == "N":
            for dx, dy in self.KNIGHT:
                self._add_target(out, src, (x + dx, y + dy), piece)
            return out
        if kind == "I":
            for dx, dy in self.KING:
                self._add_target(out, src, (x + dx, y + dy), piece)
            return out
        if kind == "T":
            return self._transparent_moves(src, piece)
        if kind in "BRQ":
            directions: Iterable[Tuple[int, int]] = self.DIAG if kind == "B" else self.ORTHO if kind == "R" else self.KING
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                while _inside(nx, ny):
                    target = self.board.get((nx, ny))
                    if target:
                        if _color(target) != side:
                            out.append(Move(src, (nx, ny), piece, target))
                        break
                    out.append(Move(src, (nx, ny), piece))
                    nx += dx
                    ny += dy
            return out
        if kind == "K":
            for dx, dy in self.KING:
                self._add_target(out, src, (x + dx, y + dy), piece)
            if not attacks_only:
                out.extend(self._castle_moves(side))
        return out

    def king_square(self, side: bool) -> Optional[Tuple[int, int]]:
        target = "K" if side else "k"
        return next((square for square, piece in self.board.items() if piece == target), None)

    def is_attacked(self, square: Tuple[int, int], by_side: bool) -> bool:
        for src, piece in list(self.board.items()):
            if _color(piece) == by_side and any(move.dst == square for move in self._pseudo(src, True)):
                return True
        return False

    def is_check(self, side: Optional[bool] = None) -> bool:
        side = self.turn if side is None else side
        king = self.king_square(side)
        return king is None or self.is_attacked(king, not side)

    @property
    def legal_moves(self) -> list[Move]:
        out: list[Move] = []
        for src, piece in list(self.board.items()):
            if _color(piece) != self.turn:
                continue
            for move in self._pseudo(src):
                if move.captured and _kind(move.captured) == "K":
                    continue
                copy = self.copy()
                copy._push_unchecked(move)
                if not copy.is_check(self.turn):
                    out.append(move)
        return out

    def find_legal_move(self, uci: str) -> Move:
        requested = Move.from_uci(uci)
        for move in self.legal_moves:
            if move.src == requested.src and move.dst == requested.dst and move.promotion == requested.promotion:
                return move
        raise ValueError("Move is no longer legal. The other player may have moved.")

    def _push_unchecked(self, move: Move) -> None:
        piece = self.board.pop(move.src)
        side = _color(piece)
        kind = _kind(piece)
        captured = move.captured
        if move.en_passant:
            dy = 1 if side else -1
            captured = self.board.pop((move.dst[0], move.dst[1] - dy), None)
        else:
            self.board.pop(move.dst, None)
        placed = move.promotion if side else (move.promotion or "").lower()
        self.board[move.dst] = placed if move.promotion else piece
        if move.castle:
            y = 0 if side else 7
            rook_src = (9, y) if move.castle == "K" else (0, y)
            rook_dst = (5, y) if move.castle == "K" else (3, y)
            self.board[rook_dst] = self.board.pop(rook_src)
        if kind == "K":
            for right in (("K", "Q") if side else ("k", "q")):
                self.castling = self.castling.replace(right, "")
        if kind == "R":
            home = 0 if side else 7
            if move.src == (0, home):
                self.castling = self.castling.replace("Q" if side else "q", "")
            elif move.src == (9, home):
                self.castling = self.castling.replace("K" if side else "k", "")
        opponent_home = 7 if side else 0
        if captured and _kind(captured) == "R" and move.dst[1] == opponent_home:
            if move.dst[0] == 0:
                self.castling = self.castling.replace("q" if side else "Q", "")
            elif move.dst[0] == 9:
                self.castling = self.castling.replace("k" if side else "K", "")
        self.ep = None
        if kind == "P" and abs(move.dst[1] - move.src[1]) == 2:
            self.ep = (move.src[0], (move.src[1] + move.dst[1]) // 2)
        self.halfmove = 0 if kind == "P" or captured else self.halfmove + 1
        if not side:
            self.fullmove += 1
        self.turn = not side

    def push(self, move: Move) -> None:
        legal = self.find_legal_move(move.uci())
        self._push_unchecked(legal)

    def san(self, move: Move) -> str:
        legal = self.find_legal_move(move.uci())
        if legal.castle:
            notation = "O-O" if legal.castle == "K" else "O-O-O"
        else:
            notation = ("" if _kind(legal.piece) == "P" else _kind(legal.piece))
            if legal.captured:
                notation += "x"
            notation += _square_name(legal.dst)
            if legal.promotion:
                notation += "=" + legal.promotion
        copy = self.copy()
        copy._push_unchecked(legal)
        if not copy.legal_moves and copy.is_check():
            notation += "#"
        elif copy.is_check():
            notation += "+"
        return notation

    def is_game_over(self, claim_draw: bool = True) -> bool:
        return not self.legal_moves or self.halfmove >= 100 or (claim_draw and self.repetition_count >= 3)

    def result(self, claim_draw: bool = True) -> str:
        if not self.legal_moves:
            if self.is_check():
                return "0-1" if self.turn else "1-0"
            return "1/2-1/2"
        if self.halfmove >= 100 or (claim_draw and self.repetition_count >= 3):
            return "1/2-1/2"
        return "*"


def initial_fen() -> str:
    return Board.initial().fen()

