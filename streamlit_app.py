from __future__ import annotations

import os
import json
from pathlib import Path
from html import escape
from textwrap import dedent
from urllib.parse import quote, urlencode

import chess
import streamlit as st
import streamlit.components.v1 as components

import chess_db as db
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

# Browser-native chess board.
# It uses its own fixed-size iframe and handles piece selection locally,
# so clicking a piece does NOT rerun or move the Streamlit page.
BOARD_DISPLAY_PX = 460
CHESS_BOARD_FRONTEND = Path(__file__).parent / "chess_board_frontend"
stadia_chess_board = components.declare_component(
    "stadia_chess_board_v087",
    path=str(CHESS_BOARD_FRONTEND),
)


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


POLISH = {
    "EN": {
        "arena_badge": "PRIVATE CHESS ARENA",
        "public_intro": "Start a private game in seconds. No account is needed for your guest.",
        "create_hint": "Create a game and share the 6-character code with your friend.",
        "join_hint": "Already have a code? Enter it below and join the game.",
        "invitation_ready": "INVITATION READY",
        "code_hint": "Send only this code. Your friend opens Premium Arena and enters it.",
        "save_game_link": "Save my game link",
        "save_game_help": "Keep this private link if you want to return to this exact game later.",
        "you_play": "YOU PLAY",
        "your_turn": "Your turn — choose a piece.",
        "opponent_turn": "Waiting for your opponent's move.",
        "game_over": "GAME FINISHED",
        "white_wins": "{name} wins with White.",
        "black_wins": "{name} wins with Black.",
        "draw": "Draw.",
        "play_again": "PLAY ANOTHER GAME",
        "back_stadia": "BACK TO STADIA",
        "moves_played": "Moves played",
        "game_reference": "Game reference",
        "share_title": "Share the invitation",
        "waiting_title": "Invitation sent",
        "waiting_text": "As soon as {friend} accepts, the board will open automatically.",
        "copy_code": 'COPY INVITATION CODE',
        "copied": 'COPIED ✓',
        "send_to_friend": 'Send this code to {friend}',
        "guest_steps": 'What {friend} needs to do',
        "guest_step_1": 'Open Stadia → Premium Arena',
        "guest_step_2": 'Enter the 6-character invitation code',
        "guest_step_3": 'Accept the invitation and play',
        "you_will_play": 'YOU WILL PLAY',
        "invite_details": 'Private game invitation',
        "no_account": 'No account is required.',
        "share_message_v089": '{white} invited you to a private chess game on Stadia.\n\nOpen Premium Arena:\n{url}\n\nInvitation code: {code}\n\nNo account is required.',
        "footer": 'Stadia Private Chess · v0.8.9.1 Invitations Flow Fix',
    },
    "IT": {
        "arena_badge": "ARENA SCACCHI PRIVATA",
        "public_intro": "Avvia una partita privata in pochi secondi. Il tuo invitato non deve creare un account.",
        "create_hint": "Crea la partita e comunica al tuo amico il codice di 6 caratteri.",
        "join_hint": "Hai già un codice? Inseriscilo qui sotto ed entra nella partita.",
        "invitation_ready": "INVITO PRONTO",
        "code_hint": "Invia solo questo codice. Il tuo amico apre Premium Arena e lo inserisce.",
        "save_game_link": "Salva il link della partita",
        "save_game_help": "Conserva questo link privato se vuoi tornare esattamente a questa partita.",
        "you_play": "TU GIOCHI",
        "your_turn": "Tocca a te — scegli un pezzo.",
        "opponent_turn": "In attesa della mossa dell'avversario.",
        "game_over": "PARTITA TERMINATA",
        "white_wins": "{name} vince con il Bianco.",
        "black_wins": "{name} vince con il Nero.",
        "draw": "Patta.",
        "play_again": "GIOCA UN'ALTRA PARTITA",
        "back_stadia": "TORNA A STADIA",
        "moves_played": "Mosse giocate",
        "game_reference": "Riferimento partita",
        "share_title": "Condividi l'invito",
        "waiting_title": "Invito inviato",
        "waiting_text": "Appena {friend} accetta, la scacchiera si aprirà automaticamente.",
        "copy_code": 'COPIA CODICE INVITO',
        "copied": 'COPIATO ✓',
        "send_to_friend": 'Invia questo codice a {friend}',
        "guest_steps": 'Cosa deve fare {friend}',
        "guest_step_1": 'Aprire Stadia → Premium Arena',
        "guest_step_2": 'Inserire il codice invito di 6 caratteri',
        "guest_step_3": "Accettare l'invito e giocare",
        "you_will_play": 'GIOCHERAI',
        "invite_details": 'Invito a partita privata',
        "no_account": 'Non è necessario creare un account.',
        "share_message_v089": '{white} ti invita a una partita privata di scacchi su Stadia.\n\nApri Premium Arena:\n{url}\n\nCodice invito: {code}\n\nNon è necessario creare un account.',
        "footer": 'Stadia Private Chess · v0.8.9.1 Invitations Flow Fix',
    },
    "DE": {
        "arena_badge": "PRIVATE SCHACH-ARENA",
        "public_intro": "Starte in wenigen Sekunden eine private Partie. Dein Gast braucht kein Konto.",
        "create_hint": "Erstelle eine Partie und sende deinem Freund den 6-stelligen Code.",
        "join_hint": "Du hast bereits einen Code? Gib ihn unten ein und tritt der Partie bei.",
        "invitation_ready": "EINLADUNG BEREIT",
        "code_hint": "Sende nur diesen Code. Dein Freund öffnet die Premium Arena und gibt ihn ein.",
        "save_game_link": "Meinen Partie-Link speichern",
        "save_game_help": "Bewahre diesen privaten Link auf, um später genau zu dieser Partie zurückzukehren.",
        "you_play": "DU SPIELST",
        "your_turn": "Du bist am Zug — wähle eine Figur.",
        "opponent_turn": "Warte auf den Zug deines Gegners.",
        "game_over": "PARTIE BEENDET",
        "white_wins": "{name} gewinnt mit Weiß.",
        "black_wins": "{name} gewinnt mit Schwarz.",
        "draw": "Remis.",
        "play_again": "NOCH EINE PARTIE",
        "back_stadia": "ZURÜCK ZU STADIA",
        "moves_played": "Gespielte Züge",
        "game_reference": "Partie-Referenz",
        "share_title": "Einladung teilen",
        "waiting_title": "Einladung gesendet",
        "waiting_text": "Sobald {friend} annimmt, öffnet sich das Brett automatisch.",
        "copy_code": 'EINLADUNGSCODE KOPIEREN',
        "copied": 'KOPIERT ✓',
        "send_to_friend": 'Sende diesen Code an {friend}',
        "guest_steps": 'Was {friend} tun muss',
        "guest_step_1": 'Stadia → Premium Arena öffnen',
        "guest_step_2": 'Den 6-stelligen Einladungscode eingeben',
        "guest_step_3": 'Einladung annehmen und spielen',
        "you_will_play": 'DU SPIELST',
        "invite_details": 'Private Partie-Einladung',
        "no_account": 'Es ist kein Konto erforderlich.',
        "share_message_v089": '{white} lädt dich zu einer privaten Schachpartie auf Stadia ein.\n\nPremium Arena öffnen:\n{url}\n\nEinladungscode: {code}\n\nEs ist kein Konto erforderlich.',
        "footer": 'Stadia Private Chess · v0.8.9.1 Invitations Flow Fix',
    },
    "FR": {
        "arena_badge": "ARÈNE D'ÉCHECS PRIVÉE",
        "public_intro": "Lancez une partie privée en quelques secondes. Votre invité n'a pas besoin de compte.",
        "create_hint": "Créez une partie et envoyez le code à 6 caractères à votre ami.",
        "join_hint": "Vous avez déjà un code ? Saisissez-le ci-dessous pour rejoindre la partie.",
        "invitation_ready": "INVITATION PRÊTE",
        "code_hint": "Envoyez uniquement ce code. Votre ami ouvre Premium Arena et le saisit.",
        "save_game_link": "Enregistrer mon lien de partie",
        "save_game_help": "Conservez ce lien privé pour revenir plus tard exactement à cette partie.",
        "you_play": "VOUS JOUEZ",
        "your_turn": "À vous de jouer — choisissez une pièce.",
        "opponent_turn": "En attente du coup de votre adversaire.",
        "game_over": "PARTIE TERMINÉE",
        "white_wins": "{name} gagne avec les Blancs.",
        "black_wins": "{name} gagne avec les Noirs.",
        "draw": "Nulle.",
        "play_again": "JOUER UNE AUTRE PARTIE",
        "back_stadia": "RETOUR À STADIA",
        "moves_played": "Coups joués",
        "game_reference": "Référence de partie",
        "share_title": "Partager l'invitation",
        "waiting_title": "Invitation envoyée",
        "waiting_text": "Dès que {friend} accepte, l'échiquier s'ouvrira automatiquement.",
        "copy_code": "COPIER LE CODE D'INVITATION",
        "copied": 'COPIÉ ✓',
        "send_to_friend": 'Envoyez ce code à {friend}',
        "guest_steps": 'Ce que {friend} doit faire',
        "guest_step_1": 'Ouvrir Stadia → Premium Arena',
        "guest_step_2": "Saisir le code d'invitation à 6 caractères",
        "guest_step_3": "Accepter l'invitation et jouer",
        "you_will_play": 'VOUS JOUEREZ',
        "invite_details": 'Invitation à une partie privée',
        "no_account": "Aucun compte n'est nécessaire.",
        "share_message_v089": "{white} vous invite à une partie d'échecs privée sur Stadia.\n\nOuvrez Premium Arena :\n{url}\n\nCode d'invitation : {code}\n\nAucun compte n'est nécessaire.",
        "footer": 'Stadia Private Chess · v0.8.9.1 Invitations Flow Fix',
    },
    "ES": {
        "arena_badge": "ARENA DE AJEDREZ PRIVADA",
        "public_intro": "Inicia una partida privada en segundos. Tu invitado no necesita crear una cuenta.",
        "create_hint": "Crea una partida y envía a tu amigo el código de 6 caracteres.",
        "join_hint": "¿Ya tienes un código? Introdúcelo abajo para entrar en la partida.",
        "invitation_ready": "INVITACIÓN LISTA",
        "code_hint": "Envía solo este código. Tu amigo abre Premium Arena y lo introduce.",
        "save_game_link": "Guardar el enlace de mi partida",
        "save_game_help": "Guarda este enlace privado para volver más tarde exactamente a esta partida.",
        "you_play": "TÚ JUEGAS",
        "your_turn": "Tu turno — elige una pieza.",
        "opponent_turn": "Esperando la jugada de tu oponente.",
        "game_over": "PARTIDA TERMINADA",
        "white_wins": "{name} gana con Blancas.",
        "black_wins": "{name} gana con Negras.",
        "draw": "Tablas.",
        "play_again": "JUGAR OTRA PARTIDA",
        "back_stadia": "VOLVER A STADIA",
        "moves_played": "Jugadas realizadas",
        "game_reference": "Referencia de partida",
        "share_title": "Compartir invitación",
        "waiting_title": "Invitación enviada",
        "waiting_text": "En cuanto {friend} acepte, el tablero se abrirá automáticamente.",
        "copy_code": 'COPIAR CÓDIGO DE INVITACIÓN',
        "copied": 'COPIADO ✓',
        "send_to_friend": 'Envía este código a {friend}',
        "guest_steps": 'Lo que debe hacer {friend}',
        "guest_step_1": 'Abrir Stadia → Premium Arena',
        "guest_step_2": 'Introducir el código de invitación de 6 caracteres',
        "guest_step_3": 'Aceptar la invitación y jugar',
        "you_will_play": 'JUGARÁS',
        "invite_details": 'Invitación a partida privada',
        "no_account": 'No es necesario crear una cuenta.',
        "share_message_v089": '{white} te invita a una partida privada de ajedrez en Stadia.\n\nAbre Premium Arena:\n{url}\n\nCódigo de invitación: {code}\n\nNo es necesario crear una cuenta.',
        "footer": 'Stadia Private Chess · v0.8.9.1 Invitations Flow Fix',
    },
}


def polish(lang: str, key: str) -> str:
    return POLISH.get(lang, POLISH["EN"]).get(
        key,
        POLISH["EN"].get(key, key),
    )


def ui(lang: str, key: str) -> str:
    return UI.get(lang, UI["EN"]).get(key, UI["EN"].get(key, key))


def render_html(fragment: str) -> None:
    cleaned = "\n".join(
        line.strip()
        for line in dedent(fragment).strip().splitlines()
    )
    st.markdown(cleaned, unsafe_allow_html=True)


def copy_button(
    value: str,
    label: str,
    copied_label: str,
) -> None:
    """
    Small browser-only clipboard button.

    It does not touch the chess engine, database, board component,
    query parameters, or game state.
    """
    value_js = json.dumps(str(value))
    label_js = json.dumps(str(label))
    copied_js = json.dumps(str(copied_label))
    label_html = escape(str(label))

    components.html(
        f"""
        <style>
        html,body{{
            margin:0;
            padding:0;
            overflow:hidden;
            background:transparent;
            font-family:Arial,sans-serif;
        }}
        #sv-copy{{
            width:100%;
            min-height:48px;
            border:0;
            border-radius:13px;
            background:#111827;
            color:#fff;
            font-size:14px;
            font-weight:800;
            cursor:pointer;
        }}
        #sv-copy:hover{{filter:brightness(1.08)}}
        </style>

        <button id="sv-copy" type="button" onclick="copyValue()">
            {label_html}
        </button>

        <script>
        const copyText = {value_js};
        const originalLabel = {label_js};
        const copiedLabel = {copied_js};

        async function copyValue(){{
            const button = document.getElementById("sv-copy");
            let copied = false;

            try {{
                await navigator.clipboard.writeText(copyText);
                copied = true;
            }} catch (err) {{
                try {{
                    const area = document.createElement("textarea");
                    area.value = copyText;
                    area.style.position = "fixed";
                    area.style.opacity = "0";
                    document.body.appendChild(area);
                    area.focus();
                    area.select();
                    copied = document.execCommand("copy");
                    document.body.removeChild(area);
                }} catch (fallbackErr) {{
                    copied = false;
                }}
            }}

            if (copied) {{
                button.textContent = copiedLabel;
                setTimeout(() => {{
                    button.textContent = originalLabel;
                }}, 1400);
            }}
        }}
        </script>
        """,
        height=52,
        scrolling=False,
    )


def seat_link(game_id: str, role: str, lang: str) -> str:
    token = make_seat_token(game_id, role, APP_SECRET)
    params = urlencode({"seat": token, "lang": lang})
    return f"{STADIA_PUBLIC_URL}/#{params}"


render_html("""
<style>
:root{
    --sv-ink:#111827;
    --sv-muted:#667085;
    --sv-purple:#7657ff;
    --sv-purple-dark:#5b3ff0;
    --sv-pink:#ec3f83;
    --sv-line:#e8e5f5;
    --sv-soft:#f8f7ff;
    --sv-success:#087f5b;
}

.block-container{
    max-width:1180px;
    padding-top:1.35rem;
    padding-bottom:3.5rem;
}
h1,h2,h3{letter-spacing:-.025em}

.sv-hero{
    border:1px solid var(--sv-line);
    border-radius:28px;
    padding:32px 34px;
    background:
        radial-gradient(circle at 92% 10%,rgba(118,87,255,.10),transparent 30%),
        linear-gradient(135deg,#fff 0%,#fbfaff 100%);
    margin-bottom:24px;
    box-shadow:0 14px 40px rgba(64,45,130,.06);
}
.sv-hero.compact{
    padding:18px 24px;
    margin-bottom:18px;
    border-radius:22px;
}
.sv-hero.compact h1{font-size:30px;margin:5px 0 0}
.sv-hero h1{font-size:46px;margin:8px 0 4px;color:var(--sv-ink)}
.sv-hero .gradient{
    background:linear-gradient(90deg,var(--sv-pink),var(--sv-purple));
    -webkit-background-clip:text;background-clip:text;color:transparent;
    margin:18px 0 8px;
}
.sv-kicker{
    font-size:11px;font-weight:900;letter-spacing:.14em;color:var(--sv-purple);
}
.sv-lead{font-size:16px;color:var(--sv-muted);max-width:800px;line-height:1.65}

.sv-section-intro{
    color:var(--sv-muted);
    margin:-4px 0 14px;
    line-height:1.55;
}
.sv-code-card{
    border:1px solid #ddd6fe;
    border-radius:24px;
    padding:25px;
    background:linear-gradient(135deg,#fff,#faf8ff);
    margin:14px 0;
    box-shadow:0 12px 30px rgba(91,63,240,.06);
}
.sv-code{
    font-size:44px;
    font-weight:950;
    letter-spacing:.20em;
    color:var(--sv-ink);
    margin:7px 0 8px;
}
.sv-code-note{color:var(--sv-muted);font-size:14px;margin-top:8px}
.sv-invite-title{
    font-size:20px;
    font-weight:900;
    color:var(--sv-ink);
    margin:5px 0 2px;
}
.sv-invite-sub{
    color:var(--sv-muted);
    font-size:14px;
    line-height:1.55;
}
.sv-invite-steps{
    border:1px solid var(--sv-line);
    border-radius:18px;
    padding:16px 18px;
    background:#fff;
    margin:12px 0 16px;
}
.sv-invite-steps-title{
    font-weight:900;
    color:var(--sv-ink);
    margin-bottom:9px;
}
.sv-invite-step{
    display:flex;
    gap:10px;
    align-items:flex-start;
    color:var(--sv-muted);
    font-size:14px;
    margin:7px 0;
}
.sv-step-num{
    flex:0 0 24px;
    height:24px;
    border-radius:999px;
    background:#eeeaff;
    color:#5038c8;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    font-weight:900;
    font-size:12px;
}
.sv-invite-meta{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    margin-top:12px;
}
.sv-meta-pill{
    display:inline-block;
    padding:7px 10px;
    border-radius:999px;
    background:#f5f4fb;
    color:#475467;
    font-size:12px;
    font-weight:800;
}

.sv-match-card{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    padding:18px 20px;
    border:1px solid var(--sv-line);
    border-radius:20px;
    background:#fff;
    margin:4px 0 12px;
}
.sv-match-names{font-size:24px;font-weight:900;color:var(--sv-ink)}
.sv-match-meta{font-size:12px;color:var(--sv-muted);margin-top:4px}
.sv-side-wrap{text-align:right;white-space:nowrap}
.sv-side-label{font-size:10px;font-weight:900;letter-spacing:.12em;color:var(--sv-muted);margin-bottom:6px}
.sv-side{
    display:inline-block;
    padding:9px 13px;
    border-radius:999px;
    background:var(--sv-ink);
    color:#fff;
    font-weight:900;
}

.sv-turn-card{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    border:1px solid var(--sv-line);
    border-radius:18px;
    padding:13px 16px;
    margin-bottom:14px;
    background:var(--sv-soft);
}
.sv-turn-main{font-size:20px;font-weight:900;color:var(--sv-ink)}
.sv-turn-sub{font-size:13px;color:var(--sv-muted);margin-top:3px}
.sv-status{
    display:inline-block;
    padding:7px 11px;
    border-radius:999px;
    background:#eeeaff;
    color:#5038c8;
    font-weight:900;
    font-size:11px;
    letter-spacing:.04em;
}
.sv-result-card{
    border:1px solid #cdeee3;
    background:#f3fcf8;
    border-radius:18px;
    padding:17px;
    margin:10px 0 12px;
}
.sv-result-title{
    font-size:11px;
    font-weight:900;
    letter-spacing:.12em;
    color:var(--sv-success);
}
.sv-result-text{
    font-size:19px;
    font-weight:900;
    color:var(--sv-ink);
    margin-top:5px;
}

div.stButton>button,
div[data-testid="stFormSubmitButton"]>button{
    min-height:52px;
    border-radius:14px;
    font-weight:850;
    font-size:14px;
}
[data-testid="stLinkButton"] a{
    min-height:50px;
    border-radius:14px;
    font-weight:850;
    font-size:14px;
    display:flex;
    align-items:center;
    justify-content:center;
}
div[data-testid="stForm"]{
    border-color:var(--sv-line);
    border-radius:20px;
    background:#fff;
}
code{word-break:break-all;white-space:pre-wrap}

@media(max-width:760px){
    .sv-hero{padding:22px}
    .sv-hero h1{font-size:36px}
    .sv-code{font-size:34px}
    .sv-match-card,.sv-turn-card{align-items:flex-start;flex-direction:column}
    .sv-side-wrap{text-align:left}
}
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

seat_token = str(st.query_params.get("seat", "")).strip()
seat = verify_seat_token(seat_token, APP_SECRET) if seat_token else None
if seat_token and not seat:
    st.error(tr(lang, "invalid_link"))
    st.stop()

if seat:
    render_html(f"""
    <div class="sv-hero compact">
        <div class="sv-kicker">{escape(polish(lang, 'arena_badge'))}</div>
        <h1>{escape(str(tr(lang, 'title')))}</h1>
    </div>
    """)
else:
    render_html(f"""
    <div class="sv-hero">
        <div class="sv-kicker">{escape(polish(lang, 'arena_badge'))}</div>
        <h1>{escape(str(tr(lang, 'title')))}</h1>
        <h2 class="gradient">{escape(str(tr(lang, 'tagline')))}</h2>
        <p class="sv-lead">{escape(polish(lang, 'public_intro'))}</p>
    </div>
    """)


# PUBLIC PAGE — JOIN FIRST, CREATE SECOND
# The invited player should never re-enter names.
if not seat:
    st.subheader(ui(lang, "join_title"))
    render_html(
        f'<p class="sv-section-intro">'
        f'{escape(polish(lang, "join_hint"))}'
        f'</p>'
    )

    pending_code = str(
        st.session_state.get(
            "pending_invite_code",
            "",
        )
    ).strip()

    if not pending_code:
        with st.form(
            "find_invitation",
            border=True,
        ):
            entered_code = st.text_input(
                ui(lang, "invite_code"),
                max_chars=8,
                help=ui(lang, "code_help"),
            )

            find_invite = st.form_submit_button(
                ui(lang, "find_button"),
                type="primary",
                use_container_width=True,
            )

        if find_invite:
            normalized = db.normalize_invite_code(
                entered_code
            )

            found_game = db.get_game_by_invite_code(
                normalized
            )

            if not found_game:
                st.error(
                    ui(
                        lang,
                        "code_not_found",
                    )
                )
            else:
                st.session_state[
                    "pending_invite_code"
                ] = normalized
                st.rerun()

    else:
        found_game = db.get_game_by_invite_code(
            pending_code
        )

        if not found_game:
            st.session_state.pop(
                "pending_invite_code",
                None,
            )
            st.error(
                ui(
                    lang,
                    "code_not_found",
                )
            )
            st.stop()

        sentence = ui(
            lang,
            "invited",
        ).format(
            white=escape(
                str(
                    found_game["white_name"]
                )
            ),
            black=escape(
                str(
                    found_game["black_name"]
                )
            ),
        )

        time_label = TIME_LABELS.get(
            str(
                found_game.get(
                    "time_control"
                )
                or ""
            ),
            str(
                found_game.get(
                    "time_control"
                )
                or "—"
            ),
        )

        render_html(
            f"""
            <div class="sv-code-card">
            <div class="sv-kicker">{escape(polish(lang, 'invite_details'))}</div>
            <div class="sv-invite-title">{sentence}</div>
            <p class="sv-invite-sub">{escape(polish(lang, 'no_account'))}</p>
            <div class="sv-code">{escape(pending_code)}</div>
            <div class="sv-invite-meta">
            <span class="sv-meta-pill">{escape(polish(lang, 'you_will_play'))}: {escape(str(tr(lang, 'black')))}</span>
            <span class="sv-meta-pill">{escape(ui(lang, 'time_control'))}: {escape(time_label)}</span>
            </div>
            <p class="sv-code-note">{escape(ui(lang, 'accept_question'))}</p>
            </div>
            """
        )

        c1, c2 = st.columns(
            [3, 1]
        )

        with c1:
            label = (
                ui(
                    lang,
                    "accept_button",
                )
                if found_game["status"] == "waiting"
                else ui(
                    lang,
                    "open_button",
                )
            )

            if st.button(
                label,
                type="primary",
                use_container_width=True,
            ):
                if found_game["status"] in {
                    "waiting",
                    "ready",
                }:
                    found_game = db.accept_invite(
                        pending_code
                    )

                st.session_state.pop(
                    "pending_invite_code",
                    None,
                )

                st.query_params["seat"] = (
                    make_seat_token(
                        found_game["id"],
                        "black",
                        APP_SECRET,
                    )
                )

                st.query_params["lang"] = lang
                st.rerun()

        with c2:
            if st.button(
                ui(
                    lang,
                    "cancel_button",
                ),
                use_container_width=True,
            ):
                st.session_state.pop(
                    "pending_invite_code",
                    None,
                )
                st.rerun()

        # Once a valid invitation is found, do not show the create-game form.
        st.caption(
            polish(
                lang,
                "footer",
            )
        )
        st.stop()

    st.divider()

    st.subheader(
        ui(
            lang,
            "create_title",
        )
    )

    render_html(
        f'<p class="sv-section-intro">'
        f'{escape(polish(lang, "create_hint"))}'
        f'</p>'
    )

    with st.form(
        "create_game",
        border=True,
    ):
        white_name = st.text_input(
            ui(
                lang,
                "your_name",
            )
        )

        friend_name = st.text_input(
            ui(
                lang,
                "friend_name",
            )
        )

        time_control = st.selectbox(
            ui(
                lang,
                "time_control",
            ),
            options=list(
                TIME_LABELS.keys()
            ),
            format_func=lambda x:
                TIME_LABELS[x],
        )

        submitted = st.form_submit_button(
            ui(
                lang,
                "create_button",
            ),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if (
            not white_name.strip()
            or not friend_name.strip()
        ):
            st.error(
                ui(
                    lang,
                    "missing_names",
                )
            )
        else:
            gid = db.create_game(
                white_name=white_name.strip(),
                black_name=friend_name.strip(),
                time_control=time_control,
            )

            st.query_params["seat"] = (
                make_seat_token(
                    gid,
                    "white",
                    APP_SECRET,
                )
            )

            st.query_params["lang"] = lang
            st.rerun()

    st.caption(
        polish(
            lang,
            "footer",
        )
    )
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


# WAITING HOST — invitation UI is static; only the tiny watcher polls.
if game["status"] == "waiting" and seat.role == "white":
    invite_code = str(game.get("invite_code") or "").upper()
    friend_name = str(game["black_name"])
    white_name = str(game["white_name"])

    render_html(f"""
    <div class="sv-code-card">
        <div class="sv-kicker">{escape(polish(lang, 'invitation_ready'))}</div>
        <div class="sv-invite-title">
            {escape(polish(lang, 'send_to_friend').format(friend=friend_name))}
        </div>

        <div class="sv-code">{escape(invite_code)}</div>

        <p class="sv-code-note">
            {escape(polish(lang, 'code_hint'))}
        </p>
    </div>
    """)

    copy_button(
        invite_code,
        polish(lang, "copy_code"),
        polish(lang, "copied"),
    )

    render_html(f"""
    <div class="sv-invite-steps">
        <div class="sv-invite-steps-title">
            {escape(polish(lang, 'guest_steps').format(friend=friend_name))}
        </div>

        <div class="sv-invite-step">
            <span class="sv-step-num">1</span>
            <span>{escape(polish(lang, 'guest_step_1'))}</span>
        </div>

        <div class="sv-invite-step">
            <span class="sv-step-num">2</span>
            <span>{escape(polish(lang, 'guest_step_2'))}</span>
        </div>

        <div class="sv-invite-step">
            <span class="sv-step-num">3</span>
            <span>{escape(polish(lang, 'guest_step_3'))}</span>
        </div>
    </div>
    """)

    message = polish(lang, "share_message_v089").format(
        white=white_name,
        url=STADIA_PUBLIC_URL + "/",
        code=invite_code,
    )

    whatsapp_url = (
        "https://wa.me/?text="
        + quote(message, safe="")
    )

    email_url = (
        "mailto:?subject="
        + quote(ui(lang, "email_subject"), safe="")
        + "&body="
        + quote(message, safe="")
    )

    st.markdown(
        f"##### {polish(lang, 'share_title')}"
    )

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

    with st.expander(
        polish(lang, "save_game_link")
    ):
        st.caption(
            polish(lang, "save_game_help")
        )
        st.code(
            seat_link(
                seat.game_id,
                "white",
                lang,
            ),
            language=None,
        )

    @st.fragment(run_every="2s")
    def acceptance_watch() -> None:
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

        if current["status"] != "waiting":
            st.rerun()
            return

        st.info(
            polish(
                lang,
                "waiting_text",
            ).format(
                friend=friend_name
            )
        )

    acceptance_watch()

    st.caption(
        polish(
            lang,
            "footer",
        )
    )
    st.stop()


# STATIC GAME HEADER — presentation only
role_label = tr(lang, seat.role)
render_html(f"""
<div class="sv-match-card">
    <div>
        <div class="sv-match-names">
            {escape(str(game['white_name']))} <span style="color:#98a2b3">vs</span> {escape(str(game['black_name']))}
        </div>
        <div class="sv-match-meta">
            {escape(polish(lang, 'game_reference'))}: {escape(game['id'][:12].upper())}
        </div>
    </div>
    <div class="sv-side-wrap">
        <div class="sv-side-label">{escape(polish(lang, 'you_play'))}</div>
        <span class="sv-side">{escape(str(role_label))}</span>
    </div>
</div>
""")

with st.expander(polish(lang, "save_game_link")):
    st.caption(polish(lang, "save_game_help"))
    st.code(seat_link(seat.game_id, seat.role, lang), language=None)


def polished_result_text(current: dict) -> str:
    result = str(current.get("result") or "").strip()

    if result == "1-0":
        return polish(lang, "white_wins").format(
            name=current.get("white_name", "White")
        )

    if result == "0-1":
        return polish(lang, "black_wins").format(
            name=current.get("black_name", "Black")
        )

    if result == "1/2-1/2":
        return polish(lang, "draw")

    return f"{tr(lang, 'result')}: {result or '—'}"


# STADIA CHESS BOARD v0.8.7 — BROWSER-NATIVE, FIXED, NO FONT DEPENDENCY
board_component_key = f"stadia_board_v087_{seat.game_id}_{seat.role}"
last_move_nonce_key = f"stadia_board_nonce_{seat.game_id}_{seat.role}"


def handle_completed_board_move() -> None:
    """
    The browser board sends a value ONLY after the player has selected both
    source and destination. The first click stays entirely inside JavaScript,
    so it cannot rerun, scroll, resize, or make the WordPress iframe jump.
    """
    payload = st.session_state.get(
        board_component_key
    )

    if not isinstance(payload, dict):
        return

    nonce = payload.get("nonce")
    uci = str(payload.get("move") or "").lower().strip()

    if (
        not nonce
        or not uci
        or nonce == st.session_state.get(last_move_nonce_key)
    ):
        return

    st.session_state[last_move_nonce_key] = nonce

    current = db.get_game(seat.game_id)
    if not current:
        return

    board = chess.Board(current["fen"])
    turn_role = "white" if board.turn == chess.WHITE else "black"

    if (
        current["status"] != "active"
        or seat.role != turn_role
    ):
        return

    try:
        # db.make_move remains the authoritative server-side validator.
        db.make_move(
            seat.game_id,
            uci,
        )
    except ValueError as exc:
        st.session_state["chess_move_error"] = str(exc)


@st.fragment(run_every="2s")
def live_board_fragment() -> None:
    """
    One stable fragment owns status, board and move list.

    Polling happens by rerunning this fragment only. The custom component keeps
    the same iframe/key and updates its DOM in place, so the outer page remains
    anchored while waiting for the other player.
    """
    current = db.get_game(seat.game_id)

    if not current:
        st.error(tr(lang, "game_missing"))
        return

    board = chess.Board(current["fen"])
    turn_role = "white" if board.turn == chess.WHITE else "black"

    can_move = (
        current["status"] == "active"
        and seat.role == turn_role
    )

    move_error = st.session_state.pop(
        "chess_move_error",
        None,
    )
    if move_error:
        st.error(move_error)

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

    if current["status"] == "finished":
        turn_sub = polish(lang, "game_over")
    elif can_move:
        turn_sub = polish(lang, "your_turn")
    else:
        turn_sub = polish(lang, "opponent_turn")

    render_html(f"""
    <div class="sv-turn-card">
        <div>
            <div class="sv-turn-main">{escape(turn_text)}</div>
            <div class="sv-turn-sub">{escape(turn_sub)}</div>
        </div>
        <span class="sv-status">{escape(str(current["status"]).upper())}</span>
    </div>
    """)

    left, right = st.columns(
        [3, 1.15],
        gap="large",
    )

    with left:
        legal_moves = (
            [move.uci() for move in board.legal_moves]
            if can_move
            else []
        )

        stadia_chess_board(
            fen=current["fen"],
            orientation=seat.role,
            interactive=can_move,
            legal_moves=legal_moves,
            size=BOARD_DISPLAY_PX,
            key=board_component_key,
            on_change=handle_completed_board_move,
        )

    with right:
        moves = db.get_moves(seat.game_id)

        st.markdown(
            f"**{polish(lang, 'moves_played')} ({len(moves)})**"
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
            result_text = polished_result_text(current)
            render_html(f"""
            <div class="sv-result-card">
                <div class="sv-result-title">{escape(polish(lang, 'game_over'))}</div>
                <div class="sv-result-text">{escape(result_text)}</div>
            </div>
            """)

            st.link_button(
                polish(lang, "play_again"),
                STADIA_PUBLIC_URL + "/",
                type="primary",
                use_container_width=True,
            )
            st.link_button(
                polish(lang, "back_stadia"),
                "https://stadiaorg.com/",
                use_container_width=True,
            )

        elif can_move:
            st.info(polish(lang, "your_turn"))
        else:
            st.info(polish(lang, "opponent_turn"))


live_board_fragment()

st.divider()
st.caption(polish(lang, "footer"))
