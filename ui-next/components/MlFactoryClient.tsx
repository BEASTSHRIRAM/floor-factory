"use client";

/* ML Factory — the sibling factory's campaign room (read-only).
 * Every number on this page comes from a committed campaign artefact
 * served by the API (/ml-factory/campaigns): the charter, the
 * baselines Evaluation scored, the verified verdicts, and the single
 * holdout score. Nothing here is recomputed or invented client-side. */

import { useEffect, useState } from "react";
import { API_BASE, credits } from "../lib/api";
import { ApiDown, Card, Loading, PageBody, PageHeader } from "./floor-ui";

type CampaignResult = {
  hypothesis_id: string;
  family: string;
  statement: string;
  agent_id: string;
  bid_price: number;
  verified_mean_f1: number;
  verified_std_f1: number;
  accepted: boolean;
  kept: boolean;
  failures: string[];
  compute_credits: number;
};

type CampaignAgent = {
  name: string;
  speciality: string;
  reputation: number;
  jobs_won: number;
  jobs_kept: number;
  earnings: number;
  lessons: string[];
};

type Campaign = {
  campaign_id: string;
  goal: string;
  dataset_source: string;
  dataset_rows: number;
  dataset_features: number;
  split_hash: string;
  duplicates_removed_at_freeze: number;
  metric: string;
  stated_baseline_f1: number;
  dumb_baseline_f1: number;
  incumbent: string | null;
  incumbent_val_f1: number;
  holdout_f1: number;
  holdout_untouched_before_close: boolean;
  total_spent_credits: number;
  campaign_budget_credits: number;
  results: CampaignResult[];
  agents: CampaignAgent[];
  log_events: number;
};

function f1(v: number) {
  return v.toFixed(4);
}

function VerdictPill({ r }: { r: CampaignResult }) {
  if (r.kept)
    return (
      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-2xs font-semibold text-emerald-500">
        Kept
      </span>
    );
  if (!r.accepted)
    return (
      <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-2xs font-semibold text-red-500">
        Rejected
      </span>
    );
  return (
    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
      Discarded
    </span>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-2xl">{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

export default function MlFactoryClient() {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/ml-factory/campaigns`);
        if (!res.ok) throw new Error("bad status");
        const data = await res.json();
        setCampaign(data.campaigns?.[0] ?? null);
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  return (
    <PageBody>
      <PageHeader
        title="ML Factory"
        sub="The lab next door: agents propose hypotheses, bid for experiment jobs, and are paid only for improvements an independent evaluator re-computes from raw predictions. Frozen splits, an anti-leakage battery, and a holdout touched exactly once."
      />
      {!loaded ? (
        <Loading />
      ) : !apiUp ? (
        <ApiDown what="the ML Factory" />
      ) : !campaign ? (
        <main className="mx-auto max-w-6xl px-6 py-6">
          <Card>
            <p className="text-sm text-muted-foreground">
              No campaign has been run yet. Campaigns are executed by the ML Factory engine and
              their verified artefacts appear here — this page never invents results.
            </p>
          </Card>
        </main>
      ) : (
        <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
          <Card>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              <Stat label="Campaign" value={campaign.campaign_id} sub={campaign.goal} />
              <Stat
                label="Stated baseline"
                value={f1(campaign.stated_baseline_f1)}
                sub={`validation ${campaign.metric.toUpperCase()} · dumb baseline ${f1(campaign.dumb_baseline_f1)}`}
              />
              <Stat
                label="Best verified"
                value={f1(campaign.incumbent_val_f1)}
                sub={campaign.incumbent ? `hypothesis ${campaign.incumbent}` : "the baseline itself"}
              />
              <Stat
                label="Holdout (once, at close)"
                value={f1(campaign.holdout_f1)}
                sub={campaign.holdout_untouched_before_close ? "untouched before close" : "hygiene check failed"}
              />
            </div>
            <p className="mt-5 text-xs text-muted-foreground">
              Dataset: {campaign.dataset_source} — {campaign.dataset_rows.toLocaleString("en-IN")}{" "}
              rows × {campaign.dataset_features} features ·{" "}
              {campaign.duplicates_removed_at_freeze.toLocaleString("en-IN")} exact duplicates
              removed by Data before splitting · split hash{" "}
              <span className="font-mono">{campaign.split_hash.slice(0, 12)}…</span> · spend{" "}
              {credits(campaign.total_spent_credits)} of {credits(campaign.campaign_budget_credits)}{" "}
              · {campaign.log_events} events in the append-only log
            </p>
          </Card>

          <Card>
            <h2 className="font-display text-lg">Hypotheses — pre-registered, then verified</h2>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-2xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3">ID</th>
                    <th className="py-2 pr-3">Family</th>
                    <th className="py-2 pr-3">Agent</th>
                    <th className="py-2 pr-3">Winning bid</th>
                    <th className="py-2 pr-3">Verified val F1</th>
                    <th className="py-2 pr-3">Compute</th>
                    <th className="py-2">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {campaign.results.map((r) => (
                    <tr key={r.hypothesis_id} className="border-b border-border/50 align-top">
                      <td className="py-2 pr-3 font-mono">{r.hypothesis_id}</td>
                      <td className="py-2 pr-3">{r.family}</td>
                      <td className="py-2 pr-3">{r.agent_id}</td>
                      <td className="py-2 pr-3">{credits(r.bid_price)}</td>
                      <td className="py-2 pr-3">
                        {f1(r.verified_mean_f1)} ± {r.verified_std_f1.toFixed(4)}
                      </td>
                      <td className="py-2 pr-3">{credits(r.compute_credits)}</td>
                      <td className="py-2">
                        <VerdictPill r={r} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {campaign.results.map((r) =>
              r.failures.length ? (
                <p key={r.hypothesis_id} className="mt-2 text-xs text-red-400">
                  {r.hypothesis_id} battery failures: {r.failures.join("; ")}
                </p>
              ) : null,
            )}
          </Card>

          <Card>
            <h2 className="font-display text-lg">Experiment agents</h2>
            <ul className="mt-3 space-y-3">
              {campaign.agents.map((a) => (
                <li key={a.name} className="text-sm">
                  <span className="font-semibold">{a.name}</span>{" "}
                  <span className="text-muted-foreground">({a.speciality})</span> — reputation{" "}
                  {a.reputation}, won {a.jobs_won}, kept {a.jobs_kept}, earned {credits(a.earnings)}
                  {a.lessons.map((l, i) => (
                    <p key={i} className="mt-1 text-xs text-muted-foreground">
                      Lesson: {l}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          </Card>
        </main>
      )}
    </PageBody>
  );
}
