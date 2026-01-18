from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="SecureFlow AI Service")


class TransactionInput(BaseModel):
    from_wallet: str
    to_wallet: str
    amount: float
    currency: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict-risk")
def predict_risk(tx: TransactionInput):
    # TEMP: static response (real ML comes later)
    return {
        "risk_score": 0.1,
        "confidence": 0.9,
        "explanation": "Baseline low-risk transaction"
    }
