import joblib
import pandas as pd
import numpy as np

# =====================================================
# LOAD TRAINED CHAMPION
# =====================================================

MODEL_PATH = "ml/churn_model_v2.pkl"

pipeline = joblib.load(MODEL_PATH)

preprocessor = pipeline.named_steps["preprocessor"]
classifier = pipeline.named_steps["classifier"]


# =====================================================
# EXTRACT TRANSFORMED FEATURE NAMES
# =====================================================

feature_names = preprocessor.get_feature_names_out()

feature_names = [
    name.replace("numeric__", "")
        .replace("categorical__", "")
    for name in feature_names
]


# =====================================================
# FEATURE IMPORTANCE
# =====================================================

if not hasattr(classifier, "feature_importances_"):
    raise AttributeError(
        "Champion classifier does not expose feature_importances_."
    )

importances = classifier.feature_importances_


importance_df = pd.DataFrame({
    "Feature": feature_names,
    "Importance": importances,
})


importance_df = (
    importance_df
    .sort_values(
        by="Importance",
        ascending=False,
    )
    .reset_index(drop=True)
)


# =====================================================
# DISPLAY TOP DRIVERS
# =====================================================

print("\n" + "=" * 70)
print("GLOBAL CHURN DRIVERS")
print("=" * 70)

print(
    importance_df
    .head(20)
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)


# =====================================================
# SAVE REPORT
# =====================================================

importance_df.to_csv(
    "ml/churn_feature_importance.csv",
    index=False,
)

print(
    "\n✅ Feature importance report saved to "
    "ml/churn_feature_importance.csv"
)