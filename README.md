# Stadia Chess GUI v1.0 — Traditional + 10×8

A multilingual Streamlit application for remote private chess on Stadia.

The host can choose either traditional chess or **Stadia 10×8 Counterintelligence Chess**. Both variants use the same secure invitation, clocks, remote synchronization, first-free-game and Premium Arena access flow. Invited partners play free.

The 10×8 rules and the pending-patent notice are available in English, Italian, German, French and Spanish.

## Goal of v0.2

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
- `counter_chess.py` — authoritative 10×8 rules engine.
- `chess_tokens.py` — permanent White/Black signed links.
- `chess_board.py` — board rendering and legal move list.
- `i18n.py` — EN / IT / DE / FR / ES core interface text.
- `counter_board_frontend/` — responsive 10×8 board and the 3D pieces.
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

Without configuration the application uses SQLite for local development and compatibility.

For permanent storage, add a PostgreSQL connection string to Streamlit Secrets:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require"
```

On the next start, the application creates or updates the PostgreSQL tables automatically. Never commit this value to GitHub.

To copy an existing SQLite database one time, run `migrate_sqlite_to_postgres.py` with `DATABASE_URL` set in the environment. The migration does not delete the SQLite source.

For a real public launch, move the database to durable PostgreSQL/Supabase before accepting real users. Streamlit Community Cloud does not guarantee persistence of local files.

## Premium Arena

The application uses the existing Stadia WordPress access and completion endpoints. The first game is free; afterwards the existing CHF 5 winner offer or CHF 9 standard offer grants 30 days of unlimited private games. The invited partner does not pay.

## Upgrade compatibility

`init_db()` adds the `variant` column automatically. Existing database games are preserved and classified as traditional chess.

## v0.2 flow change

The host enters only their own name. The invited Black player enters their own name after opening the permanent Black invitation link and presses JOIN GAME. Only then does the game become ready for White to start.
