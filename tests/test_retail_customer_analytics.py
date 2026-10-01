from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from analytics import retail_customer_analytics as a
from analytics.retail_validation import validate_customer_analytics
from etl.retail_config import COLUMNS, SHEETS
from etl.run_retail_etl import run_etl


class RetailCustomerAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.db = root / "source.xlsx", root / "retail.sqlite3"
        self.report = root / "report.json"
        self.rows = []

        def add(invoice, customer, when, qty, price, country="UK"):
            self.rows.append([invoice, "P1", "Product", qty, datetime.fromisoformat(when), price, customer, country])

        add("100001", 10001, "2010-12-15T10:00:00", 2, 10)
        add("100001", 10001, "2010-12-15T10:00:00", 1, 5)
        add("100001", 10001, "2010-12-15T10:00:00", 1, 5)  # retained duplicate occurrence
        add("100002", 10001, "2011-01-15T10:00:00", 1, 40)
        add("100003", 10001, "2011-01-15T22:00:00", 1, 10)  # same-day distinct invoice
        add("C100001", 10001, "2011-01-20T10:00:00", -1, 10)
        add("100004", 10002, "2010-12-20T10:00:00", 1, 20)
        add("100005", 10002, "2011-02-20T10:00:00", 1, 30, "France")
        add("100006", 10003, "2011-01-10T10:00:00", 1, 15)
        add("C100007", 10004, "2011-02-10T10:00:00", -1, 7)  # return only
        add("100008", None, "2011-03-31T10:00:00", 1, 100)  # observation end, anonymous
        add("100009", 10005, "2011-03-01T10:00:00", 1, 10)
        add("C100010", 10005, "2011-03-02T10:00:00", 1, 2)  # anomalous positive cancellation
        add("100011", 10002, "2011-02-22T10:00:00", -1, 3)  # non-C negative adjustment
        add("100012", 10006, "2011-03-03T10:00:00", 1, 0)  # ETL exclusion
        self.build()

    def build(self):
        book = Workbook()
        book.remove(book.active)
        for i, sheet in enumerate(SHEETS):
            ws = book.create_sheet(sheet)
            ws.append(COLUMNS)
            for row in self.rows if i == 0 else []:
                ws.append(row)
        book.save(self.source)
        book.close()
        run_etl(self.source, self.db, self.report)

    def test_order_aggregation_and_duplicate_lines(self):
        orders = a.get_purchase_orders(self.db)
        self.assertEqual(len(orders), 7)
        row = orders[orders.invoice == "100001"].iloc[0]
        self.assertEqual(row.purchase_lines, 3)
        self.assertEqual(row.gross_purchase_micros, 30_000_000)

    def test_returns_preserve_sign_and_never_become_orders(self):
        k = a.get_customer_kpis(self.db).iloc[0]
        self.assertEqual(k.gross_purchase_micros, 155_000_000)
        self.assertEqual(k.return_signed_micros, -18_000_000)
        self.assertEqual(k.net_value_micros, 137_000_000)
        self.assertEqual(k.positive_cancellation_lines, 1)
        self.assertEqual(k.return_only_customers, 1)
        self.assertAlmostEqual(k.average_order_value_gbp, 155/7)

    def test_anonymous_exclusion_and_population(self):
        k = a.get_customer_kpis(self.db).iloc[0]
        self.assertEqual(k.known_analytical_customers, 4)
        self.assertEqual(k.known_ledger_customers, 5)
        self.assertEqual(k.anonymous_lines, 1)
        self.assertEqual(k.eligible_transaction_lines, 13)

    def test_rfm_recency_and_reference_date(self):
        rfm = a.get_rfm_customers(self.db).set_index("customer_key")
        self.assertEqual(set(rfm.analysis_date), {"2011-04-01"})
        self.assertEqual(rfm.loc["10001", "recency_days"], (date(2011,4,1)-date(2011,1,15)).days)
        with self.assertRaises(ValueError):
            a.get_rfm_customers(self.db, "2011-03-01")

    def test_rfm_frequency_and_monetary(self):
        rfm = a.get_rfm_customers(self.db).set_index("customer_key")
        self.assertEqual(rfm.loc["10001", "frequency"], 3)
        self.assertEqual(rfm.loc["10001", "monetary_micros"], 80_000_000)
        self.assertNotIn("10004", rfm.index)

    def test_segment_assignment_and_coverage(self):
        rfm = a.get_rfm_customers(self.db).set_index("customer_key")
        self.assertEqual(rfm.segment.to_dict(), {
            "10001": "At Risk", "10002": "Champions", "10003": "Hibernating", "10005": "New Customers"})
        summary = a.get_rfm_segment_summary(self.db)
        self.assertEqual(summary.customers.sum(), len(rfm))
        self.assertAlmostEqual(summary.customer_pct.sum(), 100)
        self.assertTrue(rfm.index.is_unique)

    def test_equal_values_receive_equal_scores(self):
        rfm = a.get_rfm_customers(self.db).set_index("customer_key")
        self.assertEqual(rfm.loc["10003", "f_score"], rfm.loc["10005", "f_score"])
        self.rows = [self.rows[0], ["200001", "P1", "Product", 2, self.rows[0][4], 10, 99999, "UK"]]
        self.build()
        rfm = a.get_rfm_customers(self.db)
        self.assertTrue((rfm[["r_score", "f_score", "m_score"]] == 3).all().all())

    def test_cohort_assignment_and_cross_year_offset(self):
        cohorts = a.get_cohort_retention(self.db)
        dec = cohorts[cohorts.cohort_month == "2010-12"].set_index("month_offset")
        self.assertEqual(dec.cohort_size.tolist(), [2,2,2,2])
        self.assertEqual(dec.active_customers.tolist(), [2,1,1,0])
        self.assertEqual(dec.retention_pct.tolist(), [100,50,50,0])
        self.assertEqual(dec.loc[1,"activity_month"], "2011-01")

    def test_month_zero_retention_and_matrix_censoring(self):
        cohorts = a.get_cohort_retention(self.db)
        self.assertTrue((cohorts[cohorts.month_offset == 0].retention_pct == 100).all())
        self.assertTrue(cohorts.retention_pct.between(0,100).all())
        matrix = a.get_cohort_retention_matrix(self.db).set_index("cohort_month")
        self.assertEqual(matrix.loc["2010-12", "month_3"], 0)
        self.assertTrue(__import__('pandas').isna(matrix.loc["2011-03", "month_1"]))

    def test_partial_month_flag(self):
        self.rows[10][4] = datetime(2011,3,15)
        self.build()
        cohorts = a.get_cohort_retention(self.db)
        self.assertTrue((cohorts[cohorts.activity_month == "2011-03"].is_partial_month == 1).all())

    def test_repeat_purchase_classification(self):
        result = a.get_repeat_purchase_summary(self.db).iloc[0]
        self.assertEqual((result.one_time_customers,result.repeat_customers), (2,2))
        self.assertEqual(result.repeat_purchase_rate_pct, 50)
        distribution = a.get_purchase_frequency_distribution(self.db)
        self.assertEqual(distribution.customers.sum(), 4)

    def test_interpurchase_intervals(self):
        intervals = a.get_order_intervals(self.db)
        actual = intervals[intervals.interval_days.notna()].interval_days.tolist()
        self.assertEqual(actual, [31,0.5,62])
        result = a.get_repeat_purchase_summary(self.db).iloc[0]
        self.assertAlmostEqual(result.average_interval_days, 93.5/3)
        self.assertEqual(result.median_interval_days, 31)
        self.assertEqual(result.average_first_second_days, 46.5)
        self.assertEqual(result.median_first_second_days, 46.5)

    def test_historical_value_and_country_reconciliation(self):
        detail = a.get_customer_value_detail(self.db).set_index("customer_key")
        self.assertEqual(detail.net_value_micros.to_dict(), {
            "10001":70_000_000, "10002":47_000_000, "10003":15_000_000,
            "10004":-7_000_000, "10005":12_000_000})
        country = a.get_country_value_summary(self.db)
        self.assertEqual(country.net_value_micros.sum(), 137_000_000)
        self.assertEqual(a.get_rfm_segment_summary(self.db).net_value_micros.sum(), 144_000_000)

    def test_top_customer_concentration(self):
        c = a.get_customer_value_concentration(self.db).iloc[0]
        self.assertEqual(c.eligible_customers, 4)
        self.assertEqual(c.top_customer_count, 1)
        self.assertEqual(c.top_net_value_micros, 70_000_000)
        self.assertEqual(c.eligible_net_value_micros, 144_000_000)
        self.assertAlmostEqual(c.top_10pct_share_pct, 100*70/144)

    def test_concentration_ties_and_rounded_up_headcount(self):
        self.rows = [[str(200000+i), "P1", "Product", 1, datetime(2011,1,1), 10, 10000+i, "UK"]
                     for i in range(11)]
        self.build()
        concentration = a.get_customer_value_concentration(self.db).iloc[0]
        self.assertEqual(concentration.top_customer_count, 2)
        self.assertEqual(concentration.top_net_value_micros, 20_000_000)
        self.assertAlmostEqual(concentration.top_10pct_share_pct, 100*2/11)
        self.assertEqual(a.get_customer_value_detail(self.db).customer_key.iloc[:2].tolist(), ["10000","10001"])

    def test_return_only_population_has_no_invented_behavior(self):
        self.rows = [self.rows[9]]
        self.build()
        self.assertTrue(a.get_rfm_customers(self.db).empty)
        self.assertTrue(a.get_cohort_retention(self.db).empty)
        self.assertEqual(a.get_customer_kpis(self.db).iloc[0].return_only_customers, 1)
        self.assertEqual(validate_customer_analytics(self.db)["status"], "passed")

    def test_independent_fixture_reconciliation(self):
        orders, customer_net = defaultdict(int), defaultdict(int)
        for invoice, _, _, qty, _, price, customer, _ in self.rows:
            if customer is None or price <= 0:
                continue
            amount = int(Decimal(str(price)) * qty * 1_000_000)
            customer_net[str(customer)] += amount
            if qty > 0 and not str(invoice).startswith("C"):
                orders[(str(customer), str(invoice))] += amount
        k = a.get_customer_kpis(self.db).iloc[0]
        self.assertEqual(k.net_value_micros, sum(customer_net.values()))
        self.assertEqual(k.gross_purchase_micros, sum(orders.values()))
        self.assertEqual(k.purchase_invoices, len(orders))
        self.assertEqual(k.known_analytical_customers, len({key[0] for key in orders}))
        self.assertEqual(validate_customer_analytics(self.db)["status"], "passed")

    def test_empty_population(self):
        self.rows = []
        self.build()
        self.assertEqual(a.get_customer_kpis(self.db).iloc[0].known_analytical_customers, 0)
        self.assertTrue(a.get_rfm_customers(self.db).empty)
        self.assertTrue(a.get_cohort_retention(self.db).empty)
        self.assertTrue(a.get_cohort_retention_matrix(self.db).empty)
        self.assertEqual(a.get_repeat_purchase_summary(self.db).iloc[0].purchasers, 0)
        self.assertEqual(validate_customer_analytics(self.db)["status"], "passed")


if __name__ == "__main__":
    unittest.main()
