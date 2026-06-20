"""UPI transaction simulation engine.

Simulates UPI transaction processing for local demonstration. **No real money
moves** — this generates realistic transaction data and runs it through
SecureFlow's *real* detection pipeline (feature engineering → ML → risk engine →
blockchain → decision). Only the construction of input signals differs from the
live API; the detection results are genuine.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.demo_data import (
    ATTACK_SCENARIOS,
    CITIES,
    DEMO_USER_BY_VPA,
    SCENARIO_BY_ID,
)
from app.core.demo_seed import demo_user_id, reset_sender_baseline
from app.core.pipeline import StageTracker, gather_signals, recommended_action, run_pipeline
from app.database import TxnStatus, User
from app.utils.helpers import utcnow
from app.utils.logger import get_logger

logger = get_logger("upi_sim")

# Lab decision vocabulary mapped from the engine's TxnStatus.
_DECISION = {
    TxnStatus.ALLOWED: ("APPROVED", "✅ Approved — payment completed"),
    TxnStatus.STEP_UP: ("STEP_UP", "⚠️ Step-up auth required — OTP challenge"),
    TxnStatus.BLOCKED: ("BLOCKED", "🚫 Blocked — flagged to fraud team"),
}


class UPIValidationError(ValueError):
    """Raised for malformed UPI input (mapped to HTTP 422 by the route)."""


class UPISimulator:
    """Drives demo UPI payments through the real fraud-detection pipeline."""

    # ── Resolution helpers ────────────────────────────────────────────────────

    @staticmethod
    def resolve_sender(db: Session, sender_vpa: str) -> User:
        spec = DEMO_USER_BY_VPA.get(sender_vpa)
        if spec is None:
            raise UPIValidationError(
                f"Unknown demo sender '{sender_vpa}'. Use one of: "
                + ", ".join(DEMO_USER_BY_VPA)
            )
        user = db.get(User, demo_user_id(sender_vpa))
        if user is None:
            raise UPIValidationError(
                "Demo users are not seeded yet — restart the server or call /upi/reset."
            )
        return user

    @staticmethod
    def city_coords(city: Optional[str], default_vpa: str) -> tuple[float, float]:
        if city and city in CITIES:
            return CITIES[city]
        spec = DEMO_USER_BY_VPA.get(default_vpa)
        return CITIES[spec["home_city"]] if spec else CITIES["Mumbai"]

    # ── Core processing ───────────────────────────────────────────────────────

    def process_payment(
        self,
        db: Session,
        *,
        sender_vpa: str,
        receiver_vpa: str,
        amount_inr: float,
        txn_type: str = "P2P",
        note: Optional[str] = None,
        city: Optional[str] = None,
        device_id: Optional[str] = None,
        signal_overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Validate, build signals, run the real pipeline, return a Lab result."""
        sender = self.resolve_sender(db, sender_vpa)
        spec = DEMO_USER_BY_VPA[sender_vpa]
        device_id = device_id or spec["known_device"]
        lat, lon = self.city_coords(city, sender_vpa)

        overrides = dict(signal_overrides or {})
        # Translate a symbolic prior city into coordinates for geo-velocity.
        prev_city = overrides.pop("prev_city", None)
        if prev_city and prev_city in CITIES:
            overrides["prev_lat"], overrides["prev_lon"] = CITIES[prev_city]

        tracker = StageTracker(txn_id=f"pending-{int(time.time()*1000)}")
        tracker.mark("initiated", sender=sender_vpa, receiver=receiver_vpa, amount=amount_inr)
        tracker.mark("validated", device=device_id, city=city or spec["home_city"])

        signals = gather_signals(
            db,
            sender,
            to_vpa=receiver_vpa,
            amount_inr=amount_inr,
            txn_type=txn_type,
            device_id=device_id,
            location_lat=lat,
            location_lon=lon,
            overrides=overrides,
        )

        txn, ml_result, risk = run_pipeline(
            db,
            sender,
            to_vpa=receiver_vpa,
            amount_inr=amount_inr,
            txn_type=txn_type,
            device_id=device_id,
            location_lat=lat,
            location_lon=lon,
            signals=signals,
            tracker=tracker,
            note=note,
        )

        tracker.rekey(txn.id)
        decision, label = _DECISION[txn.status]
        return {
            "txn_id": txn.id,
            "sender_vpa": txn.from_vpa,
            "receiver_vpa": txn.to_vpa,
            "amount_inr": float(txn.amount_inr),
            "txn_type": txn.txn_type.value,
            "note": note,
            "decision": decision,
            "decision_label": label,
            "risk_score": txn.risk_score,
            "risk_tier": txn.risk_tier.value,
            "ml_fraud_prob": ml_result["fraud_prob"],
            "anomaly_score": ml_result["anomaly_score"],
            "ml_confidence": ml_result["confidence"],
            "components": risk["components"],
            "feature_contributions": ml_result["feature_contributions"],
            "block_index": txn.block_index,
            "block_hash": txn.block_hash,
            "recommended_action": recommended_action(txn.status),
            "total_duration_ms": tracker.total_ms,
            "pipeline": tracker.snapshot(),
            "created_at": txn.created_at.isoformat(),
        }

    # ── Scenarios ─────────────────────────────────────────────────────────────

    def run_scenario(self, db: Session, scenario_id: str) -> dict[str, Any]:
        scn = SCENARIO_BY_ID.get(scenario_id)
        if scn is None:
            raise UPIValidationError(f"Unknown scenario '{scenario_id}'")
        # Each preset scenario runs against the user's normal baseline so it is
        # repeatable regardless of prior demo activity.
        reset_sender_baseline(scn["sender"])
        if "rapid_fire" in scn:
            results = self.run_rapid_fire(db, scenario_id)
            return {"scenario": _scenario_public(scn), "results": results, "rapid_fire": True}

        result = self.process_payment(
            db,
            sender_vpa=scn["sender"],
            receiver_vpa=scn["receiver"],
            amount_inr=scn["amount"],
            txn_type=scn.get("txn_type", "P2P"),
            note=scn["name"],
            city=scn.get("city"),
            device_id=scn.get("device"),
            signal_overrides=scn.get("signal_overrides"),
        )
        return {
            "scenario": _scenario_public(scn),
            "result": result,
            "rapid_fire": False,
            "match": _expected_match(scn["expected_result"], result["decision"]),
        }

    def run_rapid_fire(self, db: Session, scenario_id: str = "rapid_fire") -> list[dict[str, Any]]:
        """Fire a burst of transactions; rising velocity + amounts escalate risk.

        Each transaction is to a fresh beneficiary from an unrecognised "bot"
        device with a steadily larger amount — a stolen-credential cash-out. The
        first few clear, then the burst crosses STEP_UP into BLOCKED as the
        velocity and amount-anomaly signals compound. Detection is fully real.
        """
        scn = SCENARIO_BY_ID.get(scenario_id, SCENARIO_BY_ID["rapid_fire"])
        reset_sender_baseline(scn["sender"])
        cfg = scn.get("rapid_fire", {})
        amounts = cfg.get("amounts") or [600, 1200, 2500, 5000, 9000, 16000, 26000, 38000, 48000, 60000]
        device = cfg.get("device", "device_bot07")
        out: list[dict[str, Any]] = []
        for i, amount in enumerate(amounts):
            res = self.process_payment(
                db,
                sender_vpa=scn["sender"],
                receiver_vpa=f"payee{i+1}@paytm",  # new beneficiary each time
                amount_inr=float(amount),
                txn_type="P2P",
                note=f"Rapid-fire #{i+1}",
                city=scn.get("city"),
                device_id=device,
                signal_overrides={"hour": 14, "is_new_device": True, "is_new_beneficiary": True},
            )
            res["sequence"] = i + 1
            out.append(res)
        return out


def _scenario_public(scn: dict[str, Any]) -> dict[str, Any]:
    """Frontend-safe scenario card (omits internal override mechanics)."""
    return {
        "id": scn["id"],
        "name": scn["name"],
        "emoji": scn["emoji"],
        "description": scn["description"],
        "expected_result": scn["expected_result"],
        "sender": scn["sender"],
        "receiver": scn.get("receiver"),
        "amount": scn.get("amount"),
        "txn_type": scn.get("txn_type"),
        "city": scn.get("city"),
        "rapid_fire": "rapid_fire" in scn,
    }


def _expected_match(expected: str, decision: str) -> bool:
    """Loose check that the observed decision is consistent with the intent."""
    exp = expected.upper()
    if decision == "APPROVED":
        return "APPROV" in exp
    if decision == "BLOCKED":
        return "BLOCK" in exp
    if decision == "STEP_UP":
        return "STEP" in exp
    return False


def scenarios_public() -> list[dict[str, Any]]:
    return [_scenario_public(s) for s in ATTACK_SCENARIOS]


simulator = UPISimulator()
