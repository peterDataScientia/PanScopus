"""Offline tests: no institutional login or live Scopus request."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OfflineChecks(unittest.TestCase):
    def test_python_sources_compile(self):
        for name in ["app.py", "scopus_backend.py"]:
            code = (ROOT / name).read_text(encoding="utf-8")
            ast.parse(code, filename=name)

    def test_secret_template_only(self):
        self.assertFalse((ROOT / ".streamlit/secrets.toml").exists())
        self.assertTrue((ROOT / ".streamlit/secrets.toml.example").exists())
        ignore = (ROOT / ".gitignore").read_text()
        self.assertIn(".streamlit/secrets.toml", ignore)

    def test_export_guard_present(self):
        src = (ROOT / "scopus_backend.py").read_text()
        self.assertIn("if self._dialog_total() != total:", src)
        self.assertIn("partial_or_mismatch", src)
        self.assertIn("def export_csv", src)

    def test_default_query_field_code(self):
        src = (ROOT / "scopus_backend.py").read_text()
        self.assertIn("TITLE-ABS-KEY", src)


if __name__ == "__main__":
    unittest.main()
