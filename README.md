# PanScopus

A local-first Streamlit research workbench for authorized Research4Life → Scopus searches and bibliographic CSV export.

## Run on Windows

1. Clone or download this repository.
2. Install: `python -m pip install -r requirements.txt`
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and enter your **authorized** institutional username/password. Never commit this private file.
4. Start: `python -m streamlit run app.py --server.address=127.0.0.1`
5. Open `http://127.0.0.1:8501`.

Use **Connect → Search → Export CSV**. The same Chrome session remains open between actions. Export only records that your institutional license permits. Confirm that downloaded CSV rows match the Scopus result count. Scopus's CSV export interface can change and has not been tested end-to-end in this Streamlit wrapper.

**Security:** This app is designed for local Windows use. Do not deploy unchanged as a public multi-user service: Selenium sessions and institutional credentials need per-user isolation. Do not commit `.streamlit/secrets.toml`.

The `ScopusWorkbench` backend supports Research4Life Standard Login, the authenticated gateway, Advanced Search Monaco editor, checked CSV export ranges, and provenance logs. If Scopus's dialog changes, the app will refuse partial exports rather than report success.
