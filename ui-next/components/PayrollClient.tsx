"use client";

/* Payroll — the floor's wage book, structured the way real payroll
 * systems structure it (runs -> entries -> payslips; cf. ERPNext
 * Payroll / Horilla) and the way PaySilo ran multi-employer payroll:
 * a run settles a whole cycle at once, and every agent's payslip is
 * just its slice of the append-only ledger.
 *
 * Data: GET /state/ledger (every row), GET /state/agents, and the
 * cycle.closed events (their payroll payload carries each cycle's
 * per-agent verdicts). All amounts are internal credits (₡) — the
 * payment-rails section at the bottom says, in plain words, what
 * that means and what connecting a real rail would take. */

import { useEffect, useMemo, useState } from "react";
import { credits, signedCredits } from "../lib/api";
import {
  COST_KINDS,
  EARN_KINDS,
  FINE_KINDS,
  KIND_LABELS,
  earnedOf,
  fetchAgents,
  fetchAllEvents,
  fetchLedger,
  groupBy,
  sumKinds,
  type RawAgent,
  type RawLedgerRow,
} from "../lib/floorData";
import { ApiDown, Card, Loading, PageBody, PageHeader } from "./floor-ui";

interface CycleClosed {
  cycle_no: number;
  payroll: { agent_id: number; name: string; verdict: string }[];
  fired: { name?: string }[] | string[];
  hired: { name?: string }[] | string[];
}

const RAILS: { name: string; blurb: string }[] = [
  { name: "Stripe", blurb: "Cards, billing and payouts over the Stripe API." },
  { name: "Razorpay", blurb: "UPI, cards and payouts for Indian businesses." },
  { name: "PayPal", blurb: "PayPal balances and payouts across 200+ markets." },
];

export default function PayrollClient() {
  const [agents, setAgents] = useState<RawAgent[]>([]);
  const [ledger, setLedger] = useState<RawLedgerRow[]>([]);
  const [closed, setClosed] = useState<Map<number, CycleClosed>>(new Map());
  const [apiUp, setApiUp] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [payslipAgent, setPayslipAgent] = useState<number | null>(null);
  const [openRail, setOpenRail] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [a, l, ev] = await Promise.all([fetchAgents(), fetchLedger(), fetchAllEvents()]);
        setAgents(a);
        setLedger(l);
        const m = new Map<number, CycleClosed>();
        for (const e of ev) {
          if (e.type !== "cycle.closed") continue;
          const p = e.payload as unknown as CycleClosed;
          if (typeof p?.cycle_no === "number") m.set(p.cycle_no, p);
        }
        setClosed(m);
        setApiUp(true);
      } catch {
        setApiUp(false);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const byCycle = useMemo(() => groupBy(ledger, (r) => r.cycle_no), [ledger]);
  const cycles = useMemo(
    () => [...byCycle.keys()].map(Number).sort((x, y) => y - x),
    [byCycle],
  );
  const byAgent = useMemo(() => groupBy(ledger, (r) => r.agent_id), [ledger]);

  useEffect(() => {
    if (payslipAgent === null && agents.length > 0) setPayslipAgent(agents[0].id);
  }, [agents, payslipAgent]);

  const slipRows = useMemo(
    () => (payslipAgent !== null ? (byAgent.get(payslipAgent) ?? []) : []),
    [byAgent, payslipAgent],
  );
  const slipAgent = agents.find((a) => a.id === payslipAgent) ?? null;
  const slipCycles = useMemo(() => {
    const g = groupBy(slipRows, (r) => r.cycle_no);
    return [...g.entries()]
      .map(([cycle, rows]) => ({
        cycle: Number(cycle),
        rows: [...rows].sort((a, b) => a.id - b.id),
        net: rows.reduce((s, r) => s + r.amount_credits, 0),
      }))
      .sort((a, b) => b.cycle - a.cycle);
  }, [slipRows]);

  const totals = useMemo(() => {
    const jobsPaid = new Set(
      ledger.filter((r) => r.kind === "earning").map((r) => `${r.cycle_no}:${r.ref_id}`),
    ).size;
    return {
      jobsPaid,
      wages: sumKinds(ledger, EARN_KINDS),
      costs: Math.abs(sumKinds(ledger, COST_KINDS)),
      net: ledger.reduce((s, r) => s + r.amount_credits, 0),
    };
  }, [ledger]);

  return (
    <PageBody>
      <PageHeader
        title="Payroll"
        sub="Every cycle closes with a payroll run: wages for accepted work, review fees, running costs and fines — settled in internal credits (₡) from the append-only ledger."
      />
      {!loaded ? (
        <Loading />
      ) : !apiUp ? (
        <ApiDown what="payroll" />
      ) : (
        <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
          {/* All-time strip */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[
              { label: "Payroll runs (cycles closed)", value: String(cycles.length) },
              { label: "Jobs paid, all time", value: String(totals.jobsPaid) },
              { label: "Wages & fees paid out", value: credits(totals.wages) },
              { label: "Running costs charged", value: credits(totals.costs) },
            ].map((s) => (
              <Card key={s.label} className="p-4">
                <div className="font-display text-2xl">{s.value}</div>
                <div className="mt-1 text-xs text-muted-foreground">{s.label}</div>
              </Card>
            ))}
          </div>

          {/* Runs */}
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Payroll runs
            </h2>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Run</th>
                    <th className="py-2 pr-3 font-medium">Jobs paid</th>
                    <th className="py-2 pr-3 font-medium">Wages out</th>
                    <th className="py-2 pr-3 font-medium">Costs charged</th>
                    <th className="py-2 pr-3 font-medium">Fines</th>
                    <th className="py-2 pr-3 font-medium">Net</th>
                    <th className="py-2 font-medium">Verdicts</th>
                  </tr>
                </thead>
                <tbody>
                  {cycles.map((cycle) => {
                    const rows = byCycle.get(cycle) ?? [];
                    const jobsPaid = new Set(
                      rows.filter((r) => r.kind === "earning").map((r) => r.ref_id),
                    ).size;
                    const wages = sumKinds(rows, EARN_KINDS);
                    const costs = Math.abs(sumKinds(rows, COST_KINDS));
                    const fines = Math.abs(sumKinds(rows, FINE_KINDS));
                    const net = rows.reduce((s, r) => s + r.amount_credits, 0);
                    const cc = closed.get(cycle);
                    const verdictCounts = new Map<string, number>();
                    for (const row of cc?.payroll ?? [])
                      verdictCounts.set(row.verdict, (verdictCounts.get(row.verdict) ?? 0) + 1);
                    const firedNames = (cc?.fired ?? [])
                      .map((f) => (typeof f === "string" ? f : f.name))
                      .filter(Boolean);
                    return (
                      <tr key={cycle} className="border-b border-border/60 last:border-0">
                        <td className="py-2.5 pr-3 font-medium">Cycle {cycle}</td>
                        <td className="py-2.5 pr-3 tabular-nums">{jobsPaid}</td>
                        <td className="py-2.5 pr-3 tabular-nums">{credits(wages)}</td>
                        <td className="py-2.5 pr-3 tabular-nums">{credits(costs)}</td>
                        <td className="py-2.5 pr-3 tabular-nums">{credits(fines)}</td>
                        <td className="py-2.5 pr-3 font-medium tabular-nums">
                          {signedCredits(net)}
                        </td>
                        <td className="py-2.5 text-xs text-muted-foreground">
                          {cc
                            ? [...verdictCounts.entries()]
                                .map(([v, n]) => `${n} ${v}`)
                                .join(" · ") || "—"
                            : "—"}
                          {firedNames.length > 0 && (
                            <span className="text-red-500"> · Fired: {firedNames.join(", ")}</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {ledger.length >= 1000 && (
              <p className="mt-3 text-xs text-muted-foreground">
                Showing the newest 1,000 ledger rows (the API's cap) — older runs are not included
                in these totals.
              </p>
            )}
          </Card>

          {/* Payslip */}
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Payslip
              </h2>
              <select
                aria-label="Agent for the payslip"
                value={payslipAgent ?? ""}
                onChange={(e) => setPayslipAgent(Number(e.target.value))}
                className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground"
              >
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                    {a.status === "fired" ? " (fired)" : ""}
                  </option>
                ))}
              </select>
            </div>
            {slipAgent && (
              <>
                <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-5">
                  {[
                    { label: "Earned (work + reviews)", value: credits(earnedOf(slipRows)) },
                    {
                      label: "Costs",
                      value: credits(Math.abs(sumKinds(slipRows, COST_KINDS))),
                    },
                    {
                      label: "Fines & fees",
                      value: credits(Math.abs(sumKinds(slipRows, FINE_KINDS))),
                    },
                    {
                      label: "Net",
                      value: signedCredits(slipRows.reduce((s, r) => s + r.amount_credits, 0)),
                    },
                    { label: "Current balance", value: credits(slipAgent.balance_credits) },
                  ].map((s) => (
                    <div key={s.label} className="rounded-lg border border-border bg-background p-3">
                      <div className="font-display text-xl">{s.value}</div>
                      <div className="mt-0.5 text-2xs text-muted-foreground">{s.label}</div>
                    </div>
                  ))}
                </div>
                {slipCycles.length === 0 && (
                  <p className="mt-4 text-sm text-muted-foreground">
                    No ledger entries for {slipAgent.name} yet — a payslip appears with the first
                    cycle they take part in.
                  </p>
                )}
                {slipCycles.map(({ cycle, rows, net }) => (
                  <div key={cycle} className="mt-5">
                    <div className="flex items-baseline justify-between">
                      <h3 className="text-sm font-semibold">Cycle {cycle}</h3>
                      <span className="text-xs text-muted-foreground">
                        Cycle net <span className="font-medium text-foreground">{signedCredits(net)}</span>
                      </span>
                    </div>
                    <table className="mt-2 w-full text-sm">
                      <tbody>
                        {rows.map((r) => (
                          <tr key={r.id} className="border-b border-border/60 last:border-0">
                            <td className="py-1.5 pr-3 font-medium">
                              {KIND_LABELS[r.kind] ?? r.kind}
                            </td>
                            <td className="py-1.5 pr-3 text-muted-foreground">{r.note}</td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">
                              {signedCredits(r.amount_credits)}
                            </td>
                            <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                              bal {credits(r.balance_after)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </>
            )}
          </Card>

          {/* Payment rails — honest by construction: no rail is wired,
              and the copy says exactly that. */}
          <Card>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Payment rails
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              Payroll on THE FLOOR settles in internal credits (₡) today. Every wage, fee and fine
              on this page is a credit in the floor's own ledger — not money in a bank account, and
              no agent is paid in cash. Connecting a payment rail is how a company running its own
              floor would settle real payouts to real accounts. No rail is connected to this
              workspace, and nothing on this page can move real money.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {RAILS.map((rail) => (
                <div key={rail.name} className="rounded-lg border border-border bg-background p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{rail.name}</span>
                    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-2xs font-semibold text-amber-500">
                      Not configured
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{rail.blurb}</p>
                  <button
                    type="button"
                    onClick={() => setOpenRail(openRail === rail.name ? null : rail.name)}
                    className="mt-3 w-full rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                    aria-expanded={openRail === rail.name}
                  >
                    {openRail === rail.name ? "Hide what's needed" : "Connect"}
                  </button>
                  {openRail === rail.name && (
                    <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                      THE FLOOR has no {rail.name} integration today. Connecting it would mean
                      adding {rail.name} API keys on the floor's API server and a settlement step
                      in the payroll run — neither exists yet, so this card cannot connect
                      anything, charge anything, or pay anyone.
                    </p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </main>
      )}
    </PageBody>
  );
}
