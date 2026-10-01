import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analytics.sqlite_analytics import (
    ingest_customers, get_customer_segment_summary, get_tenure_band_summary,
    get_overall_customer_summary, get_payment_method_summary,
    get_internet_service_summary, get_monthly_charges_distribution,
)


class SQLiteAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.csv = Path(self.temp.name) / "source.csv"
        self.db = Path(self.temp.name) / "analytics.sqlite3"
        self.df = pd.DataFrame({
            "customerID": ["001", "002", "003", "004", "005", "006", "007", "008"],
            "tenure": [0, 12, 13, 24, 25, 48, 49, 72],
            "Contract": ["Monthly"] * 4 + ["Annual"] * 4,
            "PaymentMethod": ["Bank"] * 8,
            "InternetService": ["DSL"] * 8,
            "MonthlyCharges": [10, 20, 30, 40, 50, 60, 70, 80],
            "TotalCharges": [" ", "240", "390", "960", "1250", "2880", "3430", "5760"],
            "Churn": ["Yes", "No", "Yes", "No", "No", "No", "No", "No"],
        })

    def ingest(self):
        self.df.to_csv(self.csv, index=False)
        return ingest_customers(self.csv, self.db)

    def test_required_schema(self):
        self.df = self.df.drop(columns="Contract")
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            self.ingest()
        self.assertFalse(self.db.exists())

    def test_duplicate_customer(self):
        self.df.loc[1, "customerID"] = " 001 "
        with self.assertRaisesRegex(ValueError, "duplicate_customer_ids"):
            self.ingest()

    def test_missing_customer(self):
        for value in ["", " ", None]:
            with self.subTest(value=value):
                self.df.loc[0, "customerID"] = value
                with self.assertRaisesRegex(ValueError, "missing_customer_ids"):
                    self.ingest()

    def test_invalid_churn(self):
        for value in ["Maybe", "", "1"]:
            with self.subTest(value=value):
                self.df.loc[0, "Churn"] = value
                with self.assertRaisesRegex(ValueError, "invalid_churn_labels"):
                    self.ingest()

    def test_invalid_tenure(self):
        self.df["tenure"] = self.df["tenure"].astype(object)
        for value in [-1, 73, 1.5, "bad", "", "inf"]:
            with self.subTest(value=value):
                self.df.loc[0, "tenure"] = value
                with self.assertRaisesRegex(ValueError, "invalid_tenure_values"):
                    self.ingest()

    def test_invalid_monthly_charges(self):
        self.df["MonthlyCharges"] = self.df["MonthlyCharges"].astype(object)
        for value in [-1, "bad", "", "inf"]:
            with self.subTest(value=value):
                self.df.loc[0, "MonthlyCharges"] = value
                with self.assertRaisesRegex(ValueError, "invalid_monthly_charges"):
                    self.ingest()

    def test_invalid_total_charges(self):
        for value in ["-1", "bad", "inf", "NaN"]:
            with self.subTest(value=value):
                self.df.loc[0, "TotalCharges"] = value
                with self.assertRaisesRegex(ValueError, "invalid_total_charges"):
                    self.ingest()

    def test_missing_total_charges_is_null(self):
        self.assertEqual(self.ingest()["missing_total_charges"], 1)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertIsNone(conn.execute(
                "SELECT total_charges FROM customers WHERE customer_id='001'"
            ).fetchone()[0])

    def test_idempotent_upsert(self):
        self.assertEqual(self.ingest()["stored_rows"], 8)
        self.assertEqual(self.ingest()["stored_rows"], 8)
        self.df.loc[0, "MonthlyCharges"] = 99
        self.assertEqual(self.ingest()["stored_rows"], 8)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(conn.execute(
                "SELECT monthly_charges FROM customers WHERE customer_id='001'"
            ).fetchone()[0], 99)

    def test_primary_key(self):
        self.ingest()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT customer_id) FROM customers"
            ).fetchone(), (8, 8))
            for customer_id in ["001", None]:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute("INSERT INTO customers(customer_id, observed_churn) VALUES (?, 0)",
                                 (customer_id,))

    def test_contract_summary(self):
        self.ingest()
        result = get_customer_segment_summary(self.db).set_index("contract")
        self.assertEqual(result.loc["Monthly"].tolist(), [4, 2, 50, 12.3, 25])
        self.assertEqual(result.loc["Annual"].tolist(), [4, 0, 0, 48.5, 65])

    def test_overall_reconciliation(self):
        self.ingest()
        rows = self.df.to_dict("records")
        actual = get_overall_customer_summary(self.db)
        churn = sum(r["Churn"] == "Yes" for r in rows)
        self.assertEqual(actual["customers"], len(rows))
        self.assertEqual(actual["observed_churn_customers"], churn)
        self.assertAlmostEqual(actual["observed_churn_rate_pct"], 100 * churn / len(rows))
        self.assertAlmostEqual(actual["avg_tenure_months"], sum(r["tenure"] for r in rows) / len(rows))
        self.assertAlmostEqual(actual["avg_monthly_charges"], sum(r["MonthlyCharges"] for r in rows) / len(rows))

    def test_segment_reconciliation(self):
        self.df["PaymentMethod"] = ["Bank", "Card"] * 4
        self.df["InternetService"] = ["DSL", "Fiber", "None", "DSL"] * 2
        self.ingest()
        rows = self.df.to_dict("records")
        for source_column, sql_column, query in [
            ("Contract", "contract", get_customer_segment_summary),
            ("PaymentMethod", "payment_method", get_payment_method_summary),
            ("InternetService", "internet_service", get_internet_service_summary),
        ]:
            result = query(self.db).set_index(sql_column)
            self.assertEqual(set(result.index), {r[source_column] for r in rows})
            for label in result.index:
                group = [r for r in rows if r[source_column] == label]
                churn = sum(r["Churn"] == "Yes" for r in group)
                self.assertEqual(result.loc[label, "customers"], len(group))
                self.assertAlmostEqual(result.loc[label, "observed_churn_rate_pct"],
                                       100 * churn / len(group), delta=0.0051)
                self.assertAlmostEqual(result.loc[label, "avg_monthly_charges"],
                                       sum(r["MonthlyCharges"] for r in group) / len(group), delta=0.0051)

    def test_tenure_reconciliation(self):
        self.ingest()
        rows = self.df.to_dict("records")
        result = get_tenure_band_summary(self.db).set_index("tenure_band")
        for label, low, high in [("0-12 months", 0, 12), ("13-24 months", 13, 24),
                                 ("25-48 months", 25, 48), ("49+ months", 49, 72)]:
            group = [r for r in rows if low <= r["tenure"] <= high]
            churn = sum(r["Churn"] == "Yes" for r in group)
            self.assertEqual(result.loc[label, "customers"], len(group))
            self.assertEqual(result.loc[label, "observed_churn_customers"], churn)
            self.assertAlmostEqual(result.loc[label, "observed_churn_rate_pct"], 100 * churn / len(group))

    def test_empty_snapshot(self):
        self.df = self.df.iloc[:0]
        self.ingest()
        actual = get_overall_customer_summary(self.db)
        self.assertEqual(actual["customers"], 0)
        self.assertEqual(actual["observed_churn_customers"], 0)
        self.assertIsNone(actual["observed_churn_rate_pct"])
        self.assertTrue(get_payment_method_summary(self.db).empty)

    def test_charges_distribution(self):
        self.ingest()
        actual = get_monthly_charges_distribution(self.db)
        self.assertEqual(actual["MonthlyCharges"].tolist(), self.df["MonthlyCharges"].tolist())
        self.assertEqual(actual["Customer Status"].tolist(),
                         ["Churned" if v == "Yes" else "Retained" for v in self.df["Churn"]])

    def test_tenure_bands(self):
        self.ingest()
        result = get_tenure_band_summary(self.db)
        self.assertEqual(result["tenure_band"].tolist(),
                         ["0-12 months", "13-24 months", "25-48 months", "49+ months"])
        self.assertEqual(result["customers"].tolist(), [2, 2, 2, 2])
        self.assertEqual(result["observed_churn_rate_pct"].tolist(), [50, 50, 0, 0])
        self.assertEqual(result["avg_monthly_charges"].tolist(), [15, 35, 55, 75])

    def test_snapshot_refresh(self):
        self.ingest()
        self.df = self.df.iloc[1:]
        self.assertEqual(self.ingest()["stored_rows"], 7)

    def test_invalid_refresh_preserves_database(self):
        self.ingest()
        self.df.loc[0, "Churn"] = "bad"
        with self.assertRaises(ValueError):
            self.ingest()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0], 8)


if __name__ == "__main__":
    unittest.main()
