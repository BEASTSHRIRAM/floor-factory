"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Header, { type HeaderStats } from "./Header";
import OrgChart from "./OrgChart";
import JobBoard, { type TickerItem } from "./JobBoard";
import Feeds from "./Feeds";
import PayrollDialog from "./PayrollDialog";
import type { Agent, FloorEvent, Job, LedgerRow, NarrationItem, PayrollPayload } from "../lib/types";
import {
  API_BASE,
  asArray,
  credits,
  eventText,
  fetchJSON,
  isFired,
  isManagement,
  normalizeAgent,
  normalizeJob,
  normalizeLedger,
  payloadOf,
  pick,
  postJSON,
} from "../lib/api";

gsap.registerPlugin(useGSAP);

// WebGL is client-only; load the (lightweight) floor scene lazily so the
// rest of the page paints first and stays at 60fps.
const FloorScene = dynamic(() => import("./fx/FloorScene"), {
  ssr: false,
  loading: () => <div className="floor-scene-stub" aria-hidden="true" />,
});

const EVENT_TYPES = [
  "job.posted", "bid.placed", "job.awarded", "tool.executed", "work.submitted",
  "review.completed", "appeal.filed", "appeal.decided", "payment.made",
  "cycle.closed", "agent.fired", "agent.hired", "narration",
  "tool.proposed", "tool.confirmation_requested", "system.tools_updated",
];

export default function FloorClient() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [narration, setNarration] = useState<NarrationItem[]>([]);
  const [ticker, setTicker] = useState<TickerItem[]>([]);
  const [pinkSlips, setPinkSlips] = useState<{ key: number; text: string }[]>([]);
  const [cycle, setCycle] = useState<number | null>(null);
  const [serverPaid, setServerPaid] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(false);
  const [payroll, setPayroll] = useState<PayrollPayload | null>(null);
  const [banner, setBanner] = useState(false);
  const [toast, setToast] = useState<{ msg: string; error?: boolean } | null>(null);
  const [firedIds, setFiredIds] = useState<Set<string>>(new Set());
  const [hireIds, setHireIds] = useState<Set<string>>(new Set());

  const lastSeq = useRef(0);
  const keyRef = useRef(1);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const agentsRef = useRef<Agent[]>([]);
  agentsRef.current = agents;

  /* GSAP entrance: header + panels fade/slide in once (transform/opacity
     only; skipped entirely under reduced motion). */
  useGSAP(
    () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      gsap.from(".fx-entrance", {
        y: 16,
        opacity: 0,
        duration: 0.7,
        ease: "power3.out",
        stagger: 0.08,
        clearProps: "transform,opacity",
      });
    },
    { scope: rootRef }
  );

  const showToast = useCallback((msg: string, error?: boolean) => {
    setToast({ msg, error });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4200);
  }, []);

  const narrate = useCallback((text: string, cls = "") => {
    if (!text) return;
    const key = keyRef.current++;
    setNarration((prev) => [{ key, text, cls }, ...prev].slice(0, 120));
  }, []);

  const nameOf = useCallback((p: Record<string, unknown>): string => {
    const n = pick(p, "agent_name", "name");
    if (n) return String(n);
    const id = pick(p, "agent_id", "agent");
    if (id !== undefined) {
      const found = agentsRef.current.find((a) => a.id === String(id));
      if (found) return found.name;
      return String(id);
    }
    return "An agent";
  }, []);

  const jobTitleOf = useCallback((p: Record<string, unknown>): string => {
    const t = pick(p, "job_title", "title");
    if (t) return String(t);
    const id = pick(p, "job_id");
    return id !== undefined ? `job ${id}` : "a job";
  }, []);

  /* ---------- snapshot ---------- */
  const loadSnapshot = useCallback(async () => {
    let any = false;
    try {
      const d = await fetchJSON("/state/agents");
      const list = asArray(d, ["agents", "items", "results"]).map(normalizeAgent);
      setAgents(list);
      any = true;
      if (d && !Array.isArray(d)) {
        const c = pick(d as Record<string, unknown>, "cycle", "cycle_no", "current_cycle");
        if (c !== undefined) setCycle(Number(c));
      }
    } catch { /* keep trying */ }
    try {
      const d = await fetchJSON("/state/jobs");
      setJobs(asArray(d, ["jobs", "items", "results"]).map(normalizeJob));
      any = true;
    } catch { /* keep trying */ }
    try {
      const d = await fetchJSON("/state/ledger");
      const rows = asArray(d, ["ledger", "entries", "items", "results"]).map(normalizeLedger);
      setLedger(rows);
      any = true;
      if (d && !Array.isArray(d)) {
        const o = d as Record<string, unknown>;
        const tot = pick(o, "total_paid", "paid_out", "total_paid_credits");
        if (tot !== undefined) setServerPaid(Number(tot));
        const c = pick(o, "cycle", "cycle_no", "current_cycle");
        if (c !== undefined) setCycle(Number(c));
      }
    } catch { /* keep trying */ }
    try {
      const d = await fetchJSON("/state/events");
      const evs = asArray(d, ["events", "items", "results"]) as FloorEvent[];
      const items: NarrationItem[] = [];
      evs.slice(-60).forEach((ev) => {
        const p = payloadOf(ev);
        const t = eventText(ev, p);
        if (t) items.push({ key: keyRef.current++, text: t });
        const seq = Number(pick(ev as unknown as Record<string, unknown>, "seq", "id"));
        if (Number.isFinite(seq) && seq > lastSeq.current) lastSeq.current = seq;
      });
      if (items.length) setNarration((prev) => (prev.length ? prev : items.reverse()));
      any = true;
    } catch { /* keep trying */ }
    if (any) setConnected(true);
  }, []);

  /* ---------- events ---------- */
  const handleEvent = useCallback(
    (ev: FloorEvent) => {
      if (!ev || typeof ev !== "object") return;
      const type = String(pick(ev as unknown as Record<string, unknown>, "type", "event") ?? "");
      const p = payloadOf(ev);
      const seq = Number(pick(ev as unknown as Record<string, unknown>, "seq", "id"));
      if (Number.isFinite(seq) && seq > lastSeq.current) lastSeq.current = seq;
      const text = eventText(ev, p);

      const upsertJob = (patch: Record<string, unknown>) => {
        const id = pick(patch, "id", "job_id");
        if (id === undefined) {
          void loadSnapshot();
          return;
        }
        setJobs((prev) => {
          const idx = prev.findIndex((j) => j.id === String(id));
          if (idx >= 0) {
            const next = prev.slice();
            next[idx] = normalizeJob({ ...next[idx], ...patch });
            return next;
          }
          return [...prev, normalizeJob(patch)];
        });
      };
      const upsertAgent = (patch: Record<string, unknown>) => {
        const id = pick(patch, "id", "agent_id", "name");
        if (id === undefined) {
          void loadSnapshot();
          return;
        }
        setAgents((prev) => {
          const idx = prev.findIndex((a) => a.id === String(id));
          if (idx >= 0) {
            const next = prev.slice();
            next[idx] = normalizeAgent({ ...next[idx], ...patch });
            return next;
          }
          return [...prev, normalizeAgent(patch)];
        });
      };

      switch (type) {
        case "job.posted": {
          const budget = pick(p, "budget_credits", "budget");
          narrate(text || `Manager posted "${jobTitleOf(p)}"${budget !== undefined ? ` at ${credits(budget)}` : ""}`);
          upsertJob({ ...p, status: (pick(p, "status") as string) || "open" });
          break;
        }
        case "bid.placed": {
          const price = pick(p, "price_credits", "price", "amount");
          const conf = pick(p, "confidence", "conf");
          const who = nameOf(p);
          setTicker((prev) =>
            [
              ...prev,
              {
                key: keyRef.current++,
                who,
                text: `bids ${price !== undefined ? credits(price) : ""}${conf !== undefined ? ` (conf ${Number(conf).toFixed(2)})` : ""} on "${jobTitleOf(p)}"`,
              },
            ].slice(-24)
          );
          narrate(text || `${who} placed a sealed bid on "${jobTitleOf(p)}".`);
          const jid = pick(p, "job_id", "job");
          if (jid !== undefined) {
            setJobs((prev) =>
              prev.map((j) => {
                if (j.id !== String(jid)) return j;
                const bids = [...(j.bids ?? []), p as Job["bids"] extends (infer B)[] | undefined ? B : never];
                return { ...j, bids, status: j.status === "open" ? "bidding" : j.status };
              })
            );
          }
          break;
        }
        case "job.awarded":
          narrate(text || `${nameOf(p)} won "${jobTitleOf(p)}".`);
          if (pick(p, "job_id", "id") !== undefined)
            upsertJob({ id: pick(p, "job_id", "id"), status: "awarded", winner: nameOf(p) });
          break;
        case "tool.executed":
          narrate(text || `${nameOf(p)} ran tool ${String(pick(p, "tool_name", "tool") ?? "")} on "${jobTitleOf(p)}".`);
          break;
        case "work.submitted":
          narrate(text || `${nameOf(p)} submitted work on "${jobTitleOf(p)}" for review.`);
          if (pick(p, "job_id", "id") !== undefined) upsertJob({ id: pick(p, "job_id", "id"), status: "in_review" });
          break;
        case "review.completed": {
          const verdict = pick(p, "verdict");
          const sev = pick(p, "severity");
          narrate(text || `Review complete on "${jobTitleOf(p)}" — ${verdict ?? ""}${sev ? ` (${sev})` : ""}.`);
          break;
        }
        case "appeal.filed":
          narrate(text || `${nameOf(p)} is appealing the rejection on "${jobTitleOf(p)}"…`, "appeal");
          break;
        case "appeal.decided": {
          const upheld = pick(p, "upheld", "overturned");
          const outcome = String(pick(p, "outcome", "verdict") ?? "").toLowerCase();
          narrate(
            text ||
              (outcome === "upheld" || upheld === true || outcome === "overturned"
                ? "APPEAL UPHELD — the worker is paid and the original Reviewer is penalised."
                : "Appeal denied — the rejection stands."),
            "appeal"
          );
          break;
        }
        case "payment.made": {
          const amt = pick(p, "amount_credits", "amount");
          narrate(text || `${nameOf(p)} was paid ${amt !== undefined ? credits(amt) : ""} for "${jobTitleOf(p)}".`);
          const row: LedgerRow = { ...(p as LedgerRow) };
          if (pick(row as Record<string, unknown>, "note", "reason") === undefined)
            row.note = `earning — ${jobTitleOf(p)} accepted`;
          // Ledger displays newest first (the API snapshot order); live
          // payments are the newest rows, so they go at the front.
          setLedger((prev) => [row, ...prev]);
          break;
        }
        case "cycle.closed":
          narrate(text || "Payroll ran — the cycle is closed.");
          setBanner(true);
          setTimeout(() => setBanner(false), 6000);
          setPayroll(p as PayrollPayload);
          void loadSnapshot();
          break;
        case "agent.fired": {
          const fid = pick(p, "agent_id", "id", "agent");
          if (fid !== undefined) {
            setFiredIds((prev) => new Set(prev).add(String(fid)));
            setTimeout(() => setFiredIds(new Set()), 2500);
          }
          const who = nameOf(p);
          narrate(text || `PinkSlip: ${who} has been fired by the CFO.`, "pinkslip");
          setPinkSlips((prev) => [{ key: keyRef.current++, text: `PinkSlip — ${who} terminated` }, ...prev].slice(0, 20));
          upsertAgent({ ...p, id: fid, status: "fired" });
          break;
        }
        case "agent.hired": {
          const hid = pick(p, "agent_id", "id", "agent");
          if (hid !== undefined) {
            setHireIds((prev) => new Set(prev).add(String(hid)));
            setTimeout(() => setHireIds(new Set()), 2500);
          }
          const mut = pick(p, "mutation_note", "mutation");
          narrate(text || `New hire: ${nameOf(p)}${mut ? ` — ${mut}` : ""}.`, "hire");
          upsertAgent({ ...p, id: hid, status: "idle" });
          break;
        }
        case "narration":
          narrate(text);
          break;
        default:
          if (text) narrate(text);
          break;
      }
    },
    [loadSnapshot, nameOf, jobTitleOf, narrate]
  );

  useEffect(() => {
    void loadSnapshot();
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      try {
        es = new EventSource(`${API_BASE}/events`);
      } catch {
        retry = setTimeout(connect, 5000);
        return;
      }
      es.onopen = () => setConnected(true);
      es.onmessage = (m) => {
        try {
          handleEvent(JSON.parse(m.data) as FloorEvent);
        } catch { /* ignore malformed frames */ }
      };
      EVENT_TYPES.forEach((t) => {
        es?.addEventListener(t, (m) => {
          try {
            const d = JSON.parse((m as MessageEvent).data) as FloorEvent;
            if (!d.type) d.type = t;
            handleEvent(d);
          } catch { /* ignore */ }
        });
      });
      es.onerror = () => {
        if (es && es.readyState === EventSource.CLOSED && !closed) {
          setConnected(false);
          retry = setTimeout(connect, 5000);
        }
      };
    };
    connect();

    const interval = setInterval(() => {
      setConnected((c) => {
        if (!c) void loadSnapshot();
        return c;
      });
    }, 8000);

    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      clearInterval(interval);
      es?.close();
    };
  }, [loadSnapshot, handleEvent]);

  /* ---------- derived ---------- */
  const { management, workers, fired, stats } = useMemo(() => {
    const mgmt: Agent[] = [];
    const work: Agent[] = [];
    const dead: Agent[] = [];
    agents.forEach((a) => {
      if (isFired(a)) dead.push(a);
      else if (isManagement(a)) mgmt.push(a);
      else work.push(a);
    });
    let paid = 0;
    ledger.forEach((row) => {
      const kind = String(pick(row as Record<string, unknown>, "kind", "type") ?? "").toLowerCase();
      const amt = Number(pick(row as Record<string, unknown>, "amount_credits", "amount"));
      if ((kind === "earning" || kind === "payment") && Number.isFinite(amt) && amt > 0) paid += amt;
    });
    let done = 0;
    let failed = 0;
    jobs.forEach((j) => {
      const s = j.status.toLowerCase();
      if (["paid", "done", "completed", "closed", "accepted"].includes(s)) done++;
      if (["failed", "rejected"].includes(s)) failed++;
    });
    const s: HeaderStats = {
      cycle,
      paidOut: serverPaid !== null ? serverPaid : paid,
      done,
      failed,
      activeAgents: work.length + mgmt.length,
    };
    return { management: mgmt, workers: work, fired: dead, stats: s };
  }, [agents, jobs, ledger, cycle, serverPaid]);

  /* ---------- actions ---------- */
  const onRun = useCallback(async () => {
    if (running) return;
    setRunning(true);
    try {
      await postJSON("/run/shift?cycles=2");
      showToast("Shift complete.");
      void loadSnapshot();
    } catch {
      showToast("Could not run the shift — is the factory API up?", true);
    } finally {
      setRunning(false);
    }
  }, [running, loadSnapshot, showToast]);

  const onReset = useCallback(async () => {
    if (!window.confirm("Reset the demo to its exact seeded start state?")) return;
    try {
      await postJSON("/reset");
      showToast("Demo reset to the seeded start state.");
      setFiredIds(new Set());
      setHireIds(new Set());
      setNarration([]);
      setTicker([]);
      setPinkSlips([]);
      void loadSnapshot();
    } catch {
      showToast("Reset failed — is the factory API up?", true);
    }
  }, [loadSnapshot, showToast]);

  return (
    <div ref={rootRef}>
      <a className="skip-link" href="#layout">
        Skip to mission control
      </a>
      <Header stats={stats} connected={connected} running={running} onRun={onRun} onReset={onReset} />

      {/* Lightweight 3D floor strip — subtle, capped-cost, never the centrepiece. */}
      <div className="floor-strip fx-entrance">
        <FloorScene agents={agents} />
      </div>

      {banner && (
        <div className="payroll-banner" role="alert">
          PAYROLL — CYCLE CLOSED
        </div>
      )}
      {!connected && (
        <div className="waiting" role="status">
          <div className="waiting-card">
            <h2>Waiting for factory API</h2>
            <p>
              The mission control is live, but the factory API is not reachable yet. This page will
              connect automatically as soon as the API starts.
            </p>
            <p className="waiting-sub">
              Expected at <code>{API_BASE}</code> — <code>GET /state/agents</code>,{" "}
              <code>GET /state/jobs</code>, <code>GET /state/ledger</code>, <code>GET /events</code>
            </p>
          </div>
        </div>
      )}

      <main id="layout">
        <OrgChart management={management} workers={workers} fired={fired} firedIds={firedIds} hireIds={hireIds} />
        <JobBoard jobs={jobs} ticker={ticker} />
        <Feeds
          ledger={ledger}
          narration={narration}
          extraLedgerItems={pinkSlips.map((s) => (
            <div className="feed-item pinkslip" key={s.key}>
              <span className="why">{s.text}</span>
            </div>
          ))}
        />
      </main>

      <PayrollDialog payroll={payroll} onClose={() => setPayroll(null)} />
      {toast && (
        <div className={`toast${toast.error ? " error" : ""}`} role="status" aria-live="polite">
          {toast.msg}
        </div>
      )}
    </div>
  );
}
