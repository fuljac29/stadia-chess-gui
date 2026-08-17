# Stadia Chess GUI v0.1

A clean Streamlit prototype for Stadia Private Chess.

## Goal of v0.1

Prove one flow reliably:

1. White creates a private game.
2. White receives a permanent White link.
3. White sends a different permanent Black link to a friend.
4. Black opens the link and is identified on the server as Black.
5. White starts the game.
6. Both players make legal chess moves.
7. Both can close the browser and return later using the same permanent links.

The player role is **not decided by localStorage/sessionStorage**. It is encoded in a signed server-verifiable player link.

## Project files

- `streamlit_app.py` — public player GUI.
- `pages/1_Admin.py` — password-protected administration GUI.
- `chess_db.py` — game and move storage.
- `chess_tokens.py` — permanent White/Black signed links.
- `chess_board.py` — board rendering and legal move list.
- `i18n.py` — EN / IT / DE / FR / ES core interface text.
- `.streamlit/config.toml` — Streamlit appearance.
- `.streamlit/secrets.toml.example` — secret template.
- `requirements.txt` — Python dependencies.

## Local test

Create `.streamlit/secrets.toml` from the example and change all secrets.

Then:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open `http://localhost:8501`.

## GitHub

Upload the **contents of this folder** to a new GitHub repository.

Do **not** upload `.streamlit/secrets.toml`.
It is ignored by `.gitignore`.

## Streamlit Community Cloud

Deploy `streamlit_app.py` from the GitHub repository.

In Streamlit App settings > Secrets, set:

```toml
APP_SECRET = "a-long-random-secret"
APP_BASE_URL = "https://YOUR-APP.streamlit.app"
ADMIN_PASSWORD = "a-strong-admin-password"
```

`APP_SECRET` must remain unchanged after real games are created, because existing player links are signed with it.

## Important: database persistence

v0.1 uses SQLite because it is the fastest way to test the GUI and the White/Black link architecture.

For a real public launch, move the database to durable PostgreSQL/Supabase before accepting real users. Streamlit Community Cloud does not guarantee persistence of local files.

## WooCommerce

Not connected in v0.1.

WooCommerce will be integrated only after the core flow (create -> invite -> play -> close -> return) is stable.
The future integration should grant the right to create games; WooCommerce should not control White/Black identity.
