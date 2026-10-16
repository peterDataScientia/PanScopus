"""Parse user-provided Scopus CSV locally inside Streamlit Cloud.

The uploader is an authorized-export fallback, NOT an alternative Scopus login.
It does not access Research4Life, Scopus or external services.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass


MAX_IMPORT_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class CsvSummary:
    count: int
    fields: tuple[str, ...]
    preview: tuple[dict[str, str], ...]
    doi_duplicates: int
    eid_duplicates: int
    doi_populated: int
    abstract_populated: int


def parse_scopus_csv(raw: bytes) -> CsvSummary:
    if not raw:
        raise ValueError("The CSV file is empty")
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError("CSV exceeds the 32 MB import limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use UTF-8 encoding; re-export in UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = reader.fieldnames
    if not fields or len(fields) < 2:
        raise ValueError("The uploaded file has no usable CSV header")

    fields = tuple(str(x).strip() for x in fields if x)
    if len(set(fields)) != len(fields):
        raise ValueError("CSV contains duplicate column headers")

    canonical = {name.casefold().replace(" ", "").replace("-", ""): name for name in fields}
    def find(*names):
        for name in names:
            found = canonical.get(name.replace(" ", "").replace("-", "").casefold())
            if found:
                return found
        return None

    doi_col = find("DOI")
    eid_col = find("EID")
    abstract_col = find("Abstract")

    count = 0
    doi_populated = 0
    abstract_populated = 0
    doi_seen = set()
    eid_seen = set()
    doi_duplicates = 0
    eid_duplicates = 0
    preview = []

    for row in reader:
        if None in row:
            raise ValueError("CSV has more values than header columns on a record")
        cleaned = {str(key).strip(): str(value or "").strip() for key, value in row.items()}
        if not any(cleaned.values()):
            continue
        count += 1
        if len(preview) < 12:
            preview.append(cleaned)
        if doi_col:
            value = cleaned.get(doi_col, "").casefold()
            if value:
                doi_populated += 1
                if value in doi_seen:
                    doi_duplicates += 1
                doi_seen.add(value)
        if eid_col:
            value = cleaned.get(eid_col, "").casefold()
            if value:
                if value in eid_seen:
                    eid_duplicates += 1
                eid_seen.add(value)
        if abstract_col and cleaned.get(abstract_col):
            abstract_populated += 1

    if count == 0:
        raise ValueError("CSV has column headers but no document records")

    return CsvSummary(
        count=count,
        fields=fields,
        preview=tuple(preview),
        doi_duplicates=doi_duplicates,
        eid_duplicates=eid_duplicates,
        doi_populated=doi_populated,
        abstract_populated=abstract_populated,
    )
