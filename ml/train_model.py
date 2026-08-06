import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# Sample training data
data = pd.DataFrame({
    "usage": [95, 80, 70, 50, 20, 10, 65, 90, 30, 40],
    "tickets": [2, 3, 5, 6, 10, 12, 4, 2, 8, 7],
    "nps": [9, 8, 7, 6, 2, 1, 7, 10, 3, 5],
    "renewed": [1, 1, 1, 1, 0, 0, 1, 1, 0, 0]
})

X = data[["usage", "tickets", "nps"]]
y = data["renewed"]

model = RandomForestClassifier(random_state=42)
model.fit(X, y)

joblib.dump(model, "customer_model.pkl")

print("✅ Model trained successfully!")