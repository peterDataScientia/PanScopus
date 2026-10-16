"""Offline regression checks for Cloudflare handling and Scopus CSV import."""
import unittest
from csv_import import parse_scopus_csv
from scopus_backend import ScopusWorkbench


class CloudflareChecks(unittest.TestCase):
    def test_cloudflare_attention_required(self):
        state = {
            "title": "Attention Required! | Cloudflare",
            "body_excerpt": "Sorry, you have been blocked",
        }
        message = ScopusWorkbench._page_problem(state)
        self.assertIn("Cloudflare", message)
        self.assertIn("PanScopus will not bypass", message)

    def test_normal_scopus_page_not_blocked(self):
        state = {
            "title": "Scopus - Search",
            "body_excerpt": "Advanced search Documents Sources",
        }
        self.assertIsNone(ScopusWorkbench._page_problem(state))


class ScopusCsvChecks(unittest.TestCase):
    def test_80_records_and_multiline_abstract(self):
        heading = "EID,Title,DOI,Abstract\n"
        records = []
        for index in range(80):
            abstract = '"line one\nline two"' if index == 0 else "example"
            records.append(f"EID-{index},Paper {index},10.1000/{index},{abstract}\n")
        summary = parse_scopus_csv((heading + "".join(records)).encode("utf-8-sig"))
        self.assertEqual(summary.count, 80)
        self.assertEqual(summary.abstract_populated, 80)
        self.assertEqual(summary.doi_duplicates, 0)
        self.assertEqual(summary.eid_duplicates, 0)
        self.assertEqual(len(summary.fields), 4)

    def test_duplicate_doi_count(self):
        value = (
            "EID,Title,DOI\n"
            "a,Paper One,10.1/example\n"
            "b,Paper Two,10.1/example\n"
        ).encode()
        summary = parse_scopus_csv(value)
        self.assertEqual(summary.doi_duplicates, 1)

    def test_invalid_file_rejected(self):
        with self.assertRaises(ValueError):
            parse_scopus_csv(b"")
        with self.assertRaises(ValueError):
            parse_scopus_csv(b"not_a_scopus_csv")
