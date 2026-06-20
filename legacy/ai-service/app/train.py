"""Train the fraud detection model and save it to models/fraud_model.joblib."""
import os
import random
import math
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from features import extract_features, FEATURE_COLUMNS

random.seed(42)
np.random.seed(42)

WALLETS = [
    "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "0xab5801a7d398351b8be11c439e05c5b3259aec9b",
    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
    "0xFE9e8709d3215310075d67E3ed32A380CCf451C8",
    "0x" + "a" * 40,
    "0x" + "1" * 40,
    "0x" + "f" * 40,
]

CURRENCIES = ["USD", "ETH", "USDC"]
HOURS = list(range(24))


def is_fraud(features: dict) -> int:
    """Rule-based labeler for synthetic data."""
    score = 0
    if features["is_large_transaction"]:
        score += 2
    if features["is_round_number"]:
        score += 2
    if features["is_off_hours"]:
        score += 1
    if features["high_velocity"]:
        score += 2
    if features["from_wallet_entropy"] < 2.5:
        score += 2
    if features["is_micro_transaction"]:
        score += 1
    return int(score >= 4)


def generate_sample():
    currency = random.choice(CURRENCIES)

    # 85% normal transactions, 15% suspicious
    if random.random() < 0.85:
        amount = random.uniform(1, 5000)
        hour = random.randint(7, 21)
        velocity = random.randint(0, 3)
        wallet = random.choice(WALLETS[:5])
    else:
        amount = random.choice([
            random.randint(1, 10) * 1000,
            random.uniform(0.0001, 0.5),
            random.randint(10, 100) * 1000,
        ])
        hour = random.choice(list(range(0, 6)) + list(range(22, 24)))
        velocity = random.randint(5, 20)
        wallet = random.choice(WALLETS[5:])

    from_wallet = wallet
    to_wallet = random.choice(WALLETS)
    timestamp = f"2026-01-15T{hour:02d}:00:00Z"

    return extract_features(from_wallet, to_wallet, amount, currency, timestamp, velocity)


def main():
    print("Generating synthetic training data...")
    samples = [generate_sample() for _ in range(1000)]
    labels = [is_fraud(s) for s in samples]

    print(f"Fraud samples: {sum(labels)} / {len(labels)} ({100*sum(labels)/len(labels):.1f}%)")

    X = np.array([[s[col] for col in FEATURE_COLUMNS] for s in samples])
    y = np.array(labels)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=5,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["legit", "fraud"]))

    os.makedirs("models", exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "version": "1.0.0"}, "models/fraud_model.joblib")
    print("Model saved to models/fraud_model.joblib")


if __name__ == "__main__":
    main()
