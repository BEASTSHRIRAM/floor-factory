"""ML Factory tests.

Run:  python -m pytest ml_factory/tests/ -q
  or: python -m ml_factory.tests.test_ml_factory   (plain runner)

The battery tests are the point of the factory, so they are tested
like it: a deliberately leaked feature MUST be caught, a tampered
split MUST be detected, a below-baseline result MUST be gated, and
the holdout MUST stay untouched until campaign close.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ml_factory import evaluator                       # noqa: E402
from ml_factory.campaign import BASELINE_SPEC, run_campaign  # noqa: E402
from ml_factory.freeze import freeze_dataset, load_frozen    # noqa: E402
from ml_factory.runner import render_script, run_script      # noqa: E402
from ml_factory.store import CampaignStore                   # noqa: E402

CHARTER = {"leakage_auc_threshold": 0.98}


def _tmp():
    return tempfile.mkdtemp(prefix="mlf_test_")


def _synthetic(n=600, leak=False, seed=3):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, 6)
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    names = [f"f{j}" for j in range(6)]
    if leak:
        X = np.column_stack([X, y + rng.randn(n) * 0.01])
        names.append("leaked_answer")
    return X, y, names


def _run_experiment(store, spec, exp_name):
    """Run a spec's script for 3 seeds and write its run record."""
    exp_dir = store.path("experiments", exp_name)
    os.makedirs(exp_dir, exist_ok=True)
    script_path = os.path.join(exp_dir, "train.py")
    with open(script_path, "w", encoding="utf-8") as fh:
        fh.write(render_script(spec))
    selfs = []
    for seed in (42, 43, 44):
        res = run_script(script_path, store.path("dataset"),
                         os.path.join(exp_dir, f"seed_{seed}"),
                         seed=seed, timeout_s=300)
        assert res["ok"], res["stderr_tail"]
        selfs.append(res["self_reported_f1"])
    store.write_json(os.path.join("experiments", exp_name, "run_record.json"),
                     {"self_reported_mean_f1": float(np.mean(selfs))})
    return exp_dir


def _hand_f1(y_true, y_pred):
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def test_recomputation_matches_independent_calculation():
    d = _tmp()
    try:
        store = CampaignStore(d)
        X, y, names = _synthetic()
        freeze_dataset(store, X, y, names, {"source": "synthetic"})
        frozen = load_frozen(store)
        exp_dir = _run_experiment(store, BASELINE_SPEC, "exp_recompute")
        verdict = evaluator.verify_experiment(store, frozen, exp_dir,
                                              CHARTER, baseline_f1=0.0,
                                              dumb_f1=0.0)
        # Independent hand computation from the raw predictions.
        va = np.asarray(frozen["splits"]["validation"])
        hand = []
        for seed in (42, 43, 44):
            pred = np.load(os.path.join(exp_dir, f"seed_{seed}",
                                        "predictions.npz"))
            hand.append(_hand_f1(y[va], np.asarray(pred["val_pred"])))
        # Verdict values are rounded to 6dp; compare within that.
        assert abs(verdict["verified_mean_f1"] - float(np.mean(hand))) < 2e-6
        recomp = [c for c in verdict["checks"]
                  if c["check"] == "metric_recomputation"][0]
        assert recomp["passed"], verdict
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_poison_leaked_feature_is_caught():
    d = _tmp()
    try:
        store = CampaignStore(d)
        X, y, names = _synthetic(leak=True)
        freeze_dataset(store, X, y, names, {"source": "synthetic+leak"})
        frozen = load_frozen(store)
        exp_dir = _run_experiment(store, BASELINE_SPEC, "exp_poison")
        verdict = evaluator.verify_experiment(store, frozen, exp_dir,
                                              CHARTER, baseline_f1=0.0,
                                              dumb_f1=0.0)
        assert not verdict["accepted"], verdict
        assert any(f.startswith("target_leakage")
                   for f in verdict["failures"]), verdict["failures"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_split_tampering_is_detected():
    d = _tmp()
    try:
        store = CampaignStore(d)
        X, y, names = _synthetic()
        freeze_dataset(store, X, y, names, {"source": "synthetic"})
        splits_path = store.path("dataset", "splits.json")
        os.chmod(store.path("dataset"), 0o755)
        os.chmod(splits_path, 0o644)
        with open(splits_path, encoding="utf-8") as fh:
            splits = json.load(fh)
        splits["validation"][0] = splits["train"][0]  # tamper
        with open(splits_path, "w", encoding="utf-8") as fh:
            json.dump(splits, fh)
        try:
            load_frozen(store)
            raise AssertionError("tampered splits were NOT detected")
        except ValueError as exc:
            assert "provenance mismatch" in str(exc)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_baseline_gate_rejects_below_dumb_result():
    d = _tmp()
    try:
        store = CampaignStore(d)
        rng = np.random.RandomState(5)
        n = 500
        X = rng.randn(n, 4)
        y = (rng.rand(n) < 0.9).astype(int)  # positive class is majority
        names = [f"f{j}" for j in range(4)]
        freeze_dataset(store, X, y, names, {"source": "synthetic"})
        frozen = load_frozen(store)
        va = np.asarray(frozen["splits"]["validation"])
        dumb = evaluator.dumb_baseline_metric(
            y[frozen["splits"]["train"]], y[va])
        assert dumb > 0.9  # all-positive predictions score ~0.94
        exp_dir = store.path("experiments", "exp_bad")
        for seed in (42, 43, 44):
            out = os.path.join(exp_dir, f"seed_{seed}")
            os.makedirs(out, exist_ok=True)
            np.savez(os.path.join(out, "predictions.npz"),
                     val_idx=va, val_pred=np.zeros(len(va), dtype=int),
                     features_used=np.arange(4))
        store.write_json(os.path.join("experiments", "exp_bad",
                                      "run_record.json"),
                         {"self_reported_mean_f1": 0.0})
        verdict = evaluator.verify_experiment(store, frozen, exp_dir,
                                              CHARTER, baseline_f1=0.0,
                                              dumb_f1=dumb)
        assert not verdict["accepted"]
        assert any(f.startswith("dumb_baseline_gate")
                   for f in verdict["failures"]), verdict["failures"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_holdout_untouched_until_close_and_log_order():
    d = _tmp()
    try:
        from ml_factory import datasets
        X, y, names, meta = datasets.load_breast_cancer()
        summary = run_campaign(d, {"X": X, "y": y, "feature_names": names,
                                   "meta": meta},
                               leakage_auc_threshold=0.999)
        assert summary["holdout_untouched_before_close"] is True
        store = CampaignStore(d)
        events = [r["event"] for r in store.read_log()]
        # Hypotheses registered before any job was posted.
        assert events.index("hypothesis.registered") < events.index("job.posted")
        # Holdout scored exactly once, and only as the campaign closes.
        assert events.count("holdout.scored") == 1
        assert events.index("holdout.scored") > events.index("campaign.closing")
        assert events[-1] == "campaign.closed"
        # The artefacts exist.
        for name in ("charter.json", "hypotheses.json", "model_card.md",
                     "model_card.json", "agents.json"):
            assert os.path.exists(store.path(name)), name
    finally:
        shutil.rmtree(d, ignore_errors=True)


ALL_TESTS = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failures = 0
    for t in ALL_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {t.__name__}: {exc!r}")
    sys.exit(1 if failures else 0)
