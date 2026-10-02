"""Fixture-backed retail UI and bounded Customer 360 regression checks."""
from datetime import datetime
from contextlib import closing
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook
from streamlit.testing.v1 import AppTest

from analytics import retail_customer_analytics as analytics
from etl.retail_config import COLUMNS, SHEETS
from etl.run_retail_etl import run_etl
from frontend import retail_dashboard as ui


class RetailDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.db = root / "retail.sqlite3"
        book = Workbook()
        book.remove(book.active)
        rows = [
            ["100001", "P1", "Product", 2, datetime(2011, 1, 1), 10, 10001, "UK"],
            ["100002", "P1", "Product", 1, datetime(2011, 2, 1), 30, 10001, "UK"],
            ["C100003", "P1", "Product", -1, datetime(2011, 2, 2), 5, 10001, "UK"],
            ["100004", "P1", "Product", 1, datetime(2011, 2, 3), 10, 10002, "France"],
            ["C100005", "P1", "Product", -1, datetime(2011, 2, 4), 7, 10003, "UK"],
        ]
        for i, name in enumerate(SHEETS):
            sheet = book.create_sheet(name)
            sheet.append(COLUMNS)
            for row in rows if i == 0 else []:
                sheet.append(row)
        source = root / "source.xlsx"
        book.save(source)
        book.close()
        run_etl(source, cls.db, root / "report.json")

    @classmethod
    def tearDownClass(cls):
        ui.query.clear()
        cls.temp.cleanup()

    def app(self, view="Executive Pulse", db=None):
        script = "from frontend.retail_dashboard import show_retail_dashboard\nshow_retail_dashboard(" + repr(str(db or self.db)) + ")"
        app = AppTest.from_string(script, default_timeout=60).run()
        if view != "Executive Pulse":
            app.radio[0].set_value(view).run()
        self.assertFalse(app.exception)
        return app

    def test_overview_kpis_use_database_and_safe_labels(self):
        app = self.app()
        metrics = {m.label: m.value for m in app.metric}
        self.assertEqual(metrics["Eligible Purchasers"], "2")
        self.assertEqual(metrics["Purchase Orders"], "3")
        self.assertEqual(metrics["Repeat Purchase Rate"], "50.0%")
        self.assertEqual(metrics["Gross Purchase Value"], "£60.00")
        self.assertEqual(metrics["Net Transaction Value"], "£48.00")
        self.assertEqual(metrics["Average Order Value"], "£20.00")
        self.assertEqual(metrics["Median Customer Net Value"], "£10.00")
        self.assertFalse(any("clv" in label.lower() or "revenue" in label.lower() for label in metrics))
        self.assertTrue(any("not predicted Customer Lifetime Value" in c.value for c in app.caption))

    def test_segments_and_scoped_filter(self):
        app = self.app("Customer Segments")
        expected = analytics.get_rfm_segment_summary(self.db)
        self.assertEqual(set(app.dataframe[0].value.Segment), set(expected.segment))
        app.multiselect[0].set_value([]).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)

    def test_retention_preserves_future_nulls_and_partial_month(self):
        with patch.object(ui, "chart", wraps=ui.chart) as render:
            app = self.app("Retention")
        heatmap = next(call.args[0] for call in render.call_args_list if call.args[0].data[0].type == "heatmap")
        self.assertTrue(math.isnan(heatmap.data[0].z[-1][-1]))
        matrix = app.dataframe[0].value
        self.assertTrue(matrix.month_0.eq(100).all())
        self.assertTrue(matrix.iloc[-1].isna()["month_1"])
        self.assertTrue(any("partial activity month" in w.value for w in app.warning))
        self.assertEqual({m.label: m.value for m in app.metric}["Median First-to-second Interval"], "31.0 days")

    def test_customer_lookup_profile_and_history(self):
        app = self.app("Customer 360")
        app.text_input[0].set_value("10001").run()
        self.assertFalse(app.exception)
        self.assertEqual({m.label: m.value for m in app.metric}["Net Ledger Value"], "£45.00")
        self.assertEqual(len(app.dataframe[0].value), 3)
        self.assertTrue(any("Signed adjustment value: -£5.00" in m.value for m in app.markdown))

    def test_unknown_customer_is_not_sql(self):
        app = self.app("Customer 360")
        app.text_input[0].set_value("' OR 1=1 --").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No eligible transaction history" in i.value for i in app.info))
        self.assertTrue(analytics.get_customer_history("' OR 1=1 --", self.db).empty)

    def test_return_only_and_single_purchase(self):
        app = self.app("Customer 360")
        app.text_input[0].set_value("10003").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Return/adjustment-only" in i.value for i in app.info))
        self.assertEqual({m.label: m.value for m in app.metric}["Recency"], "Not available")
        app.text_input[0].set_value("10002").run()
        self.assertFalse(app.exception)
        self.assertEqual({m.label: m.value for m in app.metric}["Median Order Interval"], "Not available")

    def test_missing_and_corrupt_database(self):
        root = Path(self.temp.name)
        self.assertTrue(self.app(db=root / "missing.db").warning)
        corrupt = root / "corrupt.db"
        corrupt.write_text("not a database", encoding="utf-8")
        self.assertTrue(self.app(db=corrupt).error)

    def test_empty_database(self):
        empty = Path(self.temp.name) / "empty.db"
        with closing(sqlite3.connect(empty)) as conn:
            conn.executescript((Path(__file__).resolve().parents[1] / "etl/schema.sql").read_text())
        self.assertTrue(any("no eligible transactions" in i.value for i in self.app(db=empty).info))

    def test_history_bounds_and_activity_order_grain(self):
        first = analytics.get_customer_history("10001", self.db, limit=1)
        second = analytics.get_customer_history("10001", self.db, limit=1, offset=1)
        self.assertNotEqual(first.iloc[0].invoice, second.iloc[0].invoice)
        with self.assertRaises(ValueError):
            analytics.get_customer_history("10001", self.db, limit=1000)
        self.assertEqual(analytics.get_customer_activity("10001", self.db).purchase_orders.sum(), 2)

    def test_profile_preserves_global_rfm_scores_and_ledger(self):
        rfm = analytics.get_rfm_customers(self.db).set_index("customer_key")
        ledger = analytics.get_customer_value_detail(self.db).set_index("customer_key")
        for customer in ledger.index:
            profile = analytics.get_customer_profile(customer, self.db).iloc[0]
            self.assertEqual(profile.net_value_micros, ledger.loc[customer, "net_value_micros"])
            if customer in rfm.index:
                for field in ("r_score", "f_score", "m_score", "segment", "recency_days", "frequency"):
                    self.assertEqual(profile[field], rfm.loc[customer, field])

    def test_cache_reuses_results_and_version_invalidates(self):
        ui.query.clear()
        real = ui.QUERIES["get_customer_ids"]
        with patch.dict(ui.QUERIES, {"get_customer_ids": unittest.mock.Mock(wraps=real)}):
            mock = ui.QUERIES["get_customer_ids"]
            ui.query("get_customer_ids", str(self.db), (1,))
            ui.query("get_customer_ids", str(self.db), (1,))
            self.assertEqual(mock.call_count, 1)
            ui.query("get_customer_ids", str(self.db), (2,))
            self.assertEqual(mock.call_count, 2)

    def test_main_navigation_reaches_retail(self):
        with patch("streamlit_option_menu.option_menu", return_value="Executive Pulse"), patch("streamlit.image"), patch("joblib.load", side_effect=FileNotFoundError), patch.object(ui, "DATABASE", self.db):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/adaptive_dashboard.py"), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Customer Intelligence" in m.value for m in app.markdown))

    def test_landing_branding_and_deterministic_brief(self):
        app = self.app()
        content = "\n".join(m.value for m in app.markdown)
        self.assertIn("Customer Intelligence &amp; Analytics Platform", content)
        self.assertIn("Command Center", content)
        self.assertIn("Customer Analytics", content)
        self.assertIn("Churn Intelligence", content)
        self.assertIn("✦ Intelligence Brief", content)
        self.assertIn("50.0% of eligible purchasers", content)
        segments = analytics.get_rfm_segment_summary(self.db)
        largest = segments.sort_values(["customers", "segment"], ascending=[False, True]).iloc[0]
        self.assertIn(f"{largest.segment} is the largest RFM segment", content)

    def test_clean_cohort_filter_and_collapsed_data(self):
        app = self.app("Retention")
        self.assertEqual(app.radio[1].value, "All cohorts")
        self.assertEqual(len(app.multiselect), 0)
        details = next(e for e in app.expander if e.label == "View cohort data")
        self.assertFalse(details.proto.expanded)
        app.radio[1].set_value("Choose cohorts").run()
        self.assertTrue(any("No cohorts selected" in i.value for i in app.info))
        app.multiselect[0].set_value(["2011-01"]).run()
        self.assertEqual(len(app.dataframe[0].value), 1)

    def test_single_search_rfm_indicators_and_single_period(self):
        app = self.app("Customer 360")
        self.assertEqual(len(app.text_input), 1)
        self.assertEqual(len(app.selectbox), 0)
        app.text_input[0].set_value("10002").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("plotly_chart")), 0)
        self.assertTrue(any("one month only (Feb 2011)" in i.value for i in app.info))
        profile = analytics.get_customer_profile("10002", self.db).iloc[0]
        content = "\n".join(m.value for m in app.markdown)
        for name, field in [("Recency", "r_score"), ("Frequency", "f_score"), ("Monetary", "m_score")]:
            self.assertIn(f'{name} score {int(profile[field])} out of 5', content)
        self.assertIn("03 Feb 2011", content)

    def test_goal_navigation_groups_and_retail_routes(self):
        from frontend.navigation import GROUPS
        self.assertEqual(GROUPS["PREDICTIVE AI"], ["Churn Intelligence", "AI Insights"])
        self.assertEqual(GROUPS["KNOWLEDGE"], ["Ask InsightFlow"])
        self.assertEqual(GROUPS["ANALYTICS"], ["Reports", "Settings"])
        for route in GROUPS["CUSTOMER INTELLIGENCE"]:
            with patch("streamlit_option_menu.option_menu", return_value=route), patch("joblib.load", side_effect=FileNotFoundError), patch.object(ui, "DATABASE", self.db):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/adaptive_dashboard.py"), default_timeout=60).run()
            self.assertFalse(app.exception)
            self.assertIn(route, [t.value for t in app.title])
        with patch("streamlit_option_menu.option_menu", return_value="Ask InsightFlow"), \
             patch("joblib.load", side_effect=FileNotFoundError):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "frontend/adaptive_dashboard.py"),
                default_timeout=60,
            ).run()
        self.assertFalse(app.exception)
        self.assertIn("Ask InsightFlow", [t.value for t in app.title])

    def test_predictive_navigation_preserves_both_telco_views(self):
        with patch("streamlit_option_menu.option_menu", return_value="Churn Intelligence"), patch("joblib.load", side_effect=FileNotFoundError):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/adaptive_dashboard.py"), default_timeout=60).run()
            self.assertFalse(app.exception)
            control = next(r for r in app.radio if r.label == "Telco workspace")
            self.assertEqual(control.options, ["Risk Dashboard", "Observed Telco Analytics"])
            control.set_value("Observed Telco Analytics").run()
            self.assertFalse(app.exception)
            self.assertIn("Observed Customer Analytics", [h.value for h in app.subheader])
