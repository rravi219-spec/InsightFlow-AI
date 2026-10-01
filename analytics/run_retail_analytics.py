"""Export SQL result tables and measured validation to ignored local storage."""
import argparse
from pathlib import Path
import json
from time import perf_counter

from . import retail_customer_analytics as api
from .retail_validation import validate_customer_analytics
from etl.retail_config import DATABASE, ROOT


def build_outputs(db_path=DATABASE, output_dir=ROOT / "data/processed/retail_analytics"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables, timings = {}, {}
    for name, query in [
        ("executive_kpis",api.get_customer_kpis), ("rfm_distribution",api.get_rfm_distribution),
        ("rfm_customers",api.get_rfm_customers), ("rfm_segments",api.get_rfm_segment_summary),
        ("cohort_retention",api.get_cohort_retention), ("cohort_matrix",api.get_cohort_retention_matrix),
        ("repeat_purchase",api.get_repeat_purchase_summary), ("frequency_distribution",api.get_purchase_frequency_distribution),
        ("order_intervals",api.get_order_intervals), ("customer_value",api.get_customer_value_detail),
        ("country_value",api.get_country_value_summary), ("value_concentration",api.get_customer_value_concentration),
    ]:
        start = perf_counter()
        tables[name] = query(db_path)
        timings[name] = round(perf_counter()-start, 6)
        print(f"{name}: {len(tables[name]):,} rows in {timings[name]:.3f}s", flush=True)
    validation = validate_customer_analytics(db_path,tables)
    for name, table in tables.items():
        table.to_csv(output_dir / f"{name}.csv",index=False)
    report = {"query_seconds": timings, "validation": validation,
              "executive_kpis": json.loads(tables["executive_kpis"].to_json(orient="records"))[0],
              "rfm_segments": json.loads(tables["rfm_segments"].to_json(orient="records")),
              "repeat_purchase": json.loads(tables["repeat_purchase"].to_json(orient="records"))[0],
              "concentration": json.loads(tables["value_concentration"].to_json(orient="records"))[0],
              "analysis_date": tables["rfm_customers"].analysis_date.iloc[0] if len(tables["rfm_customers"]) else None}
    (output_dir / "validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,default=DATABASE)
    parser.add_argument("--output-dir",type=Path,default=ROOT / "data/processed/retail_analytics")
    args = parser.parse_args()
    build_outputs(args.database,args.output_dir)
