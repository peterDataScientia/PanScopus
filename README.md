# PanScopus — Streamlit Cloud

## Chrome Companion (no Scopus API, no local server)

**Primary workflow:** PanScopus Cloud query → Chrome Companion runs Scopus Advanced Search in your authorized desktop Chrome browser → selects **all matching documents** and **all export metadata** → downloads CSV → checks downloaded row count → imports CSV into the PanScopus Cloud uploader.

**One-time setup:** Download [this GitHub repository as ZIP](https://github.com/peterDataScientia/PanScopus/archive/refs/heads/main.zip), extract it, open `chrome://extensions` in your usual Chrome browser, enable **Developer mode** → **Load unpacked** → select the `chrome_companion` folder. Then return to PanScopus Cloud, unlock with your PIN, reload, enter your query, click **Run Scopus Search + CSV via Chrome Companion** and choose the Chrome downloads folder when prompted.

The Companion has no API key and no local server. It operates only after user initiation in an authorized browser session. You may need to sign in through your institution when your normal Scopus/Research4Life browser session has expired. **Actual end-to-end Chrome/Scopus execution remains to be validated; passing code tests is not proof that Scopus's live UI will accept every action.** See [Companion installation and limitations](chrome_companion/README.md).


## Deploy on Streamlit Community Cloud (free)

1. Deploy this repository using entrypoint `app.py`.
2. Streamlit installs Python dependencies from `requirements.txt` and **Chromium + ChromeDriver** from `packages.txt` (allow time for system packages).
3. In **Manage app → Settings → Secrets**, keep your existing Research4Life username and password and add an **independent app access PIN**. Example:

```toml
[research4life]
username = "YOUR_R4L_USERNAME"
password = "YOUR_R4L_PASSWORD"

[app]
access_pin = "A_LONG_PRIVATE_PIN"
```

   Alternatively for existing deployments, top-level `R4L_USERNAME` and `R4L_PASSWORD` are also supported. **Never share institutional passwords or commit secrets to GitHub.**
4. Reboot your deployed Streamlit app to install the Linux packages and reload the Secrets.
5. Enter your app PIN, load the [Chrome Companion](chrome_companion/README.md), then use **Run Scopus Search + CSV via Chrome Companion** to automate the browser-side search and export. The existing Cloud Selenium buttons remain optional and are currently blocked by Cloudflare. CSV import remains available as a fallback.

## Security

The GitHub repository may be public, but **an anonymous public Streamlit app with institutional credentials is not secure**. Access to the app is blocked until `[app].access_pin` is set, and the PIN must be entered in each new browser session. Prefer making the deployed app private using **Streamlit Cloud → Settings → Sharing → Only specific people can view this app** too. Do not use the Research4Life password as the app PIN.

## Notes and limitations

- **Cloudflare blocked Scopus in the 2026-10-16 hosted-session test.** Research4Life authentication succeeded, but Scopus returned `Attention Required! | Cloudflare` instead of Advanced Search. This is an access challenge, not a Monaco editor or Selenium timing issue. The app detects this and stops promptly; it does not bypass Cloudflare.
- **Supported fallback on Streamlit Cloud:** export CSV from a browser where you are authorized to use Scopus; upload that CSV to step 04. The app checks the row count and metadata. This is not equivalent to live automated Scopus querying.
- Linux headless Chromium is installed, but permission to access Scopus from a hosted environment depends on Scopus and your institution.
- This app does **not** bypass institutional entitlement checks, CAPTCHAs or service rules.
- The same Selenium Chrome session is kept between clicks within one connected Streamlit session. The Cloud instance may restart or run out of memory, invalidating the session.
- The CSV export checks that the dialog targets the full record count. It refuses mismatched selections and compares actual CSV row count after download.
- Exports are saved to temporary `exports/` on the Cloud server; download them before the server restarts.
- There is no paid API or subscription dependency.
- Tests validate the Python code and Streamlit startup, **not** the authenticated browser workflow.

## Run locally (optional)

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

`secrets.toml` is excluded by `.gitignore`.
