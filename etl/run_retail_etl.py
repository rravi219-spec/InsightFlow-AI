"""Build, reconcile, then atomically publish one local retail snapshot."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from time import perf_counter

from .extract import file_digest, iter_source
from .load import initialize, load_batch, populate_analytics
from .profile import RawProfiler
from .reconcile import reconcile
from .retail_config import SOURCE, DATABASE, REPORT, SOURCE_URL
from .transform import transform_record


def peak_memory_bytes():
    """Process peak working set on Windows; unavailable platforms return None."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                "PagefileUsage", "PeakPagefileUsage")]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return counters.PeakWorkingSetSize
    return None


def run_etl(source=SOURCE, database=DATABASE, report_path=REPORT):
    source, database, report_path = map(Path, (source, database, report_path))
    if len({p.resolve() for p in (source, database, report_path)}) != 3:
        raise ValueError("Source, database, and report paths must be different")
    start = perf_counter()
    source_hash = file_digest(source)
    database.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an unrelated SQLite database, including Telco.
    if database.exists():
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as existing:
            try:
                marker = existing.execute("SELECT value FROM etl_metadata WHERE key='pipeline'").fetchone()
            except sqlite3.DatabaseError as error:
                raise ValueError("Refusing to replace a database not owned by retail ETL") from error
            if marker != ("insightflow_retail_v1",):
                raise ValueError("Refusing to replace a database not owned by retail ETL")
    descriptor, name = tempfile.mkstemp(prefix="retail_build_", suffix=".sqlite3", dir=database.parent)
    os.close(descriptor)
    build = Path(name)
    profiler = RawProfiler()
    exclusions = Counter()
    primary_reasons = Counter()
    analytical = {"amount_micros": 0, "date_min": None, "date_max": None,
                  "invoices": 0, "customers": 0, "anonymous_rows": 0}
    invoices, customers = set(), set()
    valid = 0
    try:
        with closing(sqlite3.connect(build)) as conn:
            initialize(conn)
            with conn:
                batch = []
                for sheet, row_number, raw in iter_source(source):
                    payload, fingerprint, duplicate, flags = profiler.add(sheet, raw)
                    record, reasons = transform_record(sheet, row_number, raw, payload, fingerprint, duplicate, flags)
                    exclusions.update(reasons)
                    if reasons:
                        primary_reasons[reasons[0]] += 1
                    else:
                        valid += 1
                        invoices.add(record[5])
                        if record[8] is not None:
                            customers.add(record[8])
                        else:
                            analytical["anonymous_rows"] += 1
                        analytical["amount_micros"] += record[13]
                        analytical["date_min"] = min(analytical["date_min"], record[10]) if analytical["date_min"] else record[10]
                        analytical["date_max"] = max(analytical["date_max"], record[10]) if analytical["date_max"] else record[10]
                    batch.append(record)
                    if len(batch) >= 5000:
                        load_batch(conn, batch)
                        batch.clear()
                    if profiler.rows % 100000 == 0:
                        print(f"Processed {profiler.rows:,} source rows", flush=True)
                if batch:
                    load_batch(conn, batch)
                if file_digest(source) != source_hash:
                    raise ValueError("Source changed during ETL; previous database preserved")
                analytical["invoices"], analytical["customers"] = len(invoices), len(customers)
                populate_analytics(conn)
                report = {
                    "pipeline": "insightflow_retail_v1", "source_url": SOURCE_URL,
                    "source_file": str(source.resolve()), "source_sha256": source_hash,
                    "built_at_utc": datetime.now(timezone.utc).isoformat(),
                    **profiler.report(), "valid_analytical_rows": valid,
                    "excluded_rows": profiler.rows - valid,
                    "exclusion_reasons_overlapping": dict(exclusions),
                    "primary_exclusion_reasons_disjoint": dict(primary_reasons),
                    "analytical_totals": analytical,
                }
                report["reconciliation"] = reconcile(conn, report)
                conn.execute("INSERT INTO etl_metadata VALUES ('quality_report', ?)", (json.dumps(report),))
        # Replacement is safe only after all checks and all handles close.
        os.replace(build, database)
        report["elapsed_etl_seconds"] = round(perf_counter() - start, 3)
        report["database_bytes"] = database.stat().st_size
        report["peak_process_working_set_bytes"] = peak_memory_bytes()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        if build.exists():
            build.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--database", type=Path, default=DATABASE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    report = run_etl(args.source, args.database, args.report)
    print(json.dumps({key: report[key] for key in (
        "raw_rows", "valid_analytical_rows", "excluded_rows", "reconciliation",
        "elapsed_etl_seconds", "database_bytes", "peak_process_working_set_bytes")}, indent=2))


if __name__ == "__main__":
    main()
