from __future__ import annotations

LANGUAGES = {
    "EN": "🇺🇸 English",
    "IT": "🇮🇹 Italiano",
    "DE": "🇩🇪 Deutsch",
    "FR": "🇫🇷 Français",
    "ES": "🇪🇸 Español",
}

TEXT = {
    "EN": {
        "title": "Stadia Private Chess",
        "tagline": "Invite. Play. Return.",
        "subtitle": "Create one private game, invite a friend, and return later to the same position.",
        "invalid_link": "This player link is invalid or incomplete.",
        "game_missing": "This game no longer exists.",
        "white": "White",
        "black": "Black",
        "turn": "Turn",
        "finished": "Game finished",
        "result": "Result",
        "select_move": "Choose your move",
        "make_move": "MAKE MOVE",
    },
    "IT": {
        "title": "Scacchi Privati Stadia",
        "tagline": "Invita. Gioca. Ritorna.",
        "subtitle": "Crea una partita privata, invita un amico e torna più tardi alla stessa posizione.",
        "invalid_link": "Questo link giocatore non è valido o è incompleto.",
        "game_missing": "Questa partita non esiste più.",
        "white": "Bianco",
        "black": "Nero",
        "turn": "Turno",
        "finished": "Partita terminata",
        "result": "Risultato",
        "select_move": "Scegli la tua mossa",
        "make_move": "FAI LA MOSSA",
    },
    "DE": {
        "title": "Stadia Privatschach",
        "tagline": "Einladen. Spielen. Zurückkehren.",
        "subtitle": "Erstelle eine private Partie, lade einen Freund ein und kehre später zur gleichen Stellung zurück.",
        "invalid_link": "Dieser Spieler-Link ist ungültig oder unvollständig.",
        "game_missing": "Diese Partie existiert nicht mehr.",
        "white": "Weiß",
        "black": "Schwarz",
        "turn": "Am Zug",
        "finished": "Partie beendet",
        "result": "Ergebnis",
        "select_move": "Wähle deinen Zug",
        "make_move": "ZUG AUSFÜHREN",
    },
    "FR": {
        "title": "Stadia Échecs Privés",
        "tagline": "Invitez. Jouez. Revenez.",
        "subtitle": "Créez une partie privée, invitez un ami et revenez plus tard à la même position.",
        "invalid_link": "Ce lien joueur est invalide ou incomplet.",
        "game_missing": "Cette partie n’existe plus.",
        "white": "Blancs",
        "black": "Noirs",
        "turn": "Trait",
        "finished": "Partie terminée",
        "result": "Résultat",
        "select_move": "Choisissez votre coup",
        "make_move": "JOUER LE COUP",
    },
    "ES": {
        "title": "Ajedrez Privado Stadia",
        "tagline": "Invita. Juega. Regresa.",
        "subtitle": "Crea una partida privada, invita a un amigo y vuelve más tarde a la misma posición.",
        "invalid_link": "Este enlace de jugador no es válido o está incompleto.",
        "game_missing": "Esta partida ya no existe.",
        "white": "Blancas",
        "black": "Negras",
        "turn": "Turno",
        "finished": "Partida terminada",
        "result": "Resultado",
        "select_move": "Elige tu jugada",
        "make_move": "HACER JUGADA",
    },
}


def tr(lang: str, key: str) -> str:
    language = (lang or "EN").upper()
    if language not in TEXT:
        language = "EN"

    if key in TEXT[language]:
        return TEXT[language][key]

    return TEXT["EN"].get(key, key)
