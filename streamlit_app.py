from __future__ import annotations

import os
from html import escape
from textwrap import dedent
from urllib.parse import quote, urlencode

import chess
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

import chess_db as db
from chess_board import click_to_square, legal_sources, render_board_image, resolve_move
from chess_tokens import make_seat_token, verify_seat_token
from i18n import LANGUAGES, tr


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

TIME_LABELS = {
    "rapid_15_10": "Rapid — 15 + 10",
    "blitz_5_3": "Blitz — 5 + 3",
    "relaxed": "Relaxed — no clock",
}

UI = {
    "EN": {
        "create_title": "Invite a friend", "your_name": "Your name", "friend_name": "Friend's name",
        "time_control": "Time control", "create_button": "INVITE TO PLAY",
        "join_title": "Have an invitation?", "invite_code": "Invitation code",
        "code_help": "Enter the 6-character code your friend gave you.", "find_button": "FIND INVITATION",
        "missing_names": "Enter both your name and your friend's name.", "code_not_found": "Invitation code not found.",
        "invited": "{white} invited {black} to a private chess game.", "accept_question": "Is this invitation for you?",
        "accept_button": "ACCEPT & PLAY", "open_button": "OPEN GAME", "cancel_button": "Not this invitation",
        "your_code": "Invitation code", "tell_friend": "{friend} opens Stadia → Premium Arena and enters this code.",
        "waiting_friend": "Waiting for {friend} to accept the invitation.", "send_invitation": "Send invitation",
        "send_whatsapp": "📱 WhatsApp", "send_email": "✉️ Email",
        "share_message": "{white} invites you to play private chess on Stadia.\n\nOpen:\n{url}\n\nInvitation code: {code}",
        "email_subject": "Stadia Private Chess invitation", "private_return": "Private return link",
        "private_return_help": "Keep this only for yourself if you want to return later.",
        "status": "Status", "side": "Your side", "moves": "Moves",
        "waiting_other": "Waiting for the other player.", "click_piece": "Click one of your pieces.",
        "click_destination": "Now click the destination square.", "selected_piece": "Piece selected.",
    },
    "IT": {
        "create_title": "Invita un amico", "your_name": "Il tuo nome", "friend_name": "Nome dell'amico",
        "time_control": "Cadenza", "create_button": "INVITA A GIOCARE",
        "join_title": "Hai ricevuto un invito?", "invite_code": "Codice invito",
        "code_help": "Inserisci il codice di 6 caratteri ricevuto dal tuo amico.", "find_button": "TROVA L'INVITO",
        "missing_names": "Inserisci il tuo nome e il nome dell'amico.", "code_not_found": "Codice invito non trovato.",
        "invited": "{white} ha invitato {black} a una partita privata di scacchi.", "accept_question": "Questo invito è per te?",
        "accept_button": "ACCETTA E GIOCA", "open_button": "APRI LA PARTITA", "cancel_button": "Non è questo invito",
        "your_code": "Codice invito", "tell_friend": "{friend} apre Stadia → Arena Premium e inserisce questo codice.",
        "waiting_friend": "In attesa che {friend} accetti l'invito.", "send_invitation": "Invia l'invito",
        "send_whatsapp": "📱 WhatsApp", "send_email": "✉️ E-mail",
        "share_message": "{white} ti invita a giocare a scacchi privati su Stadia.\n\nApri:\n{url}\n\nCodice invito: {code}",
        "email_subject": "Invito a Stadia Private Chess", "private_return": "Link privato per tornare",
        "private_return_help": "Conservalo solo per te se vuoi tornare più tardi.",
        "status": "Stato", "side": "Il tuo colore", "moves": "Mosse",
        "waiting_other": "In attesa dell'altro giocatore.", "click_piece": "Clicca uno dei tuoi pezzi.",
        "click_destination": "Ora clicca la casella di destinazione.", "selected_piece": "Pezzo selezionato.",
    },
    "DE": {
        "create_title": "Freund einladen", "your_name": "Dein Name", "friend_name": "Name des Freundes",
        "time_control": "Bedenkzeit", "create_button": "ZUM SPIEL EINLADEN",
        "join_title": "Hast du eine Einladung?", "invite_code": "Einladungscode",
        "code_help": "Gib den 6-stelligen Code ein, den du erhalten hast.", "find_button": "EINLADUNG FINDEN",
        "missing_names": "Gib deinen Namen und den Namen deines Freundes ein.", "code_not_found": "Einladungscode nicht gefunden.",
        "invited": "{white} hat {black} zu einer privaten Schachpartie eingeladen.", "accept_question": "Ist diese Einladung für dich?",
        "accept_button": "ANNEHMEN & SPIELEN", "open_button": "PARTIE ÖFFNEN", "cancel_button": "Nicht diese Einladung",
        "your_code": "Einladungscode", "tell_friend": "{friend} öffnet Stadia → Premium Arena und gibt diesen Code ein.",
        "waiting_friend": "Warte darauf, dass {friend} die Einladung annimmt.", "send_invitation": "Einladung senden",
        "send_whatsapp": "📱 WhatsApp", "send_email": "✉️ E-Mail",
        "share_message": "{white} lädt dich zu einer privaten Schachpartie auf Stadia ein.\n\nÖffne:\n{url}\n\nEinladungscode: {code}",
        "email_subject": "Stadia Private Chess Einladung", "private_return": "Privater Rückkehr-Link",
        "private_return_help": "Bewahre diesen Link nur für dich auf.",
        "status": "Status", "side": "Deine Farbe", "moves": "Züge",
        "waiting_other": "Warte auf den anderen Spieler.", "click_piece": "Klicke auf eine deiner Figuren.",
        "click_destination": "Klicke jetzt auf das Zielfeld.", "selected_piece": "Figur ausgewählt.",
    },
    "FR": {
        "create_title": "Inviter un ami", "your_name": "Votre nom", "friend_name": "Nom de l'ami",
        "time_control": "Cadence", "create_button": "INVITER À JOUER",
        "join_title": "Vous avez reçu une invitation ?", "invite_code": "Code d'invitation",
        "code_help": "Entrez le code de 6 caractères reçu de votre ami.", "find_button": "TROUVER L'INVITATION",
        "missing_names": "Entrez votre nom et celui de votre ami.", "code_not_found": "Code d'invitation introuvable.",
        "invited": "{white} a invité {black} à une partie d'échecs privée.", "accept_question": "Cette invitation est-elle pour vous ?",
        "accept_button": "ACCEPTER ET JOUER", "open_button": "OUVRIR LA PARTIE", "cancel_button": "Ce n'est pas cette invitation",
        "your_code": "Code d'invitation", "tell_friend": "{friend} ouvre Stadia → Arène Premium et entre ce code.",
        "waiting_friend": "En attente de l'acceptation de {friend}.", "send_invitation": "Envoyer l'invitation",
        "send_whatsapp": "📱 WhatsApp", "send_email": "✉️ E-mail",
        "share_message": "{white} vous invite à jouer aux échecs privés sur Stadia.\n\nOuvrez :\n{url}\n\nCode d'invitation : {code}",
        "email_subject": "Invitation Stadia Private Chess", "private_return": "Lien privé de retour",
        "private_return_help": "Gardez ce lien uniquement pour vous.",
        "status": "Statut", "side": "Votre couleur", "moves": "Coups",
        "waiting_other": "En attente de l'autre joueur.", "click_piece": "Cliquez sur l'une de vos pièces.",
        "click_destination": "Cliquez maintenant sur la case de destination.", "selected_piece": "Pièce sélectionnée.",
    },
    "ES": {
        "create_title": "Invitar a un amigo", "your_name": "Tu nombre", "friend_name": "Nombre del amigo",
        "time_control": "Ritmo", "create_button": "INVITAR A JUGAR",
        "join_title": "¿Has recibido una invitación?", "invite_code": "Código de invitación",
        "code_help": "Introduce el código de 6 caracteres que recibiste.", "find_button": "BUSCAR INVITACIÓN",
        "missing_names": "Introduce tu nombre y el nombre de tu amigo.", "code_not_found": "Código de invitación no encontrado.",
        "invited": "{white} ha invitado a {black} a una partida privada de ajedrez.", "accept_question": "¿Esta invitación es para ti?",
        "accept_button": "ACEPTAR Y JUGAR", "open_button": "ABRIR PARTIDA", "cancel_button": "No es esta invitación",
        "your_code": "Código de invitación", "tell_friend": "{friend} abre Stadia → Arena Premium e introduce este código.",
        "waiting_friend": "Esperando a que {friend} acepte la invitación.", "send_invitation": "Enviar invitación",
        "send_whatsapp": "📱 WhatsApp", "send_email": "✉️ Correo",
        "share_message": "{white} te invita a jugar ajedrez privado en Stadia.\n\nAbre:\n{url}\n\nCódigo de invitación: {code}",
        "email_subject": "Invitación Stadia Private Chess", "private_return": "Enlace privado de regreso",
        "private_return_help": "Guarda este enlace solo para ti.",
        "status": "Estado", "side": "Tu color", "moves": "Movimientos",
        "waiting_other": "Esperando al otro jugador.", "click_piece": "Haz clic en una de tus piezas.",
        "click_destination": "Ahora haz clic en la casilla de destino.", "selected_piece": "Pieza seleccionada.",
    },
}


def ui(lang: str, key: str) -> str:
    return UI.get(lang, UI["EN"]).get(key, UI["EN"].get(key, key))


def render_html(fragment: str) -> None:
    st.markdown(dedent(fragment).strip(), unsafe_allow_html=True)


def seat_link(game_id: str, role: str, lang: str) -> str:
    token = make_seat_token(game_id, role, APP_SECRET)
    params = urlencode({"seat": token, "lang": lang})
    return f"{STADIA_PUBLIC_URL}/#{params}"


render_html("""
<style>
.block-container{max-width:1220px;padding-top:1.6rem;padding-bottom:4rem}
h1,h2,h3{letter-spacing:-.02em}
.sv-hero{border:1px solid #e7e4ff;border-radius:26px;padding:30px;background:linear-gradient(135deg,#fff,#faf8ff);margin-bottom:22px}
.sv-hero h1{font-size:46px;margin:8px 0 4px}.sv-hero .gradient{background:linear-gradient(90deg,#ec3f83,#7657ff);-webkit-background-clip:text;background-clip:text;color:transparent;margin:20px 0 8px}
.sv-kicker{font-size:12px;font-weight:900;letter-spacing:.12em;color:#7657ff}.sv-lead{font-size:17px;color:#667085;max-width:780px;line-height:1.6}
.sv-code-card{border:1px solid #ddd6fe;border-radius:22px;padding:24px;background:linear-gradient(135deg,#fff,#faf8ff);margin:14px 0}.sv-code{font-size:42px;font-weight:950;letter-spacing:.18em;color:#111827;margin:6px 0 8px}
.sv-status{display:inline-block;padding:7px 11px;border-radius:999px;background:#f0edff;color:#5038c8;font-weight:800;font-size:13px}.sv-side{display:inline-block;padding:8px 12px;border-radius:999px;background:#111827;color:#fff;font-weight:900}
div.stButton>button,div[data-testid="stFormSubmitButton"]>button{min-height:54px;border-radius:14px;font-weight:850;font-size:15px}[data-testid="stLinkButton"] a{min-height:54px;border-radius:14px;font-weight:850;font-size:15px;display:flex;align-items:center;justify-content:center}code{word-break:break-all;white-space:pre-wrap}
@media(max-width:760px){.sv-hero{padding:22px}.sv-hero h1{font-size:36px}.sv-code{font-size:34px}}
</style>
""")

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

render_html(f"""
<div class="sv-hero">
<div class="sv-kicker">STADIA</div>
<h1>{escape(str(tr(lang, 'title')))}</h1>
<h2 class="gradient">{escape(str(tr(lang, 'tagline')))}</h2>
<p class="sv-lead">{escape(str(tr(lang, 'subtitle')))}</p>
</div>
""")

seat_token = str(st.query_params.get("seat", "")).strip()
seat = verify_seat_token(seat_token, APP_SECRET) if seat_token else None
if seat_token and not seat:
    st.error(tr(lang, "invalid_link"))
    st.stop()


# PUBLIC PAGE — CREATE OR ACCEPT BY SHORT CODE
if not seat:
    st.subheader(ui(lang, "create_title"))
    with st.form("create_game", border=True):
        white_name = st.text_input(ui(lang, "your_name"))
        friend_name = st.text_input(ui(lang, "friend_name"))
        time_control = st.selectbox(
            ui(lang, "time_control"),
            options=list(TIME_LABELS.keys()),
            format_func=lambda x: TIME_LABELS[x],
        )
        submitted = st.form_submit_button(ui(lang, "create_button"), type="primary", use_container_width=True)

    if submitted:
        if not white_name.strip() or not friend_name.strip():
            st.error(ui(lang, "missing_names"))
        else:
            gid = db.create_game(white_name=white_name.strip(), black_name=friend_name.strip(), time_control=time_control)
            st.query_params["seat"] = make_seat_token(gid, "white", APP_SECRET)
            st.query_params["lang"] = lang
            st.rerun()

    st.divider()
    st.subheader(ui(lang, "join_title"))
    pending_code = str(st.session_state.get("pending_invite_code", "")).strip()

    if not pending_code:
        with st.form("find_invitation", border=True):
            entered_code = st.text_input(ui(lang, "invite_code"), max_chars=8, help=ui(lang, "code_help"))
            find_invite = st.form_submit_button(ui(lang, "find_button"), type="primary", use_container_width=True)

        if find_invite:
            normalized = db.normalize_invite_code(entered_code)
            found_game = db.get_game_by_invite_code(normalized)
            if not found_game:
                st.error(ui(lang, "code_not_found"))
            else:
                st.session_state["pending_invite_code"] = normalized
                st.rerun()
    else:
        found_game = db.get_game_by_invite_code(pending_code)
        if not found_game:
            st.session_state.pop("pending_invite_code", None)
            st.error(ui(lang, "code_not_found"))
            st.stop()

        sentence = ui(lang, "invited").format(
            white=escape(str(found_game["white_name"])),
            black=escape(str(found_game["black_name"])),
        )
        render_html(f"""
        <div class="sv-code-card"><div class="sv-kicker">{escape(ui(lang, 'invite_code'))}</div>
        <div class="sv-code">{escape(pending_code)}</div><p style="font-size:18px;margin:8px 0 0">{sentence}</p>
        <p style="color:#667085">{escape(ui(lang, 'accept_question'))}</p></div>
        """)

        c1, c2 = st.columns([3, 1])
        with c1:
            label = ui(lang, "accept_button") if found_game["status"] == "waiting" else ui(lang, "open_button")
            if st.button(label, type="primary", use_container_width=True):
                if found_game["status"] in {"waiting", "ready"}:
                    found_game = db.accept_invite(pending_code)
                st.session_state.pop("pending_invite_code", None)
                st.query_params["seat"] = make_seat_token(found_game["id"], "black", APP_SECRET)
                st.query_params["lang"] = lang
                st.rerun()
        with c2:
            if st.button(ui(lang, "cancel_button"), use_container_width=True):
                st.session_state.pop("pending_invite_code", None)
                st.rerun()

    st.info("v0.8.3 — short invitation code and smooth click-to-move board.")
    st.stop()


game = db.get_game(seat.game_id)
if not game:
    st.error(tr(lang, "game_missing"))
    st.stop()

if game["status"] == "ready":
    try:
        db.start_game(seat.game_id)
        game = db.get_game(seat.game_id)
    except ValueError:
        pass


# WAITING HOST — only this fragment polls for the invited friend.
if game["status"] == "waiting" and seat.role == "white":
    @st.fragment(run_every="2s")
    def waiting_room() -> None:
        current = db.get_game(seat.game_id)
        if not current:
            st.error(tr(lang, "game_missing"))
            return
        if current["status"] != "waiting":
            st.rerun()
            return

        invite_code = str(current.get("invite_code") or "").upper()
        friend_name = str(current["black_name"])
        render_html(f"""
        <div class="sv-code-card"><div class="sv-kicker">{escape(ui(lang, 'your_code'))}</div>
        <div class="sv-code">{escape(invite_code)}</div>
        <p style="font-size:18px;margin:8px 0 0">{escape(ui(lang, 'tell_friend').format(friend=friend_name))}</p></div>
        """)
        st.warning(ui(lang, "waiting_friend").format(friend=friend_name))

        message = ui(lang, "share_message").format(white=current["white_name"], url=STADIA_PUBLIC_URL + "/", code=invite_code)
        whatsapp_url = "https://wa.me/?text=" + quote(message, safe="")
        email_url = "mailto:?subject=" + quote(ui(lang, "email_subject"), safe="") + "&body=" + quote(message, safe="")
        st.markdown(f"##### {ui(lang, 'send_invitation')}")
        w1, w2 = st.columns(2)
        with w1:
            st.link_button(ui(lang, "send_whatsapp"), whatsapp_url, type="primary", use_container_width=True)
        with w2:
            st.link_button(ui(lang, "send_email"), email_url, use_container_width=True)
        with st.expander(ui(lang, "private_return")):
            st.caption(ui(lang, "private_return_help"))
            st.code(seat_link(seat.game_id, "white", lang), language=None)

    waiting_room()
    st.caption("Stadia Chess GUI v0.8.3")
    st.stop()


# STATIC GAME HEADER
role_label = tr(lang, seat.role)
top1, top2 = st.columns([3, 1])
with top1:
    st.markdown(f"### {game['white_name']} vs {game['black_name']}")
    st.caption(f"Game ID: {game['id'][:12].upper()}")
with top2:
    st.markdown(f"**{ui(lang, 'side')}**")
    render_html(f'<span class="sv-side">{escape(str(role_label))}</span>')

with st.expander(ui(lang, "private_return")):
    st.caption(ui(lang, "private_return_help"))
    st.code(seat_link(seat.game_id, seat.role, lang), language=None)


# STABLE IMAGE BOARD — NO 64 BUTTON GRID, NO CONTINUOUS PAGE RERUN
selection_key = f"selected_square_{seat.game_id}_{seat.role}"
click_time_key = f"last_board_click_{seat.game_id}_{seat.role}"


def apply_square_click(
    coord: str,
    current: dict,
) -> bool:
    """
    Apply one click to the two-click move state.

    Returns True only when a real chess move was completed.
    """
    board = chess.Board(current["fen"])
    turn_role = (
        "white"
        if board.turn == chess.WHITE
        else "black"
    )

    if (
        current["status"] != "active"
        or seat.role != turn_role
    ):
        st.session_state[selection_key] = ""
        return False

    coord = (
        coord
        or ""
    ).lower().strip()

    selected = str(
        st.session_state.get(
            selection_key,
            "",
        )
    ).lower().strip()

    sources = legal_sources(
        current["fen"]
    )

    if not selected:
        if coord in sources:
            st.session_state[
                selection_key
            ] = coord
        return False

    if coord == selected:
        st.session_state[
            selection_key
        ] = ""
        return False

    if coord in sources:
        st.session_state[
            selection_key
        ] = coord
        return False

    uci = resolve_move(
        current["fen"],
        selected,
        coord,
    )

    if not uci:
        return False

    try:
        db.make_move(
            seat.game_id,
            uci,
        )
        st.session_state[
            selection_key
        ] = ""
        return True

    except ValueError as exc:
        st.session_state[
            "chess_move_error"
        ] = str(exc)
        st.session_state[
            selection_key
        ] = ""
        return False


@st.fragment
def board_fragment() -> None:
    current = db.get_game(
        seat.game_id
    )

    if not current:
        st.error(
            tr(
                lang,
                "game_missing",
            )
        )
        return

    board = chess.Board(
        current["fen"]
    )

    turn_role = (
        "white"
        if board.turn == chess.WHITE
        else "black"
    )

    can_move = (
        current["status"] == "active"
        and seat.role == turn_role
    )

    selected_square = str(
        st.session_state.get(
            selection_key,
            "",
        )
    ).lower().strip()

    if (
        not can_move
        or selected_square
        not in legal_sources(
            current["fen"]
        )
    ):
        selected_square = ""
        st.session_state[
            selection_key
        ] = ""

    move_error = st.session_state.pop(
        "chess_move_error",
        None,
    )

    if move_error:
        st.error(
            move_error
        )

    status_col, turn_col = st.columns(
        [1, 2]
    )

    with status_col:
        st.markdown(
            f"**{ui(lang, 'status')}**"
        )
        render_html(
            f'<span class="sv-status">'
            f'{escape(str(current["status"]).upper())}'
            f'</span>'
        )

    with turn_col:
        if turn_role == "white":
            turn_text = (
                "White to move"
                if lang == "EN"
                else "Muove il Bianco"
                if lang == "IT"
                else f"{tr(lang, 'turn')}: {tr(lang, turn_role)}"
            )
        else:
            turn_text = (
                "Black to move"
                if lang == "EN"
                else "Muove il Nero"
                if lang == "IT"
                else f"{tr(lang, 'turn')}: {tr(lang, turn_role)}"
            )

        st.markdown(
            f"### {turn_text}"
        )

    left, right = st.columns(
        [3, 1.15],
        gap="large",
    )

    with left:
        board_image = render_board_image(
            current["fen"],
            seat.role,
            selected_square=selected_square,
            interactive=can_move,
        )

        click = streamlit_image_coordinates(
            board_image,
            key=(
                f"stable_board_"
                f"{seat.game_id}_"
                f"{seat.role}"
            ),
            use_column_width="auto",
            cursor=(
                "pointer"
                if can_move
                else "default"
            ),
        )

        if click:
            click_time = click.get(
                "unix_time"
            )

            if (
                click_time
                and click_time
                != st.session_state.get(
                    click_time_key
                )
            ):
                st.session_state[
                    click_time_key
                ] = click_time

                coord = click_to_square(
                    click.get("x", 0),
                    click.get("y", 0),
                    width=click.get(
                        "width",
                        720,
                    ),
                    height=click.get(
                        "height",
                        720,
                    ),
                    orientation=seat.role,
                )

                if coord:
                    completed_move = (
                        apply_square_click(
                            coord,
                            current,
                        )
                    )

                    if completed_move:
                        # One full rerun only after the move is finished,
                        # so the page can enter the "waiting for opponent"
                        # state. Piece selection itself never reruns the page.
                        st.rerun()

                    st.rerun(
                        scope="fragment"
                    )

    with right:
        moves = db.get_moves(
            seat.game_id
        )

        st.markdown(
            f"**{ui(lang, 'moves')} "
            f"({len(moves)})**"
        )

        if moves:
            st.code(
                "  ".join(
                    move["san"]
                    for move in moves[-18:]
                ),
                language=None,
            )
        else:
            st.caption("—")

        if current["status"] == "finished":
            st.success(
                f"{tr(lang, 'finished')} — "
                f"{tr(lang, 'result')}: "
                f"{current['result']}"
            )

        elif can_move:
            if selected_square:
                st.success(
                    ui(
                        lang,
                        "selected_piece",
                    )
                )
                st.info(
                    ui(
                        lang,
                        "click_destination",
                    )
                )
            else:
                st.info(
                    ui(
                        lang,
                        "click_piece",
                    )
                )

        else:
            st.info(
                ui(
                    lang,
                    "waiting_other",
                )
            )


# On your turn there is no timer and no continuous refresh.
# The board reruns only when you actually click it.
board_fragment()


# Only the waiting player polls the database.
# The polling fragment is tiny and does not redraw the board.
game_after_board = db.get_game(
    seat.game_id
)

if game_after_board:
    board_after = chess.Board(
        game_after_board["fen"]
    )

    turn_after = (
        "white"
        if board_after.turn == chess.WHITE
        else "black"
    )

    waiting_for_opponent = (
        game_after_board["status"] == "active"
        and seat.role != turn_after
    )

    if waiting_for_opponent:
        known_fen = game_after_board["fen"]

        @st.fragment(
            run_every="2s"
        )
        def opponent_poll() -> None:
            latest = db.get_game(
                seat.game_id
            )

            if not latest:
                return

            if (
                latest["fen"] != known_fen
                or latest["status"]
                != game_after_board["status"]
            ):
                # Full rerun happens once, only when the opponent
                # actually moves or the game ends.
                st.rerun()

        opponent_poll()


st.divider()

st.caption(
    "Stadia Chess GUI v0.8.4 — fixed image board; "
    "White and Black orientations are independent; "
    "no continuous board refresh; two-click moves."
)
