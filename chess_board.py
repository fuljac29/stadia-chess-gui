from __future__ import annotations

from functools import lru_cache
from glob import glob
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


@lru_cache(maxsize=64)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Return a scalable font that contains chess symbols.

    Streamlit Cloud does not guarantee the same system fonts on every
    deployment. We therefore search several common locations and finally use
    Pillow's own scalable default font instead of falling back to the tiny
    bitmap font that caused the microscopic pieces in v0.8.4.
    """
    candidates = [
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
    ]

    candidates.extend(
        glob(
            "/usr/local/lib/python*/site-packages/"
            "matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"
        )
    )
    candidates.extend(
        glob(
            "/home/appuser/venv/lib/python*/site-packages/"
            "matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"
        )
    )

    for candidate in candidates:
        try:
            if Path(candidate).exists():
                return ImageFont.truetype(
                    candidate,
                    size=size,
                )
        except OSError:
            pass

    try:
        return ImageFont.truetype(
            "DejaVuSans.ttf",
            size=size,
        )
    except OSError:
        pass

    # Pillow 10.1+ provides a scalable bundled default font.
    # This is the important fallback on Streamlit Cloud.
    try:
        return ImageFont.load_default(
            size=size
        )
    except TypeError:
        return ImageFont.load_default()


@lru_cache(maxsize=64)
def _piece_font(
    symbol: str,
    square_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Fit each chess glyph to about 80% of a square, independent of the font's
    internal metrics. This keeps the pieces large and consistent.
    """
    target = max(
        30,
        int(square_size * 0.80),
    )

    probe_size = max(
        48,
        int(square_size * 1.45),
    )
    probe_font = _font(
        probe_size
    )

    probe_image = Image.new(
        "L",
        (
            square_size * 2,
            square_size * 2,
        ),
        0,
    )
    probe_draw = ImageDraw.Draw(
        probe_image
    )

    bbox = probe_draw.textbbox(
        (0, 0),
        symbol,
        font=probe_font,
        stroke_width=1,
    )

    width = max(
        1,
        bbox[2] - bbox[0],
    )
    height = max(
        1,
        bbox[3] - bbox[1],
    )

    scale = min(
        target / width,
        target / height,
    )

    fitted_size = max(
        30,
        int(probe_size * scale),
    )

    return _font(
        fitted_size
    )


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

                piece_font = _piece_font(
                    symbol,
                    int(square_px),
                )

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
                        int(square_px * 0.028),
                    )
                else:
                    fill = "#111827"
                    stroke_fill = "#F8FAFC"
                    stroke_width = max(
                        1,
                        int(square_px * 0.018),
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
