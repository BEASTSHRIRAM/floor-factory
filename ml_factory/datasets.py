"""Dataset loading for campaigns.

A dataset loader returns (X, y, feature_names, meta) with y binary
(0/1). Loaders are deliberately boring: the interesting machinery is
the freeze, the bidding, and the evaluation battery — not the ingest.

Supported sources:
  - "cicids2017": a sample of the CICIDS2017 flow-feature CSVs
    (binary task: BENIGN vs any attack), prepared by prepare_cicids.py.
  - "breast_cancer": sklearn's bundled Wisconsin breast-cancer set —
    the offline fallback when no local CICIDS sample is available.
"""
from __future__ import annotations

import os

import numpy as np


def load_breast_cancer():
    from sklearn.datasets import load_breast_cancer

    bunch = load_breast_cancer()
    X = np.asarray(bunch.data, dtype=np.float64)
    # sklearn encodes malignant=0, benign=1; flip so 1 = the positive
    # (malignant) class the campaign scores.
    y = (1 - np.asarray(bunch.target)).astype(int)
    meta = {
        "source": "sklearn.datasets.load_breast_cancer (bundled)",
        "task": "binary classification: malignant (1) vs benign (0)",
        "rows": int(X.shape[0]),
        "features": int(X.shape[1]),
    }
    return X, y, list(bunch.feature_names), meta


def load_cicids_sample(path: str):
    """Load a prepared CICIDS2017 sample .npz (see prepare_cicids.py).

    The prepared file carries X (float64), y (binary: 0 = BENIGN,
    1 = attack) and feature_names. Identifiers and timestamps were
    dropped at preparation time, before any split existed.
    """
    data = np.load(path, allow_pickle=True)
    X = np.asarray(data["X"], dtype=np.float64)
    y = np.asarray(data["y"]).astype(int)
    feature_names = [str(n) for n in data["feature_names"].tolist()]
    meta = {
        "source": "CICIDS2017 sample (Kaggle: sweety18/cicids2017-full-dataset), "
                  "prepared by ml_factory/prepare_cicids.py",
        "task": "binary classification: attack (1) vs BENIGN (0)",
        "rows": int(X.shape[0]),
        "features": int(X.shape[1]),
        "positive_rate": round(float(y.mean()), 4),
    }
    return X, y, feature_names, meta
