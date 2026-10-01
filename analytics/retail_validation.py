"""Independent streaming validation; no million-row dataframe or SQL views reused."""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime
import math
from pathlib import Path
import sqlite3
from statistics import mean, median

from . import retail_customer_analytics as api
from etl.retail_config import DATABASE


def require(condition, message):
    if not condition:
        raise ValueError("Customer analytics reconciliation failed: " + message)


def validate_customer_analytics(db_path=DATABASE, outputs=None):
    if outputs is None:
        outputs = {
            "executive_kpis": api.get_customer_kpis(db_path),
            "rfm_customers": api.get_rfm_customers(db_path),
            "rfm_segments": api.get_rfm_segment_summary(db_path),
            "cohort_retention": api.get_cohort_retention(db_path),
            "repeat_purchase": api.get_repeat_purchase_summary(db_path),
            "customer_value": api.get_customer_value_detail(db_path),
            "value_concentration": api.get_customer_value_concentration(db_path),
        }
    orders, ledger = {}, defaultdict(int)
    gross = returns = lines = 0
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        end = conn.execute("SELECT DATE(MAX(invoice_timestamp)) FROM fact_transaction").fetchone()[0]
        cursor = conn.execute("""SELECT customer_key,invoice,invoice_timestamp,quantity,is_cancelled,amount_micros
            FROM fact_transaction WHERE customer_key IS NOT NULL""")
        for customer, invoice, timestamp, quantity, cancelled, amount in cursor:
            lines += 1
            ledger[customer] += amount
            if quantity > 0 and cancelled == 0:
                gross += amount
                key = (customer, invoice)
                if key not in orders:
                    orders[key] = [timestamp, 0]
                orders[key][0] = min(orders[key][0], timestamp)
                orders[key][1] += amount
            else:
                returns += amount
    by_customer = defaultdict(list)
    for (customer, invoice), (timestamp, amount) in orders.items():
        by_customer[customer].append((timestamp, invoice, amount))
    for history in by_customer.values():
        history.sort()
    repeats = sum(len(history) >= 2 for history in by_customer.values())
    kpi = outputs["executive_kpis"].iloc[0]
    expected = {"known_analytical_customers": len(by_customer), "known_ledger_customers": len(ledger),
                "eligible_transaction_lines": lines, "purchase_invoices": len(orders),
                "repeat_customers": repeats, "one_time_customers": len(by_customer)-repeats,
                "gross_purchase_micros": gross, "return_signed_micros": returns,
                "net_value_micros": sum(ledger.values())}
    for key, value in expected.items():
        require(kpi[key] == value, key)
    require(gross + returns == sum(ledger.values()), "gross plus signed returns equals net")
    rfm = outputs["rfm_customers"]
    require(rfm.customer_key.is_unique and set(rfm.customer_key) == set(by_customer), "RFM population")
    segments = Counter()
    metric_values = []
    for row in rfm.to_dict("records"):
        history = by_customer[row["customer_key"]]
        reference = date.fromisoformat(row["analysis_date"])
        recency = (reference-date.fromisoformat(history[-1][0][:10])).days
        require(row["recency_days"] == recency and row["frequency"] == len(history), "R/F independent values")
        require(row["monetary_micros"] == sum(item[2] for item in history), "M independent value")
        metric_values.append((-recency, len(history), sum(item[2] for item in history)))
    sorted_metrics = [sorted(row[i] for row in metric_values) for i in range(3)]
    for row, metrics in zip(rfm.to_dict("records"), metric_values):
        scores = []
        for value, values in zip(metrics, sorted_metrics):
            lo, hi = bisect_left(values, value), bisect_right(values, value)
            percentile = (lo+(hi-lo-1)/2)/(len(values)-1) if len(values)>1 else 0.5
            scores.append(min(5, 1+math.floor(5*percentile)))
        require(scores == [row["r_score"],row["f_score"],row["m_score"]], "tie-aware scores")
        r, f, m = scores
        segment = ("Champions" if r>=4 and f>=4 and m>=4 else "Loyal" if r>=3 and f>=4
                   else "New Customers" if r>=4 and row["frequency"]==1
                   else "Potential Loyalists" if r>=3 else "At Risk" if f>=3 else "Hibernating")
        require(row["segment"] == segment, "segment precedence")
        segments[segment] += 1
    summary = outputs["rfm_segments"]
    require(dict(zip(summary.segment,summary.customers)) == dict(segments), "segment coverage")
    require(int(summary.gross_purchase_micros.sum()) == gross, "segment gross totals")
    require(int(summary.net_value_micros.sum()) == sum(ledger[c] for c in by_customer), "segment purchaser net totals")
    detail = outputs["customer_value"]
    require(detail.customer_key.is_unique, "customer value uniqueness")
    require(dict(zip(detail.customer_key,detail.net_value_micros)) == dict(ledger), "per-customer net ledger")
    cohorts, active = Counter(), defaultdict(set)
    intervals, first_second = [], []
    for customer, history in by_customer.items():
        cohort = history[0][0][:7]
        cohorts[cohort] += 1
        for timestamp, _, _ in history:
            active[(cohort,timestamp[:7])].add(customer)
        gaps = [(datetime.fromisoformat(b[0])-datetime.fromisoformat(a[0])).total_seconds()/86400
                for a,b in zip(history,history[1:])]
        intervals.extend(gaps)
        if gaps:
            first_second.append(gaps[0])
    retention = outputs["cohort_retention"]
    require(not retention.duplicated(["cohort_month","month_offset"]).any(), "cohort cell uniqueness")
    cells = set()
    for cohort in cohorts:
        cy, cm = map(int,cohort.split('-'))
        ey, em = map(int,end[:7].split('-'))
        cells.update((cohort, offset) for offset in range((ey-cy)*12+em-cm+1))
    require(set(zip(retention.cohort_month,retention.month_offset)) == cells, "cohort observation grid")
    for row in retention.to_dict("records"):
        cohort, month = row["cohort_month"], row["activity_month"]
        cy, cm = map(int,cohort.split('-'))
        ay, am = map(int,month.split('-'))
        require(row["month_offset"] == 12*(ay-cy)+am-cm, "calendar month offset")
        expected_active = len(active[(cohort,month)])
        require(row["cohort_size"] == cohorts[cohort] and row["active_customers"] == expected_active, "cohort size/activity")
        require(math.isclose(row["retention_pct"],100*expected_active/cohorts[cohort]), "retention denominator")
        require(0 <= row["retention_pct"] <= 100, "retention bounds")
        if row["month_offset"] == 0:
            require(row["retention_pct"] == 100, "month-zero retention")
    repeat = outputs["repeat_purchase"].iloc[0]
    require(repeat.repeat_customers == repeats and repeat.one_time_customers+repeats == len(by_customer), "repeat accounting")
    require(all(gap >= 0 for gap in intervals), "nonnegative order intervals")
    require(repeat.interval_count == len(intervals), "interval count")
    for key, values, fn in [("average_interval_days",intervals,mean), ("median_interval_days",intervals,median),
                            ("average_first_second_days",first_second,mean), ("median_first_second_days",first_second,median)]:
        if values:
            require(math.isclose(repeat[key],fn(values),abs_tol=1e-8), key)
        else:
            require(pd_is_missing(repeat[key]), key)
    ranked = sorted(by_customer, key=lambda c:(-ledger[c],c))
    top_n = math.ceil(len(ranked)/10)
    concentration = outputs["value_concentration"].iloc[0]
    require(concentration.top_customer_count == top_n, "top decile headcount")
    require(concentration.top_net_value_micros == sum(ledger[c] for c in ranked[:top_n]), "top decile value")
    return {"status": "passed", "independent_source": "streamed fact rows, Python dictionaries and datetime arithmetic",
            "known_lines_checked": lines, "orders_checked": len(orders), "customers_checked": len(by_customer),
            "cohort_cells_checked": len(retention), "order_intervals_checked": len(intervals),
            "gross_plus_signed_returns_equals_net": True, "complete_rfm_segment_coverage": True}


def pd_is_missing(value):
    return value is None or (isinstance(value,float) and math.isnan(value))
