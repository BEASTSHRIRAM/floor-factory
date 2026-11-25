"""Run one ML Factory campaign end-to-end.

Usage:
    python -m ml_factory.run_campaign --dataset cicids \
        --data ml_factory/data/cicids2017_sample.npz \
        --campaign-dir ml_factory/campaigns/campaign-001
    python -m ml_factory.run_campaign --dataset breast_cancer \
        --campaign-dir ml_factory/campaigns/campaign-bc
"""
from __future__ import annotations

import argparse
import json

from . import datasets
from .campaign import run_campaign


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["cicids", "breast_cancer"],
                    default="cicids")
    ap.add_argument("--data", default=None,
                    help="prepared CICIDS sample .npz (for --dataset cicids)")
    ap.add_argument("--campaign-dir", required=True)
    args = ap.parse_args()

    if args.dataset == "cicids":
        X, y, names, meta = datasets.load_cicids_sample(args.data)
    else:
        X, y, names, meta = datasets.load_breast_cancer()
    summary = run_campaign(args.campaign_dir,
                           {"X": X, "y": y, "feature_names": names,
                            "meta": meta})
    print(json.dumps({
        "campaign": summary["charter"]["campaign_id"],
        "baseline_f1": summary["charter"]["stated_baseline"]["verified_validation_f1"],
        "incumbent": summary["incumbent"]["hypothesis_id"] or "stated_baseline",
        "incumbent_val_f1": summary["incumbent"]["verified_mean_f1"],
        "holdout_f1": summary["holdout"]["holdout_f1"],
        "total_spent_credits": summary["total_spent_credits"],
    }, indent=2))


if __name__ == "__main__":
    main()
