"""The Experiments sandbox runner.

One experiment = ONE mutable training script, generated from the
pre-registered hypothesis, executed as a subprocess with a hard
wall-clock cap (the escrow: the run dies at its budget, it is not
negotiated with). The frozen dataset directory is read-only on disk;
the script receives its path as an argument and can only read it.

The script's contract (the frozen harness every generated script
shares): it is invoked as

    python train.py --data-dir <frozen dataset> --out-dir <run dir>
                    --seed <int> [--holdout]

and must write `predictions.npz` into its out dir containing
`val_idx`, `val_pred` and the `features_used` list. With --holdout it
additionally writes `holdout_idx` / `holdout_pred` — a flag only the
Evaluation module ever passes, at campaign close.

The runner records what the script *claims* (its self-reported metric)
but Evaluation never trusts it: Evaluation re-computes the metric from
the raw predictions.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HARNESS_PREAMBLE = '''"""Generated training script — the ONE mutable file of an experiment.
Frozen harness contract: reads the frozen dataset read-only, trains on
the train split, predicts the validation split, writes predictions.npz.
"""
import argparse, json, os, sys
import numpy as np

def load_frozen(data_dir):
    X = np.load(os.path.join(data_dir, "X.npy"))
    y = np.load(os.path.join(data_dir, "y.npy"))
    with open(os.path.join(data_dir, "splits.json")) as fh:
        splits = json.load(fh)
    return X, y, splits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--holdout", action="store_true")
    args = ap.parse_args()
    X, y, splits = load_frozen(args.data_dir)
    tr = np.asarray(splits["train"]); va = np.asarray(splits["validation"])
    model = build_model(args.seed)
    model.fit(X[tr], y[tr])
    val_pred = model.predict(X[va]).astype(int)
    out = {"val_idx": va, "val_pred": val_pred,
           "features_used": np.asarray(FEATURES_USED)}
    if args.holdout:
        ho = np.asarray(splits["holdout"])
        out["holdout_idx"] = ho
        out["holdout_pred"] = model.predict(X[ho]).astype(int)
    os.makedirs(args.out_dir, exist_ok=True)
    np.savez(os.path.join(args.out_dir, "predictions.npz"), **out)
    from sklearn.metrics import f1_score
    print(json.dumps({"self_reported_f1": float(f1_score(y[va], val_pred))}))

if __name__ == "__main__":
    main()
'''

# Model builders per hypothesis family. The hypothesis spec (a small
# JSON dict) is rendered into the script — the script is the artefact
# the agent "wrote", and it is what the ratchet keeps or discards.
BUILDERS = {
    "random_forest": '''from sklearn.ensemble import RandomForestClassifier

def build_model(seed):
    return RandomForestClassifier(
        n_estimators={n_estimators}, max_depth={max_depth},
        class_weight={class_weight!r}, random_state=seed, n_jobs=2)
''',
    "gradient_boosting": '''from sklearn.ensemble import HistGradientBoostingClassifier

def build_model(seed):
    return HistGradientBoostingClassifier(
        max_iter={max_iter}, learning_rate={learning_rate},
        max_depth={max_depth}, random_state=seed)
''',
    "mlp": '''from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

def build_model(seed):
    return make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes={hidden}, alpha={alpha},
                      max_iter={max_iter}, random_state=seed))
''',
}


def render_script(hypothesis: dict) -> str:
    """Render the hypothesis into its one mutable training script.

    v1 hypotheses vary the model family and its hyperparameters; every
    run uses all registered features (feature subsetting is not part of
    the v1 mutable surface, and the script says so rather than
    pretending otherwise).
    """
    family = hypothesis["family"]
    params = dict(hypothesis["params"])
    body = BUILDERS[family].format(**params)
    body += "\n# features: all registered features (v1 mutable surface "\
            "is the model, not the feature set)\n"
    script = HARNESS_PREAMBLE.replace(
        "FEATURES_USED", "list(range(X.shape[1]))")
    return body + "\n" + script


def run_script(script_path: str, data_dir: str, out_dir: str, seed: int,
               timeout_s: float, holdout: bool = False) -> dict:
    """Run one training script in a subprocess with a hard cap."""
    cmd = [sys.executable, script_path, "--data-dir", data_dir,
           "--out-dir", out_dir, "--seed", str(seed)]
    if holdout:
        cmd.append("--holdout")
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout_s)
        wall = time.time() - started
        self_reported = None
        for line in (proc.stdout or "").splitlines():
            try:
                self_reported = json.loads(line).get("self_reported_f1")
            except Exception:
                pass
        return {"ok": proc.returncode == 0, "wall_s": round(wall, 3),
                "self_reported_f1": self_reported,
                "stderr_tail": (proc.stderr or "")[-500:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "wall_s": round(time.time() - started, 3),
                "self_reported_f1": None,
                "stderr_tail": "KILLED: exceeded compute budget (hard cap)"}
