from __future__ import annotations

from collections.abc import Callable

import chess
import streamlit as st


PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}


def _display_squares(orientation: str) -> list[str]:
    if orientation == "black":
        ranks = range(1, 9)
        files = "hgfedcba"
    else:
        ranks = range(8, 0, -1)
        files = "abcdefgh"

    return [f"{file_}{rank}" for rank in ranks for file_ in files]


def legal_sources(fen: str) -> set[str]:
    board = chess.Board(fen)
    return {chess.square_name(move.from_square) for move in board.legal_moves}


def legal_targets(fen: str, source: str) -> set[str]:
    source = (source or "").lower().strip()
    if not source:
        return set()

    board = chess.Board(fen)
    return {
        chess.square_name(move.to_square)
        for move in board.legal_moves
        if chess.square_name(move.from_square) == source
    }


def resolve_move(fen: str, source: str, destination: str) -> str | None:
    """Resolve source→destination to a legal UCI move; queen promotion is preferred."""
    source = (source or "").lower().strip()
    destination = (destination or "").lower().strip()
    board = chess.Board(fen)

    candidates = [
        move
        for move in board.legal_moves
        if chess.square_name(move.from_square) == source
        and chess.square_name(move.to_square) == destination
    ]
    if not candidates:
        return None

    promotion_order = {
        chess.QUEEN: 0,
        chess.ROOK: 1,
        chess.BISHOP: 2,
        chess.KNIGHT: 3,
        None: 4,
    }
    candidates.sort(key=lambda move: promotion_order.get(move.promotion, 9))
    return candidates[0].uci()


def render_board(
    fen: str,
    orientation: str,
    *,
    game_key: str,
    selected_square: str = "",
    interactive: bool = True,
    on_square_click: Callable[[str], None] | None = None,
) -> None:
    """Render the board with native Streamlit buttons, so clicks do not navigate the iframe."""
    board = chess.Board(fen)
    squares = _display_squares(orientation)
    selected_square = (selected_square or "").lower().strip()
    sources = legal_sources(fen) if interactive else set()

    if selected_square not in sources:
        selected_square = ""

    targets = legal_targets(fen, selected_square) if selected_square else set()
    safe_game_key = "".join(ch if ch.isalnum() else "_" for ch in game_key)

    css_rules = [f"""
    .st-key-chess_board_{safe_game_key} {{
        max-width:720px;
        margin:0 auto;
        border:3px solid #111827;
        border-radius:16px;
        overflow:hidden;
        box-shadow:0 18px 45px rgba(17,24,39,.12);
    }}
    .st-key-chess_board_{safe_game_key} div[data-testid="stHorizontalBlock"],
    .st-key-chess_board_{safe_game_key} div[data-testid="stVerticalBlock"] {{
        gap:0 !important;
    }}
    .st-key-chess_board_{safe_game_key} button {{
        width:100% !important;
        aspect-ratio:1/1 !important;
        min-height:0 !important;
        height:auto !important;
        padding:0 !important;
        margin:0 !important;
        border:0 !important;
        border-radius:0 !important;
        font-family:"Segoe UI Symbol","Arial Unicode MS",sans-serif !important;
        font-size:clamp(30px,5.6vw,64px) !important;
        line-height:1 !important;
        position:relative !important;
        box-shadow:none;
    }}
    .st-key-chess_board_{safe_game_key} button:disabled {{
        opacity:1 !important;
        cursor:default !important;
    }}
    """]

    for coord in squares:
        square = chess.parse_square(coord)
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        is_light = (file_index + rank_index) % 2 == 1
        background = "#f2d9a5" if is_light else "#9b6845"
        key_class = f".st-key-sq_{safe_game_key}_{coord}"

        css_rules.append(f"""
        {key_class} button,
        {key_class} button:hover,
        {key_class} button:focus {{
            background:{background} !important;
            color:#111827 !important;
        }}
        """)

        if coord in sources and interactive:
            css_rules.append(f"""
            {key_class} button {{ cursor:pointer !important; }}
            {key_class} button:hover {{ filter:brightness(1.07); }}
            """)

        if coord == selected_square:
            css_rules.append(f"""
            {key_class} button {{
                box-shadow:inset 0 0 0 5px #6f4cff,
                           inset 0 0 0 8px rgba(255,255,255,.55) !important;
            }}
            """)

        if coord in targets:
            if board.piece_at(square):
                css_rules.append(f"""
                {key_class} button {{
                    box-shadow:inset 0 0 0 5px rgba(44,62,80,.55) !important;
                }}
                """)
            else:
                css_rules.append(f"""
                {key_class} button::after {{
                    content:"";
                    position:absolute;
                    width:22%;
                    aspect-ratio:1/1;
                    border-radius:999px;
                    background:rgba(44,62,80,.48);
                    pointer-events:none;
                }}
                """)

    st.markdown("<style>" + "\n".join(css_rules) + "</style>", unsafe_allow_html=True)

    with st.container(key=f"chess_board_{safe_game_key}", border=False):
        for row_start in range(0, 64, 8):
            row_squares = squares[row_start:row_start + 8]
            cols = st.columns(8, gap=None)

            for col, coord in zip(cols, row_squares):
                square = chess.parse_square(coord)
                piece = board.piece_at(square)
                symbol = PIECES.get(piece.symbol(), " ") if piece else " "

                with col:
                    st.button(
                        symbol,
                        key=f"sq_{safe_game_key}_{coord}",
                        help=coord,
                        disabled=not interactive,
                        use_container_width=True,
                        on_click=on_square_click,
                        args=(coord,),
                    )
