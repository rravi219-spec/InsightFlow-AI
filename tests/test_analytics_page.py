"""Offline page tests: real SQL queries against an isolated source/database."""
from contextlib import ExitStack
from functools import partial
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from analytics import sqlite_analytics as sql


class AnalyticsPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.csv = Path(self.temp.name) / "source.csv"
        self.db = Path(self.temp.name) / "test.sqlite3"
        self.rows = pd.DataFrame({
            "customerID": ["A", "B", "C", "D"],
            "tenure": [0, 13, 25, 49],
            "Contract": ["Month-to-month", "One year", "Two year", "Two year"],
            "PaymentMethod": ["Bank", "Card", "Bank", "Card"],
            "InternetService": ["DSL", "Fiber optic", "No", "DSL"],
            "MonthlyCharges": [20, 40, 60, 80],
            "TotalCharges": ["", "520", "1500", "3920"],
            "Churn": ["Yes", "No", "Yes", "No"],
        })
        self.rows.to_csv(self.csv, index=False)

    def run_page(self, failure=None):
        with ExitStack() as stack:
            stack.enter_context(patch("streamlit_option_menu.option_menu", return_value="Analytics"))
            # Sidebar image and model artifacts are outside observed analytics.
            stack.enter_context(patch("streamlit.image"))
            stack.enter_context(patch("joblib.load", side_effect=FileNotFoundError("Test excludes model artifacts")))
            stack.enter_context(patch.object(sql, "ingest_customers", side_effect=partial(
                sql.ingest_customers, csv_path=self.csv, db_path=self.db)))
            for name in ["get_overall_customer_summary", "get_customer_segment_summary",
                         "get_payment_method_summary", "get_internet_service_summary",
                         "get_tenure_band_summary", "get_monthly_charges_distribution"]:
                effect = failure if name == "get_overall_customer_summary" and failure else partial(
                    getattr(sql, name), db_path=self.db)
                stack.enter_context(patch.object(sql, name, side_effect=effect))
            return AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "frontend/adaptive_dashboard.py"),
                default_timeout=60,
            ).run()

    def test_sql_kpis_segments_and_wording(self):
        app = self.run_page()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        metrics = {m.label: m.value for m in app.metric}
        self.assertEqual(metrics["Total Customers"], "4")
        self.assertEqual(metrics["Observed Churn Customers"], "2")
        self.assertEqual(metrics["Observed Churn Rate"], "50.0%")
        self.assertEqual(metrics["Average Monthly Charges"], "$50.00")
        self.assertEqual(metrics["Average Tenure"], "21.8 months")
        self.assertFalse(any("revenue" in label.lower() or "loss" in label.lower() for label in metrics))
        headings = [h.value for h in app.subheader]
        self.assertIn("Observed Customer Analytics", headings)
        self.assertIn("Modeled Churn Risk / ML Analytics", headings)
        contract = app.dataframe[0].value
        self.assertEqual(contract["Customers"].sum(), 4)
        self.assertEqual(contract["Observed Churn Customers"].sum(), 2)
        tenure = app.dataframe[1].value
        self.assertEqual(tenure["Customer Count"].tolist(), [1, 1, 1, 1])
        self.assertEqual(len(app.get("plotly_chart")), 5)

    def test_database_error_is_graceful(self):
        app = self.run_page(sqlite3.OperationalError("database is locked"))
        self.assertFalse(app.exception)
        self.assertIn("Observed customer analytics are unavailable", app.error[0].value)
        self.assertEqual(len(app.metric), 0)

    def test_empty_snapshot_is_graceful(self):
        self.rows.iloc[:0].to_csv(self.csv, index=False)
        app = self.run_page()
        self.assertFalse(app.exception)
        self.assertIn("No customers", app.info[0].value)
        self.assertEqual(len(app.metric), 0)


if __name__ == "__main__":
    unittest.main()
