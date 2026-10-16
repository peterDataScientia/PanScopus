"""Offline checks for automated Windows runner and Jupyter notebook."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowsAutomationChecks(unittest.TestCase):
    def test_windows_runner_syntax(self):
        source=(ROOT/"run_windows_auto.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("browser.connect(username, password)", source)
        self.assertIn("browser.search(query)", source)
        self.assertIn("browser.export_csv(timeout=240)", source)
        self.assertIn("rows != result.count", source)
        self.assertIn("getpass.getpass(", source)

    def test_jupyter_notebook(self):
        notebook=json.loads((ROOT/"PanScopus_Windows_Auto.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"],4)
        self.assertEqual(len(notebook["cells"]),2)
        source="".join(notebook["cells"][1]["source"])
        ast.parse(source)
        self.assertIn("from run_windows_auto import run",source)
        self.assertIn("csv_path = run()",source)

    def test_batch_entrypoint(self):
        batch=(ROOT/"RUN_WINDOWS_AUTO.bat").read_text(encoding="utf-8")
        self.assertIn("python run_windows_auto.py",batch)
        self.assertIn("cd /d",batch)


if __name__=="__main__":
    unittest.main()
