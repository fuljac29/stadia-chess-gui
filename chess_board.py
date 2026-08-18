from __future__ import annotations

import html
from urllib.parse import urlencode

import chess


PIECES = {
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


def _player_href(
    seat_token: str,
    lang: str,
    *,
    src: str = "",
    move: str = "",
) -> str:
    params = {
        "embed": "true",
        "seat": seat_token,
        "lang": lang,
    }

    if src:
        params["src"] = src

    if move:
        params["move"] = move

    return "?" + urlencode(params)


def _promotion_preference(
    move: chess.Move,
) -> int:
    # If several promotion moves reach the same square,
    # use Queen by default to keep the click flow simple.
    if move.promotion == chess.QUEEN:
        return 0
    if move.promotion == chess.ROOK:
        return 1
    if move.promotion == chess.BISHOP:
        return 2
    if move.promotion == chess.KNIGHT:
        return 3
    return 4


def board_html(
    fen: str,
    orientation: str = "white",
    *,
    seat_token: str = "",
    lang: str = "EN",
    interactive: bool = False,
    selected_square: str = "",
) -> str:
    board = chess.Board(fen)

    if orientation == "black":
        ranks = range(0, 8)
        files = range(7, -1, -1)
    else:
        ranks = range(7, -1, -1)
        files = range(0, 8)

    legal_by_source: dict[str, list[chess.Move]] = {}

    if interactive:
        for move in board.legal_moves:
            source = chess.square_name(
                move.from_square
            )
            legal_by_source.setdefault(
                source,
                [],
            ).append(move)

    selected_square = (
        selected_square or ""
    ).lower().strip()

    if selected_square not in legal_by_source:
        selected_square = ""

    destination_moves: dict[str, chess.Move] = {}

    if selected_square:
        candidates = sorted(
            legal_by_source[selected_square],
            key=_promotion_preference,
        )

        for move in candidates:
            destination = chess.square_name(
                move.to_square
            )
            destination_moves.setdefault(
                destination,
                move,
            )

    cells = []

    for rank in ranks:
        for file in files:
            square = chess.square(
                file,
                rank,
            )
            coord = chess.square_name(
                square
            )
            piece = board.piece_at(
                square
            )

            symbol = (
                PIECES.get(
                    piece.symbol(),
                    "",
                )
                if piece
                else ""
            )

            light = (
                (file + rank) % 2 == 1
            )

            classes = [
                "sq",
                "light" if light else "dark",
            ]

            href = ""
            title = coord

            if interactive:
                if selected_square:
                    if coord == selected_square:
                        classes += [
                            "selected",
                            "clickable",
                        ]
                        href = _player_href(
                            seat_token,
                            lang,
                        )

                    elif coord in destination_moves:
                        classes += [
                            "target",
                            "clickable",
                        ]

                        if piece:
                            classes.append(
                                "capture"
                            )

                        href = _player_href(
                            seat_token,
                            lang,
                            move=destination_moves[
                                coord
                            ].uci(),
                        )

                    elif coord in legal_by_source:
                        classes += [
                            "selectable",
                            "clickable",
                        ]
                        href = _player_href(
                            seat_token,
                            lang,
                            src=coord,
                        )

                elif coord in legal_by_source:
                    classes += [
                        "selectable",
                        "clickable",
                    ]
                    href = _player_href(
                        seat_token,
                        lang,
                        src=coord,
                    )

            class_text = " ".join(
                classes
            )
            piece_html = html.escape(
                symbol
            )

            inner = (
                f'<span class="piece">'
                f'{piece_html}'
                f'</span>'
            )

            if href:
                cells.append(
                    f'<a class="{class_text}" '
                    f'href="{html.escape(href, quote=True)}" '
                    f'target="_self" '
                    f'title="{html.escape(title, quote=True)}">'
                    f'{inner}</a>'
                )
            else:
                cells.append(
                    f'<div class="{class_text}" '
                    f'title="{html.escape(title, quote=True)}">'
                    f'{inner}</div>'
                )

    return f"""
    <style>
      .stadia-board {{
        display:grid;
        grid-template-columns:repeat(8,minmax(0,1fr));
        grid-template-rows:repeat(8,minmax(0,1fr));
        width:min(100%,720px);
        aspect-ratio:1 / 1;
        border:3px solid #111827;
        border-radius:16px;
        overflow:hidden;
        box-sizing:border-box;
        box-shadow:0 18px 45px rgba(17,24,39,.12);
      }}

      .stadia-board .sq {{
        position:relative;
        display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        height:100%;
        min-width:0;
        min-height:0;
        overflow:hidden;
        box-sizing:border-box;
        text-decoration:none;
        color:inherit;
      }}

      .stadia-board .light {{
        background:#f2d9a5;
      }}

      .stadia-board .dark {{
        background:#9b6845;
      }}

      .stadia-board .piece {{
        position:relative;
        z-index:2;
        display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        height:100%;
        font-family:"Segoe UI Symbol","Arial Unicode MS",sans-serif;
        font-size:clamp(30px,6.3vw,70px);
        line-height:1;
        filter:drop-shadow(0 1px 0 rgba(255,255,255,.35));
        user-select:none;
        pointer-events:none;
      }}

      .stadia-board .clickable {{
        cursor:pointer;
      }}

      .stadia-board .selectable::before {{
        content:"";
        position:absolute;
        inset:8%;
        z-index:1;
        border:3px solid rgba(111,76,255,.32);
        border-radius:10px;
        box-sizing:border-box;
      }}

      .stadia-board .selected {{
        box-shadow:
          inset 0 0 0 5px #6f4cff,
          inset 0 0 0 8px rgba(255,255,255,.55);
      }}

      .stadia-board .target::after {{
        content:"";
        position:absolute;
        z-index:1;
        width:24%;
        aspect-ratio:1 / 1;
        border-radius:999px;
        background:rgba(44,62,80,.42);
        pointer-events:none;
      }}

      .stadia-board .target.capture::after {{
        width:78%;
        aspect-ratio:1 / 1;
        background:transparent;
        border:5px solid rgba(44,62,80,.42);
        box-sizing:border-box;
      }}

      .stadia-board .clickable:hover {{
        filter:brightness(1.06);
      }}

      @media(max-width:760px) {{
        .stadia-board .selectable::before {{
          inset:6%;
          border-width:2px;
        }}

        .stadia-board .selected {{
          box-shadow:
            inset 0 0 0 4px #6f4cff,
            inset 0 0 0 6px rgba(255,255,255,.55);
        }}
      }}
    </style>

    <div class="stadia-board">
      {''.join(cells)}
    </div>
    """


def move_options(
    fen: str,
) -> list[tuple[str, str]]:
    # Backward compatibility with older admin/test code.
    board = chess.Board(fen)

    result = []

    for move in board.legal_moves:
        result.append(
            (
                board.san(move),
                move.uci(),
            )
        )

    result.sort(
        key=lambda x: x[0]
    )

    return result
