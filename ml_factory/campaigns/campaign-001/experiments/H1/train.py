from sklearn.ensemble import RandomForestClassifier

def build_model(seed):
    return RandomForestClassifier(
        n_estimators=400, max_depth=None,
        class_weight='balanced', random_state=seed, n_jobs=2)

# features: all registered features (v1 mutable surface is the model, not the feature set)

"""Generated training script — the ONE mutable file of an experiment.
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
           "features_used": np.asarray(list(range(X.shape[1])))}
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
