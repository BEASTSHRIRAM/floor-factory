"use client";

import type { LedgerRow, NarrationItem } from "../lib/types";
import { pick, signedCredits } from "../lib/api";

export function LedgerFeed({ rows }: { rows: LedgerRow[] }) {
  if (!rows.length) return <span className="empty">No credit movements yet.</span>;
  return (
    <>
      {rows.map((row, i) => {
        const amt = Number(pick(row as Record<string, unknown>, "amount_credits", "amount"));
        const who = pick(row as Record<string, unknown>, "agent_name", "agent", "agent_id");
        const why = pick(row as Record<string, unknown>, "note", "reason", "kind", "type") ?? "";
        const cls = amt > 0 ? "pos" : amt < 0 ? "neg" : "";
        const kind = String(pick(row as Record<string, unknown>, "kind", "type") ?? "").toLowerCase();
        const itemCls = kind.includes("pinkslip") || kind.includes("fired") ? " pinkslip" : "";
        return (
          <div className={`feed-item${itemCls}`} key={String(row.id ?? i)}>
            <span className={`amt ${cls}`}>{signedCredits(amt)}</span>{" "}
            {who ? <b>{String(who)}</b> : null}{" "}
            <span className="why">{String(why)}</span>
          </div>
        );
      })}
    </>
  );
}

/* Bottom strip of the center surface: ledger and narration side by
   side, each scrolling on its own so the board above never moves. */
export default function Feeds({
  ledger,
  narration,
  extraLedgerItems,
}: {
  ledger: LedgerRow[];
  narration: NarrationItem[];
  extraLedgerItems: React.ReactNode;
}) {
  return (
    <section className="feeds-strip fx-entrance" aria-label="Ledger and narration">
      <div className="panel">
        <h2 className="panel-title" id="ledger-title">
          Ledger
        </h2>
        <div className="feed ledger-feed" aria-label="Credit movements">
          {extraLedgerItems}
          <LedgerFeed rows={ledger} />
        </div>
      </div>
      <div className="panel">
        <h2 className="panel-title" id="narration-title">
          Narration
        </h2>
        <div className="feed narration-log" role="log" aria-labelledby="narration-title">
          {narration.length ? (
            narration.map((n) => (
              <div className={`feed-item${n.cls ? ` ${n.cls}` : ""}`} key={n.key}>
                {n.text}
              </div>
            ))
          ) : (
            <span className="empty">The floor is quiet.</span>
          )}
        </div>
      </div>
    </section>
  );
}
