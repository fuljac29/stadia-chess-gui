\
from __future__ import annotations

import os

import streamlit as st

import chess_db as db
from chess_tokens import make_seat_token


st.set_page_config(page_title="Stadia Chess Admin", page_icon="⚙️", layout="wide")
db.init_db()


def secret(name: str, default: str) -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)


ADMIN_PASSWORD = secret("ADMIN_PASSWORD", "CHANGE-THIS-ADMIN-PASSWORD")
APP_SECRET = secret("APP_SECRET", "DEV-ONLY-CHANGE-ME")
APP_BASE_URL = secret("APP_BASE_URL", "http://localhost:8501").rstrip("/")


st.title("Stadia Chess Administration")
password = st.text_input("Admin password", type="password")
if password != ADMIN_PASSWORD:
    st.info("Enter the admin password.")
    st.stop()

games = db.list_games(include_archived=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", len(games))
c2.metric("Active", sum(g["status"] == "active" and not g["archived"] for g in games))
c3.metric("Waiting / ready", sum(g["status"] in {"waiting", "ready"} and not g["archived"] for g in games))
c4.metric("Finished", sum(g["status"] == "finished" and not g["archived"] for g in games))

status_filter = st.selectbox(
    "Filter",
    ["All", "waiting", "ready", "active", "finished", "archived"],
)

filtered = games
if status_filter == "archived":
    filtered = [g for g in games if g["archived"]]
elif status_filter != "All":
    filtered = [g for g in games if g["status"] == status_filter and not g["archived"]]
else:
    filtered = [g for g in games if not g["archived"]]

if not filtered:
    st.info("No games in this view.")
    st.stop()

for g in filtered:
    with st.container(border=True):
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.markdown(f"### {g['white_name']} vs {g['black_name']}")
        h1.caption(f"{g['id']} · updated {g['updated_at']}")
        h2.metric("Status", g["status"])
        h3.metric("Moves", g["move_count"])

        white_token = make_seat_token(g["id"], "white", APP_SECRET)
        black_token = make_seat_token(g["id"], "black", APP_SECRET)
        st.code(f"WHITE: {APP_BASE_URL}/?seat={white_token}", language=None)
        st.code(f"BLACK: {APP_BASE_URL}/?seat={black_token}", language=None)

        a, b = st.columns(2)
        with a:
            if not g["archived"]:
                if st.button("Archive", key=f"archive_{g['id']}", use_container_width=True):
                    db.archive_game(g["id"], True)
                    st.rerun()
            else:
                if st.button("Restore", key=f"restore_{g['id']}", use_container_width=True):
                    db.archive_game(g["id"], False)
                    st.rerun()
        with b:
            if g["archived"]:
                if st.button("Delete permanently", key=f"delete_{g['id']}", use_container_width=True):
                    db.delete_game(g["id"])
                    st.rerun()
