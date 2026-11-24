"use client";

/* THE FLOOR console — state engine + agent-orchestrator shell.
 *
 * The engine (snapshots, SSE with the PR #3 from_seq + watermark
 * replay guard, presence derivation, payroll, recorded-demo replay)
 * is unchanged from the previous console; only the rendering is new:
 * the shell, board and inspector are agent-orchestrator's own
 * frontend (vendored under vendor/ao, Apache-2.0 — see
 * THIRD_PARTY.md), recoloured to Claude's dark palette (DESIGN.md).
 * Floor data reaches their views exclusively through
 * components/ao/adapter.ts. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import FloorShell, {
  type AutoRunStatus,
  type ConsoleMode,
  type DemoPhase,
  type FloorTrustMode,
  type ShellStats,
} from "./ao/FloorShell";
import FloorBoard from "./ao/FloorBoard";
import FloorInspector from "./ao/FloorInspector";
import PayrollDialog from "./PayrollDialog";
import type { MascotState } from "./Mascot";
import type { Agent, FloorEvent, Job, LedgerRow, NarrationItem, PayrollPayload, Presence } from "../lib/types";
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
import {
  RECORDED_EVENTS,
  RECORDED_FINAL_AGENTS,
  RECORDED_FINAL_JOBS,
  RECORDED_SEED_AGENTS,
  RECORDED_TOTAL_PAID,
  asFloorEvent,
  type RecordedEvent,
} from "../lib/recordedShift";
import type { FloorEventLogItem, TickerItem } from "./ao/adapter";

const EVENT_TYPES = [
  "job.posted", "bid.placed", "job.awarded", "tool.executed", "work.submitted",
  "review.completed", "appeal.filed", "appeal.decided", "payment.made",
  "cycle.closed", "agent.fired", "agent.hired", "narration",
  "tool.proposed", "tool.confirmation_requested", "system.tools_updated",
  "confirmation.auto_approved", "mode.changed",
  "auto.started", "auto.paused", "auto.stopped", "auto.cycle_started",
];

/* Department filter for the board — keys match the API's
   /state/jobs department field. */
const DEPT_FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "All departments" },
  { key: "support", label: "Support" },
  { key: "qa", label: "QA triage" },
  { key: "bookkeeping", label: "Bookkeeping" },
  { key: "sdr", label: "SDR" },
  { key: "engineering", label: "Engineering" },
  { key: "hr", label: "HR" },
];

/* Mode switches (offline hero → replay, replay → live) are the two big
   state swaps on this page; where the platform offers it, run them as
   a same-document view transition so the floor morphs instead of
   cutting. Guarded: no API or reduced motion → plain state swap. */
function withTransition(fn: () => void) {
  const doc = document as Document & {
    startViewTransition?: (cb: () => void) => unknown;
  };
  if (typeof doc.startViewTransition === "function" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    doc.startViewTransition(() => flushSync(fn));
  } else {
    fn();
  }
}

/* Human phrasing for the inspector's per-job log when an event carries
   no message of its own (most live events don't). Mirrors the
   narration fallbacks in handleEvent. */
function describeEvent(type: string, p: Record<string, unknown>, who: string): string {
  const price = pick(p, "price_credits", "price", "amount", "amount_credits");
  const tool = pick(p, "tool_name", "tool");
  switch (type) {
    case "job.posted":
      return `Manager posted the job${pick(p, "budget_credits", "budget") !== undefined ? ` at ${credits(pick(p, "budget_credits", "budget"))}` : ""}`;
    case "bid.placed":
      return `${who} placed a sealed bid${price !== undefined ? ` at ${credits(price)}` : ""}${pick(p, "confidence", "conf") !== undefined ? ` (conf ${Number(pick(p, "confidence", "conf")).toFixed(2)})` : ""}`;
    case "job.awarded":
      return `${who} won the job${price !== undefined ? ` at ${credits(price)}` : ""}`;
    case "tool.executed":
      return `${who} ran ${tool ? String(tool) : "a tool"} via Synapse MCP`;
    case "confirmation.auto_approved":
      return `Gate auto-approved ${tool ? String(tool) : "a write"} — auto mode, no human at the gate; the approval is in the audit log`;
    case "work.submitted":
      return `${who} submitted work for review`;
    case "review.completed":
      return `Review complete — ${String(pick(p, "verdict") ?? "")}${pick(p, "severity") ? ` (${String(pick(p, "severity"))})` : ""}`;
    case "appeal.filed":
      return `${who} appealed the rejection`;
    case "appeal.decided":
      return `Appeal decided — ${String(pick(p, "outcome", "verdict") ?? "")}`;
    case "payment.made":
      return `${who} was paid ${price !== undefined ? credits(price) : ""}`;
    case "agent.fired":
      return `PinkSlip — ${who} fired by the CFO`;
    case "agent.hired":
      return `${who} hired${pick(p, "mutation_note", "mutation") ? ` — ${String(pick(p, "mutation_note", "mutation"))}` : ""}`;
    default:
      return type;
  }
}

export default function FloorClient() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [narration, setNarration] = useState<NarrationItem[]>([]);
  const [ticker, setTicker] = useState<TickerItem[]>([]);
  const [eventLog, setEventLog] = useState<FloorEventLogItem[]>([]);
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
  /* The Foreman avatar's one-shot reactions: payment.made flashes
     `paid`, agent.fired flashes `pinkslip`, each for ~2s over the
     derived base state (see mascotState below). */
  const [mascotFlash, setMascotFlash] = useState<"paid" | "pinkslip" | null>(null);
  const mascotTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [presence, setPresence] = useState<Record<string, Presence>>({});
  const [paidFlash, setPaidFlash] = useState<Set<string>>(new Set());
  const [selection, setSelection] = useState<{ kind: "job" | "agent"; id: string } | null>(null);

  /* Console mode: "live" talks to the factory API; "demo" replays the
     recorded real shift (lib/recordedShift) through the same handlers.
     The demo exists so a hosted console (no local API) is never a dead
     screen — and it is always badged as recorded, never as live. */
  const [mode, setMode] = useState<ConsoleMode>("live");
  const [demoPhase, setDemoPhase] = useState<DemoPhase>("idle");
  /* Trust mode (manual gate vs auto run) — server-side state from
     /mode + /auto/status, polled while live. Distinct from the
     live/demo ConsoleMode above. */
  const [floorMode, setFloorMode] = useState<FloorTrustMode | null>(null);
  const [autoStatus, setAutoStatus] = useState<AutoRunStatus | null>(null);
  const [deptFilter, setDeptFilter] = useState("all");
  const [apiUp, setApiUp] = useState(false);
  const [graceDone, setGraceDone] = useState(false);
  const [liveEpoch, setLiveEpoch] = useState(0);

  const modeRef = useRef<ConsoleMode>("live");
  modeRef.current = mode;
  const everConnectedRef = useRef(false);
  const demoTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const logSeededRef = useRef(false);

  const lastSeq = useRef(0);
  const keyRef = useRef(1);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const agentsRef = useRef<Agent[]>([]);
  agentsRef.current = agents;
  const jobsRef = useRef<Job[]>([]);
  jobsRef.current = jobs;

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

  /* ---------- live presence (derived from the event stream) ---------- */
  const resolveAgentId = useCallback((p: Record<string, unknown>): string | undefined => {
    const id = pick(p, "agent_id", "agent");
    if (id !== undefined && agentsRef.current.some((a) => a.id === String(id))) return String(id);
    // tool.executed names its actor under "worker" (e.g. "manager");
    // match names case-insensitively, then fall back to role.
    const name = pick(p, "agent_name", "name", "winner", "awarded_to", "worker", "actor");
    if (name) {
      const n = String(name).toLowerCase();
      const found =
        agentsRef.current.find((a) => a.name.toLowerCase() === n) ??
        agentsRef.current.find((a) => String(a.role ?? "").toLowerCase() === n);
      if (found) return found.id;
    }
    return id !== undefined ? String(id) : undefined;
  }, []);

  const workerIdForJob = useCallback((p: Record<string, unknown>): string | undefined => {
    const jid = pick(p, "job_id", "job");
    if (jid === undefined) return undefined;
    const job = jobsRef.current.find((j) => j.id === String(jid));
    if (!job?.winner) return undefined;
    return agentsRef.current.find((a) => a.name === String(job.winner))?.id;
  }, []);

  /** Work-order-scoped events (work.submitted, appeal.*) carry only a
   *  work_order_id; the owning job's work_orders name the agent. */
  const workerIdForWorkOrder = useCallback((p: Record<string, unknown>): string | undefined => {
    const woid = pick(p, "work_order_id");
    if (woid === undefined) return undefined;
    for (const j of jobsRef.current) {
      const orders = (j.work_orders as Record<string, unknown>[] | undefined) ?? [];
      const wo = orders.find((o) => String(o.id) === String(woid));
      if (wo?.agent_id !== undefined) return String(wo.agent_id);
    }
    return undefined;
  }, []);

  const jobIdForWorkOrder = useCallback((p: Record<string, unknown>): string | undefined => {
    const woid = pick(p, "work_order_id");
    if (woid === undefined) return undefined;
    for (const j of jobsRef.current) {
      const orders = (j.work_orders as Record<string, unknown>[] | undefined) ?? [];
      if (orders.some((o) => String(o.id) === String(woid))) return j.id;
    }
    return undefined;
  }, []);

  const setAgentPresence = useCallback((id: string | undefined, next: Presence) => {
    if (!id) return;
    setPresence((prev) => (prev[id]?.state === next.state && prev[id]?.tool === next.tool ? prev : { ...prev, [id]: next }));
  }, []);

  const flashPaid = useCallback((id: string | undefined) => {
    if (!id) return;
    setPaidFlash((prev) => new Set(prev).add(id));
    setTimeout(() => {
      setPaidFlash((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 1300);
  }, []);

  const flashMascot = useCallback((kind: "paid" | "pinkslip") => {
    setMascotFlash(kind);
    if (mascotTimer.current) clearTimeout(mascotTimer.current);
    mascotTimer.current = setTimeout(() => setMascotFlash(null), 2100);
  }, []);

  useEffect(() => () => {
    if (mascotTimer.current) clearTimeout(mascotTimer.current);
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
      const logItems: FloorEventLogItem[] = [];
      evs.slice(-60).forEach((ev) => {
        const p = payloadOf(ev);
        const t = eventText(ev, p);
        if (t) items.push({ key: keyRef.current++, text: t });
        const jid = pick(p, "job_id", "job");
        if (jid !== undefined && t) {
          logItems.push({
            key: keyRef.current++,
            type: String(pick(ev as unknown as Record<string, unknown>, "type", "event") ?? ""),
            jobId: String(jid),
            text: t,
            tone: "neutral",
          });
        }
        const seq = Number(pick(ev as unknown as Record<string, unknown>, "seq", "id"));
        if (Number.isFinite(seq) && seq > lastSeq.current) lastSeq.current = seq;
      });
      if (items.length) setNarration((prev) => (prev.length ? prev : items.reverse()));
      if (logItems.length && !logSeededRef.current) {
        logSeededRef.current = true;
        setEventLog(logItems);
      }
      any = true;
    } catch { /* keep trying */ }
    if (any) {
      everConnectedRef.current = true;
      setConnected(true);
    }
  }, []);

  /* ---------- trust mode (manual gate / auto run) ---------- */
  const fetchModeState = useCallback(async () => {
    try {
      const d = (await fetchJSON("/mode")) as Record<string, unknown>;
      const m = pick(d, "mode");
      if (m === "manual" || m === "auto") setFloorMode(m);
      const ar = pick(d, "auto_run") as AutoRunStatus | undefined;
      if (ar && typeof ar === "object") setAutoStatus(ar);
    } catch { /* API offline — the toggle simply stays hidden */ }
    try {
      const s = (await fetchJSON("/auto/status")) as AutoRunStatus;
      if (s && typeof s === "object" && "status" in s) setAutoStatus(s);
    } catch { /* API offline */ }
  }, []);

  useEffect(() => {
    if (mode !== "live") return;
    void fetchModeState();
    const iv = setInterval(() => void fetchModeState(), 4000);
    return () => clearInterval(iv);
  }, [mode, fetchModeState, liveEpoch]);

  /* ---------- events ---------- */
  const handleEvent = useCallback(
    (ev: FloorEvent) => {
      if (!ev || typeof ev !== "object") return;
      const type = String(pick(ev as unknown as Record<string, unknown>, "type", "event") ?? "");
      const p = payloadOf(ev);
      const seq = Number(pick(ev as unknown as Record<string, unknown>, "seq", "id"));
      // A genuinely new event always carries the highest seq so far, so
      // anything at or below the watermark is a replay or a duplicate
      // frame (the stream replays on reconnect, and named listeners can
      // double-deliver). Skipping those keeps one-shot effects — the
      // payroll dialog above all — from re-firing.
      if (Number.isFinite(seq) && seq > 0 && seq <= lastSeq.current) return;
      if (Number.isFinite(seq) && seq > lastSeq.current) lastSeq.current = seq;
      const text = eventText(ev, p);

      /* Per-job event log → the inspector's activity timeline and
         review passes (AO's session activity, Floor-style). */
      const logJobId =
        pick(p, "job_id", "job") !== undefined ? String(pick(p, "job_id", "job")) : jobIdForWorkOrder(p);
      if (logJobId !== undefined && type !== "narration") {
        const who = nameOf(p);
        let tone: FloorEventLogItem["tone"] = "neutral";
        if (type === "payment.made" || type === "agent.hired" || type === "confirmation.auto_approved") tone = "good";
        else if (type === "agent.fired" || type === "appeal.filed") tone = "warn";
        else if (type === "appeal.decided") tone = /upheld|accept|overturn/i.test(text) ? "good" : "warn";
        else if (type === "review.completed") tone = /reject/i.test(text) ? "warn" : "good";
        const logText = text || describeEvent(type, p, who);
        setEventLog((prev) =>
          [
            ...prev,
            { key: keyRef.current++, type, jobId: logJobId, agentName: who !== "An agent" ? who : undefined, text: logText, tone },
          ].slice(-300)
        );
      }

      const upsertJob = (patch: Record<string, unknown>) => {
        const id = pick(patch, "id", "job_id");
        if (id === undefined) {
          if (modeRef.current === "live") void loadSnapshot();
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
          if (modeRef.current === "live") void loadSnapshot();
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
          setAgentPresence(resolveAgentId(p), { state: "working" });
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
          setAgentPresence(resolveAgentId(p), { state: "bidding" });
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
          setAgentPresence(resolveAgentId(p), { state: "working" });
          break;
        case "tool.executed": {
          narrate(text || `${nameOf(p)} ran tool ${String(pick(p, "tool_name", "tool") ?? "")} on "${jobTitleOf(p)}".`);
          const tool = pick(p, "tool_name", "tool");
          setAgentPresence(resolveAgentId(p), { state: "working", tool: tool ? String(tool) : undefined });
          break;
        }
        case "work.submitted":
          narrate(text || `${nameOf(p)} submitted work on "${jobTitleOf(p)}" for review.`);
          if (pick(p, "job_id", "id") !== undefined) upsertJob({ id: pick(p, "job_id", "id"), status: "in_review" });
          setAgentPresence(resolveAgentId(p) ?? workerIdForJob(p) ?? workerIdForWorkOrder(p), { state: "review" });
          break;
        case "review.completed": {
          const verdict = pick(p, "verdict");
          const sev = pick(p, "severity");
          narrate(text || `Review complete on "${jobTitleOf(p)}" — ${verdict ?? ""}${sev ? ` (${sev})` : ""}.`);
          setAgentPresence(resolveAgentId(p) ?? workerIdForJob(p) ?? workerIdForWorkOrder(p), { state: "idle" });
          break;
        }
        case "appeal.filed":
          narrate(text || `${nameOf(p)} is appealing the rejection on "${jobTitleOf(p)}"…`, "appeal");
          setAgentPresence(resolveAgentId(p) ?? workerIdForJob(p) ?? workerIdForWorkOrder(p), { state: "appealing" });
          break;
        case "appeal.decided": {
          const upheld = pick(p, "upheld", "overturned");
          const outcome = String(pick(p, "outcome", "verdict") ?? "").toLowerCase();
          narrate(
            text ||
              (outcome === "upheld" || upheld === true || outcome === "overturned" || outcome === "accept"
                ? "APPEAL UPHELD — the worker is paid and the original Reviewer is penalised."
                : "Appeal denied — the rejection stands."),
            "appeal"
          );
          setAgentPresence(resolveAgentId(p) ?? workerIdForJob(p) ?? workerIdForWorkOrder(p), { state: "idle" });
          break;
        }
        case "payment.made": {
          flashMascot("paid");
          const amt = pick(p, "amount_credits", "amount");
          narrate(text || `${nameOf(p)} was paid ${amt !== undefined ? credits(amt) : ""} for "${jobTitleOf(p)}".`);
          const paidId = resolveAgentId(p) ?? workerIdForJob(p) ?? workerIdForWorkOrder(p);
          flashPaid(paidId);
          setAgentPresence(paidId, { state: "idle" });
          const row: LedgerRow = { ...(p as LedgerRow) };
          if (pick(row as Record<string, unknown>, "note", "reason") === undefined)
            row.note = `earning — ${jobTitleOf(p)} accepted`;
          // Ledger displays newest first (the API snapshot order); live
          // payments are the newest rows, so they go at the front.
          setLedger((prev) => [row, ...prev]);
          break;
        }
        case "cycle.closed": {
          const cn = pick(p, "cycle_no", "cycle");
          if (cn !== undefined) setCycle(Number(cn));
          narrate(text || "Payroll ran — the cycle is closed.");
          setBanner(true);
          setTimeout(() => setBanner(false), 6000);
          setPayroll(p as PayrollPayload);
          setPresence({});
          // Live mode refreshes from the API here; in demo mode the
          // replay driver applies the recorded snapshot patch instead.
          if (modeRef.current === "live") void loadSnapshot();
          break;
        }
        case "agent.fired": {
          flashMascot("pinkslip");
          const fid = pick(p, "agent_id", "id", "agent");
          if (fid !== undefined) {
            setFiredIds((prev) => new Set(prev).add(String(fid)));
            setTimeout(() => setFiredIds(new Set()), 2500);
            setAgentPresence(String(fid), { state: "fired" });
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
          if (hid !== undefined) setAgentPresence(String(hid), { state: "idle" });
          break;
        }
        case "confirmation.auto_approved": {
          const tool = pick(p, "tool_name", "tool");
          setTicker((prev) =>
            [
              ...prev,
              {
                key: keyRef.current++,
                who: "Gate",
                text: `auto-approved ${tool ? String(tool) : "a write"} on "${jobTitleOf(p)}" (auto mode — logged, no human at the gate)`,
              },
            ].slice(-24)
          );
          break;
        }
        case "mode.changed":
        case "auto.started":
        case "auto.paused":
        case "auto.stopped":
        case "auto.cycle_started":
          void fetchModeState();
          if (text) narrate(text);
          break;
        case "narration":
          narrate(text);
          break;
        default:
          if (text) narrate(text);
          break;
      }
    },
    [loadSnapshot, nameOf, jobTitleOf, narrate, resolveAgentId, workerIdForJob, workerIdForWorkOrder, jobIdForWorkOrder, setAgentPresence, flashPaid, flashMascot, fetchModeState]
  );

  useEffect(() => {
    void loadSnapshot();
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      try {
        // Resume from the last seen seq: the stream replays from from_seq,
        // and a full replay would re-fire one-shot UI effects (the payroll
        // dialog) on every reconnect.
        es = new EventSource(`${API_BASE}/events?from_seq=${lastSeq.current}`);
      } catch {
        retry = setTimeout(connect, 5000);
        return;
      }
      es.onopen = () => {
        everConnectedRef.current = true;
        setConnected(true);
      };
      es.onmessage = (m) => {
        // In demo mode the replay driver owns handleEvent; live frames
        // must not leak into a recording (the presenter may start the
        // API mid-replay — the mode bar offers a clean switch instead).
        if (modeRef.current === "demo") return;
        try {
          handleEvent(JSON.parse(m.data) as FloorEvent);
        } catch { /* ignore malformed frames */ }
      };
      EVENT_TYPES.forEach((t) => {
        es?.addEventListener(t, (m) => {
          if (modeRef.current === "demo") return;
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
      if (modeRef.current === "demo") return; // the demo probe watches instead
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
  }, [loadSnapshot, handleEvent, liveEpoch]);

  /* Offline grace: give the API ~3s to answer before offering the
     recorded demo — a slow local start should not flash the hero. */
  useEffect(() => {
    const t = setTimeout(() => setGraceDone(true), 3000);
    return () => clearTimeout(t);
  }, []);

  /* ---------- recorded demo replay ---------- */
  const stopReplay = useCallback(() => {
    demoTimers.current.forEach((t) => clearTimeout(t));
    demoTimers.current = [];
  }, []);

  const clearFloorState = useCallback(() => {
    setAgents([]);
    setJobs([]);
    setLedger([]);
    setNarration([]);
    setTicker([]);
    setEventLog([]);
    logSeededRef.current = false;
    setPinkSlips([]);
    setCycle(null);
    setServerPaid(null);
    setPayroll(null);
    setBanner(false);
    setPresence({});
    setPaidFlash(new Set());
    setFiredIds(new Set());
    setHireIds(new Set());
    setSelection(null);
    lastSeq.current = 0;
  }, []);

  /* What the live cycle.closed → loadSnapshot() refresh does, staged
     from the recording: after cycle 1, jobs 1–5 settle and balances
     become the cycle-1 payroll nets (seed balances are 0 and balance
     accrues exactly the per-cycle net — verified against the captured
     final snapshot). After cycle 2, the full final snapshots land. */
  const applyCyclePatch = useCallback((payload: Record<string, unknown>) => {
    const cycleNo = Number(pick(payload, "cycle_no", "cycle"));
    if (Number.isFinite(cycleNo)) setCycle(cycleNo);
    if (cycleNo === 1) {
      const rows = (payload.payroll as Record<string, unknown>[] | undefined) ?? [];
      const netById = new Map(rows.map((r) => [String(r.agent_id), Number(r.net)]));
      setAgents((prev) =>
        prev.map((a) => (netById.has(a.id) ? { ...a, balance_credits: netById.get(a.id) ?? 0 } : a))
      );
      setJobs(RECORDED_FINAL_JOBS.filter((j) => Number(j.id) <= 5).map(normalizeJob));
    } else if (cycleNo >= 2) {
      setAgents(RECORDED_FINAL_AGENTS.map(normalizeAgent));
      setJobs(RECORDED_FINAL_JOBS.map(normalizeJob));
      setServerPaid(RECORDED_TOTAL_PAID);
    }
  }, []);

  const dispatchRecorded = useCallback(
    (e: RecordedEvent) => {
      // Rewind the watermark so the guard in handleEvent treats this
      // recorded frame as new (recorded seqs restart from the capture).
      lastSeq.current = Math.min(lastSeq.current, e.seq - 1);
      let ev = asFloorEvent(e);
      if (e.type === "payment.made") {
        // The live ledger snapshot carries the payee's name and a kind;
        // the raw event does not. Enrich the copy with the same facts
        // (resolved from the seeded roster) so the ledger and the
        // paid-out total read exactly as they do live.
        const who = agentsRef.current.find((a) => a.id === String(e.payload.agent_id))?.name;
        ev = {
          ...ev,
          payload: { ...e.payload, kind: "payment", ...(who ? { agent_name: who } : {}) },
        };
      }
      handleEvent(ev);
      if (e.type === "cycle.closed") applyCyclePatch(e.payload);
    },
    [handleEvent, applyCyclePatch]
  );

  const startReplay = useCallback(() => {
    stopReplay();
    withTransition(() => {
      clearFloorState();
      setMode("demo");
      setDemoPhase("playing");
      setAgents(RECORDED_SEED_AGENTS.map(normalizeAgent));
    });
    narrate("Recorded shift — replaying a real 2-cycle shift captured from the live floor.");
    RECORDED_EVENTS.forEach((e) => {
      demoTimers.current.push(setTimeout(() => dispatchRecorded(e), e.at * 1000));
    });
    const last = RECORDED_EVENTS[RECORDED_EVENTS.length - 1];
    demoTimers.current.push(setTimeout(() => setDemoPhase("ended"), (last ? last.at + 2.5 : 5) * 1000));
  }, [stopReplay, clearFloorState, dispatchRecorded, narrate]);

  const resetReplay = useCallback(() => {
    stopReplay();
    withTransition(() => {
      clearFloorState();
      setMode("demo");
      setDemoPhase("idle");
      setAgents(RECORDED_SEED_AGENTS.map(normalizeAgent));
    });
  }, [stopReplay, clearFloorState]);

  const enterLive = useCallback(() => {
    stopReplay();
    withTransition(() => {
      clearFloorState();
      setMode("live");
      setDemoPhase("idle");
      setApiUp(false);
    });
    setLiveEpoch((n) => n + 1);
    void loadSnapshot();
  }, [stopReplay, clearFloorState, loadSnapshot]);

  useEffect(() => stopReplay, [stopReplay]);

  /* While a replay is on screen, keep an ear out for the real API —
     if it appears, offer the switch instead of assuming. */
  useEffect(() => {
    if (mode !== "demo" || apiUp) return;
    let cancelled = false;
    const probe = async () => {
      try {
        await fetchJSON("/health");
        if (!cancelled) setApiUp(true);
      } catch { /* still offline */ }
    };
    void probe();
    const iv = setInterval(probe, 6000);
    return () => {
      cancelled = true;
      clearInterval(iv);
    };
  }, [mode, apiUp]);

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
    const s: ShellStats = {
      cycle,
      paidOut: serverPaid !== null ? serverPaid : paid,
      done,
      failed,
      activeAgents: work.length + mgmt.length,
    };
    return { management: mgmt, workers: work, fired: dead, stats: s };
  }, [agents, jobs, ledger, cycle, serverPaid]);

  /* ---------- actions ---------- */
  const onRunLive = useCallback(async () => {
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

  const onResetLive = useCallback(async () => {
    if (!window.confirm("Reset the demo to its exact seeded start state?")) return;
    try {
      await postJSON("/reset");
      showToast("Demo reset to the seeded start state.");
      setFiredIds(new Set());
      setHireIds(new Set());
      setPresence({});
      setPaidFlash(new Set());
      setSelection(null);
      setNarration([]);
      setTicker([]);
      setEventLog([]);
      logSeededRef.current = false;
      setPinkSlips([]);
      void loadSnapshot();
    } catch {
      showToast("Reset failed — is the factory API up?", true);
    }
  }, [loadSnapshot, showToast]);

  const onFloorModeChange = useCallback(
    async (m: FloorTrustMode) => {
      try {
        await postJSON("/mode", { mode: m });
        setFloorMode(m);
        showToast(
          m === "auto"
            ? "Auto mode — writes are auto-approved and logged; the floor can run itself up to a cap."
            : "Manual mode — every write waits for a human at the confirmation gate."
        );
        void fetchModeState();
      } catch {
        showToast("Could not switch mode — is the factory API up?", true);
      }
    },
    [fetchModeState, showToast]
  );

  const onAutoStart = useCallback(
    async (cap: number) => {
      try {
        await postJSON("/auto/start", { budget_cap_credits: cap });
        showToast(`Auto run started — the floor runs itself up to a ${credits(cap)} cap.`);
        void fetchModeState();
      } catch {
        showToast("Could not start the auto run — check the cap and that no shift is running.", true);
      }
    },
    [fetchModeState, showToast]
  );

  const onAutoPause = useCallback(async () => {
    try {
      await postJSON("/auto/pause");
      showToast("Auto run pausing — the current cycle finishes first.");
      void fetchModeState();
    } catch {
      showToast("Could not pause the auto run.", true);
    }
  }, [fetchModeState, showToast]);

  const onAutoStop = useCallback(async () => {
    try {
      await postJSON("/auto/stop");
      showToast("Auto run stopped.");
      void fetchModeState();
    } catch {
      showToast("Could not stop the auto run.", true);
    }
  }, [fetchModeState, showToast]);

  const visibleJobs = useMemo(
    () => (deptFilter === "all" ? jobs : jobs.filter((j) => (j.department ?? "support") === deptFilter)),
    [jobs, deptFilter]
  );

  const demo = mode === "demo";
  const onRun = demo ? startReplay : onRunLive;
  const onReset = demo ? resetReplay : onResetLive;
  const runBusy = demo ? demoPhase === "playing" : running;

  /* The offline hero shows only when the API has never answered in
     this session — a mid-session drop keeps the (real) floor on
     screen with its Offline pill instead. */
  const showHero = !demo && !connected && graceDone && !everConnectedRef.current && agents.length === 0;

  const selectedJob = selection?.kind === "job" ? jobs.find((j) => j.id === selection.id) ?? null : null;
  const selectedAgent = selection?.kind === "agent" ? agents.find((a) => a.id === selection.id) ?? null : null;

  /* The Foreman's base state, derived from the same live signals the
     rest of the console runs on: a one-shot event flash wins, then an
     active auto run, then any agent presence in `working` (or a shift
     in flight), else idle. Presence is event-derived, so the recorded
     replay drives the avatar exactly as the live stream does. */
  const anyWorking = running || Object.values(presence).some((p) => p.state === "working");
  const mascotState: MascotState =
    mascotFlash ?? (autoStatus?.status === "running" ? "auto" : anyWorking ? "working" : "idle");

  return (
    <>
      <FloorShell
        mascotState={mascotState}
        management={management}
        workers={workers}
        fired={fired}
        stats={stats}
        presence={presence}
        paidFlash={paidFlash}
        firedIds={firedIds}
        hireIds={hireIds}
        selectedAgentId={selection?.kind === "agent" ? selection.id : null}
        onSelectAgent={(a) => setSelection({ kind: "agent", id: a.id })}
        connected={connected}
        mode={mode}
        demoPhase={demoPhase}
        floorMode={demo ? null : floorMode}
        autoStatus={demo ? null : autoStatus}
        onFloorModeChange={(m) => void onFloorModeChange(m)}
        onAutoStart={(cap) => void onAutoStart(cap)}
        onAutoPause={() => void onAutoPause()}
        onAutoStop={() => void onAutoStop()}
        running={runBusy}
        onRun={onRun}
        onReset={onReset}
        showHero={showHero}
        onStartReplay={startReplay}
        apiUp={apiUp}
        onEnterLive={enterLive}
        banner={banner}
        ledger={ledger}
        narration={narration}
        ticker={ticker}
        pinkSlips={pinkSlips}
        board={
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex shrink-0 flex-wrap items-center gap-1.5 px-4 pb-1 pt-3" role="group" aria-label="Filter jobs by department">
              {DEPT_FILTERS.map((d) => {
                const n = d.key === "all" ? jobs.length : jobs.filter((j) => (j.department ?? "support") === d.key).length;
                const active = deptFilter === d.key;
                return (
                  <button
                    key={d.key}
                    type="button"
                    onClick={() => setDeptFilter(d.key)}
                    aria-pressed={active}
                    className={`rounded-full border px-2.5 py-1 text-2xs font-medium transition-colors ${
                      active
                        ? "border-transparent bg-primary text-primary-foreground"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {d.label}
                    <span className="ml-1.5 font-mono tabular-nums opacity-75">{n}</span>
                  </button>
                );
              })}
              <a
                href="/console/connections"
                className="ml-auto rounded-full border border-border px-2.5 py-1 text-2xs font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                Connections →
              </a>
            </div>
            <div className="min-h-0 flex-1">
              <FloorBoard
                jobs={visibleJobs}
                selectedId={selection?.kind === "job" ? selection.id : null}
                onSelect={(j) => setSelection({ kind: "job", id: j.id })}
              />
            </div>
          </div>
        }
        inspector={
          selection ? (
            <div className="w-[340px] shrink-0 border-l border-border bg-background">
              <FloorInspector
                job={selectedJob}
                agent={selectedAgent}
                events={eventLog}
                presence={selectedAgent ? presence[selectedAgent.id] : undefined}
                onClose={() => setSelection(null)}
              />
            </div>
          ) : null
        }
      />
      <PayrollDialog payroll={payroll} onClose={() => setPayroll(null)} />
      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg ${
            toast.error
              ? "border-destructive/40 bg-popover text-destructive"
              : "border-border bg-popover text-popover-foreground"
          }`}
          role="status"
          aria-live="polite"
        >
          {toast.msg}
        </div>
      )}
    </>
  );
}
