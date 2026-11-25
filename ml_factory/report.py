"""Reporting: the model card — the campaign's paid artefact.

Written from the campaign summary only (verified numbers, never
self-reports presented as results). An honest "nothing beat the
baseline" card is a successful campaign report: the factory's job is
verified truth about what was tried, not a guaranteed improvement.
"""
from __future__ import annotations

import json
import os


def write_model_card(store, summary: dict) -> None:
    charter = summary["charter"]
    lines = []
    lines.append(f"# Model card — campaign {charter['campaign_id']}")
    lines.append("")
    lines.append(f"**Goal:** {charter['goal']}")
    lines.append(f"**Dataset:** {charter['dataset'].get('source')}")
    lines.append(f"**Metric:** {charter['metric']['name']} "
                 f"({charter['metric']['direction']}) — "
                 f"{charter['metric']['definition']}")
    lines.append(f"**Split hash (frozen):** `{charter['split_hash']}`")
    lines.append(f"**Data QA at freeze:** {charter.get('duplicates_removed_at_freeze', 0)} "
                 f"exact-duplicate rows removed by Data before splitting "
                 f"(duplicates straddling a split are leakage)")
    lines.append("")
    lines.append("## Baselines (both scored by Evaluation, never by a worker)")
    lines.append("")
    lines.append(f"- Stated baseline ({charter['stated_baseline']['description']}): "
                 f"validation F1 **{charter['stated_baseline']['verified_validation_f1']}**")
    lines.append(f"- Dumb baseline (majority class): validation F1 "
                 f"**{charter['dumb_baseline_f1']}**")
    lines.append("")
    lines.append("## Hypotheses (pre-registered before any run)")
    lines.append("")
    lines.append("| ID | Family | Agent | Bid ₡ | Verified val F1 (mean ± sd) | Verdict | Compute ₡ |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in summary["results"]:
        h, v = r["hypothesis"], r["verdict"]
        verdict = ("KEPT" if r["kept"] else
                   "discarded" if v["accepted"] else "REJECTED")
        lines.append(
            f"| {h['id']} | {h['family']} | {r['agent_id']} | "
            f"{r['bid']['price']} | {v['verified_mean_f1']} ± {v['verified_std_f1']} | "
            f"{verdict} | {r['compute_credits']} |")
    lines.append("")
    for r in summary["results"]:
        v = r["verdict"]
        if v["failures"]:
            lines.append(f"- **{r['hypothesis']['id']} battery failures:** "
                         + "; ".join(v["failures"]))
    lines.append("")
    lines.append("## Result")
    lines.append("")
    inc = summary["incumbent"]
    if inc["hypothesis_id"]:
        lines.append(f"Incumbent: hypothesis **{inc['hypothesis_id']}**, "
                     f"verified validation F1 **{inc['verified_mean_f1']}** "
                     f"(stated baseline: "
                     f"{charter['stated_baseline']['verified_validation_f1']}).")
    else:
        lines.append("Incumbent: **the stated baseline itself** — no "
                     "hypothesis beat it under independent evaluation. "
                     "That is an honest campaign result, reported as-is.")
    lines.append(f"Holdout F1 (scored once, at close, by Evaluation): "
                 f"**{summary['holdout']['holdout_f1']}**")
    lines.append(f"Holdout untouched before close: "
                 f"**{summary['holdout_untouched_before_close']}**")
    lines.append(f"Total campaign spend: **₡{summary['total_spent_credits']}** "
                 f"(budget ₡{charter['campaign_budget_credits']}; wages and "
                 f"compute itemised in log.jsonl)")
    lines.append("")
    lines.append("## Agents")
    lines.append("")
    for a in summary["agents"]:
        lines.append(f"- **{a['name']}** ({a['speciality']}): reputation "
                     f"{a['reputation']}, jobs won {a['jobs_won']}, kept "
                     f"{a['jobs_kept']}, earned ₡{a['earnings']}")
        for lesson in a["lessons"]:
            lines.append(f"  - lesson: {lesson}")
    lines.append("")
    card_md = "\n".join(lines)
    with open(store.path("model_card.md"), "w", encoding="utf-8") as fh:
        fh.write(card_md)
    serialisable = json.loads(json.dumps(summary, default=str))
    store.write_json("model_card.json", serialisable)
