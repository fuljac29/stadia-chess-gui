from __future__ import annotations

import os
import json
import base64
import hashlib
import hmac
import secrets
import time
import re
import urllib.error
import urllib.request
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
    page_icon="â™Ÿ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()

STADIA_PUBLIC_URL = "https://stadiaorg.com/stadia-premium-arena/".rstrip("/")
SV_ACCESS_URL = "https://stadiaorg.com/wp-json/stadia-chess/v1/access"
SV_FINISH_URL = "https://stadiaorg.com/wp-json/stadia-chess/v1/finish"

# Browser-native chess board.
# It uses its own fixed-size iframe and handles piece selection locally,
# so clicking a piece does NOT rerun or move the Streamlit page.
BOARD_DISPLAY_PX = 460
CHESS_BOARD_FRONTEND = Path(__file__).parent / "chess_board_frontend"
stadia_chess_board = components.declare_component(
    "stadia_chess_board_v087",
    path=str(CHESS_BOARD_FRONTEND),
)
COUNTER_BOARD_FRONTEND = Path(__file__).parent / "counter_board_frontend"
stadia_counter_board = components.declare_component(
    "stadia_counter_board_v100",
    path=str(COUNTER_BOARD_FRONTEND),
)


def secret(name: str, default: str) -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)


APP_SECRET = secret("APP_SECRET", "DEV-ONLY-CHANGE-ME")
SV_CHESS_CHECKOUT_SECRET = secret("SV_CHESS_CHECKOUT_SECRET", "")

TIME_LABELS = {
    "rapid_15_10": "Rapid â€” 15 + 10",
    "blitz_5_3": "Blitz â€” 5 + 3",
    "relaxed": "Relaxed â€” no clock",
}

VARIANT_TEXT = {
    "EN": ("Game", "Traditional chess", "New 10Ã—8 Counterintelligence Chess"),
    "IT": ("Gioco", "Scacchi tradizionali", "Nuovi Scacchi 10Ã—8 Controspionaggio"),
    "DE": ("Spiel", "Traditionelles Schach", "Neues 10Ã—8-Gegenspionage-Schach"),
    "FR": ("Jeu", "Ã‰checs traditionnels", "Nouveaux Ã©checs 10Ã—8 de contre-espionnage"),
    "ES": ("Juego", "Ajedrez tradicional", "Nuevo ajedrez 10Ã—8 de contraespionaje"),
}


def variant_label(lang: str, value: str) -> str:
    labels = VARIANT_TEXT.get(lang, VARIANT_TEXT["EN"])
    return labels[2] if value == db.VARIANT_COUNTER else labels[1]


COUNTER_RULES = {
    "EN": "T Â· Transparent Bishop: moves diagonally up to 3 squares and may pass over one piece, leaving it on the board. I Â· Interceptor: moves one square in any direction; when adjacent to an enemy T, it neutralizes its ability to pass over pieces. Patent protection: the official patent application has been filed and is pending (Patent Pending).",
    "IT": "T Â· Alfiere Trasparente: si muove in diagonale fino a 3 caselle e puÃ² oltrepassare un solo pezzo, lasciandolo sulla scacchiera. I Â· Intercettore: si muove di una casella in ogni direzione; quando Ã¨ adiacente a un T nemico ne neutralizza la capacitÃ  di attraversare i pezzi. Protezione brevettuale: la domanda ufficiale di brevetto Ã¨ stata depositata ed Ã¨ attualmente pendente (Patent Pending).",
    "DE": "T Â· Transparenter LÃ¤ufer: zieht diagonal bis zu 3 Felder und darf eine Figur Ã¼berspringen, die auf dem Brett bleibt. I Â· Abfangfigur: zieht ein Feld in jede Richtung; steht sie neben einem gegnerischen T, neutralisiert sie dessen FÃ¤higkeit, Figuren zu Ã¼berspringen. Patentschutz: Die offizielle Patentanmeldung wurde eingereicht und ist anhÃ¤ngig (Patent Pending).",
    "FR": "T Â· Fou transparent : se dÃ©place en diagonale jusquâ€™Ã  3 cases et peut franchir une piÃ¨ce, qui reste sur lâ€™Ã©chiquier. I Â· Intercepteur : se dÃ©place dâ€™une case dans toutes les directions ; adjacent Ã  un T adverse, il neutralise sa capacitÃ© Ã  franchir les piÃ¨ces. Protection par brevet : la demande officielle a Ã©tÃ© dÃ©posÃ©e et est en instance (Patent Pending).",
    "ES": "T Â· Alfil transparente: se mueve en diagonal hasta 3 casillas y puede atravesar una pieza, que permanece en el tablero. I Â· Interceptor: se mueve una casilla en cualquier direcciÃ³n; junto a una T enemiga neutraliza su capacidad de atravesar piezas. ProtecciÃ³n de patente: la solicitud oficial ha sido presentada y estÃ¡ pendiente (Patent Pending).",
}

DIRECT_INVITE_LABELS = {
    "EN": ("COPY DIRECT INVITATION LINK", "Invitation link copied"),
    "IT": ("COPIA LINK DIRETTO Dâ€™INVITO", "Link dâ€™invito copiato"),
    "DE": ("DIREKTEN EINLADUNGSLINK KOPIEREN", "Einladungslink kopiert"),
    "FR": ("COPIER LE LIEN DIRECT Dâ€™INVITATION", "Lien dâ€™invitation copiÃ©"),
    "ES": ("COPIAR ENLACE DIRECTO DE INVITACIÃ“N", "Enlace de invitaciÃ³n copiado"),
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
        "your_code": "Invitation code", "tell_friend": "{friend} opens Stadia â†’ Premium Arena and enters this code.",
        "waiting_friend": "Waiting for {friend} to accept the invitation.", "send_invitation": "Send invitation",
        "send_whatsapp": "ðŸ“± WhatsApp", "send_email": "âœ‰ï¸ Email",
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
        "invited": "{white} ha invitato {black} a una partita privata di scacchi.", "accept_question": "Questo invito Ã¨ per te?",
        "accept_button": "ACCETTA E GIOCA", "open_button": "APRI LA PARTITA", "cancel_button": "Non Ã¨ questo invito",
        "your_code": "Codice invito", "tell_friend": "{friend} apre Stadia â†’ Arena Premium e inserisce questo codice.",
        "waiting_friend": "In attesa che {friend} accetti l'invito.", "send_invitation": "Invia l'invito",
        "send_whatsapp": "ðŸ“± WhatsApp", "send_email": "âœ‰ï¸ E-mail",
        "share_message": "{white} ti invita a giocare a scacchi privati su Stadia.\n\nApri:\n{url}\n\nCodice invito: {code}",
        "email_subject": "Invito a Stadia Private Chess", "private_return": "Link privato per tornare",
        "private_return_help": "Conservalo solo per te se vuoi tornare piÃ¹ tardi.",
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
        "invited": "{white} hat {black} zu einer privaten Schachpartie eingeladen.", "accept_question": "Ist diese Einladung fÃ¼r dich?",
        "accept_button": "ANNEHMEN & SPIELEN", "open_button": "PARTIE Ã–FFNEN", "cancel_button": "Nicht diese Einladung",
        "your_code": "Einladungscode", "tell_friend": "{friend} Ã¶ffnet Stadia â†’ Premium Arena und gibt diesen Code ein.",
        "waiting_friend": "Warte darauf, dass {friend} die Einladung annimmt.", "send_invitation": "Einladung senden",
        "send_whatsapp": "ðŸ“± WhatsApp", "send_email": "âœ‰ï¸ E-Mail",
        "share_message": "{white} lÃ¤dt dich zu einer privaten Schachpartie auf Stadia ein.\n\nÃ–ffne:\n{url}\n\nEinladungscode: {code}",
        "email_subject": "Stadia Private Chess Einladung", "private_return": "Privater RÃ¼ckkehr-Link",
        "private_return_help": "Bewahre diesen Link nur fÃ¼r dich auf.",
        "status": "Status", "side": "Deine Farbe", "moves": "ZÃ¼ge",
        "waiting_other": "Warte auf den anderen Spieler.", "click_piece": "Klicke auf eine deiner Figuren.",
        "click_destination": "Klicke jetzt auf das Zielfeld.", "selected_piece": "Figur ausgewÃ¤hlt.",
    },
    "FR": {
        "create_title": "Inviter un ami", "your_name": "Votre nom", "friend_name": "Nom de l'ami",
        "time_control": "Cadence", "create_button": "INVITER Ã€ JOUER",
        "join_title": "Vous avez reÃ§u une invitation ?", "invite_code": "Code d'invitation",
        "code_help": "Entrez le code de 6 caractÃ¨res reÃ§u de votre ami.", "find_button": "TROUVER L'INVITATION",
        "missing_names": "Entrez votre nom et celui de votre ami.", "code_not_found": "Code d'invitation introuvable.",
        "invited": "{white} a invitÃ© {black} Ã  une partie d'Ã©checs privÃ©e.", "accept_question": "Cette invitation est-elle pour vous ?",
        "accept_button": "ACCEPTER ET JOUER", "open_button": "OUVRIR LA PARTIE", "cancel_button": "Ce n'est pas cette invitation",
        "your_code": "Code d'invitation", "tell_friend": "{friend} ouvre Stadia â†’ ArÃ¨ne Premium et entre ce code.",
        "waiting_friend": "En attente de l'acceptation de {friend}.", "send_invitation": "Envoyer l'invitation",
        "send_whatsapp": "ðŸ“± WhatsApp", "send_email": "âœ‰ï¸ E-mail",
        "share_message": "{white} vous invite Ã  jouer aux Ã©checs privÃ©s sur Stadia.\n\nOuvrez :\n{url}\n\nCode d'invitation : {code}",
        "email_subject": "Invitation Stadia Private Chess", "private_return": "Lien privÃ© de retour",
        "private_return_help": "Gardez ce lien uniquement pour vous.",
        "status": "Statut", "side": "Votre couleur", "moves": "Coups",
        "waiting_other": "En attente de l'autre joueur.", "click_piece": "Cliquez sur l'une de vos piÃ¨ces.",
        "click_destination": "Cliquez maintenant sur la case de destination.", "selected_piece": "PiÃ¨ce sÃ©lectionnÃ©e.",
    },
    "ES": {
        "create_title": "Invitar a un amigo", "your_name": "Tu nombre", "friend_name": "Nombre del amigo",
        "time_control": "Ritmo", "create_button": "INVITAR A JUGAR",
        "join_title": "Â¿Has recibido una invitaciÃ³n?", "invite_code": "CÃ³digo de invitaciÃ³n",
        "code_help": "Introduce el cÃ³digo de 6 caracteres que recibiste.", "find_button": "BUSCAR INVITACIÃ“N",
        "missing_names": "Introduce tu nombre y el nombre de tu amigo.", "code_not_found": "CÃ³digo de invitaciÃ³n no encontrado.",
        "invited": "{white} ha invitado a {black} a una partida privada de ajedrez.", "accept_question": "Â¿Esta invitaciÃ³n es para ti?",
        "accept_button": "ACEPTAR Y JUGAR", "open_button": "ABRIR PARTIDA", "cancel_button": "No es esta invitaciÃ³n",
        "your_code": "CÃ³digo de invitaciÃ³n", "tell_friend": "{friend} abre Stadia â†’ Arena Premium e introduce este cÃ³digo.",
        "waiting_friend": "Esperando a que {friend} acepte la invitaciÃ³n.", "send_invitation": "Enviar invitaciÃ³n",
        "send_whatsapp": "ðŸ“± WhatsApp", "send_email": "âœ‰ï¸ Correo",
        "share_message": "{white} te invita a jugar ajedrez privado en Stadia.\n\nAbre:\n{url}\n\nCÃ³digo de invitaciÃ³n: {code}",
        "email_subject": "InvitaciÃ³n Stadia Private Chess", "private_return": "Enlace privado de regreso",
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
        "your_turn": "Your turn â€” choose a piece.",
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
        "copied": 'COPIED âœ“',
        "send_to_friend": 'Send this code to {friend}',
        "guest_steps": 'What {friend} needs to do',
        "guest_step_1": 'Open Stadia â†’ Premium Arena',
        "guest_step_2": 'Enter the 6-character invitation code',
        "guest_step_3": 'Accept the invitation and play',
        "you_will_play": 'YOU WILL PLAY',
        "invite_details": 'Private game invitation',
        "no_account": 'No account is required.',
        "share_message_v089": '{white} invited you to a private chess game on Stadia.\n\nOpen Premium Arena:\n{url}\n\nInvitation code: {code}\n\nNo account is required.',
        "clock": 'CHESS CLOCK',
        "white_clock": 'White',
        "black_clock": 'Black',
        "clock_relaxed": 'Relaxed game â€” no clock',
        "wins_on_time": '{name} wins on time.',
        "premium_title": 'KEEP PLAYING',
        "winner_offer": "Winner's price",
        "standard_offer": 'Premium price',
        "winner_note": 'You won your free game â€” your Premium Arena price is CHF 5.',
        "standard_note": 'Your free game is complete. Continue in Premium Arena for CHF 9.',
        "premium_period": '30 days Â· unlimited private games Â· invited friends play free',
        "checkout_5": 'CONTINUE FOR CHF 5',
        "checkout_9": 'CONTINUE FOR CHF 9',
        "checkout_unavailable": 'Premium checkout is not configured yet.',
        "free_status": 'YOUR FIRST GAME IS FREE',
        "free_status_text": 'Create one private game with a friend. After it finishes, Premium is required to create more games.',
        "premium_active_label": 'PREMIUM ACTIVE',
        "premium_active_text": 'Unlimited private games until {date}. Invited friends continue to play free.',
        "premium_locked": 'YOUR FREE GAME IS COMPLETE',
        "premium_locked_text": 'To create another game, activate Premium Arena.',
        "access_unavailable": 'Premium access service is temporarily unavailable. Invitations still work, but creating a new game is paused.',
        "identity_missing": 'Player identity is missing. Open Premium Arena from stadiaorg.com.',
        "same_player": 'This invitation is using the same browser identity as the creator. For a two-player test, open the invitation in another browser or a separate private/normal browser session.',
        "existing_free_game": 'You already have a free game in progress.',
        "open_existing": 'OPEN MY CURRENT GAME',
        "premium_play_again": 'PLAY ANOTHER GAME',
        "footer": 'Stadia Private Chess Â· v0.9.2.1 Pre-game Typography Only',
    },
    "IT": {
        "arena_badge": "ARENA SCACCHI PRIVATA",
        "public_intro": "Avvia una partita privata in pochi secondi. Il tuo invitato non deve creare un account.",
        "create_hint": "Crea la partita e comunica al tuo amico il codice di 6 caratteri.",
        "join_hint": "Hai giÃ  un codice? Inseriscilo qui sotto ed entra nella partita.",
        "invitation_ready": "INVITO PRONTO",
        "code_hint": "Invia solo questo codice. Il tuo amico apre Premium Arena e lo inserisce.",
        "save_game_link": "Salva il link della partita",
        "save_game_help": "Conserva questo link privato se vuoi tornare esattamente a questa partita.",
        "you_play": "TU GIOCHI",
        "your_turn": "Tocca a te â€” scegli un pezzo.",
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
        "waiting_text": "Appena {friend} accetta, la scacchiera si aprirÃ  automaticamente.",
        "copy_code": 'COPIA CODICE INVITO',
        "copied": 'COPIATO âœ“',
        "send_to_friend": 'Invia questo codice a {friend}',
        "guest_steps": 'Cosa deve fare {friend}',
        "guest_step_1": 'Aprire Stadia â†’ Premium Arena',
        "guest_step_2": 'Inserire il codice invito di 6 caratteri',
        "guest_step_3": "Accettare l'invito e giocare",
        "you_will_play": 'GIOCHERAI',
        "invite_details": 'Invito a partita privata',
        "no_account": 'Non Ã¨ necessario creare un account.',
        "share_message_v089": '{white} ti invita a una partita privata di scacchi su Stadia.\n\nApri Premium Arena:\n{url}\n\nCodice invito: {code}\n\nNon Ã¨ necessario creare un account.',
        "clock": 'CRONOMETRO',
        "white_clock": 'Bianco',
        "black_clock": 'Nero',
        "clock_relaxed": 'Partita Relaxed â€” senza cronometro',
        "wins_on_time": '{name} vince per tempo.',
        "premium_title": 'CONTINUA A GIOCARE',
        "winner_offer": 'Prezzo vincitore',
        "standard_offer": 'Prezzo Premium',
        "winner_note": 'Hai vinto la partita gratuita â€” il tuo prezzo Premium Arena Ã¨ CHF 5.',
        "standard_note": 'La tua partita gratuita Ã¨ terminata. Continua in Premium Arena per CHF 9.',
        "premium_period": '30 giorni Â· partite private illimitate Â· gli amici invitati giocano gratis',
        "checkout_5": 'CONTINUA PER CHF 5',
        "checkout_9": 'CONTINUA PER CHF 9',
        "checkout_unavailable": 'Il checkout Premium non Ã¨ ancora configurato.',
        "free_status": 'LA TUA PRIMA PARTITA Ãˆ GRATIS',
        "free_status_text": 'Crea una partita privata con un amico. Quando termina, per creare altre partite serve Premium.',
        "premium_active_label": 'PREMIUM ATTIVO',
        "premium_active_text": 'Partite private illimitate fino al {date}. Gli amici invitati continuano a giocare gratis.',
        "premium_locked": 'LA PARTITA GRATUITA Ãˆ TERMINATA',
        "premium_locked_text": "Per creare un'altra partita, attiva Premium Arena.",
        "access_unavailable": 'Il servizio Premium Ã¨ temporaneamente non disponibile. Gli inviti funzionano ancora, ma la creazione di nuove partite Ã¨ sospesa.',
        "identity_missing": 'IdentitÃ  giocatore mancante. Apri Premium Arena da stadiaorg.com.',
        "same_player": "Questo invito usa la stessa identitÃ  browser del creatore. Per il test a due giocatori, apri l'invito in un altro browser oppure in una sessione normale/privata separata.",
        "existing_free_game": 'Hai giÃ  una partita gratuita in corso.',
        "open_existing": 'APRI LA PARTITA IN CORSO',
        "premium_play_again": "GIOCA UN'ALTRA PARTITA",
        "footer": 'Stadia Private Chess Â· v0.9.2.1 Pre-game Typography Only',
    },
    "DE": {
        "arena_badge": "PRIVATE SCHACH-ARENA",
        "public_intro": "Starte in wenigen Sekunden eine private Partie. Dein Gast braucht kein Konto.",
        "create_hint": "Erstelle eine Partie und sende deinem Freund den 6-stelligen Code.",
        "join_hint": "Du hast bereits einen Code? Gib ihn unten ein und tritt der Partie bei.",
        "invitation_ready": "EINLADUNG BEREIT",
        "code_hint": "Sende nur diesen Code. Dein Freund Ã¶ffnet die Premium Arena und gibt ihn ein.",
        "save_game_link": "Meinen Partie-Link speichern",
        "save_game_help": "Bewahre diesen privaten Link auf, um spÃ¤ter genau zu dieser Partie zurÃ¼ckzukehren.",
        "you_play": "DU SPIELST",
        "your_turn": "Du bist am Zug â€” wÃ¤hle eine Figur.",
        "opponent_turn": "Warte auf den Zug deines Gegners.",
        "game_over": "PARTIE BEENDET",
        "white_wins": "{name} gewinnt mit WeiÃŸ.",
        "black_wins": "{name} gewinnt mit Schwarz.",
        "draw": "Remis.",
        "play_again": "NOCH EINE PARTIE",
        "back_stadia": "ZURÃœCK ZU STADIA",
        "moves_played": "Gespielte ZÃ¼ge",
        "game_reference": "Partie-Referenz",
        "share_title": "Einladung teilen",
        "waiting_title": "Einladung gesendet",
        "waiting_text": "Sobald {friend} annimmt, Ã¶ffnet sich das Brett automatisch.",
        "copy_code": 'EINLADUNGSCODE KOPIEREN',
        "copied": 'KOPIERT âœ“',
        "send_to_friend": 'Sende diesen Code an {friend}',
        "guest_steps": 'Was {friend} tun muss',
        "guest_step_1": 'Stadia â†’ Premium Arena Ã¶ffnen',
        "guest_step_2": 'Den 6-stelligen Einladungscode eingeben',
        "guest_step_3": 'Einladung annehmen und spielen',
        "you_will_play": 'DU SPIELST',
        "invite_details": 'Private Partie-Einladung',
        "no_account": 'Es ist kein Konto erforderlich.',
        "share_message_v089": '{white} lÃ¤dt dich zu einer privaten Schachpartie auf Stadia ein.\n\nPremium Arena Ã¶ffnen:\n{url}\n\nEinladungscode: {code}\n\nEs ist kein Konto erforderlich.',
        "clock": 'SCHACHUHR',
        "white_clock": 'WeiÃŸ',
        "black_clock": 'Schwarz',
        "clock_relaxed": 'Relaxed-Partie â€” ohne Uhr',
        "wins_on_time": '{name} gewinnt auf Zeit.',
        "premium_title": 'WEITERSPIELEN',
        "winner_offer": 'Siegerpreis',
        "standard_offer": 'Premium-Preis',
        "winner_note": 'Du hast dein Gratis-Spiel gewonnen â€” dein Premium-Arena-Preis betrÃ¤gt CHF 5.',
        "standard_note": 'Dein Gratis-Spiel ist beendet. Spiele in der Premium Arena fÃ¼r CHF 9 weiter.',
        "premium_period": '30 Tage Â· unbegrenzte private Partien Â· eingeladene Freunde spielen gratis',
        "checkout_5": 'WEITERSPIELEN FÃœR CHF 5',
        "checkout_9": 'WEITERSPIELEN FÃœR CHF 9',
        "checkout_unavailable": 'Premium-Checkout ist noch nicht konfiguriert.',
        "free_status": 'DEINE ERSTE PARTIE IST KOSTENLOS',
        "free_status_text": 'Erstelle eine private Partie mit einem Freund. Danach ist Premium nÃ¶tig, um weitere Partien zu erstellen.',
        "premium_active_label": 'PREMIUM AKTIV',
        "premium_active_text": 'Unbegrenzte private Partien bis {date}. Eingeladene Freunde spielen weiterhin kostenlos.',
        "premium_locked": 'DEINE KOSTENLOSE PARTIE IST BEENDET',
        "premium_locked_text": 'Aktiviere Premium Arena, um eine weitere Partie zu erstellen.',
        "access_unavailable": 'Der Premium-Zugriff ist vorÃ¼bergehend nicht verfÃ¼gbar. Einladungen funktionieren weiter, neue Partien sind kurz pausiert.',
        "identity_missing": 'SpieleridentitÃ¤t fehlt. Ã–ffne Premium Arena Ã¼ber stadiaorg.com.',
        "same_player": 'Diese Einladung verwendet dieselbe Browser-IdentitÃ¤t wie der Ersteller. Ã–ffne sie fÃ¼r einen Zwei-Spieler-Test in einem anderen Browser oder einer getrennten privaten/normalen Sitzung.',
        "existing_free_game": 'Du hast bereits eine kostenlose Partie laufen.',
        "open_existing": 'MEINE AKTUELLE PARTIE Ã–FFNEN',
        "premium_play_again": 'NOCH EINE PARTIE',
        "footer": 'Stadia Private Chess Â· v0.9.2.1 Pre-game Typography Only',
    },
    "FR": {
        "arena_badge": "ARÃˆNE D'Ã‰CHECS PRIVÃ‰E",
        "public_intro": "Lancez une partie privÃ©e en quelques secondes. Votre invitÃ© n'a pas besoin de compte.",
        "create_hint": "CrÃ©ez une partie et envoyez le code Ã  6 caractÃ¨res Ã  votre ami.",
        "join_hint": "Vous avez dÃ©jÃ  un code ? Saisissez-le ci-dessous pour rejoindre la partie.",
        "invitation_ready": "INVITATION PRÃŠTE",
        "code_hint": "Envoyez uniquement ce code. Votre ami ouvre Premium Arena et le saisit.",
        "save_game_link": "Enregistrer mon lien de partie",
        "save_game_help": "Conservez ce lien privÃ© pour revenir plus tard exactement Ã  cette partie.",
        "you_play": "VOUS JOUEZ",
        "your_turn": "Ã€ vous de jouer â€” choisissez une piÃ¨ce.",
        "opponent_turn": "En attente du coup de votre adversaire.",
        "game_over": "PARTIE TERMINÃ‰E",
        "white_wins": "{name} gagne avec les Blancs.",
        "black_wins": "{name} gagne avec les Noirs.",
        "draw": "Nulle.",
        "play_again": "JOUER UNE AUTRE PARTIE",
        "back_stadia": "RETOUR Ã€ STADIA",
        "moves_played": "Coups jouÃ©s",
        "game_reference": "RÃ©fÃ©rence de partie",
        "share_title": "Partager l'invitation",
        "waiting_title": "Invitation envoyÃ©e",
        "waiting_text": "DÃ¨s que {friend} accepte, l'Ã©chiquier s'ouvrira automatiquement.",
        "copy_code": "COPIER LE CODE D'INVITATION",
        "copied": 'COPIÃ‰ âœ“',
        "send_to_friend": 'Envoyez ce code Ã  {friend}',
        "guest_steps": 'Ce que {friend} doit faire',
        "guest_step_1": 'Ouvrir Stadia â†’ Premium Arena',
        "guest_step_2": "Saisir le code d'invitation Ã  6 caractÃ¨res",
        "guest_step_3": "Accepter l'invitation et jouer",
        "you_will_play": 'VOUS JOUEREZ',
        "invite_details": 'Invitation Ã  une partie privÃ©e',
        "no_account": "Aucun compte n'est nÃ©cessaire.",
        "share_message_v089": "{white} vous invite Ã  une partie d'Ã©checs privÃ©e sur Stadia.\n\nOuvrez Premium Arena :\n{url}\n\nCode d'invitation : {code}\n\nAucun compte n'est nÃ©cessaire.",
        "clock": 'PENDULE',
        "white_clock": 'Blancs',
        "black_clock": 'Noirs',
        "clock_relaxed": 'Partie Relaxed â€” sans pendule',
        "wins_on_time": '{name} gagne au temps.',
        "premium_title": 'CONTINUER Ã€ JOUER',
        "winner_offer": 'Prix du gagnant',
        "standard_offer": 'Prix Premium',
        "winner_note": 'Vous avez gagnÃ© votre partie gratuite â€” votre prix Premium Arena est de CHF 5.',
        "standard_note": 'Votre partie gratuite est terminÃ©e. Continuez dans Premium Arena pour CHF 9.',
        "premium_period": '30 jours Â· parties privÃ©es illimitÃ©es Â· les amis invitÃ©s jouent gratuitement',
        "checkout_5": 'CONTINUER POUR CHF 5',
        "checkout_9": 'CONTINUER POUR CHF 9',
        "checkout_unavailable": "Le paiement Premium n'est pas encore configurÃ©.",
        "free_status": 'VOTRE PREMIÃˆRE PARTIE EST GRATUITE',
        "free_status_text": "CrÃ©ez une partie privÃ©e avec un ami. Une fois terminÃ©e, Premium est nÃ©cessaire pour crÃ©er d'autres parties.",
        "premium_active_label": 'PREMIUM ACTIF',
        "premium_active_text": "Parties privÃ©es illimitÃ©es jusqu'au {date}. Les amis invitÃ©s continuent Ã  jouer gratuitement.",
        "premium_locked": 'VOTRE PARTIE GRATUITE EST TERMINÃ‰E',
        "premium_locked_text": 'Activez Premium Arena pour crÃ©er une autre partie.',
        "access_unavailable": 'Le service Premium est temporairement indisponible. Les invitations fonctionnent encore, mais la crÃ©ation de nouvelles parties est suspendue.',
        "identity_missing": 'IdentitÃ© du joueur manquante. Ouvrez Premium Arena depuis stadiaorg.com.',
        "same_player": 'Cette invitation utilise la mÃªme identitÃ© de navigateur que le crÃ©ateur. Pour un test Ã  deux joueurs, ouvrez-la dans un autre navigateur ou une session privÃ©e/normale sÃ©parÃ©e.',
        "existing_free_game": 'Vous avez dÃ©jÃ  une partie gratuite en cours.',
        "open_existing": 'OUVRIR MA PARTIE EN COURS',
        "premium_play_again": 'JOUER UNE AUTRE PARTIE',
        "footer": 'Stadia Private Chess Â· v0.9.2.1 Pre-game Typography Only',
    },
    "ES": {
        "arena_badge": "ARENA DE AJEDREZ PRIVADA",
        "public_intro": "Inicia una partida privada en segundos. Tu invitado no necesita crear una cuenta.",
        "create_hint": "Crea una partida y envÃ­a a tu amigo el cÃ³digo de 6 caracteres.",
        "join_hint": "Â¿Ya tienes un cÃ³digo? IntrodÃºcelo abajo para entrar en la partida.",
        "invitation_ready": "INVITACIÃ“N LISTA",
        "code_hint": "EnvÃ­a solo este cÃ³digo. Tu amigo abre Premium Arena y lo introduce.",
        "save_game_link": "Guardar el enlace de mi partida",
        "save_game_help": "Guarda este enlace privado para volver mÃ¡s tarde exactamente a esta partida.",
        "you_play": "TÃš JUEGAS",
        "your_turn": "Tu turno â€” elige una pieza.",
        "opponent_turn": "Esperando la jugada de tu oponente.",
        "game_over": "PARTIDA TERMINADA",
        "white_wins": "{name} gana con Blancas.",
        "black_wins": "{name} gana con Negras.",
        "draw": "Tablas.",
        "play_again": "JUGAR OTRA PARTIDA",
        "back_stadia": "VOLVER A STADIA",
        "moves_played": "Jugadas realizadas",
        "game_reference": "Referencia de partida",
        "share_title": "Compartir invitaciÃ³n",
        "waiting_title": "InvitaciÃ³n enviada",
        "waiting_text": "En cuanto {friend} acepte, el tablero se abrirÃ¡ automÃ¡ticamente.",
        "copy_code": 'COPIAR CÃ“DIGO DE INVITACIÃ“N',
        "copied": 'COPIADO âœ“',
        "send_to_friend": 'EnvÃ­a este cÃ³digo a {friend}',
        "guest_steps": 'Lo que debe hacer {friend}',
        "guest_step_1": 'Abrir Stadia â†’ Premium Arena',
        "guest_step_2": 'Introducir el cÃ³digo de invitaciÃ³n de 6 caracteres',
        "guest_step_3": 'Aceptar la invitaciÃ³n y jugar',
        "you_will_play": 'JUGARÃS',
        "invite_details": 'InvitaciÃ³n a partida privada',
        "no_account": 'No es necesario crear una cuenta.',
        "share_message_v089": '{white} te invita a una partida privada de ajedrez en Stadia.\n\nAbre Premium Arena:\n{url}\n\nCÃ³digo de invitaciÃ³n: {code}\n\nNo es necesario crear una cuenta.',
        "clock": 'RELOJ',
        "white_clock": 'Blancas',
        "black_clock": 'Negras',
        "clock_relaxed": 'Partida Relaxed â€” sin reloj',
        "wins_on_time": '{name} gana por tiempo.',
        "premium_title": 'SEGUIR JUGANDO',
        "winner_offer": 'Precio del ganador',
        "standard_offer": 'Precio Premium',
        "winner_note": 'Ganaste tu partida gratuita â€” tu precio Premium Arena es CHF 5.',
        "standard_note": 'Tu partida gratuita ha terminado. ContinÃºa en Premium Arena por CHF 9.',
        "premium_period": '30 dÃ­as Â· partidas privadas ilimitadas Â· los amigos invitados juegan gratis',
        "checkout_5": 'CONTINUAR POR CHF 5',
        "checkout_9": 'CONTINUAR POR CHF 9',
        "checkout_unavailable": 'El checkout Premium aÃºn no estÃ¡ configurado.',
        "free_status": 'TU PRIMERA PARTIDA ES GRATIS',
        "free_status_text": 'Crea una partida privada con un amigo. Al terminar, necesitarÃ¡s Premium para crear mÃ¡s partidas.',
        "premium_active_label": 'PREMIUM ACTIVO',
        "premium_active_text": 'Partidas privadas ilimitadas hasta {date}. Los amigos invitados siguen jugando gratis.',
        "premium_locked": 'TU PARTIDA GRATUITA HA TERMINADO',
        "premium_locked_text": 'Activa Premium Arena para crear otra partida.',
        "access_unavailable": 'El servicio Premium no estÃ¡ disponible temporalmente. Las invitaciones siguen funcionando, pero crear nuevas partidas estÃ¡ pausado.',
        "identity_missing": 'Falta la identidad del jugador. Abre Premium Arena desde stadiaorg.com.',
        "same_player": 'Esta invitaciÃ³n usa la misma identidad de navegador que el creador. Para una prueba con dos jugadores, Ã¡brela en otro navegador o en una sesiÃ³n privada/normal separada.',
        "existing_free_game": 'Ya tienes una partida gratuita en curso.',
        "open_existing": 'ABRIR MI PARTIDA ACTUAL',
        "premium_play_again": 'JUGAR OTRA PARTIDA',
        "footer": 'Stadia Private Chess Â· v0.9.2.1 Pre-game Typography Only',
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
    line-height:1.65;
    font-size:17px;
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
.sv-code-note{color:var(--sv-muted);font-size:16px;line-height:1.6;margin-top:8px}
.sv-invite-title{
    font-size:24px;
    font-weight:900;
    color:var(--sv-ink);
    margin:5px 0 4px;
    line-height:1.35;
}
.sv-invite-sub{
    color:var(--sv-muted);
    font-size:16px;
    line-height:1.65;
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
    margin-bottom:10px;
    font-size:17px;
}
.sv-invite-step{
    display:flex;
    gap:12px;
    align-items:flex-start;
    color:var(--sv-muted);
    font-size:16px;
    line-height:1.6;
    margin:9px 0;
}
.sv-step-num{
    flex:0 0 28px;
    width:28px;
    height:28px;
    border-radius:999px;
    background:#eeeaff;
    color:#5038c8;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    font-weight:900;
    font-size:14px;
}
.sv-invite-meta{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    margin-top:12px;
}
.sv-meta-pill{
    display:inline-block;
    padding:8px 12px;
    border-radius:999px;
    background:#f5f4fb;
    color:#475467;
    font-size:14px;
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
.sv-match-names{font-size:30px;font-weight:900;color:var(--sv-ink);line-height:1.15}
.sv-match-meta{font-size:14px;color:var(--sv-muted);margin-top:6px}
.sv-side-wrap{text-align:right;white-space:nowrap}
.sv-side-label{font-size:12px;font-weight:900;letter-spacing:.12em;color:var(--sv-muted);margin-bottom:8px}
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
.sv-turn-main{font-size:28px;font-weight:900;color:var(--sv-ink);line-height:1.15}
.sv-turn-sub{font-size:15px;color:var(--sv-muted);margin-top:6px}
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

.sv-premium-offer{
    border:1px solid #ddd6fe;
    border-radius:18px;
    padding:16px;
    margin:12px 0;
    background:linear-gradient(135deg,#fff,#f8f5ff);
}
.sv-premium-kicker{
    font-size:11px;
    font-weight:900;
    letter-spacing:.12em;
    color:#5b3ff0;
}
.sv-premium-price{
    font-size:30px;
    line-height:1.05;
    font-weight:950;
    color:var(--sv-ink);
    margin-top:6px;
}
.sv-premium-note{
    font-size:14px;
    color:var(--sv-muted);
    line-height:1.5;
    margin-top:7px;
}
.sv-premium-period{
    font-size:12px;
    color:#667085;
    font-weight:750;
    margin-top:8px;
}


.sv-clock-wrap{
    margin:8px 0 14px;
}
.sv-clock-title{
    font-size:12px;
    font-weight:900;
    letter-spacing:.12em;
    color:var(--sv-muted);
    margin-bottom:7px;
}
.sv-clock-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:12px;
    min-height:88px;
}
.sv-clock-card{
    border:1px solid var(--sv-line);
    border-radius:17px;
    padding:11px 15px;
    background:#fff;
    min-height:88px;
    box-sizing:border-box;
}
.sv-clock-card.active{
    border-color:#7657ff;
    background:linear-gradient(135deg,#fff,#f5f2ff);
    box-shadow:0 8px 22px rgba(118,87,255,.10);
}
.sv-clock-name{
    font-size:14px;
    color:var(--sv-muted);
    font-weight:800;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.sv-clock-time{
    font-variant-numeric:tabular-nums;
    font-size:32px;
    line-height:1.05;
    font-weight:950;
    letter-spacing:-.03em;
    color:var(--sv-ink);
    margin-top:5px;
}
.sv-clock-card.active .sv-clock-time{
    color:#5b3ff0;
}
.sv-clock-relaxed{
    border:1px solid var(--sv-line);
    border-radius:15px;
    background:#f8f7ff;
    padding:12px 14px;
    font-size:14px;
    color:var(--sv-muted);
    font-weight:800;
}
@media(max-width:760px){
    .sv-clock-time{font-size:27px}
}

.sv-access-card{border:1px solid var(--sv-line);border-radius:18px;padding:15px 17px;background:#fff;margin:8px 0 15px}
.sv-access-card.premium{border-color:#cfc5ff;background:linear-gradient(135deg,#fff,#f6f3ff)}
.sv-access-card.locked{border-color:#f1d8a8;background:#fffaf0}
.sv-access-label{font-size:12px;font-weight:900;letter-spacing:.12em;color:#5b3ff0}
.sv-access-text{font-size:16px;line-height:1.65;color:var(--sv-muted);margin-top:5px}
div.stButton>button,
div[data-testid="stFormSubmitButton"]>button{
    min-height:54px;
    border-radius:14px;
    font-weight:850;
    font-size:15px;
}
[data-testid="stLinkButton"] a{
    min-height:52px;
    border-radius:14px;
    font-weight:850;
    font-size:15px;
    display:flex;
    align-items:center;
    justify-content:center;
}
div[data-testid="stForm"]{
    border-color:var(--sv-line);
    border-radius:20px;
    background:#fff;
}

div[data-testid="stAlert"]{
    font-size:15px!important;
    line-height:1.55!important;
}
div[data-testid="stAlert"] p{
    font-size:15px!important;
    line-height:1.55!important;
}
div[data-testid="stExpander"] summary{
    font-size:14px!important;
    font-weight:700!important;
}
.sv-panel-title{
    font-size:20px;
    font-weight:900;
    color:var(--sv-ink);
    margin:2px 0 10px;
}
.sv-move-box{
    border:1px solid var(--sv-line);
    border-radius:14px;
    background:#f7f7fb;
    color:var(--sv-ink);
    padding:14px 15px;
    font-size:16px;
    line-height:1.75;
    font-weight:700;
    word-break:break-word;
}
.sv-footer-note{
    color:var(--sv-muted);
    font-size:13px;
}
code{word-break:break-all;white-space:pre-wrap}

/* PRE-GAME TYPOGRAPHY ONLY */
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label{
    font-size:16px!important;
    font-weight:800!important;
}

div[data-testid="stTextInput"] label p,
div[data-testid="stSelectbox"] label p{
    font-size:16px!important;
    font-weight:800!important;
    line-height:1.45!important;
}

div[data-testid="stTextInput"] input{
    font-size:18px!important;
    min-height:54px!important;
    line-height:1.4!important;
}

div[data-testid="stTextInput"] input::placeholder{
    font-size:16px!important;
}

div[data-testid="stSelectbox"] [data-baseweb="select"] > div{
    font-size:17px!important;
    min-height:54px!important;
}

div[data-testid="stForm"] [data-testid="stMarkdownContainer"] p{
    font-size:16px!important;
    line-height:1.6!important;
}

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

def valid_player_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{20,80}", str(value or "").strip()))


def get_access_state(player_id_value: str) -> dict | None:
    if not valid_player_id(player_id_value):
        return None
    url = SV_ACCESS_URL + "?" + urlencode({"player_id": player_id_value})
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def signed_envelope(payload: dict) -> tuple[str, str]:
    payload = dict(payload)
    payload["exp"] = int(time.time()) + 15 * 60
    payload["jti"] = secrets.token_urlsafe(18)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    signature = hmac.new(SV_CHESS_CHECKOUT_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return payload_b64, signature


def sync_finished_game(current: dict) -> bool:
    if not SV_CHESS_CHECKOUT_SECRET or current.get("status") != "finished":
        return False
    white_player_id = str(current.get("white_player_id") or "").strip()
    black_player_id = str(current.get("black_player_id") or "").strip()
    if not valid_player_id(white_player_id) or not valid_player_id(black_player_id):
        return False
    sync_key = "sv_finish_synced_" + str(current.get("id") or "")
    if st.session_state.get(sync_key):
        return True
    p, sig = signed_envelope({"game_id": str(current["id"]), "result": str(current["result"]), "white_player_id": white_player_id, "black_player_id": black_player_id})
    body = json.dumps({"p": p, "sig": sig}).encode("utf-8")
    req = urllib.request.Request(SV_FINISH_URL, data=body, headers={"Content-Type":"application/json","User-Agent":"StadiaChess/0.9.2"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        return False
    ok = bool(isinstance(data, dict) and data.get("ok"))
    if ok:
        st.session_state[sync_key] = True
    return ok


def access_date_text(state: dict) -> str:
    raw = str(state.get("premium_until") or "")
    if not raw:
        return ""
    try:
        y,m,d = raw.split("T",1)[0].split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return raw


def signed_checkout_url(
    game_id: str,
    role: str,
    offer: str,
    player_id_value: str,
) -> str:
    """
    Create a 15-minute, one-time signed checkout offer for WordPress.
    The secret itself never appears in the URL.
    """
    if (
        not SV_CHESS_CHECKOUT_SECRET
        or not valid_player_id(player_id_value)
        or not re.fullmatch(r"[a-f0-9]{32}", str(game_id or ""))
    ):
        return ""

    payload = {
        "game_id": str(game_id),
        "role": str(role),
        "offer": str(offer),
        "player_id": str(player_id_value),
        "exp": int(time.time()) + 15 * 60,
        "jti": secrets.token_urlsafe(18),
    }

    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    payload_b64 = (
        base64.urlsafe_b64encode(raw)
        .rstrip(b"=")
        .decode("ascii")
    )

    signature = hmac.new(
        SV_CHESS_CHECKOUT_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return (
        f"{STADIA_PUBLIC_URL}/?"
        + urlencode(
            {
                "sv_chess_pay": "1",
                "p": payload_b64,
                "sig": signature,
            }
        )
    )



seat_token = str(st.query_params.get("seat", "")).strip()
seat = verify_seat_token(seat_token, APP_SECRET) if seat_token else None
if seat_token and not seat:
    st.error(tr(lang, "invalid_link"))
    st.stop()

player_id = str(st.query_params.get("player", "")).strip()
if not valid_player_id(player_id):
    player_id = ""

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


# PUBLIC PAGE â€” JOIN FIRST, CREATE SECOND
# The invited player should never re-enter names.
if not seat:
    query_invite = db.normalize_invite_code(
        str(st.query_params.get("invite", ""))
    )
    if query_invite and not st.session_state.get("pending_invite_code"):
        st.session_state["pending_invite_code"] = query_invite

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
                or "â€”"
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
            <span class="sv-meta-pill">{escape(variant_label(lang, found_game.get('variant', db.VARIANT_CLASSIC)))}</span>
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
                if not player_id:
                    st.error(polish(lang, "identity_missing"))
                elif (found_game["status"] in {"waiting", "ready"} and str(found_game.get("white_player_id") or "").strip() == player_id):
                    st.error(polish(lang, "same_player"))
                else:
                    if found_game["status"] in {"waiting", "ready"}:
                        found_game = db.accept_invite(pending_code, black_player_id=player_id)
                    st.session_state.pop("pending_invite_code", None)
                    st.query_params["seat"] = make_seat_token(found_game["id"], "black", APP_SECRET)
                    st.query_params["lang"] = lang
                    st.query_params["player"] = player_id
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

    st.subheader(ui(lang, "create_title"))

    access_state = get_access_state(player_id) if player_id else None

    # If the player closed the page immediately after a finished game,
    # recover that result here and register the free-game usage before
    # deciding whether a new game may be created.
    if (
        player_id
        and access_state
        and access_state.get("free_available")
    ):
        finished_game = db.get_latest_finished_game_by_player_id(
            player_id
        )
        if finished_game and sync_finished_game(finished_game):
            access_state = get_access_state(player_id)

    can_create = False

    if not player_id:
        st.error(polish(lang, "identity_missing"))
    elif access_state is None:
        st.warning(polish(lang, "access_unavailable"))
    elif access_state.get("premium_active"):
        premium_date = access_date_text(access_state)
        render_html(f"""<div class="sv-access-card premium"><div class="sv-access-label">{escape(polish(lang, 'premium_active_label'))}</div><div class="sv-access-text">{escape(polish(lang, 'premium_active_text').format(date=premium_date))}</div></div>""")
        can_create = True
    elif access_state.get("free_available"):
        render_html(f"""<div class="sv-access-card"><div class="sv-access-label">{escape(polish(lang, 'free_status'))}</div><div class="sv-access-text">{escape(polish(lang, 'free_status_text'))}</div></div>""")
        open_game = db.get_open_game_by_white_player_id(player_id)
        if open_game:
            st.info(polish(lang, "existing_free_game"))
            if st.button(polish(lang, "open_existing"), type="primary", use_container_width=True):
                st.query_params["seat"] = make_seat_token(open_game["id"], "white", APP_SECRET)
                st.query_params["lang"] = lang
                st.query_params["player"] = player_id
                st.rerun()
        else:
            can_create = True
    else:
        render_html(f"""<div class="sv-access-card locked"><div class="sv-access-label">{escape(polish(lang, 'premium_locked'))}</div><div class="sv-access-text">{escape(polish(lang, 'premium_locked_text'))}</div></div>""")
        offer = "winner" if (not access_state.get("paid_once") and access_state.get("first_offer") == "winner") else "standard"
        is_winner_offer = offer == "winner"
        offer_price = "CHF 5" if is_winner_offer else "CHF 9"
        render_html(f"""<div class="sv-premium-offer"><div class="sv-premium-kicker">{escape(polish(lang, 'premium_title'))}</div><div class="sv-premium-price">{escape(polish(lang, 'winner_offer') if is_winner_offer else polish(lang, 'standard_offer'))} Â· {escape(offer_price)}</div><div class="sv-premium-note">{escape(polish(lang, 'winner_note') if is_winner_offer else polish(lang, 'standard_note'))}</div><div class="sv-premium-period">{escape(polish(lang, 'premium_period'))}</div></div>""")
        checkout_url = signed_checkout_url(str(access_state.get("free_game_id") or ""), str(access_state.get("first_role") or "white"), offer, player_id)
        if checkout_url:
            st.link_button(polish(lang, "checkout_5") if is_winner_offer else polish(lang, "checkout_9"), checkout_url, type="primary", use_container_width=True)
        else:
            st.error(polish(lang, "checkout_unavailable"))

    if can_create:
        render_html(f'<p class="sv-section-intro">{escape(polish(lang, "create_hint"))}</p>')
        with st.form("create_game", border=True):
            white_name = st.text_input(ui(lang, "your_name"))
            friend_name = st.text_input(ui(lang, "friend_name"))
            time_control = st.selectbox(ui(lang, "time_control"), options=list(TIME_LABELS.keys()), format_func=lambda x: TIME_LABELS[x])
            variant = st.selectbox(
                VARIANT_TEXT.get(lang, VARIANT_TEXT["EN"])[0],
                options=[db.VARIANT_CLASSIC, db.VARIANT_COUNTER],
                format_func=lambda value: variant_label(lang, value),
            )
            submitted = st.form_submit_button(ui(lang, "create_button"), type="primary", use_container_width=True)
        if submitted:
            if not white_name.strip() or not friend_name.strip():
                st.error(ui(lang, "missing_names"))
            else:
                gid = db.create_game(white_name=white_name.strip(), black_name=friend_name.strip(), time_control=time_control, white_player_id=player_id, variant=variant)
                st.query_params["seat"] = make_seat_token(gid, "white", APP_SECRET)
                st.query_params["lang"] = lang
                st.query_params["player"] = player_id
                st.rerun()

    st.caption(polish(lang, "footer"))
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


# WAITING HOST â€” invitation UI is static; only the tiny watcher polls.
if game["status"] == "waiting" and seat.role == "white":
    invite_code = str(game.get("invite_code") or "").upper()
    friend_name = str(game["black_name"])
    white_name = str(game["white_name"])
    direct_invite_url = (
        STADIA_PUBLIC_URL
        + "/?"
        + urlencode({"invite": invite_code, "lang": lang})
    )

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

    direct_labels = DIRECT_INVITE_LABELS.get(lang, DIRECT_INVITE_LABELS["EN"])
    copy_button(direct_invite_url, direct_labels[0], direct_labels[1])

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
        url=direct_invite_url,
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


# STATIC GAME HEADER â€” presentation only
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


def player_offer(
    current: dict,
    role: str,
) -> str:
    """
    Winner gets CHF 5; loser or draw gets CHF 9.
    The authoritative result already comes from chess_db.
    """
    result = str(
        current.get("result")
        or ""
    ).strip()

    if (
        result == "1-0"
        and role == "white"
    ):
        return "winner"

    if (
        result == "0-1"
        and role == "black"
    ):
        return "winner"

    return "standard"


def start_fresh_game() -> None:
    """
    Leave the current signed seat and return to a clean Premium Arena lobby.

    This changes only Streamlit navigation/session state. It does not modify
    the finished game, chess engine, database moves, or board component.
    """
    lang_value = lang

    for key in list(st.session_state.keys()):
        if (
            key == "pending_invite_code"
            or key == "chess_move_error"
            or key.startswith("stadia_board_nonce_")
            or key.startswith("stadia_board_v087_")
        ):
            st.session_state.pop(
                key,
                None,
            )

    st.query_params.clear()
    st.query_params["lang"] = lang_value
    if player_id:
        st.query_params["player"] = player_id
    st.rerun()


def format_clock_ms(
    value: int | None,
) -> str:
    if value is None:
        return "â€”"

    remaining = max(
        0,
        int(value),
    )

    total_seconds = (
        remaining + 999
    ) // 1000

    minutes, seconds = divmod(
        total_seconds,
        60,
    )

    if minutes >= 60:
        hours, minutes = divmod(
            minutes,
            60,
        )
        return (
            f"{hours:d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def polished_result_text(current: dict) -> str:
    result = str(current.get("result") or "").strip()
    finish_reason = str(
        current.get("finish_reason")
        or ""
    ).strip()

    if finish_reason == "timeout":
        if result == "1-0":
            return polish(
                lang,
                "wins_on_time",
            ).format(
                name=current.get(
                    "white_name",
                    "White",
                )
            )

        if result == "0-1":
            return polish(
                lang,
                "wins_on_time",
            ).format(
                name=current.get(
                    "black_name",
                    "Black",
                )
            )

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

    return f"{tr(lang, 'result')}: {result or 'â€”'}"


@st.fragment(run_every="1s")
def chess_clock_fragment() -> None:
    state = db.get_clock_state(
        seat.game_id
    )

    if not state:
        return

    if not state["enabled"]:
        render_html(
            f"""
            <div class="sv-clock-wrap">
            <div class="sv-clock-title">{escape(polish(lang, 'clock'))}</div>
            <div class="sv-clock-relaxed">{escape(polish(lang, 'clock_relaxed'))}</div>
            </div>
            """
        )
        return

    current_game = db.get_game(
        seat.game_id
    )

    if not current_game:
        return

    white_name = str(
        current_game["white_name"]
    )
    black_name = str(
        current_game["black_name"]
    )

    white_time = format_clock_ms(
        state["white_ms"]
    )
    black_time = format_clock_ms(
        state["black_ms"]
    )

    white_class = (
        " active"
        if state["status"] == "active"
        and state["active_color"] == "white"
        else ""
    )

    black_class = (
        " active"
        if state["status"] == "active"
        and state["active_color"] == "black"
        else ""
    )

    mode = TIME_LABELS.get(
        str(
            current_game.get(
                "time_control"
            )
            or ""
        ),
        str(
            current_game.get(
                "time_control"
            )
            or ""
        ),
    )

    render_html(
        f"""
        <div class="sv-clock-wrap">
        <div class="sv-clock-title">{escape(polish(lang, 'clock'))} Â· {escape(mode)}</div>
        <div class="sv-clock-grid">
        <div class="sv-clock-card{white_class}">
        <div class="sv-clock-name">{escape(white_name)} Â· {escape(polish(lang, 'white_clock'))}</div>
        <div class="sv-clock-time">{escape(white_time)}</div>
        </div>
        <div class="sv-clock-card{black_class}">
        <div class="sv-clock-name">{escape(black_name)} Â· {escape(polish(lang, 'black_clock'))}</div>
        <div class="sv-clock-time">{escape(black_time)}</div>
        </div>
        </div>
        </div>
        """
    )


chess_clock_fragment()


# STADIA CHESS BOARD v0.8.7 â€” BROWSER-NATIVE, FIXED, NO FONT DEPENDENCY
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

    board = db.board_from_game(current)
    turn_role = "white" if board.turn else "black"

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

    board = db.board_from_game(current)
    turn_role = "white" if board.turn else "black"

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

    if current.get("variant") == db.VARIANT_COUNTER:
        render_html(
            f'<div class="sv-access-card"><div class="sv-access-label">{escape(variant_label(lang, db.VARIANT_COUNTER))}</div><div class="sv-access-text">{escape(COUNTER_RULES.get(lang, COUNTER_RULES["EN"]))}</div></div>'
        )

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

        board_widget = (
            stadia_counter_board
            if current.get("variant") == db.VARIANT_COUNTER
            else stadia_chess_board
        )
        board_widget(
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

        render_html(
            f'<div class="sv-panel-title">{escape(polish(lang, "moves_played"))} ({len(moves)})</div>'
        )

        if moves:
            render_html(
                f'<div class="sv-move-box">{escape("  ".join(move["san"] for move in moves[-18:]))}</div>'
            )
        else:
            render_html(
                '<div class="sv-move-box">â€”</div>'
            )

        if current["status"] == "finished":
            result_text = polished_result_text(current)
            render_html(f"""
            <div class="sv-result-card">
                <div class="sv-result-title">{escape(polish(lang, 'game_over'))}</div>
                <div class="sv-result-text">{escape(result_text)}</div>
            </div>
            """)

            sync_finished_game(current)
            access_state = get_access_state(player_id) if player_id else None

            if access_state and access_state.get("free_available"):
                st.warning(polish(lang, "access_unavailable"))
                return

            if access_state and access_state.get("premium_active"):
                premium_date = access_date_text(access_state)
                render_html(f"""<div class="sv-access-card premium"><div class="sv-access-label">{escape(polish(lang, 'premium_active_label'))}</div><div class="sv-access-text">{escape(polish(lang, 'premium_active_text').format(date=premium_date))}</div></div>""")
                if st.button(polish(lang, "premium_play_again"), type="primary", use_container_width=True, key=f"premium_new_game_{seat.game_id}_{seat.role}"):
                    start_fresh_game()
                st.link_button(polish(lang, "back_stadia"), "https://stadiaorg.com/", use_container_width=True)
                return

            if access_state is None:
                st.warning(polish(lang, "access_unavailable"))
                return

            offer = "winner" if (not access_state.get("paid_once") and access_state.get("first_offer") == "winner") else "standard"

            is_winner_offer = (
                offer == "winner"
            )

            offer_title = (
                polish(lang, "winner_offer")
                if is_winner_offer
                else polish(lang, "standard_offer")
            )

            offer_price = (
                "CHF 5"
                if is_winner_offer
                else "CHF 9"
            )

            offer_note = (
                polish(lang, "winner_note")
                if is_winner_offer
                else polish(lang, "standard_note")
            )

            render_html(
                f"""
                <div class="sv-premium-offer">
                    <div class="sv-premium-kicker">{escape(polish(lang, 'premium_title'))}</div>
                    <div class="sv-premium-price">{escape(offer_title)} Â· {escape(offer_price)}</div>
                    <div class="sv-premium-note">{escape(offer_note)}</div>
                    <div class="sv-premium-period">{escape(polish(lang, 'premium_period'))}</div>
                </div>
                """
            )

            checkout_url = signed_checkout_url(
                str(access_state.get("free_game_id") or current["id"]),
                str(access_state.get("first_role") or seat.role),
                offer,
                player_id,
            )

            if checkout_url:
                st.link_button(
                    (
                        polish(lang, "checkout_5")
                        if is_winner_offer
                        else polish(lang, "checkout_9")
                    ),
                    checkout_url,
                    type="primary",
                    use_container_width=True,
                )
            else:
                st.error(
                    polish(
                        lang,
                        "checkout_unavailable",
                    )
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
render_html(
    f'<div class="sv-footer-note">{escape(polish(lang, "footer"))}</div>'
)
