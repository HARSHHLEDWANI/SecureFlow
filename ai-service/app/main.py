from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SecureFlow AI Service")


# -----------------------------
# Input schema (from backend)
# -----------------------------
class TransactionInput(BaseModel):
    from_wallet: str = Field(..., description="Sender wallet address")
    to_wallet: str = Field(..., description="Receiver wallet address")
    amount: float = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., min_length=1)


# -----------------------------
# Output schema (to backend)
# -----------------------------
class FraudPrediction(BaseModel):
    risk_score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str


# -----------------------------
# Health check
# -----------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


# -----------------------------
# Fraud risk prediction (AI advisory)
# -----------------------------
@app.post("/predict-risk", response_model=FraudPrediction)
def predict_risk(tx: TransactionInput):
    """
    Advisory fraud risk prediction.
    This endpoint NEVER approves or rejects transactions.
    """

    # Baseline rule-based logic (temporary)
    if tx.amount < 1000:
        risk_score = 0.1
        explanation = "Low-value transaction"
    else:
        risk_score = 0.6
        explanation = "High-value transaction"

    return FraudPrediction(
        risk_score=risk_score,
        confidence=0.9,
        explanation=explanation
    )
