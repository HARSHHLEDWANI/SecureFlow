"""On-demand plain-English explanations of a fraud decision (Feature A).

**The LLM explains a decision the risk engine already made — it never influences
the score, the tier, or the action.** It receives the finished decision plus the
structured risk signals as input and produces prose as output, nothing more. The
score/tier/status are computed entirely by `app/core/risk_engine.py` before this
module is ever called.

Design guarantees:
  * If ``ANTHROPIC_API_KEY`` is unset, the API errors, or the call exceeds a short
    timeout, we fall back to a deterministic template built from the strongest
    risk signals. Every result carries ``source`` ("llm" | "template") so the UI
    can be honest about which path produced it.
  * This is the one feature in the project with an external, per-call cost. It is
    on-demand only, cached per transaction (in the route), rate-limited more
    tightly than other endpoints, uses a small/fast/cheap model, and has a hard
    timeout — so the cost is bounded and close to zero. See
    docs/TECH_STACK_AND_ALTERNATIVES.md.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("explain")

# Human labels for the composite risk components (see risk_engine.WEIGHTS).
_COMPONENT_LABELS = {
    "ml_fraud": "high ML fraud probability",
    "anomaly": "an anomalous transaction pattern",
    "velocity": "elevated transaction velocity",
    "geo": "an impossible-travel / large geo jump",
    "new_device": "an unrecognised device",
    "amount": "an unusual amount for this user",
    "time": "an unusual time of day",
}

_DECISION_LABELS = {
    "ALLOWED": "allowed",
    "STEP_UP": "flagged for step-up OTP verification",
    "BLOCKED": "blocked",
}

_SYSTEM_PROMPT = (
    "You are a fraud-analytics assistant for SecureFlow, a UPI payments fraud "
    "system. You are given a payment decision that has ALREADY been made by a "
    "rule + ML risk engine, plus the structured signals behind it. Write 2-3 short "
    "plain-English sentences explaining WHY that decision was made, for a fraud "
    "analyst. Rules: use only the facts provided; invent nothing; do not restate "
    "raw JSON or field names; do not add disclaimers or hedging; do not suggest the "
    "decision might change. Refer to concrete signals (amount, distance, device, "
    "time, velocity) when they are elevated."
)


def _top_signals(components: dict[str, float], k: int = 3) -> list[str]:
    """The k strongest composite risk components, as human labels."""
    ranked = sorted(
        ((name, float(val)) for name, val in (components or {}).items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    labels = [_COMPONENT_LABELS.get(name, name) for name, val in ranked if val > 0.01]
    return labels[:k]


def build_facts(txn: Any, components: dict[str, float], feature_contributions: list[dict]) -> str:
    """Assemble the structured, decision-already-made context passed to the model."""
    decision = _DECISION_LABELS.get(txn.status.value, txn.status.value)
    lines = [
        f"Decision (already made): {decision}.",
        f"Risk score: {txn.risk_score}/100 (tier {txn.risk_tier.value}).",
        f"Amount: INR {float(txn.amount_inr):,.0f}, type {txn.txn_type.value}, "
        f"to {txn.to_vpa}.",
        f"ML fraud probability: {float(txn.ml_fraud_prob) * 100:.0f}%; "
        f"anomaly score: {float(txn.anomaly_score) * 100:.0f}%.",
    ]
    top = _top_signals(components)
    if top:
        lines.append("Strongest risk signals: " + ", ".join(top) + ".")
    if feature_contributions:
        drivers = ", ".join(
            f"{f.get('feature')}={f.get('value')}" for f in feature_contributions[:4]
        )
        lines.append(f"Top model feature drivers: {drivers}.")
    return "\n".join(lines)


def template_explanation(
    txn: Any, components: dict[str, float], feature_contributions: list[dict]
) -> str:
    """Deterministic fallback — used when the LLM is unavailable/errors/times out."""
    decision = _DECISION_LABELS.get(txn.status.value, txn.status.value)
    top = _top_signals(components)
    if not top and feature_contributions:
        top = [str(f.get("feature")) for f in feature_contributions[:2]]
    reason = ", ".join(top) if top else "the combined risk signals"
    return (
        f"This payment of INR {float(txn.amount_inr):,.0f} was {decision} "
        f"(risk score {txn.risk_score}/100, {txn.risk_tier.value} tier). "
        f"Flagged primarily due to: {reason}."
    )


def _llm_explanation(facts: str) -> str:
    """Call the LLM for a short explanation. Raises on any failure (caller falls back)."""
    import anthropic  # imported lazily so a missing package simply triggers the fallback

    settings = get_settings()
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.explain_timeout_seconds,
        max_retries=0,  # this path costs money — don't silently retry
    )
    resp = client.messages.create(
        model=settings.explain_model,
        max_tokens=settings.explain_max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": facts}],
    )
    text = " ".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    if not text:
        raise ValueError("Empty LLM response")
    return text


def explain_decision(
    txn: Any, components: dict[str, float], feature_contributions: list[dict]
) -> dict[str, str]:
    """Return ``{"explanation", "source"}`` for an already-made decision.

    Tries the LLM first when an API key is configured; on any failure (no key,
    error, timeout) falls back to the deterministic template. Never raises.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {
            "explanation": template_explanation(txn, components, feature_contributions),
            "source": "template",
        }
    try:
        facts = build_facts(txn, components, feature_contributions)
        return {"explanation": _llm_explanation(facts), "source": "llm"}
    except Exception as exc:  # noqa: BLE001 - any failure degrades to the template
        logger.warning("LLM explanation failed (%s) - using template fallback", exc)
        return {
            "explanation": template_explanation(txn, components, feature_contributions),
            "source": "template",
        }
