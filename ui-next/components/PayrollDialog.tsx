"use client";

/* Payroll statement — kept custom (agent-orchestrator has no payroll
 * concept), styled with their theme tokens and Claude's display
 * serif for the title. Native <dialog>: top layer, focus trap, Esc
 * and light-dismiss (closedby) come from the platform. It opens only
 * from the cycle.closed handler in FloorClient, which the PR #3
 * seq-watermark guard keeps one-shot — a replayed frame can never
 * re-open it. */

import { useEffect, useRef } from "react";
import type { PayrollPayload, PayrollRow } from "../lib/types";
import Mascot from "./Mascot";
import { credits, pick, signedCredits } from "../lib/api";
import { Button } from "../vendor/ao/button";

const VERDICT_CLASS: Record<string, string> = {
  SAFE: "bg-success/15 text-success",
  "ON-NOTICE": "bg-status-in-review/15 text-status-in-review",
  FIRED: "bg-destructive/15 text-destructive",
};

export default function PayrollDialog({
  payroll,
  onClose,
}: {
  payroll: PayrollPayload | null;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg || !payroll) return;
    if (!dlg.open) {
      if (typeof dlg.showModal === "function") dlg.showModal();
      else dlg.setAttribute("open", "");
    }
    timer.current = setTimeout(() => onClose(), 12000);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [payroll, onClose]);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (!payroll && dlg.open) dlg.close();
  }, [payroll]);

  if (!payroll) return null;
  const rows: PayrollRow[] =
    (pick(payroll as Record<string, unknown>, "rows", "agents", "payroll") as PayrollRow[]) ?? [];
  const cycle = pick(payroll as Record<string, unknown>, "cycle_no", "cycle");
  const totalNet = rows.reduce((sum, r) => sum + Number(r.net ?? 0), 0);

  return (
    <dialog
      ref={ref}
      className="m-auto w-[min(600px,94vw)] rounded-xl border border-border bg-popover p-0 text-popover-foreground shadow-xl backdrop:bg-black/60 backdrop:backdrop-blur-[2px]"
      {...({ closedby: "any" } as Record<string, string>)}
      aria-labelledby="payroll-title"
      onClick={() => onClose()}
      onCancel={() => onClose()}
    >
      <div className="border-b border-border px-6 pb-4 pt-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-4">
          <Mascot state="paid" size={56} />
          <div className="min-w-0">
            <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-brand-logo-text">Payroll statement</p>
            <h2 id="payroll-title" className="font-display mt-1 text-[26px] leading-tight">
              Cycle {cycle !== undefined ? String(cycle) : "—"} — who earned, who burned
            </h2>
          </div>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Deterministic CFO payroll: earnings minus salary and tool costs. Two consecutive negative cycles and the agent is fired.
        </p>
      </div>
      <div className="max-h-[55vh] overflow-y-auto px-6 py-3" onClick={(e) => e.stopPropagation()}>
        {rows.length > 0 ? (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-2xs uppercase tracking-[0.08em] text-passive">
                <th className="py-2 pr-3 font-medium">Agent</th>
                <th className="py-2 pr-3 text-right font-medium">Earned</th>
                <th className="py-2 pr-3 text-right font-medium">Costs</th>
                <th className="py-2 pr-3 text-right font-medium">Net</th>
                <th className="py-2 text-right font-medium">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const name = String(pick(r as Record<string, unknown>, "agent_name", "name") ?? "Agent");
                const verdict = String(pick(r as Record<string, unknown>, "verdict", "status") ?? "");
                const net = Number(r.net ?? 0);
                return (
                  <tr key={i} className="border-t border-border">
                    <td className="py-2 pr-3 font-medium text-foreground">{name}</td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums text-muted-foreground">{credits(r.earnings ?? r.earned)}</td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums text-muted-foreground">{credits(r.costs ?? r.cost)}</td>
                    <td className={`py-2 pr-3 text-right font-mono font-medium tabular-nums ${net < 0 ? "text-destructive" : "text-success"}`}>
                      {signedCredits(net)}
                    </td>
                    <td className="py-2 text-right">
                      {verdict && (
                        <span className={`inline-block rounded-full px-2 py-0.5 text-2xs font-semibold ${VERDICT_CLASS[verdict] ?? "bg-muted text-muted-foreground"}`}>
                          {verdict}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="py-2 text-sm text-muted-foreground">Payroll ran — the cycle is closed.</p>
        )}
      </div>
      <div
        className="flex items-center justify-between border-t border-border px-6 py-3.5"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="text-xs text-muted-foreground">
          Total net <span className={`font-mono font-medium tabular-nums ${totalNet < 0 ? "text-destructive" : "text-success"}`}>{signedCredits(totalNet)}</span>
        </span>
        <Button variant="primary" size="sm" onClick={onClose}>
          Close statement
        </Button>
      </div>
    </dialog>
  );
}
