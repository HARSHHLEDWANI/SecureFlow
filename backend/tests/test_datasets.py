"""Dataset adapters: canonical schema, PaySim column mapping and history features."""
import numpy as np
import pandas as pd
import pytest

from app.ml.datasets import CANONICAL_COLUMNS, get_dataset
from app.ml.datasets.paysim import DatasetNotFoundError, PaySimDataset, build_raw_signals, featurise
from app.ml.datasets.synthetic import SyntheticDataset
from app.ml.features import extract_features


def _paysim_frame() -> pd.DataFrame:
    rows = [
        # step, type, amount, orig, dest, fraud
        (1, "TRANSFER", 100.0, "C1", "C9", 0),
        (1, "PAYMENT", 50.0, "C1", "M1", 0),      # same account, same step
        (2, "CASH_IN", 999.0, "C7", "C8", 0),     # dropped: not a payment decision
        (5, "TRANSFER", 300.0, "C1", "C9", 0),    # repeat beneficiary, 4 steps later
        (30, "CASH_OUT", 5000.0, "C2", "C3", 1),
        (30, "DEBIT", 20.0, "C4", "C5", 0),
    ]
    return pd.DataFrame(rows, columns=["step", "type", "amount", "nameOrig", "nameDest", "isFraud"])


def test_synthetic_adapter_returns_canonical_columns():
    df = SyntheticDataset(n_rows=300, seed=1).load()
    assert list(df.columns) == CANONICAL_COLUMNS
    assert df["time_step"].is_monotonic_increasing
    assert set(df["is_fraud"].unique()) <= {0, 1}


def test_synthetic_adapter_is_reproducible_across_calls():
    a = SyntheticDataset(n_rows=200, seed=7).load()
    b = SyntheticDataset(n_rows=200, seed=7).load()
    pd.testing.assert_frame_equal(a, b)


def test_paysim_missing_path_gives_actionable_error(tmp_path):
    with pytest.raises(DatasetNotFoundError, match="PAYSIM_PATH"):
        PaySimDataset(path=str(tmp_path / "nope.csv")).load()
    with pytest.raises(DatasetNotFoundError, match="paysim1"):
        PaySimDataset(path="").load()


def test_paysim_rejects_csv_without_required_columns():
    with pytest.raises(ValueError, match="missing required columns"):
        build_raw_signals(pd.DataFrame({"step": [1], "type": ["TRANSFER"]}))


def test_paysim_history_features_use_only_prior_rows():
    sig = build_raw_signals(_paysim_frame())
    assert len(sig) == 5  # CASH_IN dropped
    c1 = sig[sig["amount_inr"].isin([100.0, 50.0, 300.0])].reset_index(drop=True)

    first, second, third = c1.iloc[0], c1.iloc[1], c1.iloc[2]
    # First txn of the account: no history at all.
    assert first["velocity_1h"] == 0 and first["velocity_24h"] == 0
    assert first["is_new_beneficiary"] == 1 and first["minutes_since_last"] == 1440.0
    assert first["user_avg_amount"] == first["amount_inr"] and first["user_std_amount"] == 0.0
    # Same account, same step, different beneficiary.
    assert second["velocity_1h"] == 1 and second["velocity_24h"] == 1
    assert second["is_new_beneficiary"] == 1 and second["minutes_since_last"] == 0.0
    assert second["user_avg_amount"] == 100.0  # only the one prior amount
    # Four steps later, repeat beneficiary: both earlier txns fall in the 24-step window.
    assert third["velocity_1h"] == 0 and third["velocity_24h"] == 2
    assert third["is_new_beneficiary"] == 0 and third["minutes_since_last"] == 240.0
    assert third["user_avg_amount"] == pytest.approx(75.0)  # mean(100, 50), excludes itself


def test_paysim_type_hour_and_neutral_constants():
    sig = build_raw_signals(_paysim_frame())
    row = sig[sig["amount_inr"] == 5000.0].iloc[0]
    assert row["txn_type"] == "P2P" and row["hour"] == 30 % 24 and row["is_fraud"] == 1
    assert row["time_step"] == 30
    assert (sig["geo_distance_km"] == 0).all() and (sig["is_new_device"] == 0).all()
    assert sig[sig["amount_inr"] == 20.0].iloc[0]["txn_type"] == "BILL_PAY"
    assert sig["time_step"].is_monotonic_increasing


def test_paysim_featurise_matches_shared_extract_features():
    sig = build_raw_signals(_paysim_frame())
    df = featurise(sig)
    assert list(df.columns) == CANONICAL_COLUMNS
    raw = sig.drop(columns=["is_fraud", "time_step"]).iloc[3].to_dict()
    expected = extract_features(raw)
    for col, val in expected.items():
        assert df.iloc[3][col] == pytest.approx(val, rel=1e-5, abs=1e-5)


def test_paysim_load_from_csv_respects_max_rows(tmp_path):
    path = tmp_path / "ps.csv"
    _paysim_frame().to_csv(path, index=False)
    full = PaySimDataset(path=str(path), max_rows=0).load()
    head = PaySimDataset(path=str(path), max_rows=3).load()
    # max_rows counts raw CSV rows; the CASH_IN row inside the prefix is then dropped.
    assert len(full) == 5 and len(head) == 2
    assert head["time_step"].max() <= full["time_step"].max()
    assert get_dataset("synthetic").name == "synthetic"
    with pytest.raises(ValueError):
        get_dataset("nope")
    assert np.isfinite(full[CANONICAL_COLUMNS].to_numpy(dtype=float)).all()


def test_paysim_simulator_matches_schema_and_loads_through_the_adapter(tmp_path):
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "simulate_paysim.py"
    spec = importlib.util.spec_from_file_location("simulate_paysim", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    df = mod.simulate(40_000, fraud_rate=0.01, seed=1)
    assert list(df.columns) == ["step", "type", "amount", "nameOrig", "nameDest", "isFraud"]
    assert df["step"].is_monotonic_increasing and df["step"].between(1, 743).all()
    assert df.loc[df["isFraud"] == 1, "type"].isin(["TRANSFER", "CASH_OUT"]).all()
    assert df["nameOrig"].nunique() > 0.95 * len(df)  # origins almost all unique, like PaySim
    csv = tmp_path / "sim.csv"
    df.to_csv(csv, index=False)
    out = PaySimDataset(path=str(csv), max_rows=0).load()
    assert list(out.columns) == CANONICAL_COLUMNS and out["is_fraud"].sum() == df["isFraud"].sum()
