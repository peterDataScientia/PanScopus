"""PanScopus cloud-capable Streamlit interface for authorized Research4Life/Scopus access."""
from __future__ import annotations

import csv
import hmac
import platform
from pathlib import Path

import streamlit as st

from scopus_backend import DEFAULT_QUERY, MAX_CSV_EXPORT, ScopusWorkbench
from csv_import import parse_scopus_csv

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
if "last_debug" not in st.session_state:
    st.session_state.last_debug = None

client = st.session_state.client
IS_HOSTED_LINUX = platform.system() == "Linux"

# The Cloud web app uses institutional credentials stored in secrets.
# Block anonymous visitors from using them on public deployments.
def configured_access_pin():
    """Read the app PIN from several valid Streamlit Secrets layouts.

    This avoids silently treating correctly saved top-level secrets as
    missing when the original app expected only [app].access_pin.
    Never log or display the PIN.
    """
    paths = (
        ("app", "access_pin"),
        ("app", "pin"),
        ("app", "APP_ACCESS_PIN"),
        ("auth", "access_pin"),
        ("security", "access_pin"),
        ("research4life", "access_pin"),
        ("research4life", "app_access_pin"),
        ("APP_ACCESS_PIN",),
        ("PANSCOPUS_ACCESS_PIN",),
        ("app_access_pin",),
        ("access_pin",),
        ("ACCESS_PIN",),
    )
    try:
        secrets = st.secrets
        for path in paths:
            obj = secrets
            try:
                for key in path:
                    obj = obj[key]
                if isinstance(obj, (str, int)):
                    value = str(obj).strip()
                    if value and not value.startswith("SET_A_"):
                        return value
            except (KeyError, TypeError, AttributeError):
                continue
    except Exception:
        pass
    return ""

if IS_HOSTED_LINUX and not st.session_state.get("authorized", False):
    st.title("PanScopus")
    st.caption("Research4Life → Scopus · Cloud workbench")
    pin = configured_access_pin()
    if not pin:
        st.error("PanScopus access PIN was not detected in this deployment.")
        st.markdown(
            "Open **Manage app → Settings → Secrets** and add either "
            "`access_pin = \"YOUR_PRIVATE_PIN\"` at the top level or "
            "`[app]` followed by `access_pin = \"YOUR_PRIVATE_PIN\"`. "
            "Click **Save**, then **Reboot app**. "
            "Do not paste your actual PIN or institutional password into this chat."
        )
        st.caption(
            "The web interface loaded. Institutional login remains protected "
            "until the app receives its access PIN."
        )
    else:
        with st.form("panscopus_unlock"):
            entered = st.text_input("PanScopus access PIN", type="password")
            submitted = st.form_submit_button("Unlock PanScopus", type="primary")
        if submitted:
            if hmac.compare_digest(entered, pin):
                st.session_state.authorized = True
                st.rerun()
            else:
                st.error("Invalid access PIN")
    st.stop()


def configured_credentials():
    """Missing or malformed secrets must NEVER crash the Streamlit UI."""
    try:
        credentials = st.secrets.get("research4life", {})
        username = str(
            credentials.get("username") or st.secrets.get("R4L_USERNAME")
            or st.secrets.get("username") or ""
        ).strip()
        password = str(
            credentials.get("password") or st.secrets.get("R4L_PASSWORD")
            or st.secrets.get("password") or ""
        )
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
                st.session_state.last_debug = client.save_debug("streamlit_error")
                if st.session_state.last_debug:
                    st.info("Scopus browser diagnostic screenshot and JSON are available below.")
            except Exception as diagnostic_error:
                log("Diagnostic capture unavailable: " + type(diagnostic_error).__name__)
            return None
        finally:
            client.log = old


user, password = configured_credentials()
connected = client.session_alive() and client.is_scopus()
last = client.last_search
export = st.session_state.last_export

with st.sidebar:
    st.title("PanScopus")
    st.caption("Research4Life → Scopus · Cloud workbench")
    st.caption("Build: Cloudflare-aware v4")
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
if IS_HOSTED_LINUX:
    st.info("Cloud mode: headless Chromium. Login access still depends on Research4Life institutional authorization.")

with st.container(border=True):
    st.subheader("01 · Connect")
    st.write("Open Research4Life Standard Login and navigate to Scopus Advanced Search.")
    if st.button("Connect to Scopus", type="primary", disabled=not(user and password)):
        if run_action("Connecting to Scopus", lambda: client.connect(user, password)) is not None:
            st.session_state.last_debug = None
            st.rerun()
    if connected and st.button("Retry Advanced Search", use_container_width=True):
        if run_action("Opening Advanced Search", client.return_to_advanced) is not None:
            st.session_state.last_debug = None
            st.rerun()

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

with st.container(border=True):
    st.subheader("04 · Import authorized Scopus CSV")
    st.caption(
        "Cloudflare is currently refusing the hosted Scopus browser. "
        "Export CSV from a Scopus session that your institution authorizes, "
        "then upload it here for a record-count and metadata check. "
        "No Selenium login is required for importing."
    )
    uploaded = st.file_uploader(
        "Upload Scopus CSV",
        type=["csv"],
        key="scopus_csv_upload",
        help="Original CSV export from Scopus. This does not bypass Cloudflare.",
    )
    if uploaded is not None:
        try:
            file_bytes = uploaded.getvalue()
            summary = parse_scopus_csv(file_bytes)
            expected_import_count = st.number_input(
                "Expected Scopus result count (0 = skip comparison)",
                min_value=0,
                max_value=20000,
                value=80,
                step=1,
                key="scopus_import_expected",
            )
            cols = st.columns(3)
            cols[0].metric("CSV documents", f"{summary.count:,}")
            cols[1].metric("Metadata columns", f"{len(summary.fields):,}")
            cols[2].metric("Abstracts populated", f"{summary.abstract_populated:,}")
            if expected_import_count:
                if summary.count == expected_import_count:
                    st.success(f"CSV count matches your expected total: {summary.count:,}/{expected_import_count:,}.")
                else:
                    st.error(
                        f"CSV count {summary.count:,} differs from the expected "
                        f"{expected_import_count:,} records."
                    )
            st.caption(
                f"DOI populated: {summary.doi_populated:,} · "
                f"Repeated nonempty DOI: {summary.doi_duplicates:,} · "
                f"Repeated nonempty EID: {summary.eid_duplicates:,}"
            )
            if summary.doi_duplicates or summary.eid_duplicates:
                st.warning(
                    "Possible duplicate identifiers found; inspect records "
                    "before PRISMA screening."
                )
            with st.expander("Scopus metadata preview (first 12 records)"):
                st.dataframe(list(summary.preview), hide_index=True)
            with st.expander("Exported metadata fields"):
                st.write(", ".join(summary.fields))
            st.download_button(
                "Download original Scopus CSV",
                file_bytes,
                file_name=uploaded.name,
                mime="text/csv",
                use_container_width=True,
                key="download_imported_csv",
            )
            st.caption(
                "CSV checks confirm its contents and your stated expected count; "
                "they cannot independently verify the live Scopus result set."
            )
        except ValueError as err:
            st.error(f"CSV import rejected: {err}")

with st.expander("Activity log"):
    st.code("\n".join(st.session_state.logs[-60:]), language="text")
    st.caption(f"Server export folder: {OUTPUT}")

diagnostic = st.session_state.last_debug
if diagnostic:
    with st.expander("Scopus browser diagnostics", expanded=True):
        st.write("The login steps may succeed even when Scopus Advanced Search fails to render.")
        screenshot, metadata = (Path(p) for p in diagnostic)
        if screenshot.is_file():
            st.image(str(screenshot), caption="Current Scopus browser page", use_container_width=True)
            st.download_button(
                "Download screenshot",
                data=screenshot.read_bytes(),
                file_name=screenshot.name,
                mime="image/png",
                key="scopus_diag_png",
            )
        if metadata.is_file():
            st.download_button(
                "Download page-state JSON",
                data=metadata.read_bytes(),
                file_name=metadata.name,
                mime="application/json",
                key="scopus_diag_json",
            )
        st.caption("Never share passwords, cookies or Streamlit Secrets in diagnostics.")

st.caption("Streamlit Cloud uses headless Chromium; sessions and exported files are temporary. Use only authorized institutional access.")
