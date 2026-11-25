"""The Data department's one job in v1: freeze the dataset.

Splitting happens exactly once, here, before any feature work or
experiment exists. The frozen artefacts are:

    dataset/X.npy, dataset/y.npy          the full matrix + labels
    dataset/splits.json                   train/validation/holdout indices
    dataset/manifest.json                 provenance + split hash

The split hash is a SHA-256 over the split index lists and the data
matrix bytes. Every later step (runner, evaluator) re-computes and
verifies it before touching the data; a mismatch voids the run.

After freezing, the dataset directory is chmod'ed read-only — the
freeze is enforced by the filesystem, not by politeness.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat

import numpy as np


def split_hash(X: np.ndarray, y: np.ndarray, splits: dict) -> str:
    h = hashlib.sha256()
    h.update(X.tobytes())
    h.update(y.tobytes())
    for name in ("train", "validation", "holdout"):
        h.update(name.encode())
        h.update(np.asarray(splits[name], dtype=np.int64).tobytes())
    return h.hexdigest()


def make_splits(y: np.ndarray, seed: int = 42,
                fractions=(0.60, 0.20, 0.20)) -> dict:
    """Stratified train/validation/holdout split, deterministic."""
    rng = np.random.RandomState(seed)
    parts = {"train": [], "validation": [], "holdout": []}
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_train = int(round(n * fractions[0]))
        n_val = int(round(n * fractions[1]))
        parts["train"].extend(idx[:n_train].tolist())
        parts["validation"].extend(idx[n_train:n_train + n_val].tolist())
        parts["holdout"].extend(idx[n_train + n_val:].tolist())
    for name in parts:
        parts[name] = sorted(int(i) for i in parts[name])
    return parts


def _deduplicate(X: np.ndarray, y: np.ndarray):
    """Data QA: remove exact-duplicate rows before splitting.

    An exact duplicate is the same flow recorded twice; if copies land
    on both sides of a split, the evaluation measures memorisation,
    not generalisation — the overlap battery (check 3) would then fail
    every run for a property of the dataset, not of any experiment.
    Deduplication therefore belongs here, in Data, before splits
    exist. Rows whose features repeat with a *conflicting* label are
    dropped entirely (ambiguous evidence).
    """
    seen: dict[bytes, int] = {}
    conflicted: set[bytes] = set()
    keep = []
    for i in range(len(y)):
        key = X[i].tobytes()
        if key in conflicted:
            continue
        if key in seen:
            if seen[key] != int(y[i]):
                conflicted.add(key)
            continue
        seen[key] = int(y[i])
        keep.append(i)
    keep = [i for i in keep if X[i].tobytes() not in conflicted]
    removed = len(y) - len(keep)
    return X[keep], y[keep], removed


def freeze_dataset(store, X: np.ndarray, y: np.ndarray,
                   feature_names: list[str], meta: dict,
                   seed: int = 42) -> dict:
    X, y, duplicates_removed = _deduplicate(X, y)
    ds_dir = store.path("dataset")
    os.makedirs(ds_dir, exist_ok=True)
    np.save(os.path.join(ds_dir, "X.npy"), X)
    np.save(os.path.join(ds_dir, "y.npy"), y)
    splits = make_splits(y, seed=seed)
    digest = split_hash(X, y, splits)
    with open(os.path.join(ds_dir, "splits.json"), "w", encoding="utf-8") as fh:
        json.dump(splits, fh)
    manifest = {
        "dataset": meta,
        "duplicates_removed_at_freeze": duplicates_removed,
        "feature_names": feature_names,
        "split_seed": seed,
        "split_sizes": {k: len(v) for k, v in splits.items()},
        "split_hash": digest,
        "class_balance": {
            "train_positive_rate": round(float(y[splits["train"]].mean()), 4),
            "validation_positive_rate": round(float(y[splits["validation"]].mean()), 4),
            "holdout_positive_rate": round(float(y[splits["holdout"]].mean()), 4),
        },
    }
    with open(os.path.join(ds_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    # Enforce the freeze: files read-only, directory read+execute only.
    for name in os.listdir(ds_dir):
        os.chmod(os.path.join(ds_dir, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    os.chmod(ds_dir, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP |
             stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    store.log("data.frozen", split_hash=digest,
              split_sizes=manifest["split_sizes"],
              duplicates_removed=duplicates_removed,
              dataset_source=meta.get("source"))
    return manifest


def load_frozen(store) -> dict:
    """Load the frozen dataset and verify its provenance hash."""
    ds_dir = store.path("dataset")
    with open(os.path.join(ds_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    X = np.load(os.path.join(ds_dir, "X.npy"))
    y = np.load(os.path.join(ds_dir, "y.npy"))
    with open(os.path.join(ds_dir, "splits.json"), encoding="utf-8") as fh:
        splits = json.load(fh)
    actual = split_hash(X, y, splits)
    if actual != manifest["split_hash"]:
        raise ValueError(
            f"split provenance mismatch: manifest {manifest['split_hash'][:12]}… "
            f"vs recomputed {actual[:12]}… — the frozen dataset was tampered with")
    return {"X": X, "y": y, "splits": splits, "manifest": manifest}
