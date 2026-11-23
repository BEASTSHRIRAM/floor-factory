"use client";

import { useEffect, useRef } from "react";
import type { PayrollPayload, PayrollRow } from "../lib/types";
import { credits, pick, signedCredits } from "../lib/api";
import LottieBadge from "./fx/LottieBadge";

/** Payroll overlay: native <dialog> — top layer, focus trap and Esc come
 *  from the platform. GSAP is not needed here; a CSS fade is enough and
 *  stays transform/opacity-only. */
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

  return (
    <dialog
      ref={ref}
      className="overlay"
      aria-labelledby="payroll-title"
      onClick={() => onClose()}
      onCancel={() => onClose()}
    >
      <div className="overlay-card">
        <div className="overlay-head">
          <LottieBadge kind="payroll" size={44} />
          <h2 id="payroll-title">Payroll — Cycle {cycle !== undefined ? String(cycle) : "—"}</h2>
        </div>
        {rows.length > 0 && (
          <table className="payroll-table">
            <thead>
              <tr>
                <th scope="col">Agent</th>
                <th scope="col" className="num">
                  Earnings
                </th>
                <th scope="col" className="num">
                  Costs
                </th>
                <th scope="col" className="num">
                  Net
                </th>
                <th scope="col">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const verdict = String(pick(r as Record<string, unknown>, "verdict", "status") ?? "SAFE")
                  .toUpperCase()
                  .replace("_", "-");
                const earn = Number(pick(r as Record<string, unknown>, "earnings", "earned"));
                const cost = Number(pick(r as Record<string, unknown>, "costs", "cost", "upkeep"));
                let net = Number(pick(r as Record<string, unknown>, "net"));
                if (!Number.isFinite(net)) net = (Number.isFinite(earn) ? earn : 0) - (Number.isFinite(cost) ? cost : 0);
                return (
                  <tr key={i}>
                    <td>{String(pick(r as Record<string, unknown>, "agent_name", "name", "agent") ?? "Agent")}</td>
                    <td className="num">{credits(earn)}</td>
                    <td className="num">{credits(cost)}</td>
                    <td className="num">{signedCredits(net)}</td>
                    <td>
                      <span className={`verdict ${verdict}`}>{verdict}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p className="overlay-hint">Press Esc or click anywhere to dismiss.</p>
      </div>
    </dialog>
  );
}
