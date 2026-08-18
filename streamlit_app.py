from __future__ import annotations

import os
from html import escape
from textwrap import dedent
from urllib.parse import quote, urlencode

import chess
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import chess_db as db
from chess_board import board_html
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

STADIA_PUBLIC_URL = "https://stadiaorg.com/stadia-premium-arena/".rstrip("/")


def secret(name: str, default: str) -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)


APP_SECRET = secret("APP_SECRET", "DEV-ONLY-CHANGE-ME")


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
        "create_title": "Invite a friend",
        "your_name": "Your name",
        "friend_name": "Friend's name",
        "time_control": "Time control",
        "create_button": "INVITE TO PLAY",
        "join_title": "Have an invitation?",
        "invite_code": "Invitation code",
        "code_help": "Enter the 6-character code your friend gave you.",
        "find_button": "FIND INVITATION",
        "missing_names": "Enter both your name and your friend's name.",
        "code_not_found": "Invitation code not found.",
        "invited": "{white} invited {black} to a private chess game.",
        "accept_question": "Is this invitation for you?",
        "accept_button": "ACCEPT & PLAY",
        "open_button": "OPEN GAME",
        "cancel_button": "Not this invitation",
        "your_code": "Invitation code",
        "tell_friend": "{friend} opens Stadia → Premium Arena and enters this code.",
        "waiting_friend": "Waiting for {friend} to accept the invitation.",
        "send_invitation": "Send invitation",
        "send_whatsapp": "📱 WhatsApp",
        "send_email": "✉️ Email",
        "share_message": (
            "{white} invites you to play private chess on Stadia.\n\n"
            "Open:\n{url}\n\n"
            "Invitation code: {code}"
        ),
        "email_subject": "Stadia Private Chess invitation",
        "private_return": "Private return link",
        "private_return_help": "Keep this only for yourself if you want to return later.",
        "status": "Status",
        "side": "Your side",
        "waiting_other": "Waiting for the other player.",
        "click_piece": "Click one of your pieces on the board.",
        "click_destination": "Now click the destination square.",
        "selected_piece": "Piece selected. Choose where to move it.",
        "moves": "Moves",
    },
    "IT": {
        "create_title": "Invita un amico",
        "your_name": "Il tuo nome",
        "friend_name": "Nome dell'amico",
        "time_control": "Cadenza",
        "create_button": "INVITA A GIOCARE",
        "join_title": "Hai ricevuto un invito?",
        "invite_code": "Codice invito",
        "code_help": "Inserisci il codice di 6 caratteri ricevuto dal tuo amico.",
        "find_button": "TROVA L'INVITO",
        "missing_names": "Inserisci il tuo nome e il nome dell'amico.",
        "code_not_found": "Codice invito non trovato.",
        "invited": "{white} ha invitato {black} a una partita privata di scacchi.",
        "accept_question": "Questo invito è per te?",
        "accept_button": "ACCETTA E GIOCA",
        "open_button": "APRI LA PARTITA",
        "cancel_button": "Non è questo invito",
        "your_code": "Codice invito",
        "tell_friend": "{friend} apre Stadia → Arena Premium e inserisce questo codice.",
        "waiting_friend": "In attesa che {friend} accetti l'invito.",
        "send_invitation": "Invia l'invito",
        "send_whatsapp": "📱 WhatsApp",
        "send_email": "✉️ E-mail",
        "share_message": (
            "{white} ti invita a giocare a scacchi privati su Stadia.\n\n"
            "Apri:\n{url}\n\n"
            "Codice invito: {code}"
        ),
        "email_subject": "Invito a Stadia Private Chess",
        "private_return": "Link privato per tornare",
        "private_return_help": "Conservalo solo per te se vuoi tornare più tardi.",
        "status": "Stato",
        "side": "Il tuo colore",
        "waiting_other": "In attesa dell'altro giocatore.",
        "click_piece": "Clicca uno dei tuoi pezzi sulla scacchiera.",
        "click_destination": "Ora clicca la casella di destinazione.",
        "selected_piece": "Pezzo selezionato. Scegli dove muoverlo.",
        "moves": "Mosse",
    },
    "DE": {
        "create_title": "Freund einladen",
        "your_name": "Dein Name",
        "friend_name": "Name des Freundes",
        "time_control": "Bedenkzeit",
        "create_button": "ZUM SPIEL EINLADEN",
        "join_title": "Hast du eine Einladung?",
        "invite_code": "Einladungscode",
        "code_help": "Gib den 6-stelligen Code ein, den du erhalten hast.",
        "find_button": "EINLADUNG FINDEN",
        "missing_names": "Gib deinen Namen und den Namen deines Freundes ein.",
        "code_not_found": "Einladungscode nicht gefunden.",
        "invited": "{white} hat {black} zu einer privaten Schachpartie eingeladen.",
        "accept_question": "Ist diese Einladung für dich?",
        "accept_button": "ANNEHMEN & SPIELEN",
        "open_button": "PARTIE ÖFFNEN",
        "cancel_button": "Nicht diese Einladung",
        "your_code": "Einladungscode",
        "tell_friend": "{friend} öffnet Stadia → Premium Arena und gibt diesen Code ein.",
        "waiting_friend": "Warte darauf, dass {friend} die Einladung annimmt.",
        "send_invitation": "Einladung senden",
        "send_whatsapp": "📱 WhatsApp",
        "send_email": "✉️ E-Mail",
        "share_message": (
            "{white} lädt dich zu einer privaten Schachpartie auf Stadia ein.\n\n"
            "Öffne:\n{url}\n\n"
            "Einladungscode: {code}"
        ),
        "email_subject": "Stadia Private Chess Einladung",
        "private_return": "Privater Rückkehr-Link",
        "private_return_help": "Bewahre diesen Link nur für dich auf.",
        "status": "Status",
        "side": "Deine Farbe",
        "waiting_other": "Warte auf den anderen Spieler.",
        "click_piece": "Klicke auf eine deiner Figuren auf dem Brett.",
        "click_destination": "Klicke jetzt auf das Zielfeld.",
        "selected_piece": "Figur ausgewählt. Wähle das Zielfeld.",
        "moves": "Züge",
    },
    "FR": {
        "create_title": "Inviter un ami",
        "your_name": "Votre nom",
        "friend_name": "Nom de l'ami",
        "time_control": "Cadence",
        "create_button": "INVITER À JOUER",
        "join_title": "Vous avez reçu une invitation ?",
        "invite_code": "Code d'invitation",
        "code_help": "Entrez le code de 6 caractères reçu de votre ami.",
        "find_button": "TROUVER L'INVITATION",
        "missing_names": "Entrez votre nom et celui de votre ami.",
        "code_not_found": "Code d'invitation introuvable.",
        "invited": "{white} a invité {black} à une partie d'échecs privée.",
        "accept_question": "Cette invitation est-elle pour vous ?",
        "accept_button": "ACCEPTER ET JOUER",
        "open_button": "OUVRIR LA PARTIE",
        "cancel_button": "Ce n'est pas cette invitation",
        "your_code": "Code d'invitation",
        "tell_friend": "{friend} ouvre Stadia → Arène Premium et entre ce code.",
        "waiting_friend": "En attente de l'acceptation de {friend}.",
        "send_invitation": "Envoyer l'invitation",
        "send_whatsapp": "📱 WhatsApp",
        "send_email": "✉️ E-mail",
        "share_message": (
            "{white} vous invite à jouer aux échecs privés sur Stadia.\n\n"
            "Ouvrez :\n{url}\n\n"
            "Code d'invitation : {code}"
        ),
        "email_subject": "Invitation Stadia Private Chess",
        "private_return": "Lien privé de retour",
        "private_return_help": "Gardez ce lien uniquement pour vous.",
        "status": "Statut",
        "side": "Votre couleur",
        "waiting_other": "En attente de l'autre joueur.",
        "click_piece": "Cliquez sur l'une de vos pièces sur l'échiquier.",
        "click_destination": "Cliquez maintenant sur la case de destination.",
        "selected_piece": "Pièce sélectionnée. Choisissez sa destination.",
        "moves": "Coups",
    },
    "ES": {
        "create_title": "Invitar a un amigo",
        "your_name": "Tu nombre",
        "friend_name": "Nombre del amigo",
        "time_control": "Ritmo",
        "create_button": "INVITAR A JUGAR",
        "join_title": "¿Has recibido una invitación?",
        "invite_code": "Código de invitación",
        "code_help": "Introduce el código de 6 caracteres que recibiste.",
        "find_button": "BUSCAR INVITACIÓN",
        "missing_names": "Introduce tu nombre y el nombre de tu amigo.",
        "code_not_found": "Código de invitación no encontrado.",
        "invited": "{white} ha invitado a {black} a una partida privada de ajedrez.",
        "accept_question": "¿Esta invitación es para ti?",
        "accept_button": "ACEPTAR Y JUGAR",
        "open_button": "ABRIR PARTIDA",
        "cancel_button": "No es esta invitación",
        "your_code": "Código de invitación",
        "tell_friend": "{friend} abre Stadia → Arena Premium e introduce este código.",
        "waiting_friend": "Esperando a que {friend} acepte la invitación.",
        "send_invitation": "Enviar invitación",
        "send_whatsapp": "📱 WhatsApp",
        "send_email": "✉️ Correo",
        "share_message": (
            "{white} te invita a jugar ajedrez privado en Stadia.\n\n"
            "Abre:\n{url}\n\n"
            "Código de invitación: {code}"
        ),
        "email_subject": "Invitación Stadia Private Chess",
        "private_return": "Enlace privado de regreso",
        "private_return_help": "Guarda este enlace solo para ti.",
        "status": "Estado",
        "side": "Tu color",
        "waiting_other": "Esperando al otro jugador.",
        "click_piece": "Haz clic en una de tus piezas del tablero.",
        "click_destination": "Ahora haz clic en la casilla de destino.",
        "selected_piece": "Pieza seleccionada. Elige dónde moverla.",
        "moves": "Movimientos",
    },
}


def ui(lang: str, key: str) -> str:
    language = UI.get(lang, UI["EN"])
    return language.get(key, UI["EN"].get(key, key))


def render_html(fragment: str) -> None:
    st.markdown(dedent(fragment).strip(), unsafe_allow_html=True)


def seat_link(game_id: str, role: str, lang: str) -> str:
    token = make_seat_token(game_id, role, APP_SECRET)
    params = urlencode({"seat": token, "lang": lang})
    return f"{STADIA_PUBLIC_URL}/#{params}"


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
        margin-bottom:22px;
    }

    .sv-hero h1{
        font-size:46px;
        margin:8px 0 4px;
    }

    .sv-hero .gradient{
        background:linear-gradient(90deg,#ec3f83,#7657ff);
        -webkit-background-clip:text;
        background-clip:text;
        color:transparent;
        margin:20px 0 8px;
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

    .sv-code-card{
        border:1px solid #ddd6fe;
        border-radius:22px;
        padding:24px;
        background:linear-gradient(135deg,#fff,#faf8ff);
        margin:14px 0;
    }

    .sv-code{
        font-size:42px;
        font-weight:950;
        letter-spacing:.18em;
        color:#111827;
        margin:6px 0 8px;
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
        .sv-code{font-size:34px}
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
# PUBLIC PAGE — CREATE OR ACCEPT BY SHORT CODE
# =========================================================

if not seat:
    st.subheader(ui(lang, "create_title"))

    with st.form("create_game", border=True):
        white_name = st.text_input(ui(lang, "your_name"), value="")
        friend_name = st.text_input(ui(lang, "friend_name"), value="")

        time_control = st.selectbox(
            ui(lang, "time_control"),
            options=list(TIME_LABELS.keys()),
            format_func=lambda x: TIME_LABELS[x],
        )

        submitted = st.form_submit_button(
            ui(lang, "create_button"),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not white_name.strip() or not friend_name.strip():
            st.error(ui(lang, "missing_names"))
        else:
            gid = db.create_game(
                white_name=white_name.strip(),
                black_name=friend_name.strip(),
                time_control=time_control,
            )

            st.query_params["seat"] = make_seat_token(
                gid,
                "white",
                APP_SECRET,
            )
            st.query_params["lang"] = lang
            st.rerun()

    st.divider()
    st.subheader(ui(lang, "join_title"))

    pending_code = str(st.session_state.get("pending_invite_code", "")).strip()

    if not pending_code:
        with st.form("find_invitation", border=True):
            entered_code = st.text_input(
                ui(lang, "invite_code"),
                value="",
                max_chars=8,
                help=ui(lang, "code_help"),
            )

            find_invite = st.form_submit_button(
                ui(lang, "find_button"),
                type="primary",
                use_container_width=True,
            )

        if find_invite:
            normalized = db.normalize_invite_code(entered_code)
            game = db.get_game_by_invite_code(normalized)

            if not game:
                st.error(ui(lang, "code_not_found"))
            else:
                st.session_state["pending_invite_code"] = normalized
                st.rerun()

    else:
        game = db.get_game_by_invite_code(pending_code)

        if not game:
            st.session_state.pop("pending_invite_code", None)
            st.error(ui(lang, "code_not_found"))
            st.stop()

        white_name = escape(str(game["white_name"]))
        black_name = escape(str(game["black_name"]))
        sentence = ui(lang, "invited").format(
            white=white_name,
            black=black_name,
        )

        render_html(
            f"""
            <div class="sv-code-card">
                <div class="sv-kicker">{escape(ui(lang, "invite_code"))}</div>
                <div class="sv-code">{escape(pending_code)}</div>
                <p style="font-size:18px;margin:8px 0 0">{sentence}</p>
                <p style="color:#667085">{escape(ui(lang, "accept_question"))}</p>
            </div>
            """
        )

        c1, c2 = st.columns([3, 1])

        with c1:
            button_label = (
                ui(lang, "accept_button")
                if game["status"] == "waiting"
                else ui(lang, "open_button")
            )

            if st.button(
                button_label,
                type="primary",
                use_container_width=True,
            ):
                if game["status"] == "waiting":
                    game = db.accept_invite(pending_code)

                st.session_state.pop("pending_invite_code", None)
                st.query_params["seat"] = make_seat_token(
                    game["id"],
                    "black",
                    APP_SECRET,
                )
                st.query_params["lang"] = lang
                st.rerun()

        with c2:
            if st.button(
                ui(lang, "cancel_button"),
                use_container_width=True,
            ):
                st.session_state.pop("pending_invite_code", None)
                st.rerun()

    st.info(
        "v0.8 — short invitation code: create → share code → accept → play."
    )
    st.stop()


# =========================================================
# LOAD GAME
# =========================================================

game = db.get_game(seat.game_id)

if not game:
    st.error(tr(lang, "game_missing"))
    st.stop()


# Legacy v0.7 games may still be in READY.
# v0.8 starts new games immediately when the friend accepts.
if game["status"] == "ready":
    try:
        db.start_game(seat.game_id)
        game = db.get_game(seat.game_id)
    except ValueError:
        pass


# =========================================================
# AUTO REFRESH
# =========================================================

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
# WAITING HOST — SHOW ONLY SHORT CODE
# =========================================================

if game["status"] == "waiting" and seat.role == "white":
    invite_code = str(game.get("invite_code") or "").upper()
    friend_name = str(game["black_name"])

    render_html(
        f"""
        <div class="sv-code-card">
            <div class="sv-kicker">{escape(ui(lang, "your_code"))}</div>
            <div class="sv-code">{escape(invite_code)}</div>
            <p style="font-size:18px;margin:8px 0 0">
                {escape(ui(lang, "tell_friend").format(friend=friend_name))}
            </p>
        </div>
        """
    )

    st.warning(
        ui(lang, "waiting_friend").format(friend=friend_name)
    )

    message = ui(lang, "share_message").format(
        white=game["white_name"],
        url=STADIA_PUBLIC_URL + "/",
        code=invite_code,
    )

    whatsapp_url = "https://wa.me/?text=" + quote(message, safe="")
    email_url = (
        "mailto:?subject="
        + quote(ui(lang, "email_subject"), safe="")
        + "&body="
        + quote(message, safe="")
    )

    st.markdown(f"##### {ui(lang, 'send_invitation')}")
    w1, w2 = st.columns(2)

    with w1:
        st.link_button(
            ui(lang, "send_whatsapp"),
            whatsapp_url,
            type="primary",
            use_container_width=True,
        )

    with w2:
        st.link_button(
            ui(lang, "send_email"),
            email_url,
            use_container_width=True,
        )

    with st.expander(ui(lang, "private_return")):
        st.caption(ui(lang, "private_return_help"))
        st.code(
            seat_link(seat.game_id, "white", lang),
            language=None,
        )

    st.stop()


# =========================================================
# GAME HEADER
# =========================================================

role_label = tr(lang, seat.role)

top1, top2, top3 = st.columns([2, 1, 1])

with top1:
    st.markdown(f"### {game['white_name']} vs {game['black_name']}")
    st.caption(f"Game ID: {game['id'][:12].upper()}")

with top2:
    st.markdown(f"**{ui(lang, 'side')}**")
    render_html(
        f'<span class="sv-side">{escape(str(role_label))}</span>'
    )

with top3:
    st.markdown(f"**{ui(lang, 'status')}**")
    render_html(
        f'<span class="sv-status">{escape(str(game["status"]).upper())}</span>'
    )


# =========================================================
# PRIVATE RETURN LINK — COLLAPSED
# =========================================================

with st.expander(ui(lang, "private_return")):
    st.caption(ui(lang, "private_return_help"))
    st.code(
        seat_link(seat.game_id, seat.role, lang),
        language=None,
    )


# =========================================================
# FINISHED
# =========================================================

if game["status"] == "finished":
    st.success(
        f"{tr(lang, 'finished')} — "
        f"{tr(lang, 'result')}: {game['result']}"
    )


# =========================================================
# ACTIVE / FINISHED BOARD — CLICK TO MOVE
# =========================================================

board = chess.Board(game["fen"])
orientation = seat.role
turn_role = "white" if board.turn == chess.WHITE else "black"

can_move = (
    game["status"] == "active"
    and seat.role == turn_role
)

selected_square = str(
    st.query_params.get("src", "")
).lower().strip()

requested_move = str(
    st.query_params.get("move", "")
).lower().strip()

# A click on a legal destination sends the exact UCI move
# back to Streamlit. The server still validates the move.
if requested_move:
    if can_move:
        try:
            db.make_move(
                seat.game_id,
                requested_move,
            )
        except ValueError as exc:
            st.session_state["chess_move_error"] = str(exc)

    if "src" in st.query_params:
        del st.query_params["src"]
    if "move" in st.query_params:
        del st.query_params["move"]

    st.rerun()

move_error = st.session_state.pop(
    "chess_move_error",
    None,
)

if move_error:
    st.error(move_error)

left, right = st.columns([3, 1.15], gap="large")

with left:
    st.markdown(
        board_html(
            game["fen"],
            orientation=orientation,
            seat_token=seat_token,
            lang=lang,
            interactive=can_move,
            selected_square=selected_square,
        ),
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        f"### {tr(lang, 'turn')}: {tr(lang, turn_role)}"
    )

    moves = db.get_moves(seat.game_id)

    st.markdown(
        f"**{ui(lang, 'moves')} ({len(moves)})**"
    )

    if moves:
        st.code(
            "  ".join(m["san"] for m in moves[-18:]),
            language=None,
        )
    else:
        st.caption("—")

    if can_move:
        if selected_square:
            st.success(ui(lang, "selected_piece"))
            st.info(ui(lang, "click_destination"))
        else:
            st.info(ui(lang, "click_piece"))
    elif game["status"] == "active":
        st.info(ui(lang, "waiting_other"))


st.divider()
st.caption(
    "Stadia Chess GUI v0.8.2 — short invitation code; "
    "click a piece, then click its destination; "
    "automatic start after acceptance; private signed player identity."
)
