"""Offline Chrome configuration check; no live Scopus login."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import scopus_backend as backend


class CloudBrowserTest(TestCase):
    def test_cloud_packages(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(
            (root / "packages.txt").read_text().splitlines(),
            ["chromium", "chromium-driver"],
        )

    def test_headless_launch_configuration(self):
        def which(name):
            return {
                "chromium": "/usr/bin/chromium",
                "chromedriver": "/usr/bin/chromedriver",
            }.get(name)

        fake_driver = MagicMock()
        with (
            patch.object(backend.sys, "platform", "linux"),
            patch.object(backend.shutil, "which", side_effect=which),
            patch.object(backend.webdriver, "Chrome", return_value=fake_driver) as create,
        ):
            client = backend.ScopusWorkbench("/tmp/panscopus-test-cloud")
            client._start_browser()
            kwargs = create.call_args.kwargs
            self.assertIn("--headless=new", kwargs["options"].arguments)
            self.assertIn("--no-sandbox", kwargs["options"].arguments)
            self.assertEqual(kwargs["options"].binary_location, "/usr/bin/chromium")
            self.assertTrue(kwargs["service"].path.endswith("chromedriver"))
            self.assertIs(client.driver, fake_driver)
