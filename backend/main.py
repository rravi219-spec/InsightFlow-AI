from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from pathlib import Path
import joblib
import pandas as pd

from database import SessionLocal
from models import Customer
from schemas import CustomerCreate, CustomerResponse

app = FastAPI()

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "ml"
    / "customer_model.pkl"
)

churn_model = joblib.load(MODEL_PATH)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {
        "message": "Customer Success AI Platform 🚀"
    }
@app.get("/customers")
def get_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()

@app.post("/customers")
def create_customer(
        customer: CustomerCreate,
        db: Session = Depends(get_db)):

    new_customer = Customer(
        name=customer.name,
        usage=customer.usage,
        tickets=customer.tickets,
        nps=customer.nps,
        renewal_status=customer.renewal_status
    )

    db.add(new_customer)

    db.commit()

    db.refresh(new_customer)

    return new_customer
@app.get("/health-score/{customer_id}")
def health_score(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if customer is None:
        return {"error": "Customer not found"}

    score = customer.usage * 0.5 + customer.nps * 5 - customer.tickets * 2

    if score >= 80:
        status = "Healthy"
        recommendation = "Strong engagement detected. Consider upsell opportunities."
    elif score >= 60:
        status = "At Risk"
        recommendation = "Schedule a customer success review."
    else:
        status = "Critical"
        recommendation = "Immediate intervention required."

    return {
        "customer": customer.name,
        "usage": customer.usage,
        "tickets": customer.tickets,
        "nps": customer.nps,
        "health_score": round(score, 2),
        "status": status,
        "recommendation": recommendation
    }
@app.get("/predict/{customer_id}")
def predict_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if customer is None:
        return {"error": "Customer not found"}

    input_data = pd.DataFrame(
        [
            {
                "usage": customer.usage,
                "tickets": customer.tickets,
                "nps": customer.nps,
            }
        ]
    )

    probabilities = churn_model.predict_proba(input_data)[0]

    renewal_probability = round(float(probabilities[1]) * 100, 2)
    churn_probability = round(float(probabilities[0]) * 100, 2)

    if churn_probability >= 70:
        risk_level = "High"
        recommendation = (
            "Immediate intervention required. "
            "Schedule an executive review."
        )
    elif churn_probability >= 40:
        risk_level = "Medium"
        recommendation = (
            "Schedule a customer success check-in."
        )
    else:
        risk_level = "Low"
        recommendation = (
            "Customer is healthy. Consider upsell opportunities."
        )

    return {
        "customer": customer.name,
        "renewal_probability": renewal_probability,
        "churn_probability": churn_probability,
        "risk_level": risk_level,
        "recommendation": recommendation,
    }