\
from __future__ import annotations

import html

import chess


PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}


def board_html(fen: str, orientation: str = "white") -> str:
    board = chess.Board(fen)
    if orientation == "black":
        ranks = range(0, 8)
        files = range(7, -1, -1)
    else:
        ranks = range(7, -1, -1)
        files = range(0, 8)

    cells = []
    for rank in ranks:
        for file in files:
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            symbol = PIECES.get(piece.symbol(), "") if piece else ""
            light = (file + rank) % 2 == 1
            cls = "light" if light else "dark"
            coord = chess.square_name(square)
            cells.append(
                f'<div class="sq {cls}" title="{coord}">'
                f'<span class="piece">{html.escape(symbol)}</span>'
                f'</div>'
            )

    return f"""
    <style>
      .stadia-board {{
        display:grid;
        grid-template-columns:repeat(8,1fr);
        width:min(100%,720px);
        aspect-ratio:1/1;
        border:3px solid #111827;
        border-radius:16px;
        overflow:hidden;
        box-shadow:0 18px 45px rgba(17,24,39,.12);
      }}
      .stadia-board .sq {{
        display:flex;
        align-items:center;
        justify-content:center;
        min-width:0;
        min-height:0;
      }}
      .stadia-board .light {{ background:#f2d9a5; }}
      .stadia-board .dark {{ background:#9b6845; }}
      .stadia-board .piece {{
        font-family:"Segoe UI Symbol","Arial Unicode MS",sans-serif;
        font-size:clamp(30px,6.3vw,70px);
        line-height:1;
        filter:drop-shadow(0 1px 0 rgba(255,255,255,.35));
      }}
    </style>
    <div class="stadia-board">{''.join(cells)}</div>
    """


def move_options(fen: str) -> list[tuple[str, str]]:
    board = chess.Board(fen)
    result = []
    for move in board.legal_moves:
        result.append((board.san(move), move.uci()))
    result.sort(key=lambda x: x[0])
    return result
