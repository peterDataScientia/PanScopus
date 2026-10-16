"""Verify the Streamlit UI can start without institutional secrets or Chrome."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitStartupTest(unittest.TestCase):
    def test_app_starts_without_secrets(self):
        app_file = Path(__file__).resolve().parents[1] / "app.py"
        at = AppTest.from_file(str(app_file)).run(timeout=45)
        self.assertEqual(
            len(at.exception), 0,
            "Streamlit app produced startup exceptions: " + str([e.message for e in at.exception]),
        )
        self.assertTrue(
            any("PanScopus" in h.value for h in at.title),
            "PanScopus title not rendered",
        )


if __name__ == "__main__":
    unittest.main()
