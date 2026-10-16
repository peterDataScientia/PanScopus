"""Verify the Streamlit UI can start without institutional secrets or Chrome."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitStartupTest(unittest.TestCase):
    def _run(self, secrets=None):
        app_file = Path(__file__).resolve().parents[1] / "app.py"
        at = AppTest.from_file(str(app_file))
        if secrets:
            for key, value in secrets.items():
                at.secrets[key] = value
        at.run(timeout=45)
        self.assertEqual(
            len(at.exception), 0,
            "Streamlit app produced startup exceptions: " + str([e.message for e in at.exception]),
        )
        return at

    def test_app_starts_without_secrets(self):
        at = self._run()
        self.assertTrue(
            any("PanScopus" in h.value for h in at.title),
            "PanScopus title not rendered",
        )

    def test_top_level_access_pin_detected(self):
        at = self._run({"access_pin": "TEST_PRIVATE_PIN"})
        self.assertFalse(
            any("access PIN was not detected" in x.message for x in at.error)
        )
        self.assertTrue(
            any("PanScopus access PIN" in x.label for x in at.text_input)
        )

    def test_nested_access_pin_detected(self):
        at = self._run({"app": {"access_pin": "TEST_PRIVATE_PIN"}})
        self.assertFalse(
            any("access PIN was not detected" in x.message for x in at.error)
        )
        self.assertTrue(
            any("PanScopus access PIN" in x.label for x in at.text_input)
        )


if __name__ == "__main__":
    unittest.main()
