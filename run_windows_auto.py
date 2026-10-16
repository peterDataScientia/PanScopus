"""PanScopus: single-command Windows automation using authorized Research4Life access.

Run from the PanScopus repository:
    python run_windows_auto.py

No Scopus API, Chrome extension, Streamlit Cloud or manual CSV export.
"""
from __future__ import annotations

import csv
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path

from scopus_backend import DEFAULT_QUERY, ScopusWorkbench

ROOT = Path(__file__).resolve().parent
EXPORT_DIR = ROOT / "exports"
EXPORT_DIR.mkdir(exist_ok=True)


def get_query() -> str:
    query_path = ROOT / "sample_query.txt"
    text = query_path.read_text(encoding="utf-8").strip() if query_path.exists() else ""
    return text or DEFAULT_QUERY


def get_credentials() -> tuple[str, str]:
    # Credentials are requested through the terminal if not in the Windows
    # environment. They are never written to CSV, GitHub or application logs.
    username = os.environ.get("R4L_USERNAME", "").strip()
    password = os.environ.get("R4L_PASSWORD", "")
    if not username:
        username = input("Research4Life username: ").strip()
    if not password:
        password = getpass.getpass("Research4Life password (hidden): ")
    if not username or not password:
        raise ValueError("Research4Life username and password are required")
    return username, password


def run() -> Path:
    if not sys.platform.startswith("win"):
        raise RuntimeError("This runner is for Windows desktop Chrome, not hosted Cloud/Colab")
    print("\nPanScopus — Windows automated Research4Life → Scopus → CSV")
    print("No Chrome extension or Scopus API required.")
    print("Authorized institutional access is required.\n")

    query = get_query()
    print("Advanced query:\n" + query + "\n")
    username, password = get_credentials()
    browser = ScopusWorkbench(EXPORT_DIR, logger=lambda msg: print(msg, flush=True))
    try:
        browser.connect(username, password)
        result = browser.search(query)
        if result.count == 0:
            raise RuntimeError("Scopus found zero records; nothing to export")

        print(f"\nScopus count: {result.count:,} records")
        exported = browser.export_csv(timeout=240)

        if exported.state != "complete" or exported.path is None:
            raise RuntimeError(
                f"CSV export was not verified: {exported.state} "
                f"({exported.rows}/{exported.expected}); no success claimed."
            )
        file = Path(exported.path)
        if not file.is_file():
            raise FileNotFoundError(f"Expected CSV file was not found: {file}")
        with file.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
            rows = sum(1 for _ in csv.DictReader(handle))
        if rows != result.count:
            raise RuntimeError(
                f"CSV count mismatch: {rows}/{result.count}; full export not verified."
            )
        print(f"\nSUCCESS: {rows:,}/{result.count:,} records verified")
        print(f"CSV saved to: {file.resolve()}")
        print("Finished at:", datetime.now().isoformat(timespec="seconds"))
        return file.resolve()

    except Exception:
        try:
            diagnostic = browser.save_debug("windows_failure")
            if diagnostic:
                print("Diagnostic screenshot / JSON:", *diagnostic)
        except Exception:
            pass
        raise
    finally:
        browser.close()
        # Remove references to plain-text credentials from this stack frame.
        del username, password


if __name__ == "__main__":
    try:
        run()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(130)
    except Exception as error:
        print(f"\nFAILED: {type(error).__name__}: {error}")
        sys.exit(1)
