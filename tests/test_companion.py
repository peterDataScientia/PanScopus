"""Source-level checks for Chrome Companion browser bridge.

These tests never contact Scopus and never inspect credentials.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "chrome_companion"


class CompanionChecks(unittest.TestCase):
    def test_extension_files_present_and_manifest_scoped(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("https://www.scopus.com/*", manifest["host_permissions"])
        self.assertIn("https://*.streamlit.app/*", manifest["host_permissions"])
        self.assertIn("https://share.streamlit.io/*", manifest["host_permissions"])
        self.assertEqual(manifest["version"], "0.1.1")
        self.assertNotIn("<all_urls>", manifest["host_permissions"])
        self.assertNotIn("cookies", manifest["permissions"])
        self.assertNotIn("webRequest", manifest["permissions"])
        for filename in [
            "background.js", "panscopus_content.js",
            "runner.html", "runner.js", "popup.html", "popup.js", "README.md",
        ]:
            self.assertTrue((EXT / filename).exists(), filename)

    def test_companion_not_enabled_without_click(self):
        content = (EXT / "panscopus_content.js").read_text(encoding="utf-8")
        background = (EXT / "background.js").read_text(encoding="utf-8")
        self.assertIn("btn.addEventListener(\"click\"", content)
        self.assertIn("PANSCOPUS_START", content)
        self.assertIn("sender.tab.url", background)
        self.assertIn("panscopusJob", background)
        self.assertIn("appTabId", background)
        self.assertIn("currentQueryField()", content)
        self.assertIn('field.closest(', content)
        self.assertNotIn('document.querySelector(marker)', content)
        popup = (EXT / "popup.js").read_text(encoding="utf-8")
        self.assertIn("PANSCOPUS_START", popup)
        self.assertIn("executeScript", popup)

    def test_csv_refuses_partial_exports(self):
        runner = (EXT / "runner.js").read_text(encoding="utf-8")
        self.assertIn("count!==total", runner)
        self.assertIn("CSV export", runner)
        self.assertIn("countCSV(csv)", runner)
        self.assertIn("rows!==total", runner)
        self.assertIn("PANSCOPUS_IMPORT_CSV", runner)

    def test_streamlit_companion_entrypoint(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('st.text_area(', app)
        self.assertIn("Build: Chrome Companion v6.1", app)
        self.assertIn("st.html(", app)
        self.assertIn('id="panscopus-companion"', app)
        self.assertIn("parse_scopus_csv", app)


if __name__ == "__main__":
    unittest.main()
