"""PanScopus local Streamlit interface for authorized Research4Life/Scopus access."""
from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st

from scopus_backend import DEFAULT_QUERY, MAX_CSV_EXPORT, ScopusWorkbench

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "exports"
OUTPUT.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="PanScopus", page_icon="🔎", layout="wide")


def log(message: str):
    st.session_state.logs = (st.session_state.logs + [str(message)])[-100:]


if "logs" not in st.session_state:
    st.session_state.logs = []
if "client" not in st.session_state:
    st.session_state.client = ScopusWorkbench(OUTPUT, logger=log)
if "query" not in st.session_state:
    st.session_state.query = DEFAULT_QUERY
if "last_export" not in st.session_state:
    st.session_state.last_export = None

client = st.session_state.client


def configured_credentials():
    """Missing or malformed secrets must NEVER crash the Streamlit UI."""
    try:
        credentials = st.secrets["research4life"]
        username = str(credentials.get("username", "")).strip()
        password = str(credentials.get("password", ""))
        if username.startswith("YOUR_") or password.startswith("YOUR_"):
            return "", ""
        return username, password
    except Exception:
        # Streamlit may raise StreamlitSecretNotFoundError when secrets
        # are absent. This is not always a FileNotFoundError subclass.
        return "", ""


def run_action(title, call):
    with st.status(title, expanded=True) as box:
        old = client.log
        try:
            client.log = lambda line: (log(line), st.write(line))
            value = call()
            box.update(label=title + " — finished", state="complete", expanded=False)
            return value
        except Exception as exc:
            log(f"{type(exc).__name__}: {exc}")
            st.error(f"{type(exc).__name__}: {exc}")
            box.update(label=title + " — stopped", state="error", expanded=True)
            try:
                client.save_debug("streamlit_error")
            except Exception:
                pass
            return None
        finally:
            client.log = old


user, password = configured_credentials()
connected = client.session_alive() and client.is_scopus()
last = client.last_search
export = st.session_state.last_export

with st.sidebar:
    st.title("PanScopus")
    st.caption("Research4Life → Scopus · Local workbench")
    if user and password:
        st.success("Secrets configured")
    else:
        st.warning("Configure Research4Life credentials in Streamlit Secrets (cloud) or .streamlit/secrets.toml (local)")
    st.write("🟢 Scopus connected" if connected else "⚪ Browser disconnected")
    if last:
        st.metric("Matching documents", last.count)
    if st.button("Disconnect browser", disabled=not client.session_alive(), use_container_width=True):
        client.close()
        st.session_state.last_export = None
        st.rerun()
    st.caption("Institutional credentials are not shown, saved in logs, or included in exports.")

st.title("PanScopus")
st.caption("Research4Life authentication · Advanced document search · Verified CSV export")

with st.container(border=True):
    st.subheader("01 · Connect")
    st.write("Open Research4Life Standard Login and navigate to Scopus Advanced Search.")
    if st.button("Connect to Scopus", type="primary", disabled=not(user and password)):
        if run_action("Connecting to Scopus", lambda: client.connect(user, password)) is not None:
            st.success("Scopus Advanced Search is ready.")

with st.container(border=True):
    st.subheader("02 · Search")
    st.text_area("Advanced Scopus query", height=155, key="query")
    a, b = st.columns([2, 1])
    with a:
        clicked = st.button("Run search", use_container_width=True,
                            type="primary", disabled=not connected or not st.session_state.query.strip())
    with b:
        go_back = st.button("Back to Advanced Search", use_container_width=True, disabled=not connected)
    if clicked:
        result = run_action("Running search", lambda: client.search(st.session_state.query))
        if result is not None:
            st.session_state.last_export = None
            st.success(f"Verified {result.count:,} matching Scopus documents.")
            st.caption(result.results_url)
    if go_back:
        if run_action("Returning to Advanced Search", client.return_to_advanced) is not None:
            client.last_search = None
            st.session_state.last_export = None
            st.info("Advanced Search reopened on the same Chrome session.")
    if client.last_search:
        st.info(f"Current search: {client.last_search.count:,} documents")

with st.container(border=True):
    st.subheader("03 · Export")
    st.caption("Checks the Scopus query, full document selection, metadata and downloaded CSV row count.")
    count = client.last_search.count if client.last_search else 0
    if count > MAX_CSV_EXPORT:
        st.warning(f"{count:,} records exceed the {MAX_CSV_EXPORT:,} per-export CSV limit; partition the query.")
    if st.button("Export all matching records", type="primary", use_container_width=True,
                 disabled=not connected or not (0 < count <= MAX_CSV_EXPORT)):
        result = run_action("Exporting CSV", client.export_csv)
        if result is not None:
            st.session_state.last_export = result
            if result.state == "complete":
                st.success(f"CSV verified: {result.rows:,}/{result.expected:,} rows.")
            elif result.state == "partial_or_mismatch":
                st.error(f"Row-count mismatch: {result.rows} of {result.expected}.")
            else:
                st.info("Export submitted; check the Scopus Exports Dashboard for completion.")

    previous = st.session_state.last_export
    if previous and previous.path:
        file = Path(previous.path)
        if file.is_file():
            st.download_button("Download CSV", data=file.read_bytes(), file_name=file.name,
                               mime="text/csv", use_container_width=True)
            with st.expander("Preview first five records"):
                with file.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
                    records = list(row for _, row in zip(range(5), csv.DictReader(handle)))
                if records:
                    st.dataframe(records, hide_index=True)

with st.expander("Activity log"):
    st.code("\n".join(st.session_state.logs[-60:]), language="text")
    st.caption(f"Local export folder: {OUTPUT}")

st.caption("The interface can load on Streamlit Cloud, but authenticated Selenium browser automation is supported for local Windows use only; cloud execution has not been validated.")
