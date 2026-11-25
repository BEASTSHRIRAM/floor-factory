"""Prepare a CICIDS2017 sample for a campaign.

Reads ONE raw CICIDS2017 flow-feature CSV (the MachineLearningCVE
files), cleans it the way anyone who has worked with this dataset
knows it needs:

  - column names stripped of their leading spaces
  - identifier / non-numeric columns dropped (Flow ID, IPs, ports are
    kept out — source/destination ports are dropped too: they identify
    the experiment's addressing, not the traffic's behaviour, and are
    a classic shortcut feature on this dataset)
  - rows with NaN / inf flow rates dropped (a known CICIDS artefact)
  - label binarised: BENIGN -> 0, anything else -> 1
  - stratified sample of N rows written as a compact .npz

Usage:
    python -m ml_factory.prepare_cicids <raw_csv> <out_npz> [rows]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

DROP_COLUMNS = {
    "Flow ID", "Source IP", "Destination IP", "Source Port",
    "Destination Port", "Timestamp",
}


def prepare(raw_csv: str, out_npz: str, rows: int = 20000, seed: int = 7):
    df = pd.read_csv(raw_csv, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    label_col = "Label"
    if label_col not in df.columns:
        raise ValueError(f"no Label column in {raw_csv}: {list(df.columns)[:5]}")
    y_all = (df[label_col].astype(str).str.strip() != "BENIGN").astype(int)
    drop = [c for c in df.columns if c in DROP_COLUMNS or c == label_col]
    feats = df.drop(columns=drop)
    feats = feats.apply(pd.to_numeric, errors="coerce")
    feats = feats.replace([np.inf, -np.inf], np.nan)
    mask = feats.notna().all(axis=1)
    feats, y_all = feats[mask], y_all[mask]
    # Drop constant columns (they carry no signal and break AUC scans).
    feats = feats.loc[:, feats.nunique() > 1]
    X = feats.to_numpy(dtype=np.float64)
    y = y_all.to_numpy(dtype=int)
    if len(y) > rows:
        rng = np.random.RandomState(seed)
        pos = np.where(y == 1)[0]
        neg = np.where(y == 0)[0]
        n_pos = min(len(pos), rows // 2)
        n_neg = min(len(neg), rows - n_pos)
        keep = np.sort(np.concatenate([
            rng.choice(pos, size=n_pos, replace=False),
            rng.choice(neg, size=n_neg, replace=False),
        ]))
        X, y = X[keep], y[keep]
    np.savez_compressed(out_npz, X=X, y=y,
                        feature_names=np.asarray(list(feats.columns)))
    print(f"wrote {out_npz}: {X.shape[0]} rows x {X.shape[1]} features, "
          f"positive rate {y.mean():.3f}")


if __name__ == "__main__":
    prepare(sys.argv[1], sys.argv[2],
            int(sys.argv[3]) if len(sys.argv) > 3 else 20000)
