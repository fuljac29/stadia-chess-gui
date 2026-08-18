from __future__ import annotations

import os
from html import escape
from textwrap import dedent
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

# Permanent player URLs always remain inside stadiaorg.com.
STADIA_PUBLIC_URL = "https://stadiaorg.com/stadia-premium-arena/".rstrip("/")


# =========================================================
# LABELS
# =========================================================

TIME_LABELS = {
    "rapid_15_10": "Rapid — 15 + 10",
    "blitz_5_3": "Blitz — 5 + 3",
    "relaxed": "Relaxed — no clock",
}


UI = {
    "EN": {
        "status": "Status",
        "links": "Permanent access links",
        "send_invitation": "Send invitation",
        "send_whatsapp": "📱 Send via WhatsApp",
        "send_email": "✉️ Send by email",
        "invitation_kicker": "STADIA PRIVATE CHESS",
        "invitation_title": "You have been invited",
        "invitation_from": "{name} invited you to a private chess game.",
        "your_side": "Your side",
        "black_side": "Black",
        "time_control": "Time control",
        "accept_help": (
            "Enter your name and accept the invitation. "
            "The invitation URL you opened is your permanent player URL."
        ),
        "accept_button": "✓ ACCEPT INVITATION & JOIN GAME",
        "name_required": "Please enter your name.",
        "accepted": "Invitation accepted.",
        "player_url_ready": (
            "Your permanent player URL is active. "
            "Keep this page or bookmark it to return to this exact game."
        ),
        "your_player_link": "Your permanent player URL",
        "waiting_host": "Waiting for White to start the game.",
        "white_waiting": "Waiting for your friend to accept the invitation.",
        "share_help": "Send only the Black invitation link to your friend.",
        "friend_joined": "Your friend accepted the invitation.",
        "waiting_other": "Waiting for the other player.",
    },
    "IT": {
        "status": "Stato",
        "links": "Link di accesso permanenti",
        "send_invitation": "Invia l'invito",
        "send_whatsapp": "📱 Invia con WhatsApp",
        "send_email": "✉️ Invia per e-mail",
        "invitation_kicker": "STADIA SCACCHI PRIVATI",
        "invitation_title": "Hai ricevuto un invito",
        "invitation_from": "{name} ti invita a una partita privata di scacchi.",
        "your_side": "Il tuo colore",
        "black_side": "Nero",
        "time_control": "Cadenza",
        "accept_help": (
            "Inserisci il tuo nome e accetta l'invito. "
            "L'URL dell'invito che hai aperto diventa il tuo URL permanente di giocatore."
        ),
        "accept_button": "✓ ACCETTA L'INVITO ED ENTRA",
        "name_required": "Inserisci il tuo nome.",
        "accepted": "Invito accettato.",
        "player_url_ready": (
            "Il tuo URL permanente di giocatore è attivo. "
            "Conserva questa pagina o aggiungila ai preferiti per tornare a questa partita."
        ),
        "your_player_link": "Il tuo URL permanente di giocatore",
        "waiting_host": "In attesa che il Bianco inizi la partita.",
        "white_waiting": "In attesa che il tuo amico accetti l'invito.",
        "share_help": "Invia al tuo amico soltanto il link Nero.",
        "friend_joined": "Il tuo amico ha accettato l'invito.",
        "waiting_other": "In attesa dell'altro giocatore.",
    },
    "DE": {
        "status": "Status",
        "links": "Permanente Zugangslinks",
        "send_invitation": "Einladung senden",
        "send_whatsapp": "📱 Über WhatsApp senden",
        "send_email": "✉️ Per E-Mail senden",
        "invitation_kicker": "STADIA PRIVATSCHACH",
        "invitation_title": "Du wurdest eingeladen",
        "invitation_from": "{name} lädt dich zu einer privaten Schachpartie ein.",
        "your_side": "Deine Farbe",
        "black_side": "Schwarz",
        "time_control": "Bedenkzeit",
        "accept_help": (
            "Gib deinen Namen ein und nimm die Einladung an. "
            "Die geöffnete Einladungs-URL bleibt deine permanente Spieler-URL."
        ),
        "accept_button": "✓ EINLADUNG ANNEHMEN & BEITRETEN",
        "name_required": "Bitte gib deinen Namen ein.",
        "accepted": "Einladung angenommen.",
        "player_url_ready": (
            "Deine permanente Spieler-URL ist aktiv. "
            "Speichere diese Seite, um zu dieser Partie zurückzukehren."
        ),
        "your_player_link": "Deine permanente Spieler-URL",
        "waiting_host": "Warte darauf, dass Weiß die Partie startet.",
        "white_waiting": "Warte darauf, dass dein Freund die Einladung annimmt.",
        "share_help": "Sende deinem Freund nur den schwarzen Einladungslink.",
        "friend_joined": "Dein Freund hat die Einladung angenommen.",
        "waiting_other": "Warte auf den anderen Spieler.",
    },
    "FR": {
        "status": "Statut",
        "links": "Liens d'accès permanents",
        "send_invitation": "Envoyer l'invitation",
        "send_whatsapp": "📱 Envoyer par WhatsApp",
        "send_email": "✉️ Envoyer par e-mail",
        "invitation_kicker": "STADIA ÉCHECS PRIVÉS",
        "invitation_title": "Vous avez reçu une invitation",
        "invitation_from": "{name} vous invite à une partie d'échecs privée.",
        "your_side": "Votre couleur",
        "black_side": "Noirs",
        "time_control": "Cadence",
        "accept_help": (
            "Entrez votre nom et acceptez l'invitation. "
            "L'URL d'invitation ouverte restera votre URL permanente de joueur."
        ),
        "accept_button": "✓ ACCEPTER L'INVITATION ET REJOINDRE",
        "name_required": "Veuillez entrer votre nom.",
        "accepted": "Invitation acceptée.",
        "player_url_ready": (
            "Votre URL permanente de joueur est active. "
            "Conservez cette page pour revenir exactement à cette partie."
        ),
        "your_player_link": "Votre URL permanente de joueur",
        "waiting_host": "En attente du démarrage de la partie par les Blancs.",
        "white_waiting": "En attente de l'acceptation de votre ami.",
        "share_help": "Envoyez uniquement le lien Noir à votre ami.",
        "friend_joined": "Votre ami a accepté l'invitation.",
        "waiting_other": "En attente de l'autre joueur.",
    },
    "ES": {
        "status": "Estado",
        "links": "Enlaces de acceso permanentes",
        "send_invitation": "Enviar invitación",
        "send_whatsapp": "📱 Enviar por WhatsApp",
        "send_email": "✉️ Enviar por correo",
        "invitation_kicker": "STADIA AJEDREZ PRIVADO",
        "invitation_title": "Has recibido una invitación",
        "invitation_from": "{name} te invita a una partida privada de ajedrez.",
        "your_side": "Tu color",
        "black_side": "Negras",
        "time_control": "Ritmo",
        "accept_help": (
            "Introduce tu nombre y acepta la invitación. "
            "La URL de invitación que abriste seguirá siendo tu URL permanente de jugador."
        ),
        "accept_button": "✓ ACEPTAR INVITACIÓN Y ENTRAR",
        "name_required": "Introduce tu nombre.",
        "accepted": "Invitación aceptada.",
        "player_url_ready": (
            "Tu URL permanente de jugador está activa. "
            "Guarda esta página para volver exactamente a esta partida."
        ),
        "your_player_link": "Tu URL permanente de jugador",
        "waiting_host": "Esperando a que las Blancas inicien la partida.",
        "white_waiting": "Esperando a que tu amigo acepte la invitación.",
        "share_help": "Envía únicamente el enlace de Negras a tu amigo.",
        "friend_joined": "Tu amigo ha aceptado la invitación.",
        "waiting_other": "Esperando al otro jugador.",
    },
}


def ui(lang: str, key: str) -> str:
    language = UI.get(lang, UI["EN"])
    return language.get(key, UI["EN"].get(key, key))


# =========================================================
# HELPERS
# =========================================================

def render_html(fragment: str) -> None:
    """Render HTML without Markdown treating indentation as a code block."""
    st.markdown(dedent(fragment).strip(), unsafe_allow_html=True)


def seat_link(game_id: str, role: str, lang: str) -> str:
    token = make_seat_token(game_id, role, APP_SECRET)
    params = urlencode({"seat": token, "lang": lang})
    return f"{STADIA_PUBLIC_URL}/?{params}"


def invitation_text(lang: str, black_link: str) -> str:
    messages = {
        "EN": (
            "I invite you to play a private chess game on Stadia.\n\n"
            "Open this personal link to join as Black:\n"
            f"{black_link}\n\n"
            "See you on the board!"
        ),
        "IT": (
            "Ti invito a giocare una partita privata a scacchi su Stadia.\n\n"
            "Apri questo link personale per entrare con i Neri:\n"
            f"{black_link}\n\n"
            "Ci vediamo sulla scacchiera!"
        ),
        "DE": (
            "Ich lade dich zu einer privaten Schachpartie auf Stadia ein.\n\n"
            "Öffne diesen persönlichen Link, um als Schwarz beizutreten:\n"
            f"{black_link}\n\n"
            "Bis gleich am Schachbrett!"
        ),
        "FR": (
            "Je t'invite à jouer une partie d'échecs privée sur Stadia.\n\n"
            "Ouvre ce lien personnel pour rejoindre la partie avec les Noirs :\n"
            f"{black_link}\n\n"
            "À bientôt sur l'échiquier !"
        ),
        "ES": (
            "Te invito a jugar una partida privada de ajedrez en Stadia.\n\n"
            "Abre este enlace personal para entrar con Negras:\n"
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

render_html(
    """
    <style>
    .block-container{
        max-width:1220px;
        padding-top:1.6rem;
        padding-bottom:4rem;
    }

    h1,h2,h3{letter-spacing:-0.02em}

    .sv-hero{
        border:1px solid #e7e4ff;
        border-radius:26px;
        padding:30px;
        background:linear-gradient(135deg,#fff 0%,#faf8ff 100%);
        margin-bottom:20px;
    }

    .sv-hero h1{
        font-size:46px;
        margin:8px 0 4px 0;
    }

    .sv-hero .gradient{
        background:linear-gradient(90deg,#ec3f83,#7657ff);
        -webkit-background-clip:text;
        background-clip:text;
        color:transparent;
        margin:20px 0 8px 0;
    }

    .sv-kicker{
        font-size:12px;
        font-weight:900;
        letter-spacing:.12em;
        color:#7657ff;
    }

    .sv-lead{
        font-size:17px;
        color:#667085;
        max-width:780px;
        line-height:1.6;
    }

    .sv-invite{
        border:1px solid #ddd6fe;
        border-radius:24px;
        padding:28px;
        margin:18px 0 16px;
        background:linear-gradient(135deg,#fff,#faf8ff);
    }

    .sv-invite h2{
        margin:8px 0 12px;
        font-size:34px;
    }

    .sv-invite p{
        color:#475569;
        font-size:16px;
        line-height:1.6;
    }

    .sv-status{
        display:inline-block;
        padding:7px 11px;
        border-radius:999px;
        background:#f0edff;
        color:#5038c8;
        font-weight:800;
        font-size:13px;
    }

    .sv-side{
        display:inline-block;
        padding:8px 12px;
        border-radius:999px;
        background:#111827;
        color:#fff;
        font-weight:900;
    }

    div.stButton > button,
    div[data-testid="stFormSubmitButton"] > button{
        min-height:54px;
        border-radius:14px;
        font-weight:850;
        font-size:15px;
    }

    [data-testid="stLinkButton"] a{
        min-height:54px;
        border-radius:14px;
        font-weight:850;
        font-size:15px;
        display:flex;
        align-items:center;
        justify-content:center;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div > div{
        min-height:48px;
    }

    code{
        word-break:break-all;
        white-space:pre-wrap;
    }

    @media(max-width:760px){
        .sv-hero{padding:22px}
        .sv-hero h1{font-size:36px}
        .sv-invite{padding:20px}
        .sv-invite h2{font-size:28px}
    }
    </style>
    """
)


# =========================================================
# LANGUAGE
# =========================================================

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


# =========================================================
# HERO
# =========================================================

render_html(
    f"""
    <div class="sv-hero">
        <div class="sv-kicker">STADIA</div>
        <h1>{escape(str(tr(lang, "title")))}</h1>
        <h2 class="gradient">{escape(str(tr(lang, "tagline")))}</h2>
        <p class="sv-lead">{escape(str(tr(lang, "subtitle")))}</p>
    </div>
    """
)


# =========================================================
# PLAYER TOKEN
# =========================================================

seat_token = str(st.query_params.get("seat", "")).strip()
seat = verify_seat_token(seat_token, APP_SECRET) if seat_token else None

if seat_token and not seat:
    st.error(tr(lang, "invalid_link"))
    st.stop()


# =========================================================
# CREATE NEW GAME
# =========================================================

if not seat:
    st.subheader(tr(lang, "new_game"))

    with st.form("create_game", border=True):
        white_name = st.text_input(tr(lang, "white_name"), value="")
        st.caption(tr(lang, "friend_name_later"))

        time_control = st.selectbox(
            tr(lang, "time_control"),
            options=list(TIME_LABELS.keys()),
            format_func=lambda x: TIME_LABELS[x],
        )

        submitted = st.form_submit_button(
            tr(lang, "create"),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        gid = db.create_game(
            white_name=white_name or "White",
            black_name="Friend",
            time_control=time_control,
        )

        # This changes the Streamlit iframe to White's signed seat.
        # The permanent shareable URL is generated below on stadiaorg.com.
        st.query_params["seat"] = make_seat_token(gid, "white", APP_SECRET)
        st.query_params["lang"] = lang
        st.rerun()

    st.info(
        "v0.6 — permanent Stadia player URLs, direct invitations "
        "and explicit guest acceptance."
    )
    st.stop()


# =========================================================
# LOAD GAME
# =========================================================

game = db.get_game(seat.game_id)

if not game:
    st.error(tr(lang, "game_missing"))
    st.stop()


white_link = seat_link(seat.game_id, "white", lang)
black_link = seat_link(seat.game_id, "black", lang)


# =========================================================
# BLACK INVITATION PAGE — BEFORE NORMAL GAME UI
# =========================================================
#
# This is intentionally handled before the normal header.
# The invited friend gets a clean invitation page:
#   invitation -> name -> ACCEPT -> same permanent Black URL.
#

if seat.role == "black" and game["status"] == "waiting":
    time_label = TIME_LABELS.get(
        game.get("time_control", "rapid_15_10"),
        str(game.get("time_control", "Rapid")),
    )

    safe_white_name = escape(str(game["white_name"]))
    invite_sentence = ui(lang, "invitation_from").format(name=safe_white_name)

    render_html(
        f"""
        <div class="sv-invite">
            <div class="sv-kicker">{escape(ui(lang, "invitation_kicker"))}</div>
            <h2>{escape(ui(lang, "invitation_title"))}</h2>
            <p style="font-size:19px">
                {invite_sentence}
            </p>
            <p>
                <strong>{escape(ui(lang, "your_side"))}:</strong>
                {escape(ui(lang, "black_side"))}
            </p>
            <p>
                <strong>{escape(ui(lang, "time_control"))}:</strong>
                {escape(str(time_label))}
            </p>
        </div>
        """
    )

    st.info(ui(lang, "accept_help"))

    with st.form("accept_invitation", border=True):
        black_name = st.text_input(
            tr(lang, "your_name_black"),
            value="",
        )

        accepted = st.form_submit_button(
            ui(lang, "accept_button"),
            type="primary",
            use_container_width=True,
        )

    if accepted:
        if not black_name.strip():
            st.error(ui(lang, "name_required"))
            st.stop()

        try:
            db.join_black(seat.game_id, black_name.strip())

            # IMPORTANT:
            # We do not replace or remove ?seat=...
            # The Black invitation URL remains the friend's permanent player URL.
            st.rerun()

        except ValueError as exc:
            st.error(str(exc))

    st.stop()


# =========================================================
# AUTO REFRESH
# =========================================================
#
# At this point Black is no longer filling the invitation form.
# White/Black can safely refresh to see status/moves from the other player.
#

st_autorefresh(
    interval=3000,
    limit=None,
    key=f"game_refresh_{seat.game_id}",
)

game = db.get_game(seat.game_id)

if not game:
    st.error(tr(lang, "game_missing"))
    st.stop()


# =========================================================
# NORMAL GAME HEADER
# =========================================================

role_label = tr(lang, seat.role)

top1, top2, top3 = st.columns([2, 1, 1])

with top1:
    st.markdown(f"### {game['white_name']} vs {game['black_name']}")
    st.caption(f"Game ID: {game['id'][:12].upper()}")

with top2:
    st.markdown(f"**{tr(lang, 'side')}**")
    render_html(
        f'<span class="sv-side">{escape(str(role_label))}</span>'
    )

with top3:
    st.markdown(f"**{ui(lang, 'status')}**")
    render_html(
        f'<span class="sv-status">{escape(str(game["status"]).upper())}</span>'
    )


# =========================================================
# WHITE — PERMANENT LINKS + SHARE
# =========================================================

if seat.role == "white":
    with st.expander(
        ui(lang, "links"),
        expanded=game["status"] in {"waiting", "ready"},
    ):
        st.markdown(f"**{tr(lang, 'your_link')}**")
        st.code(white_link, language=None)

        st.markdown(f"**{tr(lang, 'friend_link')}**")
        st.code(black_link, language=None)

        invite_message = invitation_text(lang, black_link)
        subject = invitation_subject(lang)

        whatsapp_url = (
            "https://wa.me/?text="
            + quote(invite_message, safe="")
        )

        email_url = (
            "mailto:?subject="
            + quote(subject, safe="")
            + "&body="
            + quote(invite_message, safe="")
        )

        st.markdown(f"##### {ui(lang, 'send_invitation')}")

        share1, share2 = st.columns(2)

        with share1:
            st.link_button(
                ui(lang, "send_whatsapp"),
                whatsapp_url,
                type="primary",
                use_container_width=True,
            )

        with share2:
            st.link_button(
                ui(lang, "send_email"),
                email_url,
                use_container_width=True,
            )

        st.caption(ui(lang, "share_help"))
        st.success(tr(lang, "return_later"))


# =========================================================
# WAITING — WHITE
# =========================================================

if game["status"] == "waiting":
    if seat.role == "white":
        st.warning(ui(lang, "white_waiting"))
        st.caption(tr(lang, "friend_name_later"))
    st.stop()


# =========================================================
# READY
# =========================================================

if game["status"] == "ready":
    if seat.role == "white":
        st.success(ui(lang, "friend_joined"))
        st.success(tr(lang, "ready"))

        if st.button(
            tr(lang, "start"),
            type="primary",
            use_container_width=True,
        ):
            try:
                db.start_game(seat.game_id)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    else:
        st.success(ui(lang, "accepted"))
        st.info(ui(lang, "player_url_ready"))

        with st.expander(ui(lang, "your_player_link")):
            st.code(black_link, language=None)

        st.warning(ui(lang, "waiting_host"))

    st.stop()


# =========================================================
# FINISHED
# =========================================================

if game["status"] == "finished":
    st.success(
        f"{tr(lang, 'finished')} — "
        f"{tr(lang, 'result')}: {game['result']}"
    )


# =========================================================
# ACTIVE / FINISHED BOARD
# =========================================================

board = chess.Board(game["fen"])
orientation = seat.role

left, right = st.columns([3, 1.15], gap="large")

with left:
    st.markdown(
        board_html(game["fen"], orientation),
        unsafe_allow_html=True,
    )

with right:
    turn_role = "white" if board.turn == chess.WHITE else "black"

    st.markdown(
        f"### {tr(lang, 'turn')}: {tr(lang, turn_role)}"
    )

    st.caption(tr(lang, "return_later"))

    moves = db.get_moves(seat.game_id)

    st.markdown(
        f"**{tr(lang, 'moves')} ({len(moves)})**"
    )

    if moves:
        st.code(
            "  ".join(m["san"] for m in moves[-18:]),
            language=None,
        )
    else:
        st.caption("—")

    can_move = (
        game["status"] == "active"
        and seat.role == turn_role
    )

    options = move_options(game["fen"]) if can_move else []

    if can_move and options:
        labels = [san for san, _ in options]

        chosen = st.selectbox(
            tr(lang, "select_move"),
            labels,
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
                    uci_by_san[chosen],
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    elif game["status"] == "active":
        st.info(ui(lang, "waiting_other"))


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Stadia Chess GUI v0.6 — "
    "permanent Stadia-domain player URLs; "
    "WhatsApp/email invitation; "
    "explicit guest acceptance; "
    "server-signed White/Black identity."
)
