import os
import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional
from contextlib import asynccontextmanager

from app.features import extract_features, FEATURE_COLUMNS

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "fraud_model.joblib")

_model_bundle: Optional[dict] = None


def load_model():
    global _model_bundle
    if os.path.exists(MODEL_PATH):
        _model_bundle = joblib.load(MODEL_PATH)
    else:
        _model_bundle = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(title="SecureFlow AI Service", version="1.0.0", lifespan=lifespan)


class TransactionInput(BaseModel):
    fromWallet: str
    toWallet: str
    amount: float = Field(..., gt=0)
    currency: str
    timestamp: Optional[str] = None
    velocityCount: Optional[int] = 0


class PredictionResponse(BaseModel):
    risk_score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str
    features_used: dict


def build_explanation(features: dict, risk_score: float) -> str:
    flags = []
    if features["is_large_transaction"]:
        flags.append(f"large transaction (${features['amount_usd']:,.0f})")
    if features["is_micro_transaction"]:
        flags.append("micro-transaction (possible dust attack)")
    if features["is_round_number"]:
        flags.append("round-number amount")
    if features["is_off_hours"]:
        flags.append(f"off-hours activity ({int(features['hour_of_day'])}:00)")
    if features["high_velocity"]:
        flags.append(f"high velocity ({int(features['velocity_count'])} tx in 10 min)")
    if features["from_wallet_entropy"] < 2.5:
        flags.append("low wallet address entropy (suspicious pattern)")
    if features["is_weekend"]:
        flags.append("weekend transaction")

    if not flags:
        return "No anomalies detected. Transaction pattern within normal parameters."

    severity = "CRITICAL" if risk_score >= 0.7 else "HIGH" if risk_score >= 0.4 else "MODERATE"
    return f"{severity}: {'; '.join(flags)}."


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": _model_bundle is not None,
        "model_version": _model_bundle["version"] if _model_bundle else None,
    }


@app.post("/predict-risk", response_model=PredictionResponse)
def predict_risk(tx: TransactionInput):
    features = extract_features(
        tx.fromWallet,
        tx.toWallet,
        tx.amount,
        tx.currency,
        tx.timestamp,
        tx.velocityCount or 0,
    )

    feature_vec = np.array([[features[col] for col in FEATURE_COLUMNS]])

    if _model_bundle is None:
        risk_score = min(
            0.3 * features["is_large_transaction"]
            + 0.25 * features["is_round_number"]
            + 0.2 * features["high_velocity"]
            + 0.15 * features["is_off_hours"]
            + 0.1 * (1 - min(features["from_wallet_entropy"] / 4.0, 1.0)),
            1.0,
        )
        confidence = 0.5
    else:
        model = _model_bundle["model"]
        proba = model.predict_proba(feature_vec)[0]
        risk_score = float(proba[1])
        confidence = 0.5 + abs(risk_score - 0.5)

    explanation = build_explanation(features, risk_score)

    return PredictionResponse(
        risk_score=round(risk_score, 4),
        confidence=round(confidence, 4),
        explanation=explanation,
        features_used={k: round(v, 4) if isinstance(v, float) else v for k, v in features.items()},
    )
