import math
from datetime import datetime
from typing import Optional

CURRENCY_TO_USD = {
    "USD": 1.0,
    "ETH": 3200.0,
    "USDC": 1.0,
}


def to_usd(amount: float, currency: str) -> float:
    return amount * CURRENCY_TO_USD.get(currency.upper(), 1.0)


def wallet_entropy(address: str) -> float:
    """Shannon entropy of hex chars in wallet address (post 0x prefix)."""
    chars = address[2:].lower() if address.startswith("0x") else address.lower()
    if not chars:
        return 0.0
    freq = {}
    for c in chars:
        freq[c] = freq.get(c, 0) + 1
    length = len(chars)
    return -sum((f / length) * math.log2(f / length) for f in freq.values())


def extract_features(
    from_wallet: str,
    to_wallet: str,
    amount: float,
    currency: str,
    timestamp: Optional[str] = None,
    velocity_count: int = 0,
) -> dict:
    amount_usd = to_usd(amount, currency)

    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()

    hour = dt.hour
    is_weekend = dt.weekday() >= 5

    features = {
        "amount_usd": amount_usd,
        "amount_log": math.log1p(amount_usd),
        "is_round_number": int(amount_usd % 1000 == 0 and amount_usd >= 1000),
        "is_large_transaction": int(amount_usd > 10_000),
        "is_micro_transaction": int(amount_usd < 1.0),
        "hour_of_day": hour,
        "is_off_hours": int(hour < 6 or hour >= 22),
        "is_weekend": int(is_weekend),
        "from_wallet_entropy": wallet_entropy(from_wallet),
        "to_wallet_entropy": wallet_entropy(to_wallet),
        "velocity_count": velocity_count,
        "high_velocity": int(velocity_count > 5),
    }
    return features


FEATURE_COLUMNS = [
    "amount_usd",
    "amount_log",
    "is_round_number",
    "is_large_transaction",
    "is_micro_transaction",
    "hour_of_day",
    "is_off_hours",
    "is_weekend",
    "from_wallet_entropy",
    "to_wallet_entropy",
    "velocity_count",
    "high_velocity",
]
