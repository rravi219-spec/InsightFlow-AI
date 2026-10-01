"""Raw, pre-transformation profiling, also reused by every ETL run."""
from collections import Counter
from hashlib import sha256
import json

from .extract import iter_source, raw_json, file_digest
from .retail_config import COLUMNS, SOURCE, PROFILE
from .validate import classify, text, parse_date


class RawProfiler:
    def __init__(self):
        self.rows = 0
        self.sheets = Counter()
        self.missing = Counter()
        self.types = {c: Counter() for c in COLUMNS}
        self.flags = Counter()
        self.seen = set()
        self.duplicates = 0
        self.keys = {c: set() for c in ("Customer ID", "Invoice", "StockCode", "Country")}
        self.date_min = self.date_max = None

    def add(self, sheet, row):
        payload = raw_json([row[c] for c in COLUMNS])
        fingerprint = sha256(payload.encode("utf-8")).hexdigest()
        duplicate = fingerprint in self.seen
        self.seen.add(fingerprint)
        self.duplicates += duplicate
        self.rows += 1
        self.sheets[sheet] += 1
        flags = classify(row)
        self.flags.update({k: int(v) for k, v in flags.items()})
        for col in COLUMNS:
            self.types[col][type(row[col]).__name__] += 1
            self.missing[col] += text(row[col]) is None
        for col in self.keys:
            value = text(row[col])
            if value is not None:
                self.keys[col].add(value)
        timestamp = parse_date(row["InvoiceDate"])
        if timestamp is not None:
            self.date_min = min(self.date_min, timestamp) if self.date_min else timestamp
            self.date_max = max(self.date_max, timestamp) if self.date_max else timestamp
        return payload, fingerprint, duplicate, flags

    def report(self):
        return {
            "raw_rows": self.rows, "sheets": dict(self.sheets), "columns": list(COLUMNS),
            "cell_types": self.types, "missing_values": dict(self.missing),
            "duplicate_source_rows": self.duplicates, "quality_flags": dict(self.flags),
            "unique_values": {k: len(v) for k, v in self.keys.items()},
            "countries": sorted(self.keys["Country"]),
            "date_min": self.date_min.isoformat() if self.date_min else None,
            "date_max": self.date_max.isoformat() if self.date_max else None,
        }


def profile_source(source=SOURCE, output=PROFILE):
    profiler = RawProfiler()
    for sheet, _, row in iter_source(source):
        profiler.add(sheet, row)
    report = {"source_file": str(source), "source_sha256": file_digest(source), **profiler.report()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(profile_source(), indent=2))
