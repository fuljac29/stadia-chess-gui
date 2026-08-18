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


# =========================================================
# CONFIG
# =========================================================

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

# All permanent player links remain inside Stadia.
STADIA_PUBLIC_URL = (
    "https://stadiaorg.com/stadia-premium-arena/"
).rstrip("/")


# =========================================================
# CONSTANTS
# =========================================================

TIME_LABELS = {
    "rapid_15_10": "Rapid — 15 + 10",
    "blitz_5_3": "Blitz — 5 + 3",
    "relaxed": "Relaxed — no clock",
}


UI = {
    "EN": {
        "send_invitation": "Send invitation",
        "send_whatsapp": "📱 Send via WhatsApp",
        "send_email": "✉️ Send by email",

        "invitation_title": "You have been invited",
        "invitation_from": "{name} invited you to a private chess game.",
        "your_side": "Your side",
        "time_control": "Time control",
        "black_side": "Black",

        "accept_help":
            "Enter your name and accept the invitation. "
            "This permanent player link will remain yours.",

        "accept_button": "✓ ACCEPT INVITATION & JOIN GAME",

        "name_required": "Please enter your name.",

        "accepted": "Invitation accepted.",
        "player_url_ready":
            "Your permanent player URL is active. "
            "Keep this page or bookmark it to return to this game.",

        "your_player_link": "Your permanent player link",

        "waiting_host":
            "Waiting for White to start the game.",

        "white_waiting":
            "Waiting for your friend to accept the invitation.",

        "share_help":
            "Send only the Black invitation link to your friend.",
    },

    "IT": {
        "send_invitation": "Invia l'invito",
        "send_whatsapp": "📱 Invia con WhatsApp",
        "send_email": "✉️ Invia per e-mail",

        "invitation_title": "Hai ricevuto un invito",
        "invitation_from":
            "{name} ti invita a una partita privata di scacchi.",

        "your_side": "Il tuo colore",
        "time_control": "Cadenza",
        "black_side": "Nero",

        "accept_help":
            "Inserisci il tuo nome e accetta l'invito. "
            "Questo link personale rimarrà il tuo accesso permanente.",

        "accept_button": "✓ ACCETTA L'INVITO ED ENTRA",

        "name_required": "Inserisci il tuo nome.",

        "accepted": "Invito accettato.",
        "player_url_ready":
            "Il tuo URL personale permanente è attivo. "
            "Conserva questa pagina o aggiungila ai preferiti "
            "per tornare alla partita.",

        "your_player_link": "Il tuo link permanente",

        "waiting_host":
            "In attesa che il Bianco inizi la partita.",

        "white_waiting":
            "In attesa che il tuo amico accetti l'invito.",

        "share_help":
            "Invia al tuo amico soltanto il link Nero.",
    },

    "DE": {
        "send_invitation": "Einladung senden",
        "send_whatsapp": "📱 Über WhatsApp senden",
        "send_email": "✉️ Per E-Mail senden",

        "invitation_title": "Du wurdest eingeladen",
        "invitation_from":
            "{name} lädt dich zu einer privaten Schachpartie ein.",

        "your_side": "Deine Farbe",
        "time_control": "Bedenkzeit",
        "black_side": "Schwarz",

        "accept_help":
            "Gib deinen Namen ein und akzeptiere die Einladung. "
            "Dieser persönliche Link bleibt dein dauerhafter Zugang.",

        "accept_button": "✓ EINLADUNG ANNEHMEN & BEITRETEN",

        "name_required": "Bitte gib deinen Namen ein.",

        "accepted": "Einladung angenommen.",
        "player_url_ready":
            "Dein permanenter Spieler-Link ist aktiv. "
            "Speichere diese Seite, um später zurückzukehren.",

        "your_player_link": "Dein permanenter Spieler-Link",

        "waiting_host":
            "Warte darauf, dass Weiß die Partie startet.",

        "white_waiting":
            "Warte darauf, dass dein Freund die Einladung annimmt.",

        "share_help":
            "Sende deinem Freund nur den schwarzen Einladungslink.",
    },

    "FR": {
        "send_invitation": "Envoyer l'invitation",
        "send_whatsapp": "📱 Envoyer par WhatsApp",
        "send_email": "✉️ Envoyer par e-mail",

        "invitation_title": "Vous avez reçu une invitation",
        "invitation_from":
            "{name} vous invite à une partie d'échecs privée.",

        "your_side": "Votre couleur",
        "time_control": "Cadence",
        "black_side": "Noirs",

        "accept_help":
            "Entrez votre nom et acceptez l'invitation. "
            "Ce lien personnel restera votre accès permanent.",

        "accept_button": "✓ ACCEPTER L'INVITATION ET REJOINDRE",

        "name_required": "Veuillez entrer votre nom.",

        "accepted": "Invitation acceptée.",
        "player_url_ready":
            "Votre URL personnelle permanente est active. "
            "Conservez cette page pour revenir à la partie.",

        "your_player_link": "Votre lien permanent",

        "waiting_host":
            "En attente du démarrage de la partie par les Blancs.",

        "white_waiting":
            "En attente de l'acceptation de votre ami.",

        "share_help":
            "Envoyez uniquement le lien Noir à votre ami.",
    },

    "ES": {
        "send_invitation": "Enviar invitación",
        "send_whatsapp": "📱 Enviar por WhatsApp",
        "send_email": "✉️ Enviar por correo",

        "invitation_title": "Has recibido una invitación",
        "invitation_from":
            "{name} te invita a una partida privada de ajedrez.",

        "your_side": "Tu color",
        "time_control": "Ritmo",
        "black_side": "Negras",

        "accept_help":
            "Introduce tu nombre y acepta la invitación. "
            "Este enlace personal seguirá siendo tu acceso permanente.",

        "accept_button": "✓ ACEPTAR INVITACIÓN Y ENTRAR",

        "name_required": "Introduce tu nombre.",

        "accepted": "Invitación aceptada.",
        "player_url_ready":
            "Tu URL personal permanente está activa. "
            "Guarda esta página para volver a la partida.",

        "your_player_link": "Tu enlace permanente",

        "waiting_host":
            "Esperando a que las Blancas inicien la partida.",

        "white_waiting":
            "Esperando a que tu amigo acepte la invitación.",

        "share_help":
            "Envía únicamente el enlace de Negras a tu amigo.",
    },
}


def ui(lang: str, key: str) -> str:
    language = UI.get(lang, UI["EN"])
    return language.get(key, UI["EN"].get(key, key))


# =========================================================
# LINKS
# =========================================================

def seat_link(game_id: str, role: str, lang: str) -> str:
    token = make_seat_token(game_id, role, APP_SECRET)

    return (
        f"{STADIA_PUBLIC_URL}/?"
        f"{urlencode({'seat': token, 'lang': lang})}"
    )


# =========================================================
# INVITATION TEXT
# =========================================================

def invitation_text(lang: str, black_link: str) -> str:

    messages = {
        "EN": (
            "I invite you to play a private chess game on Stadia.\n\n"
            "Open this personal link to join as Black:\n"
            f"{black_link}\n\n"
            "See you on the board!"
        ),

        "IT": (
            "Ti invito a giocare una partita privata "
            "a scacchi su Stadia.\n\n"
            "Apri questo link personale per entrare con i Neri:\n"
            f"{black_link}\n\n"
            "Ci vediamo sulla scacchiera!"
        ),

        "DE": (
            "Ich lade dich zu einer privaten Schachpartie "
            "auf Stadia ein.\n\n"
            "Öffne diesen persönlichen Link, "
            "um als Schwarz beizutreten:\n"
            f"{black_link}\n\n"
            "Bis gleich am Schachbrett!"
        ),

        "FR": (
            "Je t'invite à jouer une partie d'échecs privée "
            "sur Stadia.\n\n"
            "Ouvre ce lien personnel pour rejoindre "
            "la partie avec les Noirs :\n"
            f"{black_link}\n\n"
            "À bientôt sur l'échiquier !"
        ),

        "ES": (
            "Te invito a jugar una partida privada "
            "de ajedrez en Stadia.\n\n"
            "Abre este enlace personal para entrar "
            "con Negras:\n"
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


# =========================================================
# CSS
# =========================================================

def inject_css():

    st.markdown(
        """
        <style>

        .block-container {
            max-width:1220px;
            padding-top:1.6rem;
            padding-bottom:4rem;
        }

        h1,h2,h3 {
            letter-spacing:-0.02em;
        }

        .sv-hero {
            border:1px solid #e7e4ff;
            border-radius:26px;
            padding:30px;
            background:linear-gradient(
                135deg,
                #fff 0%,
                #faf8ff 100%
            );
            margin-bottom:20px;
        }

        .sv-hero h1 {
            font-size:46px;
            margin:0 0 4px 0;
        }

        .sv-hero .gradient {
            background:linear-gradient(
                90deg,
                #ec3f83,
                #7657ff
            );
            -webkit-background-clip:text;
            color:transparent;
        }

        .sv-invite {
            border:1px solid #ddd6fe;
            border-radius:24px;
            padding:26px;
            margin:18px 0;
            background:
                linear-gradient(
                    135deg,
                    #ffffff,
                    #faf8ff
                );
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


# =========================================================
# LANGUAGE
# =========================================================

query_lang = str(
    st.query_params.get("lang", "EN")
).upper()

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


# =========================================================
# HERO
# =========================================================

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


# =========================================================
# PLAYER TOKEN
# =========================================================

seat_token = str(
    st.query_params.get("seat", "")
).strip()

seat = (
    verify_seat_token(
        seat_token,
        APP_SECRET
    )
    if seat_token
    else None
)


if seat_token and not seat:

    st.error(
        tr(lang, "invalid_link")
    )

    st.stop()


# =========================================================
# CREATE GAME
# =========================================================

if not seat:

    st.subheader(
        tr(lang, "new_game")
    )

    with st.form(
        "create_game",
        border=True
    ):

        white_name = st.text_input(
            tr(lang, "white_name"),
            value=""
        )

        st.caption(
            tr(lang, "friend_name_later")
        )

        time_control = st.selectbox(
            tr(lang, "time_control"),
            options=list(TIME_LABELS.keys()),
            format_func=lambda x: TIME_LABELS[x],
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

        st.query_params["seat"] = (
            make_seat_token(
                gid,
                "white",
                APP_SECRET
            )
        )

        st.query_params["lang"] = lang

        st.rerun()


    st.info(
        "v0.5: permanent Stadia player links, "
        "direct invitations and explicit guest acceptance."
    )

    st.stop()


# =========================================================
# LOAD GAME
# =========================================================

game = db.get_game(
    seat.game_id
)

if not game:

    st.error(
        tr(lang, "game_missing")
    )

    st.stop()


# =========================================================
# AUTO REFRESH
# =========================================================
#
# White needs refresh while waiting for Black.
# Black does NOT need refresh while filling the invitation form.
#

if not (
    game["status"] == "waiting"
    and seat.role == "black"
):

    st_autorefresh(
        interval=3000,
        limit=None,
        key=f"game_refresh_{seat.game_id}",
    )

    game = db.get_game(
        seat.game_id
    )

    if not game:

        st.error(
            tr(lang, "game_missing")
        )

        st.stop()


# =========================================================
# PLAYER LINKS
# =========================================================

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


# =========================================================
# HEADER
# =========================================================

top1, top2, top3 = st.columns(
    [2, 1, 1]
)


with top1:

    st.markdown(
        f"### {game['white_name']} "
        f"vs {game['black_name']}"
    )

    st.caption(
        f"Game ID: "
        f"{game['id'][:12].upper()}"
    )


with top2:

    st.markdown(
        f"**{tr(lang,'side')}**"
    )

    st.markdown(
        f"<span class='sv-side'>"
        f"{role_label}"
        f"</span>",
        unsafe_allow_html=True,
    )


with top3:

    st.markdown(
        "**Status**"
    )

    st.markdown(
        f"<span class='sv-status'>"
        f"{game['status'].upper()}"
        f"</span>",
        unsafe_allow_html=True,
    )


# =========================================================
# WHITE — LINKS AND INVITATION
# =========================================================

if seat.role == "white":

    with st.expander(
        "Permanent access links",
        expanded=game["status"] in {
            "waiting",
            "ready",
        },
    ):

        st.markdown(
            f"**{tr(lang,'your_link')}**"
        )

        st.code(
            white_link,
            language=None
        )


        st.markdown(
            f"**{tr(lang,'friend_link')}**"
        )

        st.code(
            black_link,
            language=None
        )


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


        st.markdown(
            f"##### "
            f"{ui(lang,'send_invitation')}"
        )


        share1, share2 = st.columns(2)


        with share1:

            st.link_button(
                ui(
                    lang,
                    "send_whatsapp"
                ),
                whatsapp_url,
                type="primary",
                use_container_width=True,
            )


        with share2:

            st.link_button(
                ui(
                    lang,
                    "send_email"
                ),
                email_url,
                use_container_width=True,
            )


        st.caption(
            ui(
                lang,
                "share_help"
            )
        )


        st.success(
            tr(
                lang,
                "return_later"
            )
        )


# =========================================================
# WAITING
# =========================================================

if game["status"] == "waiting":

    # -----------------------------------------------------
    # WHITE waits for friend
    # -----------------------------------------------------

    if seat.role == "white":

        st.warning(
            ui(
                lang,
                "white_waiting"
            )
        )

        st.caption(
            tr(
                lang,
                "friend_name_later"
            )
        )

        st.stop()


    # -----------------------------------------------------
    # BLACK — REAL INVITATION PAGE
    # -----------------------------------------------------

    time_label = TIME_LABELS.get(
        game.get(
            "time_control",
            "rapid_15_10"
        ),
        game.get(
            "time_control",
            "Rapid"
        )
    )


    st.markdown(
        f"""
        <div class="sv-invite">

            <div style="
                font-size:12px;
                font-weight:900;
                letter-spacing:.10em;
                color:#7657ff;
                margin-bottom:8px;
            ">
                STADIA PRIVATE CHESS
            </div>

            <h2 style="
                margin:0 0 12px 0;
            ">
                {ui(lang,'invitation_title')}
            </h2>

            <p style="
                font-size:18px;
                margin-bottom:18px;
            ">
                {
                    ui(
                        lang,
                        'invitation_from'
                    ).format(
                        name=game['white_name']
                    )
                }
            </p>

            <p>
                <strong>
                    {ui(lang,'your_side')}:
                </strong>
                {ui(lang,'black_side')}
            </p>

            <p>
                <strong>
                    {ui(lang,'time_control')}:
                </strong>
                {time_label}
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )


    st.info(
        ui(
            lang,
            "accept_help"
        )
    )


    with st.form(
        "accept_invitation",
        border=True
    ):

        black_name = st.text_input(
            tr(
                lang,
                "your_name_black"
            ),
            value=""
        )


        accepted = st.form_submit_button(
            ui(
                lang,
                "accept_button"
            ),
            type="primary",
            use_container_width=True,
        )


    if accepted:

        if not black_name.strip():

            st.error(
                ui(
                    lang,
                    "name_required"
                )
            )

            st.stop()


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


# =========================================================
# READY
# =========================================================

if game["status"] == "ready":

    # -----------------------------------------------------
    # WHITE
    # -----------------------------------------------------

    if seat.role == "white":

        st.success(
            tr(
                lang,
                "ready"
            )
        )


        if st.button(
            tr(
                lang,
                "start"
            ),
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


    # -----------------------------------------------------
    # BLACK
    # -----------------------------------------------------

    else:

        st.success(
            ui(
                lang,
                "accepted"
            )
        )

        st.info(
            ui(
                lang,
                "player_url_ready"
            )
        )


        with st.expander(
            ui(
                lang,
                "your_player_link"
            )
        ):

            st.code(
                black_link,
                language=None
            )


        st.warning(
            ui(
                lang,
                "waiting_host"
            )
        )


    st.stop()


# =========================================================
# FINISHED
# =========================================================

if game["status"] == "finished":

    st.success(
        f"{tr(lang,'finished')} — "
        f"{tr(lang,'result')}: "
        f"{game['result']}"
    )


# =========================================================
# ACTIVE GAME
# =========================================================

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
        f"{tr(lang,turn_role)}"
    )


    st.caption(
        tr(
            lang,
            "return_later"
        )
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
            tr(
                lang,
                "select_move"
            ),
            labels
        )


        uci_by_san = {
            san: uci
            for san, uci in options
        }


        if st.button(
            tr(
                lang,
                "make_move"
            ),
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


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Stadia Chess GUI v0.5 — "
    "permanent Stadia-domain player links; "
    "WhatsApp/email invitation; "
    "explicit guest acceptance; "
    "server-signed White/Black identity."
)
