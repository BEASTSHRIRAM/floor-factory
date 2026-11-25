# ML Factory — v1

A sibling factory to THE FLOOR, built on the same economy: agents
propose hypotheses, bid for experiment jobs, run experiments, and are
paid only for metric improvements an **independent evaluator
re-computes from raw predictions**. Design: `ml_factory/ML_FACTORY.md`
in the project workspace (the factory itself lives here, in the repo).

## The loop

```
charter (human-signed: dataset, metric, baseline, budgets)
  → Data freezes the dataset (splits + provenance hash, duplicates
    removed, directory chmod'ed read-only)
  → Evaluation scores the stated baseline and the dumb baseline
  → hypotheses pre-registered (before any run exists)
  → each hypothesis becomes a job: agents bid (fee + compute estimate),
    awarded by THE FLOOR's formula
        score = 0.5*(1 - price/cap) + 0.3*(reputation/100) + 0.2*confidence
  → the winner's ONE mutable training script runs in a subprocess
    sandbox, 3 seeds, hard wall-clock cap (the compute escrow)
  → Evaluation re-computes the metric from raw predictions and runs
    the anti-leakage battery: split provenance · metric recomputation
    · train/test overlap · target-leakage scan · feature provenance ·
    seed discipline (mean of >= 3 seeds) · dumb-baseline gate ·
    holdout hygiene
  → keep/discard is mechanical; discards write lessons into the
    agent's record; kept runs pay the winner's fee
  → holdout scored exactly once, at campaign close, by Evaluation
  → model card (Markdown + JSON) is the campaign's report
```

A campaign where nothing beats the baseline is a successful v1 if
the machinery verified — the factory's product is verified truth
about what was tried, not a guaranteed improvement.

## Run it

```bash
.venv/bin/pip install scikit-learn pandas   # campaign dependencies

# prepare the CICIDS2017 sample (one-time; raw CSV from the Kaggle
# dataset sweety18/cicids2017-full-dataset)
.venv/bin/python -m ml_factory.prepare_cicids <raw_combine.csv> \
    ml_factory/data/cicids2017_sample.npz 20000

# run a campaign
.venv/bin/python -m ml_factory.run_campaign --dataset cicids \
    --data ml_factory/data/cicids2017_sample.npz \
    --campaign-dir ml_factory/campaigns/campaign-001

# tests (the battery is tested like it matters)
.venv/bin/python -m ml_factory.tests.test_ml_factory
```

## Layout

| File | Role |
|---|---|
| `campaign.py` | the campaign engine (charter → close) |
| `freeze.py` | Data: split once, hash, dedupe, chmod read-only |
| `agents.py` | personas, sealed bids, the floor's award formula |
| `runner.py` | sandbox: one mutable script per experiment, hard cap |
| `evaluator.py` | Evaluation: recomputation + the 8-check battery |
| `report.py` | the model card |
| `datasets.py` / `prepare_cicids.py` | dataset loading / preparation |
| `campaigns/<id>/` | committed campaign evidence: charter, log, card |
