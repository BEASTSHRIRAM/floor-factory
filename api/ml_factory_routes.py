"""ML Factory read-only routes.

Serves committed campaign artefacts (charter, hypotheses, verified
verdicts, model card) from ml_factory/campaigns/<id>/ so the console
can show a campaign exactly as Evaluation verified it. Read-only by
design: campaigns are run by the campaign engine, never from the API.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ml-factory", tags=["ml-factory"])

CAMPAIGNS_DIR = Path(__file__).resolve().parent.parent / "ml_factory" / "campaigns"


def _read_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _campaign_summary(campaign_dir: Path) -> dict:
    card = _read_json(campaign_dir / "model_card.json")
    charter = card["charter"]
    results = []
    for r in card["results"]:
        results.append({
            "hypothesis_id": r["hypothesis"]["id"],
            "family": r["hypothesis"]["family"],
            "statement": r["hypothesis"]["statement"],
            "agent_id": r["agent_id"],
            "bid_price": r["bid"]["price"],
            "verified_mean_f1": r["verdict"]["verified_mean_f1"],
            "verified_std_f1": r["verdict"]["verified_std_f1"],
            "accepted": r["verdict"]["accepted"],
            "kept": r["kept"],
            "failures": r["verdict"]["failures"],
            "compute_credits": r["compute_credits"],
        })
    log_path = campaign_dir / "log.jsonl"
    log_events = 0
    if log_path.exists():
        with open(log_path, encoding="utf-8") as fh:
            log_events = sum(1 for line in fh if line.strip())
    return {
        "campaign_id": charter["campaign_id"],
        "goal": charter["goal"],
        "dataset_source": charter["dataset"].get("source"),
        "dataset_rows": charter["dataset"].get("rows"),
        "dataset_features": charter["dataset"].get("features"),
        "split_hash": charter["split_hash"],
        "duplicates_removed_at_freeze":
            charter.get("duplicates_removed_at_freeze", 0),
        "metric": charter["metric"]["name"],
        "stated_baseline_f1":
            charter["stated_baseline"]["verified_validation_f1"],
        "dumb_baseline_f1": charter["dumb_baseline_f1"],
        "incumbent": card["incumbent"]["hypothesis_id"],
        "incumbent_val_f1": card["incumbent"]["verified_mean_f1"],
        "holdout_f1": card["holdout"]["holdout_f1"],
        "holdout_untouched_before_close":
            card["holdout_untouched_before_close"],
        "total_spent_credits": card["total_spent_credits"],
        "campaign_budget_credits": charter["campaign_budget_credits"],
        "results": results,
        "agents": card["agents"],
        "log_events": log_events,
    }


@router.get("/campaigns")
def list_campaigns():
    if not CAMPAIGNS_DIR.exists():
        return {"campaigns": []}
    out = []
    for name in sorted(os.listdir(CAMPAIGNS_DIR)):
        card = CAMPAIGNS_DIR / name / "model_card.json"
        if card.exists():
            out.append(_campaign_summary(CAMPAIGNS_DIR / name))
    return {"campaigns": out}


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str):
    campaign_dir = CAMPAIGNS_DIR / campaign_id
    if not (campaign_dir / "model_card.json").exists():
        raise HTTPException(status_code=404, detail="campaign not found")
    return _campaign_summary(campaign_dir)
