from __future__ import annotations

from pathlib import Path

import chess
from PIL import Image, ImageDraw, ImageFont


BOARD_SIZE = 720
LIGHT_SQUARE = "#F0D9B5"
DARK_SQUARE = "#B58863"
SELECTED = "#7C5CFC"
TARGET = "#344054"

PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)

    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def legal_sources(fen: str) -> set[str]:
    board = chess.Board(fen)
    return {
        chess.square_name(move.from_square)
        for move in board.legal_moves
    }


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


def resolve_move(
    fen: str,
    source: str,
    destination: str,
) -> str | None:
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

    candidates.sort(
        key=lambda move: promotion_order.get(
            move.promotion,
            9,
        )
    )

    return candidates[0].uci()


def _screen_square(
    row: int,
    col: int,
    orientation: str,
) -> str:
    if orientation == "black":
        file_index = 7 - col
        rank_index = row
    else:
        file_index = col
        rank_index = 7 - row

    return chess.square_name(
        chess.square(
            file_index,
            rank_index,
        )
    )


def click_to_square(
    x: int | float,
    y: int | float,
    *,
    width: int | float,
    height: int | float,
    orientation: str,
) -> str | None:
    if width <= 0 or height <= 0:
        return None

    col = int(float(x) * 8 / float(width))
    row = int(float(y) * 8 / float(height))

    if not (0 <= col <= 7 and 0 <= row <= 7):
        return None

    return _screen_square(
        row,
        col,
        orientation,
    )


def render_board_image(
    fen: str,
    orientation: str,
    *,
    selected_square: str = "",
    interactive: bool = True,
    size: int = BOARD_SIZE,
) -> Image.Image:
    """
    Render one rigid square image.

    This avoids Streamlit's column/button layout completely, so there can be
    no white gaps between rows, stretched cells, or different board geometry
    between White and Black.
    """
    board = chess.Board(fen)
    selected_square = (selected_square or "").lower().strip()

    sources = (
        legal_sources(fen)
        if interactive
        else set()
    )

    if selected_square not in sources:
        selected_square = ""

    targets = (
        legal_targets(
            fen,
            selected_square,
        )
        if selected_square
        else set()
    )

    image = Image.new(
        "RGB",
        (size, size),
        "white",
    )
    draw = ImageDraw.Draw(image)

    square_px = size / 8
    piece_font = _font(
        max(
            24,
            int(square_px * 0.72),
        )
    )
    coord_font = _font(
        max(
            10,
            int(square_px * 0.13),
        )
    )

    for row in range(8):
        for col in range(8):
            coord = _screen_square(
                row,
                col,
                orientation,
            )
            square = chess.parse_square(
                coord
            )

            file_index = chess.square_file(
                square
            )
            rank_index = chess.square_rank(
                square
            )

            light = (
                (file_index + rank_index) % 2 == 1
            )

            x0 = round(col * square_px)
            y0 = round(row * square_px)
            x1 = round((col + 1) * square_px)
            y1 = round((row + 1) * square_px)

            draw.rectangle(
                (x0, y0, x1, y1),
                fill=(
                    LIGHT_SQUARE
                    if light
                    else DARK_SQUARE
                ),
            )

            if coord == selected_square:
                border = max(
                    4,
                    int(square_px * 0.055),
                )
                draw.rectangle(
                    (
                        x0 + border // 2,
                        y0 + border // 2,
                        x1 - border // 2,
                        y1 - border // 2,
                    ),
                    outline=SELECTED,
                    width=border,
                )

            if coord in targets:
                piece_on_target = board.piece_at(
                    square
                )

                if piece_on_target:
                    border = max(
                        4,
                        int(square_px * 0.055),
                    )
                    draw.ellipse(
                        (
                            x0 + border,
                            y0 + border,
                            x1 - border,
                            y1 - border,
                        ),
                        outline=TARGET,
                        width=border,
                    )
                else:
                    radius = max(
                        6,
                        int(square_px * 0.11),
                    )
                    cx = (
                        x0 + x1
                    ) // 2
                    cy = (
                        y0 + y1
                    ) // 2
                    draw.ellipse(
                        (
                            cx - radius,
                            cy - radius,
                            cx + radius,
                            cy + radius,
                        ),
                        fill=TARGET,
                    )

            piece = board.piece_at(
                square
            )

            if piece:
                symbol = PIECES[
                    piece.symbol()
                ]

                bbox = draw.textbbox(
                    (0, 0),
                    symbol,
                    font=piece_font,
                    stroke_width=1,
                )

                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                tx = (
                    x0
                    + (x1 - x0 - tw) / 2
                    - bbox[0]
                )
                ty = (
                    y0
                    + (y1 - y0 - th) / 2
                    - bbox[1]
                    - square_px * 0.02
                )

                if piece.color == chess.WHITE:
                    fill = "#FFFDF7"
                    stroke_fill = "#111827"
                    stroke_width = max(
                        1,
                        int(square_px * 0.022),
                    )
                else:
                    fill = "#111827"
                    stroke_fill = "#F8FAFC"
                    stroke_width = max(
                        1,
                        int(square_px * 0.012),
                    )

                draw.text(
                    (tx, ty),
                    symbol,
                    font=piece_font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                )

            # Coordinate labels are intentionally tiny and fixed inside
            # the board image, so they cannot affect layout height.
            file_char = coord[0]
            rank_char = coord[1]

            if row == 7:
                label_color = (
                    DARK_SQUARE
                    if light
                    else LIGHT_SQUARE
                )
                draw.text(
                    (
                        x1 - square_px * 0.16,
                        y1 - square_px * 0.18,
                    ),
                    file_char,
                    font=coord_font,
                    fill=label_color,
                    anchor="mm",
                )

            if col == 0:
                label_color = (
                    DARK_SQUARE
                    if light
                    else LIGHT_SQUARE
                )
                draw.text(
                    (
                        x0 + square_px * 0.08,
                        y0 + square_px * 0.11,
                    ),
                    rank_char,
                    font=coord_font,
                    fill=label_color,
                    anchor="mm",
                )

    # A fixed border is drawn inside the image itself.
    border_width = max(
        3,
        int(size * 0.005),
    )
    draw.rectangle(
        (
            0,
            0,
            size - 1,
            size - 1,
        ),
        outline="#111827",
        width=border_width,
    )

    return image
