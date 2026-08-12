import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    brier_score_loss,
    roc_auc_score,
    log_loss,
)

# =====================================================
# LOAD DATA
# =====================================================

DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"

df = pd.read_csv(DATA_PATH)

# Match training preparation
df["TotalCharges"] = pd.to_numeric(
    df["TotalCharges"],
    errors="coerce"
)

df = df.dropna().copy()

df["Churn"] = (
    df["Churn"]
    .map({"Yes": 1, "No": 0})
)

X = df.drop(
    columns=["Churn", "customerID"]
)

y = df["Churn"]


# =====================================================
# RECREATE HOLDOUT SPLIT
# =====================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)


# =====================================================
# LOAD CHAMPION
# =====================================================

model = joblib.load(
    "ml/churn_model_v2.pkl"
)

probabilities = model.predict_proba(
    X_test
)[:, 1]


# =====================================================
# CALIBRATION METRICS
# =====================================================

brier = brier_score_loss(
    y_test,
    probabilities
)

auc = roc_auc_score(
    y_test,
    probabilities
)

loss = log_loss(
    y_test,
    probabilities
)

print("\n" + "=" * 65)
print("CHAMPION PROBABILITY CALIBRATION")
print("=" * 65)

print(f"ROC-AUC:    {auc:.4f}")
print(f"Brier:      {brier:.4f}")
print(f"Log Loss:   {loss:.4f}")


# =====================================================
# CALIBRATION TABLE
# =====================================================

fraction_positive, mean_predicted = calibration_curve(
    y_test,
    probabilities,
    n_bins=10,
    strategy="quantile",
)

calibration_df = pd.DataFrame({
    "Predicted Probability": mean_predicted,
    "Actual Churn Rate": fraction_positive,
})

calibration_df["Calibration Gap"] = (
    calibration_df["Predicted Probability"]
    - calibration_df["Actual Churn Rate"]
).abs()

print("\nCalibration by probability bin:\n")

print(
    calibration_df.round(4).to_string(
        index=False
    )
)

print(
    "\nMean absolute calibration gap:",
    round(
        calibration_df["Calibration Gap"].mean(),
        4,
    )
)