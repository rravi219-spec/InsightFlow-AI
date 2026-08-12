import pandas as pd
import numpy as np
import joblib

from pathlib import Path

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_validate,
)

from sklearn.compose import ColumnTransformer

from sklearn.pipeline import Pipeline

from sklearn.preprocessing import (
    OneHotEncoder,
    StandardScaler,
)

from sklearn.impute import SimpleImputer

from sklearn.linear_model import LogisticRegression

from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
)
# =====================================================
# DATASET CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

DATA_PATH = PROJECT_ROOT / "data" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"

if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"Dataset not found at: {DATA_PATH}\n"
        "Create a 'data' folder in the project root and place the Telco CSV inside it."
    )


# =====================================================
# LOAD DATA
# =====================================================

df = pd.read_csv(DATA_PATH)

print(f"✅ Dataset loaded: {df.shape[0]:,} rows x {df.shape[1]} columns")
print("\nColumns:")
print(df.columns.tolist())
# =====================================================
# DATA VALIDATION AND CLEANING
# =====================================================

required_columns = ["Churn", "customerID", "TotalCharges"]

missing_required = [
    column for column in required_columns
    if column not in df.columns
]

if missing_required:
    raise ValueError(
        f"Missing required columns: {missing_required}"
    )


# Convert TotalCharges to numeric
df["TotalCharges"] = pd.to_numeric(
    df["TotalCharges"],
    errors="coerce",
)


# Remove rows where target is missing
df = df.dropna(subset=["Churn"])


# Convert churn labels to binary target
df["Churn"] = (
    df["Churn"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({
        "yes": 1,
        "no": 0,
    })
)


# Remove rows with invalid churn labels
df = df.dropna(subset=["Churn"])

df["Churn"] = df["Churn"].astype(int)


# =====================================================
# FEATURE / TARGET SPLIT
# =====================================================

X = df.drop(
    columns=[
        "Churn",
        "customerID",
    ]
)

y = df["Churn"]


# =====================================================
# BASIC DATASET CHECKS
# =====================================================

print("\n" + "=" * 60)
print("V2 DATA PREPARATION")
print("=" * 60)

print(f"Rows after cleaning: {len(df):,}")
print(f"Features available: {X.shape[1]}")
print(f"Churn cases: {int(y.sum()):,}")
print(f"Non-churn cases: {int((y == 0).sum()):,}")
print(f"Observed churn rate: {y.mean() * 100:.2f}%")

print("\nMissing values by feature:")
print(
    X.isna()
    .sum()
    .sort_values(ascending=False)
    .head(10)
)
# =====================================================
# COLUMN TYPE DETECTION
# =====================================================

numeric_features = (
    X.select_dtypes(include=["int64", "float64"])
    .columns
    .tolist()
)

categorical_features = (
    X.select_dtypes(exclude=["int64", "float64"])
    .columns
    .tolist()
)

print("\nNumeric features:")
print(numeric_features)

print("\nCategorical features:")
print(categorical_features)
# =====================================================
# TRAIN / TEST SPLIT
# =====================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

print("\n" + "=" * 60)
print("TRAIN / TEST SPLIT")
print("=" * 60)

print(f"Training customers: {len(X_train):,}")
print(f"Testing customers:  {len(X_test):,}")
print(f"Training churn rate: {y_train.mean() * 100:.2f}%")
print(f"Testing churn rate:  {y_test.mean() * 100:.2f}%")


# =====================================================
# PREPROCESSING PIPELINES
# =====================================================

numeric_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        (
            "scaler",
            StandardScaler(),
        ),
    ]
)

categorical_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent"),
        ),
        (
            "onehot",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False,
            ),
        ),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_transformer,
            numeric_features,
        ),
        (
            "categorical",
            categorical_transformer,
            categorical_features,
        ),
    ]
)

print("\n✅ Preprocessing pipeline created successfully.")
# =====================================================
# MODEL DEFINITIONS
# =====================================================

models = {
    "Logistic Regression": LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    ),

    "Random Forest": RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    ),

    "Gradient Boosting": GradientBoostingClassifier(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=3,
        random_state=42,
    ),
}


# =====================================================
# STRATIFIED CROSS-VALIDATION
# =====================================================

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)


scoring = {
    "roc_auc": "roc_auc",
    "pr_auc": "average_precision",
    "precision": "precision",
    "recall": "recall",
    "f1": "f1",
}


# =====================================================
# MODEL COMPARISON
# =====================================================

results = []

print("\n" + "=" * 70)
print("⚔️ CHURN V2 — MODEL BATTLE")
print("=" * 70)


for model_name, model in models.items():

    print(f"\nTraining: {model_name}...")

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", model),
        ]
    )

    cv_scores = cross_validate(
        pipeline,
        X_train,
        y_train,
        cv=cv,
        scoring=scoring,
        n_jobs=-1,
    )

    result = {
        "Model": model_name,
        "ROC-AUC": cv_scores["test_roc_auc"].mean(),
        "PR-AUC": cv_scores["test_pr_auc"].mean(),
        "Precision": cv_scores["test_precision"].mean(),
        "Recall": cv_scores["test_recall"].mean(),
        "F1": cv_scores["test_f1"].mean(),
    }

    results.append(result)

    print(
        f"ROC-AUC: {result['ROC-AUC']:.4f} | "
        f"PR-AUC: {result['PR-AUC']:.4f} | "
        f"Recall: {result['Recall']:.4f} | "
        f"F1: {result['F1']:.4f}"
    )


# =====================================================
# RESULTS TABLE
# =====================================================

results_df = pd.DataFrame(results)

results_df = results_df.sort_values(
    by="ROC-AUC",
    ascending=False,
).reset_index(drop=True)


print("\n" + "=" * 70)
print("🏆 CROSS-VALIDATION RESULTS")
print("=" * 70)

print(
    results_df.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)
# =====================================================
# HOLDOUT TEST EVALUATION
# =====================================================

from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix,
)

print("\n" + "=" * 70)
print("HOLDOUT TEST RESULTS")
print("=" * 70)

test_results = []

fitted_models = {}

for model_name, model in models.items():

    print(f"\nTesting: {model_name}")

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", model),
        ]
    )

    # Train using the entire training dataset
    pipeline.fit(X_train, y_train)

    # Predictions
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    # Save fitted pipeline for later
    fitted_models[model_name] = pipeline

    result = {
        "Model": model_name,
        "Accuracy": accuracy_score(y_test, y_pred),
        "ROC-AUC": roc_auc_score(y_test, y_prob),
        "PR-AUC": average_precision_score(y_test, y_prob),
        "Precision": precision_score(y_test, y_pred),
        "Recall": recall_score(y_test, y_pred),
        "F1": f1_score(y_test, y_pred),
    }

    test_results.append(result)

    print(f"ROC-AUC:  {result['ROC-AUC']:.4f}")
    print(f"PR-AUC:   {result['PR-AUC']:.4f}")
    print(f"Precision:{result['Precision']:.4f}")
    print(f"Recall:   {result['Recall']:.4f}")
    print(f"F1:       {result['F1']:.4f}")

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))


test_results_df = pd.DataFrame(test_results)

test_results_df = test_results_df.sort_values(
    by="ROC-AUC",
    ascending=False,
).reset_index(drop=True)

print("\n" + "=" * 70)
print("FINAL HOLDOUT COMPARISON")
print("=" * 70)

print(
    test_results_df.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)
# =====================================================
# THRESHOLD ANALYSIS USING TRAINING DATA ONLY
# =====================================================

from sklearn.model_selection import cross_val_predict
import numpy as np

print("\n" + "=" * 70)
print("THRESHOLD ANALYSIS — OUT-OF-FOLD TRAINING PREDICTIONS")
print("=" * 70)

threshold_results = []

for model_name, model in models.items():

    print(f"\nAnalyzing thresholds: {model_name}")

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", model),
        ]
    )

    # Out-of-fold probabilities.
    # Every training customer is predicted by a model
    # that did NOT train on that customer.
    oof_probabilities = cross_val_predict(
        pipeline,
        X_train,
        y_train,
        cv=cv,
        method="predict_proba",
        n_jobs=-1,
    )[:, 1]

    for threshold in np.arange(0.20, 0.81, 0.05):

        predictions = (
            oof_probabilities >= threshold
        ).astype(int)

        precision = precision_score(
            y_train,
            predictions,
            zero_division=0,
        )

        recall = recall_score(
            y_train,
            predictions,
            zero_division=0,
        )

        f1 = f1_score(
            y_train,
            predictions,
            zero_division=0,
        )

        threshold_results.append({
            "Model": model_name,
            "Threshold": threshold,
            "Precision": precision,
            "Recall": recall,
            "F1": f1,
        })


threshold_df = pd.DataFrame(threshold_results)

print("\nTOP THRESHOLD BY F1 FOR EACH MODEL")
print("-" * 70)

for model_name in models.keys():

    model_thresholds = threshold_df[
        threshold_df["Model"] == model_name
    ]

    best_row = model_thresholds.loc[
        model_thresholds["F1"].idxmax()
    ]

    print(f"\n{model_name}")
    print(f"Best threshold: {best_row['Threshold']:.2f}")
    print(f"Precision:      {best_row['Precision']:.4f}")
    print(f"Recall:         {best_row['Recall']:.4f}")
    print(f"F1:             {best_row['F1']:.4f}")
    # =====================================================
# HYPERPARAMETER TUNING
# =====================================================

from sklearn.model_selection import RandomizedSearchCV

print("\n" + "=" * 70)
print("HYPERPARAMETER TUNING")
print("=" * 70)


# -----------------------------------------------------
# 1. LOGISTIC REGRESSION
# -----------------------------------------------------

logistic_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ]
)

logistic_params = {
    "classifier__C": [
        0.01,
        0.05,
        0.1,
        0.5,
        1,
        2,
        5,
        10,
    ]
}

logistic_search = RandomizedSearchCV(
    estimator=logistic_pipeline,
    param_distributions=logistic_params,
    n_iter=8,
    scoring="roc_auc",
    cv=cv,
    n_jobs=-1,
    random_state=42,
)

print("\nTuning Logistic Regression...")

logistic_search.fit(
    X_train,
    y_train,
)

print("Best Logistic parameters:")
print(logistic_search.best_params_)

print(
    f"Best Logistic CV ROC-AUC: "
    f"{logistic_search.best_score_:.4f}"
)


# -----------------------------------------------------
# 2. RANDOM FOREST
# -----------------------------------------------------

rf_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            RandomForestClassifier(
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ]
)

rf_params = {
    "classifier__n_estimators": [
        200,
        300,
        500,
        700,
    ],

    "classifier__max_depth": [
        None,
        5,
        8,
        12,
        16,
    ],

    "classifier__min_samples_split": [
        2,
        5,
        10,
        20,
    ],

    "classifier__min_samples_leaf": [
        1,
        2,
        4,
        8,
    ],

    "classifier__max_features": [
        "sqrt",
        "log2",
        None,
    ],
}

rf_search = RandomizedSearchCV(
    estimator=rf_pipeline,
    param_distributions=rf_params,
    n_iter=25,
    scoring="roc_auc",
    cv=cv,
    n_jobs=-1,
    random_state=42,
)

print("\nTuning Random Forest...")

rf_search.fit(
    X_train,
    y_train,
)

print("Best Random Forest parameters:")
print(rf_search.best_params_)

print(
    f"Best Random Forest CV ROC-AUC: "
    f"{rf_search.best_score_:.4f}"
)


# -----------------------------------------------------
# 3. GRADIENT BOOSTING
# -----------------------------------------------------

gb_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            GradientBoostingClassifier(
                random_state=42,
            ),
        ),
    ]
)

gb_params = {
    "classifier__n_estimators": [
        100,
        150,
        200,
        300,
    ],

    "classifier__learning_rate": [
        0.01,
        0.03,
        0.05,
        0.1,
    ],

    "classifier__max_depth": [
        2,
        3,
        4,
        5,
    ],

    "classifier__min_samples_split": [
        2,
        5,
        10,
    ],

    "classifier__min_samples_leaf": [
        1,
        2,
        4,
        8,
    ],

    "classifier__subsample": [
        0.7,
        0.85,
        1.0,
    ],
}

gb_search = RandomizedSearchCV(
    estimator=gb_pipeline,
    param_distributions=gb_params,
    n_iter=25,
    scoring="roc_auc",
    cv=cv,
    n_jobs=-1,
    random_state=42,
)

print("\nTuning Gradient Boosting...")

gb_search.fit(
    X_train,
    y_train,
)

print("Best Gradient Boosting parameters:")
print(gb_search.best_params_)

print(
    f"Best Gradient Boosting CV ROC-AUC: "
    f"{gb_search.best_score_:.4f}"
)


# =====================================================
# TUNING SUMMARY
# =====================================================

print("\n" + "=" * 70)
print("TUNING SUMMARY")
print("=" * 70)

print(
    f"Logistic Regression: "
    f"{logistic_search.best_score_:.4f}"
)

print(
    f"Random Forest:       "
    f"{rf_search.best_score_:.4f}"
)

print(
    f"Gradient Boosting:    "
    f"{gb_search.best_score_:.4f}"
)
# =====================================================
# SAVE CHAMPION MODEL
# =====================================================

import joblib

champion_model = gb_search.best_estimator_

MODEL_PATH = "ml/churn_model_v2.pkl"

joblib.dump(
    champion_model,
    MODEL_PATH,
)

print("\n" + "=" * 70)
print("CHAMPION MODEL SAVED")
print("=" * 70)

print("Model: Gradient Boosting")
print(f"CV ROC-AUC: {gb_search.best_score_:.4f}")
print(f"Saved to: {MODEL_PATH}")
# =====================================================
# CHAMPION THRESHOLD OPTIMIZATION
# Tuned Gradient Boosting only
# =====================================================

from sklearn.base import clone
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import precision_score, recall_score, f1_score
import numpy as np


print("\n" + "=" * 70)
print("CHAMPION THRESHOLD OPTIMIZATION")
print("=" * 70)

# Clone the tuned champion so we do not alter the saved estimator
champion_for_threshold = clone(
    gb_search.best_estimator_
)


# -----------------------------------------------------
# Generate out-of-fold churn probabilities
# -----------------------------------------------------

champion_oof_prob = cross_val_predict(
    champion_for_threshold,
    X_train,
    y_train,
    cv=cv,
    method="predict_proba",
    n_jobs=-1,
)[:, 1]


# -----------------------------------------------------
# Test many thresholds
# -----------------------------------------------------

threshold_rows = []

for threshold in np.arange(0.10, 0.71, 0.01):

    predictions = (
        champion_oof_prob >= threshold
    ).astype(int)

    precision = precision_score(
        y_train,
        predictions,
        zero_division=0,
    )

    recall = recall_score(
        y_train,
        predictions,
        zero_division=0,
    )

    f1 = f1_score(
        y_train,
        predictions,
        zero_division=0,
    )

    threshold_rows.append({
        "Threshold": threshold,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
    })


champion_threshold_df = pd.DataFrame(
    threshold_rows
)


# -----------------------------------------------------
# Select threshold with highest F1
# -----------------------------------------------------

best_index = champion_threshold_df[
    "F1"
].idxmax()

best_threshold_row = champion_threshold_df.loc[
    best_index
]

CHAMPION_THRESHOLD = float(
    best_threshold_row["Threshold"]
)


print("\nBest tuned Gradient Boosting threshold:")
print(
    f"Threshold: {CHAMPION_THRESHOLD:.2f}"
)

print(
    f"Precision: "
    f"{best_threshold_row['Precision']:.4f}"
)

print(
    f"Recall:    "
    f"{best_threshold_row['Recall']:.4f}"
)

print(
    f"F1:        "
    f"{best_threshold_row['F1']:.4f}"
)
# =====================================================
# SAVE CHAMPION CONFIGURATION
# =====================================================

champion_config = {
    "model": "Gradient Boosting",
    "threshold": CHAMPION_THRESHOLD,
    "cv_roc_auc": float(
        gb_search.best_score_
    ),
}

joblib.dump(
    champion_config,
    "ml/champion_config.pkl",
)

print("\nChampion configuration saved.")
print(
    f"Decision threshold: "
    f"{CHAMPION_THRESHOLD:.2f}"
)
