from __future__ import annotations

import chess


PIECE_MAP = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}


def move_options(fen: str) -> list[tuple[str, str]]:
    board = chess.Board(fen)
    options = []

    for move in board.legal_moves:
        san = board.san(move)
        options.append((san, move.uci()))

    return options


def board_html(fen: str, orientation: str = "white") -> str:
    board = chess.Board(fen)

    files = list("abcdefgh")
    ranks = list(range(8, 0, -1))

    if orientation == "black":
        files = list(reversed(files))
        ranks = list(reversed(ranks))

    cells = []

    for rank in ranks:
        for file_ in files:
            square_name = f"{file_}{rank}"
            square = chess.parse_square(square_name)
            piece = board.piece_at(square)

            file_index = chess.square_file(square)
            rank_index = chess.square_rank(square)

            is_light = (file_index + rank_index) % 2 == 0
            square_class = "light" if is_light else "dark"

            piece_html = PIECE_MAP.get(piece.symbol(), "&nbsp;") if piece else "&nbsp;"

            # coordinate labels
            coord_bottom = ""
            coord_top = ""
            coord_left = ""
            coord_right = ""

            # show file letters on bottom edge
            if orientation == "white":
                if rank == 1:
                    coord_bottom = f'<span class="cb-file">{file_}</span>'
                if file_ == "a":
                    coord_left = f'<span class="cb-rank">{rank}</span>'
            else:
                if rank == 8:
                    coord_top = f'<span class="cb-file">{file_}</span>'
                if file_ == "h":
                    coord_right = f'<span class="cb-rank">{rank}</span>'

            cells.append(
                f"""
                <div class="cb-square {square_class}">
                    {coord_bottom}
                    {coord_top}
                    {coord_left}
                    {coord_right}
                    <span class="cb-piece">{piece_html}</span>
                </div>
                """
            )

    return f"""
    <style>
    .cb-wrap {{
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
    }}

    .cb-board {{
        width: min(92vw, 640px);
        aspect-ratio: 1 / 1;
        display: grid;
        grid-template-columns: repeat(8, 1fr);
        border: 2px solid #1f2a44;
        border-radius: 14px;
        overflow: hidden;
        box-sizing: border-box;
        background: #1f2a44;
    }}

    .cb-square {{
        position: relative;
        width: 100%;
        aspect-ratio: 1 / 1;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
    }}

    .cb-square.light {{
        background: #e7d2a4;
    }}

    .cb-square.dark {{
        background: #a9744a;
    }}

    .cb-piece {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;
        font-size: clamp(28px, 4.2vw, 48px);
        line-height: 1;
        user-select: none;
    }}

    .cb-file {{
        position: absolute;
        right: 6px;
        bottom: 4px;
        font-size: 11px;
        font-weight: 700;
        color: rgba(0,0,0,0.65);
        line-height: 1;
    }}

    .cb-rank {{
        position: absolute;
        left: 6px;
        top: 4px;
        font-size: 11px;
        font-weight: 700;
        color: rgba(0,0,0,0.65);
        line-height: 1;
    }}

    .cb-square.dark .cb-file,
    .cb-square.dark .cb-rank {{
        color: rgba(255,255,255,0.75);
    }}

    @media (max-width: 700px) {{
        .cb-board {{
            width: min(96vw, 520px);
        }}

        .cb-piece {{
            font-size: clamp(24px, 6vw, 40px);
        }}
    }}
    </style>

    <div class="cb-wrap">
        <div class="cb-board">
            {''.join(cells)}
        </div>
    </div>
    """
