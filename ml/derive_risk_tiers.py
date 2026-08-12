import joblib
import pandas as pd
import numpy as np

from sklearn.base import clone
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_predict,
)


# =====================================================
# FILE PATHS
# =====================================================

DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"
MODEL_PATH = "ml/churn_model_v2.pkl"
CONFIG_PATH = "ml/champion_config.pkl"


# =====================================================
# LOAD DATA
# =====================================================

df = pd.read_csv(DATA_PATH)

df["TotalCharges"] = pd.to_numeric(
    df["TotalCharges"],
    errors="coerce",
)

df["Churn"] = (
    df["Churn"]
    .map({
        "Yes": 1,
        "No": 0,
    })
)

df = df.dropna(
    subset=["Churn"]
).copy()


X = df.drop(
    columns=[
        "Churn",
        "customerID",
    ]
)

y = df["Churn"]


# =====================================================
# RECREATE TRAINING SPLIT
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

champion = joblib.load(
    MODEL_PATH
)

config = joblib.load(
    CONFIG_PATH
)

intervention_threshold = float(
    config["threshold"]
)


# =====================================================
# OUT-OF-FOLD PROBABILITIES
# =====================================================

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

oof_probabilities = cross_val_predict(
    clone(champion),
    X_train,
    y_train,
    cv=cv,
    method="predict_proba",
    n_jobs=-1,
)[:, 1]


risk_df = pd.DataFrame({
    "Probability": oof_probabilities,
    "ActualChurn": y_train.reset_index(drop=True),
})


# =====================================================
# DECILE ANALYSIS
# =====================================================

risk_df["RiskDecile"] = pd.qcut(
    risk_df["Probability"],
    q=10,
    duplicates="drop",
)

decile_summary = (
    risk_df
    .groupby(
        "RiskDecile",
        observed=False,
    )
    .agg(
        Customers=("ActualChurn", "size"),
        AverageProbability=("Probability", "mean"),
        ActualChurnRate=("ActualChurn", "mean"),
    )
    .reset_index()
)

decile_summary["AverageProbability"] *= 100
decile_summary["ActualChurnRate"] *= 100


print("\n" + "=" * 75)
print("EMPIRICAL CHURN RISK DISTRIBUTION")
print("=" * 75)

print(
    decile_summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.2f}",
    )
)


# =====================================================
# BUSINESS RISK TIERS
# =====================================================

def assign_risk_tier(probability):

    if probability < 0.15:
        return "LOW"

    elif probability < intervention_threshold:
        return "MEDIUM"

    elif probability < 0.60:
        return "HIGH"

    else:
        return "CRITICAL"


risk_df["RiskTier"] = risk_df[
    "Probability"
].apply(assign_risk_tier)


tier_summary = (
    risk_df
    .groupby("RiskTier")
    .agg(
        Customers=("ActualChurn", "size"),
        AverageProbability=("Probability", "mean"),
        ActualChurnRate=("ActualChurn", "mean"),
    )
)


# Put tiers in logical order
tier_order = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
]

tier_summary = tier_summary.reindex(
    tier_order
)


tier_summary["AverageProbability"] *= 100
tier_summary["ActualChurnRate"] *= 100


print("\n" + "=" * 75)
print("INSIGHTFLOW RISK TIERS")
print("=" * 75)

print(
    tier_summary.to_string(
        float_format=lambda x: f"{x:.2f}",
    )
)


print("\nIntervention threshold:")
print(
    f"{intervention_threshold:.2f}"
)


# =====================================================
# SAVE RESULTS
# =====================================================

decile_summary.to_csv(
    "ml/churn_risk_deciles.csv",
    index=False,
)

tier_summary.to_csv(
    "ml/churn_risk_tiers.csv"
)

print(
    "\n✅ Risk analysis saved."
)