"""Static demo data for the UPI Simulation Lab: cities, users, scenarios.

Kept separate from the seeding/simulation logic so it is trivially importable by
the API layer (e.g. ``GET /upi/users`` and ``GET /upi/scenarios``) without
pulling in the database.
"""
from __future__ import annotations

from typing import Any

# Indian city coordinates used for geo-velocity / impossible-travel reasoning.
CITIES: dict[str, tuple[float, float]] = {
    "Pune": (18.5204, 73.8567),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bangalore": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
}

# Shared demo password for every seeded user (demo only — never production).
DEMO_PASSWORD = "demopass123"

# Preset "users" with history so the model + risk engine have real context.
DEMO_USERS: list[dict[str, Any]] = [
    {
        "vpa": "harsh@upi",
        "name": "Harsh Ledwani",
        "email": "harsh.demo@secureflow.local",
        "home_city": "Pune",
        "avg_transaction": 500,
        "amount_spread": 220,
        "usual_hours": (8, 23),
        "known_device": "device_001",
        "risk_profile": "low",
        "usual_payees": ["kirana@okaxis", "swiggy@ybl", "electricity@oksbi", "friend.rohan@upi"],
    },
    {
        "vpa": "amit@upi",
        "name": "Amit Sharma",
        "email": "amit.demo@secureflow.local",
        "home_city": "Delhi",
        "avg_transaction": 2000,
        "amount_spread": 900,
        "usual_hours": (9, 21),
        "known_device": "device_002",
        "risk_profile": "medium",
        "usual_payees": ["bigbasket@ybl", "landlord@oksbi", "amazon@apl", "cousin.neha@upi"],
    },
    {
        "vpa": "priya@upi",
        "name": "Priya Menon",
        "email": "priya.demo@secureflow.local",
        "home_city": "Bangalore",
        "avg_transaction": 1200,
        "amount_spread": 500,
        "usual_hours": (7, 22),
        "known_device": "device_003",
        "risk_profile": "low",
        "usual_payees": ["zomato@ybl", "cafe.coffee@okhdfc", "gym@paytm", "mom@upi"],
    },
    {
        "vpa": "rahul@upi",
        "name": "Rahul Verma",
        "email": "rahul.demo@secureflow.local",
        "home_city": "Mumbai",
        "avg_transaction": 800,
        "amount_spread": 350,
        "usual_hours": (8, 24),
        "known_device": "device_004",
        "risk_profile": "low",
        "usual_payees": ["localtrain@oksbi", "medical@ybl", "dmart@paytm", "roommate@upi"],
    },
    {
        "vpa": "sneha@upi",
        "name": "Sneha Iyer",
        "email": "sneha.demo@secureflow.local",
        "home_city": "Chennai",
        "avg_transaction": 1500,
        "amount_spread": 600,
        "usual_hours": (9, 22),
        "known_device": "device_005",
        "risk_profile": "medium",
        "usual_payees": ["jewellery@okhdfc", "tuition@ybl", "petrol@paytm", "sister@upi"],
    },
]

DEMO_USER_BY_VPA = {u["vpa"]: u for u in DEMO_USERS}

# Default "sender" for one-click scenarios.
DEFAULT_SENDER = "harsh@upi"


# ── Attack / behaviour scenarios ──────────────────────────────────────────────
#
# ``signal_overrides`` is fed verbatim into ``gather_signals`` to make each
# scenario deterministic regardless of seeded history or wall-clock time. The
# detection itself (ML + risk engine) is never faked.

ATTACK_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "normal",
        "name": "Normal Transaction",
        "emoji": "🟢",
        "description": "A regular payment within the user's usual patterns.",
        "expected_result": "APPROVED — Low Risk",
        "sender": "harsh@upi",
        "receiver": "kirana@okaxis",
        "amount": 350,
        "txn_type": "P2M",
        "city": "Pune",
        "device": "device_001",
        "signal_overrides": {"hour": 14, "is_new_device": False, "is_new_beneficiary": False},
    },
    {
        "id": "high_amount",
        "name": "Unusual High Amount",
        "emoji": "🟡",
        "description": "Amount ~90x higher than the user's average spending.",
        "expected_result": "STEP-UP AUTH — Elevated Risk",
        "sender": "harsh@upi",
        "receiver": "unknown_merchant@paytm",
        "amount": 45000,
        "txn_type": "P2M",
        "city": "Pune",
        "device": "device_001",
        "signal_overrides": {"hour": 14, "is_new_beneficiary": True},
    },
    {
        "id": "impossible_travel",
        "name": "Impossible Travel Attack",
        "emoji": "🔴",
        "description": "₹40k from Kolkata on a new device at 2 AM, 5 min after a Pune payment.",
        "expected_result": "BLOCKED — High Risk (impossible travel)",
        "sender": "harsh@upi",
        "receiver": "store@ybl",
        "amount": 40000,
        "txn_type": "P2M",
        "city": "Kolkata",
        "device": "device_travel99",
        "signal_overrides": {
            "hour": 2,
            "prev_city": "Pune",
            "minutes_since_last": 5,
            "is_new_device": True,
            "is_new_beneficiary": True,
        },
    },
    {
        "id": "new_device_high_value",
        "name": "New Device + High Value",
        "emoji": "🔴",
        "description": "Login from an unknown device making a large transfer.",
        "expected_result": "STEP-UP AUTH — High Risk",
        "sender": "harsh@upi",
        "receiver": "unknown@paytm",
        "amount": 25000,
        "txn_type": "P2P",
        "city": "Pune",
        "device": "device_999",
        "signal_overrides": {"hour": 16, "is_new_device": True, "is_new_beneficiary": True},
    },
    {
        "id": "midnight_anomaly",
        "name": "Midnight Unusual Activity",
        "emoji": "🟡",
        "description": "₹25k at 3 AM to a new payee — the user never transacts at night.",
        "expected_result": "STEP-UP AUTH — Elevated Risk (time anomaly)",
        "sender": "harsh@upi",
        "receiver": "merchant@ybl",
        "amount": 25000,
        "txn_type": "P2P",
        "city": "Pune",
        "device": "device_001",
        "signal_overrides": {"hour": 3, "is_new_beneficiary": True},
    },
    {
        "id": "account_takeover",
        "name": "Full Account Takeover",
        "emoji": "🔴",
        "description": "New device + new city + high amount + 2:30 AM — every red flag.",
        "expected_result": "BLOCKED — Critical Risk",
        "sender": "harsh@upi",
        "receiver": "attacker_wallet@paytm",
        "amount": 49999,
        "txn_type": "P2P",
        "city": "Kolkata",
        "device": "device_unknown",
        "signal_overrides": {
            "hour": 2,
            "prev_city": "Pune",
            "minutes_since_last": 8,
            "is_new_device": True,
            "is_new_beneficiary": True,
        },
    },
    {
        "id": "rapid_fire",
        "name": "Rapid-Fire Transactions",
        "emoji": "⚡",
        "description": "10 txns in ~2 min from a bot device, draining ever-larger amounts.",
        "expected_result": "Escalates: APPROVED → STEP-UP → BLOCKED",
        "sender": "harsh@upi",
        "receiver": "various@paytm",
        "amount": 2500,
        "txn_type": "P2P",
        "city": "Pune",
        "device": "device_bot07",
        "rapid_fire": {
            "device": "device_bot07",
            # Escalating amounts so the burst visibly crosses APPROVED→STEP_UP→BLOCKED
            # as velocity climbs — a stolen-credential cash-out pattern.
            "amounts": [600, 1200, 2500, 5000, 9000, 16000, 26000, 38000, 48000, 60000],
        },
    },
]

SCENARIO_BY_ID = {s["id"]: s for s in ATTACK_SCENARIOS}
