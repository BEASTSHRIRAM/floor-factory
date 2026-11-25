"""The campaign engine: one research goal, run end-to-end.

    charter → freeze → baseline scored by Evaluation → hypotheses
    pre-registered → each hypothesis becomes a job → agents bid →
    winner's script runs in the sandbox (3 seeds, hard cap) →
    Evaluation re-computes + runs the battery → keep/discard ratchet →
    lessons written → holdout scored once, at close → model card.

Every step appends to the campaign's append-only log. The ordering in
the log is the audit: hypotheses are registered before any job is
posted; the holdout event exists exactly once, after campaign close
begins.
"""
from __future__ import annotations

import json
import os
import time

from . import evaluator
from .agents import award_job, default_roster
from .freeze import freeze_dataset, load_frozen
from .report import write_model_card
from .runner import render_script, run_script
from .store import CampaignStore

SEEDS = (42, 43, 44)

DEFAULT_HYPOTHESES = [
    {
        "id": "H1",
        "family": "random_forest",
        "statement": "A larger random forest with balanced class weights "
                     "beats the default-config forest on attack detection.",
        "falsifier": "Verified mean validation F1 does not exceed the "
                     "stated baseline.",
        "params": {"n_estimators": 400, "max_depth": None,
                   "class_weight": "balanced"},
    },
    {
        "id": "H2",
        "family": "gradient_boosting",
        "statement": "Histogram gradient boosting (300 rounds, lr 0.08) "
                     "beats the stated baseline by fitting attack "
                     "boundaries the forest smooths over.",
        "falsifier": "Verified mean validation F1 does not exceed the "
                     "stated baseline.",
        "params": {"max_iter": 300, "learning_rate": 0.08, "max_depth": None},
    },
    {
        "id": "H3",
        "family": "mlp",
        "statement": "A small MLP (128-64) on standardised features "
                     "beats the stated baseline by learning feature "
                     "interactions trees miss.",
        "falsifier": "Verified mean validation F1 does not exceed the "
                     "stated baseline.",
        "params": {"hidden": (128, 64), "alpha": 0.001, "max_iter": 300},
    },
]

BASELINE_SPEC = {
    "family": "random_forest",
    "params": {"n_estimators": 100, "max_depth": None, "class_weight": None},
    "description": "default-config random forest (scikit-learn defaults)",
}


def run_campaign(campaign_dir: str, dataset: dict,
                 hypotheses: list[dict] | None = None,
                 per_experiment_cap: float = 120.0,
                 campaign_budget: float = 600.0,
                 cpu_rate_per_min: float = 1.0,
                 leakage_auc_threshold: float = 0.98) -> dict:
    hypotheses = hypotheses or DEFAULT_HYPOTHESES
    store = CampaignStore(campaign_dir)
    X, y, feature_names, meta = (dataset["X"], dataset["y"],
                                 dataset["feature_names"], dataset["meta"])
    store.log("campaign.opened", goal=meta.get("task"),
              dataset_source=meta.get("source"))

    # -- Data: freeze before anything else exists ----------------------
    manifest = freeze_dataset(store, X, y, feature_names, meta)
    frozen = load_frozen(store)

    # -- Evaluation scores the baselines (workers never do) ------------
    baseline_f1 = evaluator.stated_baseline_metric(frozen)
    fy = frozen["y"]
    dumb_f1 = evaluator.dumb_baseline_metric(
        fy[frozen["splits"]["train"]], fy[frozen["splits"]["validation"]])
    store.log("baseline.scored", stated_baseline_f1=round(baseline_f1, 6),
              dumb_baseline_f1=round(dumb_f1, 6), scored_by="evaluation")

    charter = {
        "campaign_id": os.path.basename(os.path.normpath(campaign_dir)),
        "goal": meta.get("task"),
        "dataset": meta,
        "metric": {"name": "f1", "direction": "higher_is_better",
                   "definition": "binary F1 on the positive class, "
                                 "recomputed by Evaluation from raw "
                                 "predictions; campaign metric is the "
                                 "mean over >= 3 seeds"},
        "stated_baseline": {**BASELINE_SPEC,
                            "verified_validation_f1": round(baseline_f1, 6)},
        "dumb_baseline_f1": round(dumb_f1, 6),
        "split_hash": manifest["split_hash"],
        "duplicates_removed_at_freeze": manifest["duplicates_removed_at_freeze"],
        "leakage_auc_threshold": leakage_auc_threshold,
        "rate_card": {"cpu_credit_per_minute": cpu_rate_per_min,
                      "note": "local CPU sandbox, priced nominally so "
                              "compute burn is visible in the same units "
                              "as wages"},
        "per_experiment_cap_credits": per_experiment_cap,
        "campaign_budget_credits": campaign_budget,
        "holdout_policy": "holdout is not mounted in any experiment; "
                          "scored exactly once, by Evaluation, at "
                          "campaign close",
        "signed_by": "human (charter layer)",
    }
    store.write_json("charter.json", charter)
    store.log("charter.frozen", baseline_f1=round(baseline_f1, 6),
              per_experiment_cap=per_experiment_cap,
              campaign_budget=campaign_budget)

    # -- Research: hypotheses pre-registered before any job ------------
    store.write_json("hypotheses.json", hypotheses)
    for h in hypotheses:
        store.log("hypothesis.registered", hypothesis_id=h["id"],
                  family=h["family"], statement=h["statement"],
                  falsifier=h["falsifier"])

    # -- Experiments: bid, run, verify, ratchet -------------------------
    agents = default_roster()
    agents_by_id = {a.id: a for a in agents}
    incumbent = {"hypothesis_id": None, "script": None,
                 "verified_mean_f1": baseline_f1}
    results = []
    spent = 0.0
    for h in hypotheses:
        job = {"id": f"job_{h['id']}", "hypothesis_id": h["id"],
               "family": h["family"], "cap": per_experiment_cap}
        store.log("job.posted", job_id=job["id"], family=h["family"],
                  cap=per_experiment_cap)
        winning_bid = award_job(store, job, agents)
        winner = agents_by_id[winning_bid["agent_id"]]

        exp_dir = store.path("experiments", h["id"])
        os.makedirs(exp_dir, exist_ok=True)
        script = render_script(h)
        script_path = os.path.join(exp_dir, "train.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script)

        per_seed_timeout = (per_experiment_cap / cpu_rate_per_min) * 60 / len(SEEDS)
        run_records = []
        wall_total = 0.0
        for seed in SEEDS:
            out_dir = os.path.join(exp_dir, f"seed_{seed}")
            res = run_script(script_path, store.path("dataset"), out_dir,
                             seed=seed, timeout_s=per_seed_timeout)
            run_records.append({"seed": seed, **res})
            wall_total += res["wall_s"]
            store.log("run.completed", job_id=job["id"], seed=seed,
                      ok=res["ok"], wall_s=res["wall_s"],
                      self_reported_f1=res["self_reported_f1"])
        self_reports = [r["self_reported_f1"] for r in run_records
                        if r["self_reported_f1"] is not None]
        compute_credits = round(wall_total / 60.0 * cpu_rate_per_min, 4)
        spent += compute_credits
        store.log("compute.charged", job_id=job["id"],
                  credits=compute_credits, wall_s=round(wall_total, 3))
        record = {
            "hypothesis_id": h["id"], "agent_id": winner.id,
            "winning_bid": winning_bid,
            "runs": run_records,
            "self_reported_mean_f1": (round(sum(self_reports) / len(self_reports), 6)
                                      if self_reports else None),
            "compute_credits": compute_credits,
        }
        store.write_json(os.path.join("experiments", h["id"], "run_record.json"),
                         record)

        verdict = evaluator.verify_experiment(store, frozen, exp_dir,
                                              charter, baseline_f1, dumb_f1)
        kept = bool(verdict["accepted"]
                    and verdict["verified_mean_f1"] > incumbent["verified_mean_f1"])
        store.log("evaluation.verdict", job_id=job["id"],
                  accepted=verdict["accepted"], kept=kept,
                  verified_mean_f1=verdict["verified_mean_f1"],
                  failures=verdict["failures"])
        if kept:
            incumbent = {"hypothesis_id": h["id"], "script": script_path,
                         "verified_mean_f1": verdict["verified_mean_f1"]}
            winner.jobs_kept += 1
            winner.reputation += 6.0
            winner.earnings += winning_bid["fee"]
            spent += winning_bid["fee"]
            store.log("ratchet.kept", hypothesis_id=h["id"],
                      verified_mean_f1=verdict["verified_mean_f1"])
            store.log("payment.made", job_id=job["id"], agent_id=winner.id,
                      fee=winning_bid["fee"],
                      reason="verified improvement accepted")
        else:
            if verdict["accepted"]:
                winner.reputation += 1.0
                reason = (f"verified mean F1 {verdict['verified_mean_f1']:.4f} "
                          f"did not beat the incumbent "
                          f"{incumbent['verified_mean_f1']:.4f}")
            else:
                winner.reputation -= 8.0
                reason = "rejected by the battery: " + "; ".join(verdict["failures"])
            lesson = (f"{h['family']} hypothesis {h['id']} discarded — {reason}. "
                      f"Pre-registered falsifier: {h['falsifier']}")
            winner.lessons.append(lesson)
            store.log("ratchet.discarded", hypothesis_id=h["id"], reason=reason)
            store.log("lesson.written", agent_id=winner.id, lesson=lesson)
        results.append({"hypothesis": h, "agent_id": winner.id,
                        "bid": winning_bid, "verdict": verdict,
                        "kept": kept, "compute_credits": compute_credits})

    # -- Close: holdout hygiene first, then the single holdout touch ---
    untouched = evaluator.assert_holdout_untouched(store)
    store.log("holdout.hygiene_checked", untouched_before_close=untouched)
    if incumbent["script"] is None:
        # Incumbent is the baseline itself: render its script so the
        # holdout path is identical (Evaluation runs the script).
        base_dir = store.path("experiments", "baseline_incumbent")
        os.makedirs(base_dir, exist_ok=True)
        incumbent_script = os.path.join(base_dir, "train.py")
        with open(incumbent_script, "w", encoding="utf-8") as fh:
            fh.write(render_script(BASELINE_SPEC))
    else:
        incumbent_script = incumbent["script"]
    store.log("campaign.closing",
              incumbent=incumbent["hypothesis_id"] or "stated_baseline")
    holdout = evaluator.score_holdout(
        store, frozen, incumbent_script,
        store.path("experiments", "holdout_close"))
    store.log("campaign.closed", holdout_f1=holdout["holdout_f1"],
              total_spent_credits=round(spent, 4))

    store.write_json("agents.json", [a.to_dict() for a in agents])
    summary = {
        "charter": charter, "results": results, "incumbent": incumbent,
        "holdout": holdout, "total_spent_credits": round(spent, 4),
        "agents": [a.to_dict() for a in agents],
        "holdout_untouched_before_close": untouched,
        "finished_at": round(time.time(), 3),
    }
    write_model_card(store, summary)
    return summary
