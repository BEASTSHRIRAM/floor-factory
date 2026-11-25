# Model card — campaign campaign-001

**Goal:** binary classification: attack (1) vs BENIGN (0)
**Dataset:** CICIDS2017 sample (Kaggle: sweety18/cicids2017-full-dataset), prepared by ml_factory/prepare_cicids.py
**Metric:** f1 (higher_is_better) — binary F1 on the positive class, recomputed by Evaluation from raw predictions; campaign metric is the mean over >= 3 seeds
**Split hash (frozen):** `7572572fa0b8976343626ec465efc4824a68f553e306a1377c165b91b1b75f90`
**Data QA at freeze:** 5451 exact-duplicate rows removed by Data before splitting (duplicates straddling a split are leakage)

## Baselines (both scored by Evaluation, never by a worker)

- Stated baseline (default-config random forest (scikit-learn defaults)): validation F1 **0.991588**
- Dumb baseline (majority class): validation F1 **0.0**

## Hypotheses (pre-registered before any run)

| ID | Family | Agent | Bid ₡ | Verified val F1 (mean ± sd) | Verdict | Compute ₡ |
|---|---|---|---|---|---|---|
| H1 | random_forest | agent_forester | 62.4 | 0.993004 ± 0.000657 | KEPT | 0.3878 |
| H2 | gradient_boosting | agent_booster | 62.4 | 0.995816 ± 0.0 | KEPT | 0.5527 |
| H3 | mlp | agent_weaver | 62.4 | 0.991426 ± 0.000247 | discarded | 0.9622 |


## Result

Incumbent: hypothesis **H2**, verified validation F1 **0.995816** (stated baseline: 0.991588).
Holdout F1 (scored once, at close, by Evaluation): **0.996862**
Holdout untouched before close: **True**
Total campaign spend: **₡54.7027** (budget ₡600.0; wages and compute itemised in log.jsonl)

## Agents

- **Forester** (random_forest): reputation 56.0, jobs won 1, kept 1, earned ₡26.4
- **Booster** (gradient_boosting): reputation 56.0, jobs won 1, kept 1, earned ₡26.4
- **Weaver** (mlp): reputation 51.0, jobs won 1, kept 0, earned ₡0.0
  - lesson: mlp hypothesis H3 discarded — verified mean F1 0.9914 did not beat the incumbent 0.9958. Pre-registered falsifier: Verified mean validation F1 does not exceed the stated baseline.
