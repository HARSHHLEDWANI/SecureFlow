from fastapi import FastAPI
from pydantic import BaseModel, Field
from sklearn.ensemble import IsolationForest
import numpy as np

app = FastAPI(title="SecureFlow AI Service")


# -----------------------------
# Input schema
# -----------------------------
class TransactionInput(BaseModel):
    from_wallet: str
    to_wallet: str
    amount: float = Field(..., gt=0)
    currency: str


# -----------------------------
# Output schema
# -----------------------------
class FraudPrediction(BaseModel):
    risk_score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str


# -----------------------------
# Train a simple model (startup)
# -----------------------------
# Fake historical transaction amounts (baseline behavior)
historical_amounts = np.array([
    10, 20, 50, 100, 200, 300, 500, 700, 900
]).reshape(-1, 1)

model = IsolationForest(
    n_estimators=100,
    contamination=0.15,
    random_state=42
)

model.fit(historical_amounts)


# -----------------------------
# Health check
# -----------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


# -----------------------------
# Fraud risk prediction
# -----------------------------
@app.post("/predict-risk", response_model=FraudPrediction)
def predict_risk(tx: TransactionInput):
    amount_array = np.array([[tx.amount]])

    prediction = model.predict(amount_array)[0]
    anomaly_score = model.decision_function(amount_array)[0]

    # Normalize anomaly score to 0–1 risk
    risk_score = min(max(-anomaly_score, 0), 1)

    explanation = (
        "Transaction amount deviates from normal patterns"
        if prediction == -1
        else "Transaction amount within normal range"
    )

    return FraudPrediction(
        risk_score=risk_score,
        confidence=0.85,
        explanation=explanation
    )
