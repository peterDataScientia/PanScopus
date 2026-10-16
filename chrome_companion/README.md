# PanScopus Chrome Companion (MV3)

**Purpose:** automate Scopus Advanced Search → CSV export → PanScopus Cloud upload, using the user's **normal, institutionally authorized Chrome browser session**. This runs on the user's Chrome browser; no Scopus API key or locally hosted server is needed.

## Installation (one time)

1. Download the PanScopus GitHub repository ZIP and extract it.
2. In Chrome, open \`chrome://extensions\`, enable **Developer mode**, choose **Load unpacked**, and select the \`chrome_companion\` folder.
3. Open/reload the PanScopus Streamlit Cloud app (with your app access PIN already set). The **Run Scopus Search + CSV via Chrome Companion** button appears below the Scopus query.
4. Make sure you have previously signed in to Scopus through your **authorized Research4Life access** in the same Chrome profile. The extension does not log in for you or store institutional credentials.
5. Click the Companion Run button. The first time, select your actual **Chrome download folder** in the Runner and grant its read permission. If Chrome uses a different download location, choose that folder. Click **Run Search + Export + Import**.

If you later change your Downloads folder, click **Choose Chrome download folder** again. To avoid prompts on each export, ensure Chrome does not ask for a new location for each download.

## Built-in safeguards

- Runs only after a user clicks its button in PanScopus.
- Reuses normal Scopus access; no cookie copying, proxy, CAPTCHA solver or Cloudflare workaround.
- Stops if a browser access challenge appears or Scopus Search fails.
- Verifies the exact query in the Monaco editor before clicking Search, and checks results contain that query.
- Verifies the **full document count** is selected inside the CSV export dialog before submitting; refuses partial exports. Verifies CSV metadata selection.
- Checks downloaded CSV rows equal the result count. Otherwise keeps the original downloaded file but **does not import it**.
- The chosen folder is authorized through Chrome's File System Access API and read only to load the new CSV. No other directory scanning and no credential access.
- The Chrome \`debugger\` permission is needed to send normal keyboard text to Scopus's Monaco editor and range input, as in the previously tested Windows automation. Chrome may display a browser debugging warning while the short-lived input operation runs. The extension detaches immediately afterward.
- The extension's Streamlit site access is scoped to \`*.streamlit.app\` because PanScopus deployments have dynamic hostnames. It only activates on a page with the PanScopus Companion marker and explicit user click. Extension code is open for audit.

## Limitations and status

**This is a new integration, not yet live-tested in the user's authenticated Chrome/Scopus session.** Cloud CI checks JavaScript syntax and wiring, not Scopus account access or actual export. Chrome/Scopus UI changes can break selectors. The extension uses the Scopus website and does not bypass service restrictions. A normal browser sign-in may still be needed when a Research4Life session expires.

The user grants read access to the selected Chrome download folder (once, or again if permission expires), not a local server. Auto-import injects the resulting CSV into PanScopus's Streamlit upload widget. If Streamlit changes its widget behavior, the CSV will remain in the user's Downloads folder and a clear error will be shown.

If a run fails, copy **only its safe Runner progress log**, not passwords, cookies, or session tokens.

## Files

- \`manifest.json\`: Chrome extension MV3 permissions.
- \`background.js\`: receives explicit PanScopus start requests.
- \`panscopus_content.js\`: inserts Run button and delivers CSV to the Streamlit uploader.
- \`runner.html\` + \`runner.js\`: search, export, count verification and import.
- \`popup.html\`: extension information.
