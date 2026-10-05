"""Dataset adapters: every source returns the same canonical frame.

``load()`` returns a DataFrame with exactly :data:`app.ml.features.FEATURE_COLUMNS`
plus ``is_fraud`` (0/1) and ``time_step`` (monotone integer clock used for
chronological splitting). Features are always built by
:func:`app.ml.features.extract_features`, never re-implemented per dataset, so
train/serve parity holds for every source.
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd

from app.ml.features import FEATURE_COLUMNS

CANONICAL_COLUMNS: list[str] = [*FEATURE_COLUMNS, "is_fraud", "time_step"]


class DatasetAdapter(Protocol):
    name: str
    #: True if metrics measured on this source may be reported as model performance.
    is_benchmark: bool

    def load(self) -> pd.DataFrame: ...


def get_dataset(name: str) -> DatasetAdapter:
    """Return the adapter registered under ``name`` (``synthetic`` | ``paysim``)."""
    if name == "synthetic":
        from app.ml.datasets.synthetic import SyntheticDataset

        return SyntheticDataset()
    if name == "paysim":
        from app.ml.datasets.paysim import PaySimDataset

        return PaySimDataset()
    raise ValueError(f"Unknown dataset {name!r}; expected 'synthetic' or 'paysim'.")
