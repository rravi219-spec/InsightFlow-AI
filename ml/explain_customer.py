import joblib
import pandas as pd
import numpy as np
import shap

from recommend_actions import (
    get_risk_tier,
    get_recommendations,
)
# =====================================================
# FILE PATHS
# =====================================================

MODEL_PATH = "ml/churn_model_v2.pkl"
CONFIG_PATH = "ml/champion_config.pkl"
DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"


# =====================================================
# LOAD MODEL + CONFIG
# =====================================================

pipeline = joblib.load(MODEL_PATH)
config = joblib.load(CONFIG_PATH)

threshold = config["threshold"]

preprocessor = pipeline.named_steps["preprocessor"]
classifier = pipeline.named_steps["classifier"]


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

df = df.dropna(subset=["Churn"]).copy()


# =====================================================
# SELECT SAMPLE CUSTOMER
# =====================================================

customer_index = 0

customer_row = df.iloc[
    [customer_index]
].copy()

customer_id = customer_row[
    "customerID"
].iloc[0]

actual_churn = int(
    customer_row["Churn"].iloc[0]
)


# =====================================================
# PREPARE FEATURES
# =====================================================

X_customer = customer_row.drop(
    columns=[
        "Churn",
        "customerID",
    ]
)


# =====================================================
# PREDICTION
# =====================================================

churn_probability = pipeline.predict_proba(
    X_customer
)[0, 1]

prediction = int(
    churn_probability >= threshold
)


# =====================================================
# TRANSFORM CUSTOMER FOR SHAP
# =====================================================

X_transformed = preprocessor.transform(
    X_customer
)

feature_names = preprocessor.get_feature_names_out()

feature_names = [
    name.replace("numeric__", "")
        .replace("categorical__", "")
    for name in feature_names
]


# =====================================================
# SHAP EXPLANATION
# =====================================================

explainer = shap.TreeExplainer(
    classifier
)

shap_values = explainer.shap_values(
    X_transformed
)

if isinstance(shap_values, list):
    shap_values = shap_values[1]

shap_values = np.array(
    shap_values
).reshape(-1)


# =====================================================
# BUILD CONTRIBUTION TABLE
# =====================================================

explanation_df = pd.DataFrame({
    "Feature": feature_names,
    "SHAP Value": shap_values,
})

explanation_df["Absolute Impact"] = (
    explanation_df["SHAP Value"]
    .abs()
)

explanation_df = (
    explanation_df
    .sort_values(
        "Absolute Impact",
        ascending=False,
    )
    .reset_index(drop=True)
)


# =====================================================
# DISPLAY RESULTS
# =====================================================

print("\n" + "=" * 70)
print("CUSTOMER-LEVEL CHURN EXPLANATION")
print("=" * 70)

print(f"\nCustomer ID: {customer_id}")

print(
    f"Churn probability: "
    f"{churn_probability * 100:.2f}%"
)

print(
    f"Decision threshold: "
    f"{threshold:.2f}"
)

print(
    f"Predicted churn: "
    f"{'YES' if prediction == 1 else 'NO'}"
)

print(
    f"Actual churn: "
    f"{'YES' if actual_churn == 1 else 'NO'}"
)


print("\nTOP CUSTOMER-SPECIFIC MODEL DRIVERS")
print("-" * 70)

print(
    explanation_df
    .head(10)
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)
# =====================================================
# INSIGHTFLOW CUSTOMER SUCCESS INTELLIGENCE
# =====================================================

risk_tier = get_risk_tier(
    churn_probability
)

customer_dict = (
    X_customer.iloc[0].to_dict()
)

recommendations = get_recommendations(
    customer_dict,
    risk_tier,
)


print("\n" + "=" * 70)
print("INSIGHTFLOW CUSTOMER SUCCESS INTELLIGENCE")
print("=" * 70)

print(
    f"\nRisk Tier: {risk_tier}"
)

print(
    f"Churn Probability: "
    f"{churn_probability * 100:.2f}%"
)

print("\nRECOMMENDED CSM ACTIONS")
print("-" * 70)

for number, action in enumerate(
    recommendations,
    start=1,
):
    print(
        f"{number}. {action}"
    )