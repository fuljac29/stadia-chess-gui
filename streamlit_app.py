from __future__ import annotations

import os
from urllib.parse import quote, urlencode

import chess
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import chess_db as db
from chess_board import board_html, move_options
from chess_tokens import make_seat_token, verify_seat_token
from i18n import LANGUAGES, tr


st.set_page_config(
    page_title="Stadia Private Chess",
    page_icon="♟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()


def secret(name: str, default: str) -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)


APP_SECRET = secret("APP_SECRET", "DEV-ONLY-CHANGE-ME")

# Permanent White/Black links must always stay inside Stadia.
# This is intentionally fixed in code so Streamlit Secrets cannot
# accidentally redirect players back to streamlit.app.
STADIA_PUBLIC_URL = "https://stadiaorg.com/stadia-premium-arena/".rstrip("/")


def seat_link(game_id: str, role: str, lang: str) -> str:
    token = make_seat_token(game_id, role, APP_SECRET)
    return f"{STADIA_PUBLIC_URL}/?{urlencode({'seat': token, 'lang': lang})}"


def invitation_text(lang: str, black_link: str) -> str:
    messages = {
        "EN": (
            "I invite you to play a private chess game on Stadia.\n\n"
            "Open this link to join the game as Black:\n"
            f"{black_link}\n\n"
            "See you on the board!"
        ),
        "IT": (
            "Ti invito a giocare una partita privata a scacchi su Stadia.\n\n"
            "Apri questo link per entrare nella partita con i Neri:\n"
            f"{black_link}\n\n"
            "Ci vediamo sulla scacchiera!"
        ),
        "DE": (
            "Ich lade dich zu einer privaten Schachpartie auf Stadia ein.\n\n"
            "Öffne diesen Link, um als Schwarz an der Partie teilzunehmen:\n"
            f"{black_link}\n\n"
            "Bis gleich am Schachbrett!"
        ),
        "FR": (
            "Je t'invite à jouer une partie d'échecs privée sur Stadia.\n\n"
            "Ouvre ce lien pour rejoindre la partie avec les Noirs :\n"
            f"{black_link}\n\n"
            "À bientôt sur l'échiquier !"
        ),
        "ES": (
            "Te invito a jugar una partida privada de ajedrez en Stadia.\n\n"
            "Abre este enlace para entrar en la partida con Negras:\n"
            f"{black_link}\n\n"
            "¡Nos vemos en el tablero!"
        ),
    }

    return messages.get(lang, messages["EN"])


def invitation_subject(lang: str) -> str:
    subjects = {
        "EN": "Stadia Private Chess invitation",
        "IT": "Invito a una partita privata di scacchi su Stadia",
        "DE": "Einladung zu einer privaten Schachpartie auf Stadia",
        "FR": "Invitation à une partie d'échecs privée sur Stadia",
        "ES": "Invitación a una partida privada de ajedrez en Stadia",
    }

    return subjects.get(lang, subjects["EN"])


def inject_css():
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1220px;
            padding-top: 1.6rem;
            padding-bottom: 4rem;
        }

        h1,h2,h3 {
            letter-spacing:-0.02em;
        }

        .sv-hero {
            border:1px solid #e7e4ff;
            border-radius:26px;
            padding:30px;
            background:linear-gradient(135deg,#fff 0%,#faf8ff 100%);
            margin-bottom:20px;
        }

        .sv-hero h1 {
            font-size:46px;
            margin:0 0 4px 0;
        }

        .sv-hero .gradient {
            background:linear-gradient(90deg,#ec3f83,#7657ff);
            -webkit-background-clip:text;
            color:transparent;
        }

        .sv-card {
            border:1px solid #e7e4ff;
            border-radius:22px;
            padding:22px;
            background:#fff;
            margin:10px 0 18px 0;
        }

        .sv-status {
            display:inline-block;
            padding:7px 11px;
            border-radius:999px;
            background:#f0edff;
            color:#5038c8;
            font-weight:800;
            font-size:13px;
        }

        .sv-side {
            display:inline-block;
            padding:8px 12px;
            border-radius:999px;
            background:#111827;
            color:#fff;
            font-weight:900;
        }

        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height:54px;
            border-radius:14px;
            font-weight:850;
            font-size:15px;
        }

        [data-testid="stLinkButton"] a {
            min-height:54px;
            border-radius:14px;
            font-weight:850;
            font-size:15px;
            display:flex;
            align-items:center;
            justify-content:center;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stSelectbox"] > div > div {
            min-height:48px;
        }

        code {
            word-break:break-all;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

# Language travels with player links.
query_lang = str(st.query_params.get("lang", "EN")).upper()

if query_lang not in LANGUAGES:
    query_lang = "EN"


with st.sidebar:
    lang = st.selectbox(
        "Language",
        options=list(LANGUAGES.keys()),
        format_func=lambda x: LANGUAGES[x],
        index=list(LANGUAGES.keys()).index(query_lang),
    )

    if lang != query_lang:
        st.query_params["lang"] = lang
        st.rerun()


st.markdown(
    f"""
    <div class="sv-hero">
      <div style="
        font-size:12px;
        font-weight:900;
        letter-spacing:.12em;
        color:#7657ff;
      ">
        STADIA
      </div>

      <h1>{tr(lang,'title')}</h1>

      <h2 class="gradient">
        {tr(lang,'tagline')}
      </h2>

      <p style="
        font-size:17px;
        color:#667085;
        max-width:780px;
      ">
        {tr(lang,'subtitle')}
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


seat_token = str(st.query_params.get("seat", "")).strip()

seat = verify_seat_token(
    seat_token,
    APP_SECRET
) if seat_token else None


if seat_token and not seat:
    st.error(tr(lang, "invalid_link"))
    st.stop()


# ---------------------------------------------------------
# CREATE NEW GAME
# ---------------------------------------------------------

if not seat:

    st.subheader(tr(lang, "new_game"))

    with st.form("create_game", border=True):

        white_name = st.text_input(
            tr(lang, "white_name"),
            value=""
        )

        st.caption(
            tr(lang, "friend_name_later")
        )

        time_control = st.selectbox(
            tr(lang, "time_control"),
            options=[
                "rapid_15_10",
                "blitz_5_3",
                "relaxed",
            ],
            format_func=lambda x: {
                "rapid_15_10": "Rapid — 15 + 10",
                "blitz_5_3": "Blitz — 5 + 3",
                "relaxed": "Relaxed — no clock",
            }[x],
        )

        submitted = st.form_submit_button(
            tr(lang, "create"),
            use_container_width=True,
        )

    if submitted:

        gid = db.create_game(
            white_name=white_name or "White",
            black_name="Friend",
            time_control=time_control,
        )

        st.query_params["seat"] = make_seat_token(
            gid,
            "white",
            APP_SECRET
        )

        st.query_params["lang"] = lang

        st.rerun()

    st.info(
        "v0.4: permanent White/Black links stay inside stadiaorg.com; "
        "player identity is server-signed; invitations can be shared "
        "directly by WhatsApp or email."
    )

    st.stop()


# ---------------------------------------------------------
# LOAD GAME
# ---------------------------------------------------------

game = db.get_game(seat.game_id)

if not game:
    st.error(tr(lang, "game_missing"))
    st.stop()


# Black must explicitly enter their own name before joining.
# Opening the permanent Black link alone does not mark the
# game as joined.


# ---------------------------------------------------------
# AUTO REFRESH
# ---------------------------------------------------------

st_autorefresh(
    interval=3000,
    limit=None,
    key=f"game_refresh_{seat.game_id}",
)


game = db.get_game(seat.game_id)

if not game:
    st.error(tr(lang, "game_missing"))
    st.stop()


# ---------------------------------------------------------
# PERMANENT LINKS
# ---------------------------------------------------------

white_link = seat_link(
    seat.game_id,
    "white",
    lang
)

black_link = seat_link(
    seat.game_id,
    "black",
    lang
)

role_label = tr(
    lang,
    seat.role
)


# ---------------------------------------------------------
# GAME HEADER
# ---------------------------------------------------------

top1, top2, top3 = st.columns(
    [2, 1, 1]
)


with top1:

    st.markdown(
        f"### {game['white_name']} vs {game['black_name']}"
    )

    st.caption(
        f"Game ID: {game['id'][:12].upper()}"
    )


with top2:

    st.markdown(
        f"**{tr(lang,'side')}**"
    )

    st.markdown(
        f"<span class='sv-side'>{role_label}</span>",
        unsafe_allow_html=True,
    )


with top3:

    st.markdown("**Status**")

    st.markdown(
        f"<span class='sv-status'>"
        f"{game['status'].upper()}"
        f"</span>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# PERMANENT ACCESS LINKS
# ---------------------------------------------------------

with st.expander(
    "Permanent access links",
    expanded=game["status"] in {
        "waiting",
        "ready",
    },
):

    if seat.role == "white":

        # ---------------------------------------------
        # WHITE PERSONAL LINK
        # ---------------------------------------------

        st.markdown(
            f"**{tr(lang,'your_link')}**"
        )

        st.code(
            white_link,
            language=None
        )

        # ---------------------------------------------
        # BLACK / FRIEND LINK
        # ---------------------------------------------

        st.markdown(
            f"**{tr(lang,'friend_link')}**"
        )

        st.code(
            black_link,
            language=None
        )

        # ---------------------------------------------
        # SHARE INVITATION
        # ---------------------------------------------

        invite_message = invitation_text(
            lang,
            black_link
        )

        subject = invitation_subject(
            lang
        )

        whatsapp_url = (
            "https://wa.me/?text="
            + quote(
                invite_message,
                safe=""
            )
        )

        email_url = (
            "mailto:"
            "?subject="
            + quote(
                subject,
                safe=""
            )
            + "&body="
            + quote(
                invite_message,
                safe=""
            )
        )

        st.markdown("##### Send invitation")

        share_whatsapp, share_email = st.columns(2)

        with share_whatsapp:

            st.link_button(
                "📱 Send via WhatsApp",
                whatsapp_url,
                type="primary",
                use_container_width=True,
            )

        with share_email:

            st.link_button(
                "✉️ Send by email",
                email_url,
                use_container_width=True,
            )

        st.caption(
            tr(lang, "copy_hint")
        )

    else:

        st.markdown(
            f"**{tr(lang,'friend_link')}**"
        )

        st.code(
            black_link,
            language=None
        )

    st.success(
        tr(lang, "return_later")
    )


# ---------------------------------------------------------
# WAITING FOR BLACK
# ---------------------------------------------------------

if game["status"] == "waiting":

    if seat.role == "white":

        st.warning(
            tr(lang, "waiting")
        )

        st.markdown(
            "Send the **Black permanent link** "
            "to your friend using WhatsApp, email, "
            "or the copy icon above."
        )

        st.caption(
            tr(lang, "friend_name_later")
        )

        st.stop()


    st.info(
        tr(lang, "black_invitation")
    )

    st.markdown(
        f"### {game['white_name']} vs …"
    )

    st.caption(
        tr(lang, "black_name_help")
    )


    with st.form(
        "join_black",
        border=True
    ):

        black_name = st.text_input(
            tr(lang, "your_name_black"),
            value=""
        )

        joined = st.form_submit_button(
            tr(lang, "join_game"),
            type="primary",
            use_container_width=True,
        )


    if joined:

        try:

            db.join_black(
                seat.game_id,
                black_name
            )

            st.rerun()

        except ValueError as exc:

            st.error(
                str(exc)
            )

    st.stop()


# ---------------------------------------------------------
# READY - WHITE STARTS
# ---------------------------------------------------------

if game["status"] == "ready":

    if seat.role == "white":

        st.success(
            tr(lang, "ready")
        )

        if st.button(
            tr(lang, "start"),
            type="primary",
            use_container_width=True,
        ):

            try:

                db.start_game(
                    seat.game_id
                )

                st.rerun()

            except ValueError as exc:

                st.error(
                    str(exc)
                )

    else:

        st.info(
            tr(lang, "black_wait")
        )

    st.stop()


# ---------------------------------------------------------
# FINISHED GAME
# ---------------------------------------------------------

if game["status"] == "finished":

    st.success(
        f"{tr(lang,'finished')} — "
        f"{tr(lang,'result')}: "
        f"{game['result']}"
    )


# ---------------------------------------------------------
# CHESS BOARD
# ---------------------------------------------------------

board = chess.Board(
    game["fen"]
)

orientation = seat.role


left, right = st.columns(
    [3, 1.15],
    gap="large"
)


with left:

    st.markdown(
        board_html(
            game["fen"],
            orientation
        ),
        unsafe_allow_html=True,
    )


with right:

    turn_role = (
        "white"
        if board.turn == chess.WHITE
        else "black"
    )

    st.markdown(
        f"### {tr(lang,'turn')}: "
        f"{tr(lang, turn_role)}"
    )

    st.caption(
        tr(lang, "return_later")
    )


    moves = db.get_moves(
        seat.game_id
    )

    st.markdown(
        f"**{tr(lang,'moves')} "
        f"({len(moves)})**"
    )


    if moves:

        st.code(
            "  ".join(
                m["san"]
                for m in moves[-18:]
            ),
            language=None,
        )

    else:

        st.caption("—")


    can_move = (
        game["status"] == "active"
        and seat.role == turn_role
    )


    options = (
        move_options(
            game["fen"]
        )
        if can_move
        else []
    )


    if can_move and options:

        labels = [
            san
            for san, _ in options
        ]

        chosen = st.selectbox(
            tr(lang, "select_move"),
            labels
        )

        uci_by_san = {
            san: uci
            for san, uci in options
        }


        if st.button(
            tr(lang, "make_move"),
            type="primary",
            use_container_width=True,
        ):

            try:

                db.make_move(
                    seat.game_id,
                    uci_by_san[chosen]
                )

                st.rerun()

            except ValueError as exc:

                st.error(
                    str(exc)
                )


    elif game["status"] == "active":

        st.info(
            "Waiting for the other player."
        )


# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.divider()

st.caption(
    "Stadia Chess GUI v0.4 — "
    "Stadia-domain permanent links; "
    "WhatsApp/email invitations; "
    "Black enters their own name; "
    "server-signed player identity."
)
