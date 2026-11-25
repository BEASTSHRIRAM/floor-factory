"""Evaluation — a separate module the experiment workers cannot touch.

It never reads a worker's claimed metric as truth. It re-computes the
campaign metric from the run's raw predictions, and runs the
deterministic anti-leakage battery BEFORE any verdict:

  1. split provenance   — frozen hash verified; the run's validation
                          indices must be exactly the frozen ones
  2. metric recomputation — from raw predictions, with the frozen
                          metric implementation; a self-report that
                          disagrees beyond tolerance is flagged
  3. train/test overlap — exact row-hash overlap between the frozen
                          train and validation splits must be zero
  4. target-leakage scan — every feature's solo predictive power
                          (univariate AUC on the train split); a
                          feature above the charter threshold is a
                          column that encodes the answer → reject
  5. feature provenance — the run's features_used must be a subset of
                          the features registered at freeze time
  6. seed discipline    — >= 3 seed runs; the verified metric is the
                          MEAN of the recomputed per-seed metrics
  7. baseline gate      — the verified mean must beat the dumb
                          baseline (majority class) or the run is a
                          rejection, not a result; beating the stated
                          baseline is the ratchet's keep test
  8. holdout hygiene    — no holdout predictions may exist anywhere
                          in the campaign before close; the holdout is
                          scored exactly once, here, at close
"""
from __future__ import annotations

import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, roc_auc_score

from .freeze import load_frozen
from .runner import run_script

FLOAT_TOL = 1e-6


def metric(y_true, y_pred) -> float:
    return float(f1_score(y_true, y_pred, zero_division=0))


def dumb_baseline_metric(y_train, y_val) -> float:
    majority = int(np.bincount(y_train).argmax())
    return metric(y_val, np.full(len(y_val), majority))


def stated_baseline_metric(frozen, seed: int = 42) -> float:
    """The charter's stated baseline: a default-config random forest,
    trained and scored by Evaluation — never by a worker."""
    X, y, splits = frozen["X"], frozen["y"], frozen["splits"]
    tr, va = splits["train"], splits["validation"]
    model = RandomForestClassifier(random_state=seed)  # all defaults
    model.fit(X[tr], y[tr])
    return metric(y[va], model.predict(X[va]))


def _row_hashes(X, idx) -> set:
    return {X[i].tobytes() for i in idx}


def overlap_scan(frozen) -> int:
    X, splits = frozen["X"], frozen["splits"]
    train_hashes = _row_hashes(X, splits["train"])
    val_hashes = _row_hashes(X, splits["validation"])
    return len(train_hashes & val_hashes)


def leakage_scan(frozen, threshold: float) -> list[dict]:
    """Single-feature AUC of every feature against the target, train
    split only. A feature that nearly is the answer gets flagged."""
    X, y, splits = frozen["X"], frozen["y"], frozen["splits"]
    tr = splits["train"]
    ytr = y[tr]
    flagged = []
    names = frozen["manifest"]["feature_names"]
    for j in range(X.shape[1]):
        col = X[tr, j]
        if np.all(col == col[0]):
            continue
        try:
            auc = roc_auc_score(ytr, col)
        except ValueError:
            continue
        solo = max(auc, 1.0 - auc)
        if solo >= threshold:
            flagged.append({"feature_index": j, "feature": names[j],
                            "solo_auc": round(float(solo), 4)})
    return flagged


def verify_experiment(store, frozen, exp_dir: str, charter: dict,
                      baseline_f1: float, dumb_f1: float) -> dict:
    """Run the full battery over one experiment's seed runs.

    exp_dir holds one subdirectory per seed (seed_<n>/predictions.npz)
    plus run_record.json written by the campaign engine.
    """
    X, y, splits = frozen["X"], frozen["y"], frozen["splits"]
    checks: list[dict] = []
    failures: list[str] = []

    def check(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        if not ok:
            failures.append(f"{name}: {detail}")

    # 1. split provenance — load_frozen already verified the hash;
    #    here the run's indices must match the frozen validation split.
    va = np.asarray(splits["validation"])
    seed_dirs = sorted(d for d in os.listdir(exp_dir)
                       if d.startswith("seed_"))
    per_seed = []
    idx_ok, prov_ok, selfreport_ok = True, True, True
    n_features = X.shape[1]
    for sd in seed_dirs:
        pred_path = os.path.join(exp_dir, sd, "predictions.npz")
        if not os.path.exists(pred_path):
            idx_ok = False
            continue
        pred = np.load(pred_path, allow_pickle=True)
        if not np.array_equal(np.asarray(pred["val_idx"]), va):
            idx_ok = False
        used = [int(i) for i in np.asarray(pred["features_used"]).tolist()]
        if any(i < 0 or i >= n_features for i in used):
            prov_ok = False
        per_seed.append(metric(y[va], np.asarray(pred["val_pred"])))
    check("split_provenance", idx_ok,
          "run validation indices == frozen validation indices"
          if idx_ok else "run used different validation indices than frozen")
    check("feature_provenance", prov_ok,
          "features_used within the registered feature set"
          if prov_ok else "run used an unregistered feature index")

    # 2. metric recomputation — per_seed above IS the recomputation;
    #    compare against the run record's self-report.
    record_path = os.path.join(exp_dir, "run_record.json")
    self_mean = None
    if os.path.exists(record_path):
        import json
        with open(record_path, encoding="utf-8") as fh:
            record = json.load(fh)
        self_mean = record.get("self_reported_mean_f1")
    if per_seed and self_mean is not None:
        recomputed_mean = float(np.mean(per_seed))
        selfreport_ok = abs(recomputed_mean - self_mean) <= 1e-3
    check("metric_recomputation", selfreport_ok,
          f"recomputed mean F1 vs self-reported mean F1 "
          f"({self_mean}) within tolerance"
          if selfreport_ok else
          f"self-report {self_mean} disagrees with recomputation "
          f"{float(np.mean(per_seed)) if per_seed else None}")

    # 3. overlap scan (frozen splits; a run cannot change these, but
    #    the battery re-proves it every time).
    overlap = overlap_scan(frozen)
    check("train_test_overlap", overlap == 0,
          f"{overlap} exact duplicate rows shared by train/validation")

    # 4. target-leakage scan.
    flagged = leakage_scan(frozen, charter["leakage_auc_threshold"])
    check("target_leakage", not flagged,
          "no feature above the solo-AUC threshold"
          if not flagged else f"leaky features: {flagged}")

    # 6. seed discipline.
    check("seed_discipline", len(per_seed) >= 3,
          f"{len(per_seed)} seed runs recomputed (need >= 3)")

    verified_mean = float(np.mean(per_seed)) if per_seed else 0.0
    verified_std = float(np.std(per_seed)) if per_seed else 0.0

    # 7. baseline gate — losing to the dumb baseline is a rejection.
    check("dumb_baseline_gate", verified_mean > dumb_f1,
          f"verified mean F1 {verified_mean:.4f} vs dumb baseline {dumb_f1:.4f}")

    accepted = not failures
    beats_baseline = verified_mean > baseline_f1
    return {
        "accepted": accepted,
        "checks": checks,
        "failures": failures,
        "verified_mean_f1": round(verified_mean, 6),
        "verified_std_f1": round(verified_std, 6),
        "per_seed_f1": [round(v, 6) for v in per_seed],
        "beats_stated_baseline": bool(beats_baseline),
        "stated_baseline_f1": round(baseline_f1, 6),
        "dumb_baseline_f1": round(dumb_f1, 6),
    }


def assert_holdout_untouched(store) -> bool:
    """Battery check 8: no holdout predictions anywhere yet."""
    for root, _dirs, files in os.walk(store.dir):
        if "dataset" in root:
            continue
        for f in files:
            if f == "predictions.npz":
                import numpy as np
                pred = np.load(os.path.join(root, f), allow_pickle=True)
                if "holdout_pred" in pred:
                    return False
    return True


def score_holdout(store, frozen, script_path: str, work_dir: str,
                  timeout_s: float = 600.0) -> dict:
    """Campaign close: Evaluation itself runs the incumbent script
    once with the holdout flag and scores it. The only holdout touch
    in the entire campaign."""
    result = run_script(script_path, store.path("dataset"), work_dir,
                        seed=42, timeout_s=timeout_s, holdout=True)
    if not result["ok"]:
        raise RuntimeError(f"holdout run failed: {result['stderr_tail']}")
    pred = np.load(os.path.join(work_dir, "predictions.npz"),
                   allow_pickle=True)
    y = frozen["y"]
    ho = np.asarray(frozen["splits"]["holdout"])
    if not np.array_equal(np.asarray(pred["holdout_idx"]), ho):
        raise RuntimeError("holdout indices mismatch at campaign close")
    value = metric(y[ho], np.asarray(pred["holdout_pred"]))
    store.log("holdout.scored", holdout_f1=round(value, 6),
              scored_by="evaluation")
    return {"holdout_f1": round(value, 6)}
