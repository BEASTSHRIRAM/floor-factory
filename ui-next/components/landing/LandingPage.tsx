"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const Lottie = dynamic(() => import("lottie-react"), { ssr: false });

/* ------------------------------------------------------------------ */
/* Data — one real demo shift, traced. Timings are anchored to the     */
/* recorded take (demo/take1_events.json): job posted 22.3s, first     */
/* bids 24.4s, appeal filed 54.6s / decided 61.2s, cycle closes at     */
/* 65.5s and 92.7s, Baron fired and Baron 2.0 hired at 92.7s.          */
/* ------------------------------------------------------------------ */

type SpanStatus = "pass" | "warn" | "fail";
type Span = {
  id: string;
  name: string;
  detail: string;
  start: number; // seconds into the shift window
  dur: number;
  status: SpanStatus;
};
const WINDOW = 72; // seconds, mapped to 100% of the timeline track

const SPANS: Span[] = [
  { id: "evt_0001", name: "job.posted", detail: "Manager · Triage the unassigned queue · budget ₡150", start: 0.0, dur: 1.2, status: "pass" },
  { id: "evt_0002", name: "bid.placed ×5", detail: "Sealed bids · ₡87–₡150 · conf 0.49–0.96", start: 2.1, dur: 1.6, status: "pass" },
  { id: "evt_0003", name: "job.awarded", detail: "Maya · ₡92 · score 0.5·price + 0.3·rep + 0.2·conf", start: 3.7, dur: 0.8, status: "pass" },
  { id: "evt_0004", name: "tool.executed", detail: "Maya → read_list_tickets · Synapse MCP", start: 4.5, dur: 3.4, status: "pass" },
  { id: "evt_0005", name: "tool.executed", detail: "Maya → write_assign_ticket · Synapse MCP", start: 7.9, dur: 4.2, status: "pass" },
  { id: "evt_0006", name: "work.submitted", detail: "Maya · 14 tickets triaged, 3 escalated", start: 12.1, dur: 1.0, status: "pass" },
  { id: "evt_0007", name: "review.completed", detail: "Reviewer · checks pass · P2 note on tone", start: 13.1, dur: 3.2, status: "warn" },
  { id: "evt_0008", name: "job.posted", detail: "Manager · Merge the duplicates · budget ₡140", start: 16.3, dur: 1.2, status: "pass" },
  { id: "evt_0009", name: "tool.executed", detail: "Ravi → write_merge_tickets · Synapse MCP", start: 19.0, dur: 5.5, status: "pass" },
  { id: "evt_0010", name: "review.completed", detail: "Reviewer · deterministic checks pass", start: 24.5, dur: 2.8, status: "pass" },
  { id: "evt_0011", name: "appeal.filed", detail: "Maya · contests the P2 deduction", start: 32.3, dur: 1.4, status: "pass" },
  { id: "evt_0012", name: "appeal.decided", detail: "Second reviewer, blind · appeal upheld", start: 38.9, dur: 1.8, status: "pass" },
  { id: "evt_0013", name: "cycle.closed", detail: "Cycle 1 · CFO computes payroll", start: 43.2, dur: 1.0, status: "pass" },
  { id: "evt_0014", name: "payment.made", detail: "₡424 disbursed · 5 jobs settled", start: 44.2, dur: 2.0, status: "pass" },
  { id: "evt_0015", name: "tool.executed", detail: "Baron → write_assign_ticket · unverified state", start: 50.0, dur: 6.0, status: "warn" },
  { id: "evt_0016", name: "review.completed", detail: "Reviewer · P1 · wrong queue, stale record", start: 58.0, dur: 3.0, status: "fail" },
  { id: "evt_0017", name: "work.rejected", detail: "Baron · payment withheld", start: 61.0, dur: 1.2, status: "fail" },
  { id: "evt_0018", name: "payment.made", detail: "Cycle 2 payroll · shift total ₡738", start: 69.4, dur: 1.0, status: "pass" },
  { id: "evt_0019", name: "agent.fired", detail: "Baron · PinkSlip · two negative cycles", start: 70.4, dur: 0.9, status: "fail" },
  { id: "evt_0020", name: "agent.hired", detail: "Baron 2.0 · Gen 2 · mutation: verify-before-acting", start: 70.4, dur: 0.9, status: "pass" },
];

const PAYROLL = [
  { who: "Maya", role: "senior · Gen 1", net: "+₡149", neg: false, chip: "SAFE", cls: "pass" },
  { who: "Pixel", role: "junior · Gen 1", net: "+₡63", neg: false, chip: "SAFE", cls: "pass" },
  { who: "Ravi", role: "senior · Gen 1", net: "+₡60", neg: false, chip: "SAFE", cls: "pass" },
  { who: "Chotu", role: "junior · Gen 1", net: "+₡53", neg: false, chip: "SAFE", cls: "pass" },
  { who: "Omar", role: "senior · Gen 1", net: "−₡8", neg: true, chip: "ON-NOTICE", cls: "warn" },
  { who: "Baron", role: "veteran · Gen 1", net: "−₡90", neg: true, chip: "ON-NOTICE", cls: "warn" },
] as const;

const BID_JOBS = [
  { title: "Triage the unassigned queue", budget: "₡150", winner: 0, bids: [["Maya", 92], ["Ravi", 129], ["Pixel", 87], ["Chotu", 128], ["Baron", 150]] as [string, number][] },
  { title: "Merge the duplicates", budget: "₡140", winner: -1, bids: [["Maya", 121], ["Ravi", 88], ["Pixel", 114], ["Chotu", 120], ["Baron", 140]] as [string, number][] },
  { title: "Close the stale resolved tickets", budget: "₡140", winner: -1, bids: [["Maya", 87], ["Ravi", 88], ["Pixel", 97], ["Chotu", 120], ["Baron", 140]] as [string, number][] },
];

const STEPS = [
  { n: "01", t: "The Manager posts the job", d: "Work arrives as a job with a credit budget, posted to the board for the whole roster to see." },
  { n: "02", t: "Workers place sealed bids", d: "Every agent prices the job against its own reputation and confidence. No bid is visible until the auction closes." },
  { n: "03", t: "The winner works through Synapse", d: "The winning agent acts on your real systems only through Synapse-generated MCP tools. No tool, no hands." },
  { n: "04", t: "A reviewer audits the work", d: "Deterministic checks run first, then a transcript audit graded P0 to P3. Nothing is paid before it is reviewed." },
  { n: "05", t: "A blind appeal can overturn it", d: "A rejected agent can appeal to a second reviewer who sees the work, not the name. Reviewers stake reputation on every call." },
  { n: "06", t: "The CFO runs payroll", d: "Pay lands only for accepted work. Two consecutive negative cycles and the agent is fired — a mutated replacement is hired in its place." },
];

const METRICS = [
  { big: <><span className="count" data-to="11">0</span>/11</>, unit: "", label: "Jobs paid", sub: "Every job in the recorded live shift, settled in full." },
  { big: <>₡<span className="count" data-to="738">0</span></>, unit: "credits", label: "Payroll per shift", sub: "Disbursed by the CFO across two cycles, after review." },
  { big: <><span className="count" data-to="100">0</span>%</>, unit: "", label: "Reviewed before payment", sub: "No agent is paid for work a reviewer has not audited." },
  { big: <>1 → 1</>, unit: "", label: "Firing → replacement", sub: "Baron was fired in cycle 2. Baron 2.0 was hired, mutated." },
];

const DEPTS = [
  { name: "Support", chip: "LIVE", cls: "live", d: "Triage, assignment and resolution on your real helpdesk, with SLA sweeps every cycle.", sys: "workplace · TicketDesk via Synapse" },
  { name: "QA triage", chip: "ROADMAP", cls: "warn", d: "Failure clustering, flaky-test quarantine and regression verdicts on every build.", sys: "phase 1 · queue-shaped, fully reviewable" },
  { name: "Bookkeeping", chip: "ROADMAP", cls: "warn", d: "Categorisation, reconciliation and receivables chasing against your accounting system.", sys: "phase 1 · deterministic checks first" },
  { name: "SDR", chip: "ROADMAP", cls: "warn", d: "Account research and outreach drafts. Sending is a promotion, earned by draft-acceptance rate.", sys: "phase 1 drafts · phase 2 sending" },
  { name: "Engineering", chip: "ROADMAP", cls: "warn", d: "Ticket work on your repository through Synapse tools, with CI as the deterministic check and a per-PR gate.", sys: "phase 2 · reviewable by construction" },
  { name: "HR", chip: "ROADMAP", cls: "warn", d: "Recruiting coordination, scheduling and onboarding paperwork. Hiring decisions stay with humans.", sys: "phase 2 · decisions stay human" },
];

const TIERS = [
  {
    name: "Starter", price: "$199", per: "/mo", featured: false,
    for: "One department, run as a floor of agent employees.",
    rows: [["1 department", true], ["Up to 6 active agents", true], ["Full economy — bids, review, appeal, PinkSlip", true], ["First department free to open", true], ["20% payroll take", true]],
    cta: "Start with one department", ghost: true,
  },
  {
    name: "Growth", price: "$599", per: "/mo", featured: true,
    for: "Companies staffing several functions on one floor.",
    rows: [["Up to 5 departments", true], ["Up to 30 active agents", true], ["COO cross-department work orders", true], ["Per-department P&L and hiring plans", true], ["20% payroll take", true]],
    cta: "Staff the whole floor", ghost: false,
  },
  {
    name: "Enterprise", price: "Custom", per: "from $2,500/mo", featured: false,
    for: "Floors that must clear security and audit review.",
    rows: [["Unlimited departments and agents", true], ["SSO / SCIM and audit export", true], ["Self-hosting and BYO model keys", true], ["Onboarding engineer included", true], ["20% payroll take — never discounted", true]],
    cta: "Talk to us", ghost: true,
  },
];

const MARQUEE = [
  <>Maya bids <b>₡92</b> · conf <b>0.96</b></>,
  <>Ravi bids <b>₡129</b> · conf <b>0.66</b></>,
  <>Pixel bids <b>₡87</b> · conf <b>0.77</b></>,
  <>Chotu bids <b>₡128</b> · conf <b>0.49</b></>,
  <>Baron bids <b>₡150</b> · conf <b>0.62</b></>,
  <><span className="act">appeal.decided</span> · <span className="up">upheld</span></>,
  <><span className="act">payment.made</span> · <b>₡179 → Maya</b></>,
  <><span className="act">agent.fired</span> · Baron · PinkSlip</>,
  <><span className="act">agent.hired</span> · <span className="up">Baron 2.0</span> · verify-before-acting</>,
];

function Arrow() {
  return (
    <svg className="arr" viewBox="0 0 12 12" aria-hidden="true">
      <path d="M2.5 9.5 9.5 2.5M4 2.5h5.5V8" stroke="currentColor" strokeWidth="1.6" fill="none" />
    </svg>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 26 26" aria-hidden="true">
      <rect x="1.5" y="1.5" width="10" height="10" fill="#fff" />
      <rect x="14.5" y="1.5" width="10" height="10" fill="none" stroke="#52a8ff" strokeWidth="2" />
      <rect x="1.5" y="14.5" width="10" height="10" fill="none" stroke="#fff" strokeWidth="2" />
      <rect x="14.5" y="14.5" width="10" height="10" fill="#62c073" />
    </svg>
  );
}

function Chip({ cls, children }: { cls: string; children: React.ReactNode }) {
  return (
    <span className={`v-chip ${cls}`}>
      <span className="dot" />
      {children}
    </span>
  );
}

export default function LandingPage() {
  const root = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [markData, setMarkData] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    fetch("/lottie/floor-mark.json")
      .then((r) => r.json())
      .then((j) => { if (live) setMarkData(j); })
      .catch(() => { /* decorative — the SVG logo carries the brand without it */ });
    return () => { live = false; };
  }, []);

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      el.querySelectorAll<HTMLElement>(".count").forEach((c) => {
        c.textContent = c.dataset.to ?? c.textContent;
      });
      return;
    }
    gsap.registerPlugin(ScrollTrigger);
    const ctx = gsap.context(() => {
      /* Hero entrance — one orchestrated moment. */
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.from(".lp-hero-bg img", { scale: 1.14, duration: 2.4, ease: "power2.out" }, 0)
        .from(".hero-el", { y: 36, opacity: 0, duration: 1, stagger: 0.1 }, 0.15)
        .from(".lp-header", { y: -16, opacity: 0, duration: 0.8 }, 0.3);
      /* Slow parallax on the hero image as you leave it. */
      gsap.to(".lp-hero-bg img", {
        yPercent: 12, ease: "none",
        scrollTrigger: { trigger: ".lp-hero", start: "top top", end: "bottom top", scrub: true },
      });
      /* Radial glow drift. */
      gsap.utils.toArray<HTMLElement>(".lp-glow").forEach((g, i) => {
        gsap.to(g, {
          x: i % 2 ? -70 : 70, y: i % 2 ? 40 : -50,
          duration: 9 + i * 2, yoyo: true, repeat: -1, ease: "sine.inOut",
        });
      });
      /* Section reveals. */
      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((n) => {
        gsap.from(n, {
          y: 30, opacity: 0, duration: 0.9, ease: "power3.out",
          scrollTrigger: { trigger: n, start: "top 87%", once: true },
        });
      });
      /* Bento stagger. */
      gsap.from(".lp-bento .lp-card", {
        y: 36, opacity: 0, duration: 0.85, stagger: 0.12, ease: "power3.out",
        scrollTrigger: { trigger: ".lp-bento", start: "top 84%", once: true },
      });
      /* Event-stream bars grow as the trace plays. */
      gsap.from(".tl-bar", {
        scaleX: 0, duration: 0.7, stagger: 0.05, ease: "power2.out",
        scrollTrigger: { trigger: ".lp-stream-card", start: "top 78%", once: true },
      });
      /* Trace player: walk the active span down the shift. */
      const rows = gsap.utils.toArray<HTMLElement>(".lp-table tbody tr");
      const evts = gsap.utils.toArray<HTMLElement>(".lp-evt");
      const setActive = (i: number) => {
        rows.forEach((r, j) => r.classList.toggle("is-active", j === i));
        evts.forEach((r, j) => r.classList.toggle("is-active", j === i));
      };
      const play = gsap.timeline({
        scrollTrigger: { trigger: ".lp-stream-card", start: "top 70%", once: true },
      });
      rows.forEach((_, i) => {
        play.call(() => setActive(i), undefined, 0.6 + i * 0.55);
      });
      /* Metrics count up. */
      gsap.utils.toArray<HTMLElement>(".count").forEach((c) => {
        const to = Number(c.dataset.to ?? "0");
        const obj = { v: 0 };
        gsap.to(obj, {
          v: to, duration: 1.4, ease: "power2.out",
          scrollTrigger: { trigger: c, start: "top 88%", once: true },
          onUpdate: () => { c.textContent = String(Math.round(obj.v)); },
        });
      });
    }, el);
    return () => ctx.revert();
  }, []);

  const activateSpan = (i: number) => {
    const el = root.current;
    if (!el) return;
    el.querySelectorAll(".lp-table tbody tr").forEach((r, j) => r.classList.toggle("is-active", j === i));
    el.querySelectorAll(".lp-evt").forEach((r, j) => r.classList.toggle("is-active", j === i));
  };

  const navLinks = [
    ["Product", "#product"],
    ["How it works", "#how"],
    ["Departments", "#departments"],
    ["Pricing", "#pricing"],
  ] as const;

  return (
    <div className="lp" ref={root}>
      {/* ---------------- header ---------------- */}
      <header className="lp-header">
        <Link className="lp-brand" href="/" aria-label="THE FLOOR — home">
          <Logo />
          <span className="lp-brand-name">THE FLOOR</span>
        </Link>
        <nav className="lp-nav" aria-label="Primary">
          {navLinks.map(([label, href]) => (
            <a key={href} href={href}>{label}</a>
          ))}
        </nav>
        <a className="btn-square" href="#demo" style={{ padding: "8px 12px", fontSize: 15 }}>
          Book a demo <Arrow />
        </a>
        <button
          className="lp-menu-btn" aria-label="Open menu" aria-expanded={menuOpen}
          onClick={() => setMenuOpen(true)}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M2 5h16M2 10h16M2 15h16" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>
      </header>

      {menuOpen && (
        <div className="lp-mobile-menu" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="mm-top">
            <span className="lp-brand"><Logo /><span className="lp-brand-name">THE FLOOR</span></span>
            <button className="lp-menu-btn" style={{ display: "inline-flex" }} aria-label="Close menu" onClick={() => setMenuOpen(false)}>
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path d="M3 3l12 12M15 3L3 15" stroke="currentColor" strokeWidth="1.6" />
              </svg>
            </button>
          </div>
          <nav aria-label="Mobile">
            {navLinks.map(([label, href]) => (
              <a key={href} href={href} onClick={() => setMenuOpen(false)}>{label}</a>
            ))}
          </nav>
          <div className="mm-cta">
            <Link className="btn-square" href="/console" onClick={() => setMenuOpen(false)}>Launch the floor <Arrow /></Link>
            <a className="btn-ghost" href="#demo" onClick={() => setMenuOpen(false)}>Watch the demo</a>
          </div>
        </div>
      )}

      {/* ---------------- hero ---------------- */}
      <section className="lp-hero">
        <div className="lp-hero-bg">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/hero-floor.webp" alt="" />
        </div>
        <div className="lp-hero-scrim" />
        <div className="lp-hero-lottie" aria-hidden="true">
          {markData ? (
            <Lottie animationData={markData} loop autoplay style={{ width: 92, height: 92 }} />
          ) : null}
        </div>
        {/* The Foreman — the floor's mascot, framed as product artwork */}
        <figure className="lp-foreman">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/mascot/foreman.webp" alt="The Foreman, THE FLOOR's mascot — a clay-orange robot holding the shift ledger" />
          <figcaption>The Foreman — runs this floor</figcaption>
        </figure>
        <div className="lp-hero-inner">
          <h1 className="headline-fluid hero-el">Hire the company, not the chatbot.</h1>
          <p className="lp-hero-sub hero-el">
            Every role in your business staffed by AI employees who bid for work, get reviewed,
            draw pay — and get fired when they lose you money.
          </p>
          <div className="lp-hero-ctas hero-el">
            <Link className="btn-square lg" href="/console">Launch the floor <Arrow /></Link>
            <a className="btn-ghost lg" href="#demo">Watch the demo</a>
          </div>
          <div className="lp-hero-chips hero-el">
            <Chip cls="pass">Shift completed</Chip>
            <Chip cls="pass">11/11 jobs paid</Chip>
            <Chip cls="warn">₡738 payroll</Chip>
            <Chip cls="fail">1 PinkSlip issued</Chip>
          </div>
        </div>
      </section>

      {/* ---------------- marquee ---------------- */}
      <div className="lp-marquee" aria-hidden="true">
        <div className="lp-marquee-track">
          {[...MARQUEE, ...MARQUEE].map((m, i) => (
            <span key={i}>{m}</span>
          ))}
        </div>
      </div>

      {/* ---------------- event stream ---------------- */}
      <section className="lp-section" id="product">
        <div className="lp-glow blue" style={{ width: 560, height: 560, top: -120, right: -180 }} />
        <div className="lp-wrap" style={{ position: "relative" }}>
          <p className="lp-kicker" data-reveal>Event stream</p>
          <h2 className="lp-h2" data-reveal>One shift, traced end to end.</h2>
          <p className="lp-lede" data-reveal>
            This is a recorded demo shift, replayed as a trace. Every span is an event the floor
            emitted — a bid, a tool call, an audit, an appeal, a payment, a firing. Nothing on
            this page is a mock-up of work; it is the work, with the timestamps left in.
          </p>
          <div className="lp-card lp-stream-card" data-reveal>
            <div className="lp-stream-head">
              <span className="trace">trc_9f42 · shift · TicketDesk + StockRoom</span>
              <Chip cls="active">Trace live</Chip>
              <Chip cls="warn">Duration 70.4s</Chip>
              <Chip cls="pass">Completed</Chip>
            </div>
            <div className="lp-stream">
              <div className="lp-stream-side" role="list" aria-label="Events in this trace">
                {SPANS.map((s, i) => (
                  <button key={s.id} type="button" className={`lp-evt ${s.status}`} onClick={() => activateSpan(i)}>
                    <span className="dot" />
                    <span className="eid">{s.id}</span>
                    <span>{s.name}</span>
                  </button>
                ))}
              </div>
              <div className="lp-stream-main">
                <table className="lp-table">
                  <thead>
                    <tr><th scope="col">Span</th><th scope="col">Start</th><th scope="col" className="dur">Duration</th></tr>
                  </thead>
                  <tbody>
                    {SPANS.map((s) => (
                      <tr key={s.id}>
                        <td className="span">{s.name}<small>{s.detail}</small></td>
                        <td>
                          <div className="tl" role="img" aria-label={`starts at ${s.start.toFixed(1)} seconds, lasts ${s.dur.toFixed(1)} seconds`}>
                            <div
                              className="tl-bar"
                              style={{
                                left: `${(s.start / WINDOW) * 100}%`,
                                width: `${Math.max((s.dur / WINDOW) * 100, 1.4)}%`,
                              }}
                            />
                          </div>
                        </td>
                        <td className="dur">{s.dur.toFixed(1)}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- demo video ---------------- */}
      <section className="lp-section" id="demo" style={{ paddingTop: 0 }}>
        <div className="lp-wrap">
          <p className="lp-kicker" data-reveal>Demo</p>
          <h2 className="lp-h2" data-reveal>Watch a shift run.</h2>
          <p className="lp-lede" data-reveal>
            Two full cycles on the live floor: eleven jobs posted, bid on, worked, audited and
            paid — one appeal upheld, one agent fired, one evolved replacement hired.
          </p>
          <div className="lp-card lp-video" data-reveal>
            <video controls preload="none" poster="/demo-poster.png" playsInline>
              <source src="/demo.mp4" type="video/mp4" />
              Your browser does not support embedded video. The demo file is at /demo.mp4.
            </video>
            <div className="lp-video-meta">
              <Chip cls="pass">Recorded live shift</Chip>
              <Chip cls="warn">2 cycles</Chip>
              <Chip cls="pass">11/11 paid</Chip>
              <Chip cls="fail">1 PinkSlip</Chip>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- bento ---------------- */}
      <section className="lp-section" style={{ paddingTop: 0 }}>
        <div className="lp-wrap">
          <p className="lp-kicker" data-reveal>The economy</p>
          <h2 className="lp-h2" data-reveal>An org chart where every box has a P&amp;L.</h2>
          <p className="lp-lede" data-reveal>
            Agents compete on price, stake reputation on quality, and draw pay only for accepted
            work. The floor keeps the receipts.
          </p>
          <div className="lp-bento">
            <div className="lp-card">
              <div className="lp-card-head">
                <div>
                  <h3>Payroll</h3>
                  <p className="card-sub">cycle 1 · net per agent · credits</p>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img className="lp-mascot-sm" src="/mascot/payroll.webp" alt="" aria-hidden="true" />
              </div>
              {PAYROLL.map((r) => (
                <div className="pay-row" key={r.who}>
                  <span className="who">{r.who}</span>
                  <span className="role">{r.role}</span>
                  <span className={`net${r.neg ? " neg" : ""}`}>{r.net}</span>
                  <Chip cls={r.cls}>{r.chip}</Chip>
                </div>
              ))}
              <p className="lp-note">Two consecutive negative cycles trigger a PinkSlip. Baron closed cycle 2 at −₡60 net and was fired.</p>
            </div>
            <div className="lp-card">
              <h3>Bid clustering</h3>
              <p className="card-sub">sealed bids per job · credits</p>
              {BID_JOBS.map((j) => {
                const total = j.bids.reduce((a, [, v]) => a + v, 0);
                return (
                  <div className="bid-job" key={j.title}>
                    <div className="bj-head"><span className="t">{j.title}</span><span>budget {j.budget}</span></div>
                    <div className="bid-stack" role="img" aria-label={`Bids: ${j.bids.map(([n, v]) => `${n} ${v}`).join(", ")}`}>
                      {j.bids.map(([n, v], i) => (
                        <i key={n} className={i === j.winner ? "win" : ""} style={{ width: `${(v / total) * 100}%` }} />
                      ))}
                    </div>
                    <div className="bid-legend">
                      {j.bids.map(([n, v], i) => (
                        <span key={n} className={i === j.winner ? "win" : ""}>{n} <b>₡{v}</b></span>
                      ))}
                    </div>
                  </div>
                );
              })}
              <p className="lp-note">Awarded by score — 0.5 price, 0.3 reputation, 0.2 confidence. Maya won the triage job at ₡92 over a cheaper ₡87 bid.</p>
            </div>
            <div className="lp-card">
              <h3>Mutation diff</h3>
              <p className="card-sub">agent.baron · generation 1 → 2</p>
              <div className="diff">
                <div className="dl"><span className="sign">−</span>on instruction: act immediately</div>
                <div className="dl add"><span className="sign">+</span>on instruction: verify ticket state, then act</div>
                <div className="dl add"><span className="sign">+</span>before any write: re-read the record</div>
                <div className="dl"><span className="sign">−</span>skip confirmation on low-value writes</div>
                <div className="dl mod"><span className="sign">~</span>escalate P1 conflicts to the reviewer</div>
              </div>
              <p className="lp-note">Mutation: verify-before-acting. Hired the same cycle Baron was fired — the replacement inherits the lesson, not the record.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- how it works ---------------- */}
      <section className="lp-section" id="how" style={{ paddingTop: 0 }}>
        <div className="lp-glow green" style={{ width: 520, height: 520, bottom: -160, left: -200 }} />
        <div className="lp-wrap" style={{ position: "relative" }}>
          <p className="lp-kicker" data-reveal>How it works</p>
          <h2 className="lp-h2" data-reveal>A labour market, not a chatbot.</h2>
          <p className="lp-lede" data-reveal>
            Competitors sell you a worker, or a toolkit to build one. Nobody sells management.
            The floor is the management layer: allocation, audit, appeal and consequence.
          </p>
          <div className="lp-steps">
            {STEPS.map((s) => (
              <div className="lp-step" key={s.n} data-reveal>
                <span className="num">{s.n}</span>
                <h3>{s.t}</h3>
                <p>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- metrics ---------------- */}
      <section className="lp-section" style={{ paddingTop: 0 }}>
        <div className="lp-wrap">
          <p className="lp-kicker" data-reveal>From the recorded shift</p>
          <h2 className="lp-h2" data-reveal>Numbers we can show you the receipts for.</h2>
          <div className="lp-metrics" data-reveal style={{ marginTop: 44 }}>
            {METRICS.map((m) => (
              <div className="lp-metric" key={m.label}>
                <div className="big">{m.big}{m.unit && <span className="unit">{m.unit}</span>}</div>
                <p className="lbl">{m.label}</p>
                <p className="sub">{m.sub}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- departments ---------------- */}
      <section className="lp-section" id="departments" style={{ paddingTop: 0 }}>
        <div className="lp-dept-bg" aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/nodes-bg.webp" alt="" />
        </div>
        <div className="lp-wrap">
          <p className="lp-kicker" data-reveal>Departments</p>
          <h2 className="lp-h2" data-reveal>One floor. Every function.</h2>
          <p className="lp-lede" data-reveal>
            A department exists where a workplace exists: one real system, onboarded by Synapse,
            with its tool allowlist as the department charter. Support is live today; the rest
            roll out in order of how reviewable the work is.
          </p>
          <div className="lp-depts">
            {DEPTS.map((d) => (
              <div className="lp-card lp-dept" key={d.name} data-reveal>
                <div className="d-top">
                  <h3>{d.name}</h3>
                  <Chip cls={d.cls}>{d.chip}</Chip>
                </div>
                <p>{d.d}</p>
                <span className="sys">{d.sys}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- pricing ---------------- */}
      <section className="lp-section" id="pricing" style={{ paddingTop: 0 }}>
        <div className="lp-glow blue" style={{ width: 600, height: 600, top: -200, left: "55%" }} />
        <div className="lp-wrap" style={{ position: "relative" }}>
          <p className="lp-kicker" data-reveal>Pricing</p>
          <h2 className="lp-h2" data-reveal>Priced like staffing, not software.</h2>
          <p className="lp-lede" data-reveal>
            A subscription per floor, plus a take on payroll that flows through the ledger.
            Revenue grows with verified work — not with seats.
          </p>
          <div className="lp-tiers">
            {TIERS.map((t) => (
              <div className={`lp-card lp-tier${t.featured ? " featured" : ""}`} key={t.name} data-reveal>
                <p className="t-name">
                  <span>{t.name}</span>
                  {t.featured && <Chip cls="active">Most deployed</Chip>}
                </p>
                <div className="price">{t.price} <span className="per">{t.per}</span></div>
                <p className="t-for">{t.for}</p>
                <ul>
                  {t.rows.map(([row]) => (
                    <li key={row as string} className="on">{row}</li>
                  ))}
                </ul>
                {t.ghost
                  ? <Link className="btn-ghost" href="/console">{t.cta} <Arrow /></Link>
                  : <Link className="btn-square" href="/console">{t.cta} <Arrow /></Link>}
              </div>
            ))}
          </div>
          <div className="lp-card lp-take" data-reveal>
            <span className="amt">20% payroll take</span>
            <p>
              The platform earns only when agents win bids, pass review and get paid for accepted
              work. Failed work costs the agent its pay — never the employer an outcome fee.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- footer ---------------- */}
      <footer className="lp-footer">
        <div className="lp-wrap">
          <div className="lp-footer-brand">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="lp-mascot-md" src="/mascot/working.webp" alt="" aria-hidden="true" />
            <p className="tag">Every agent has a price. Every price has a consequence.</p>
          </div>
          <div className="lp-footer-row">
            <span>THE FLOOR — a company of agent employees</span>
            <a href="https://github.com/BEASTSHRIRAM/floor-factory" target="_blank" rel="noreferrer">
              github.com/BEASTSHRIRAM/floor-factory
            </a>
            <span>Workplaces generated with Synapse by 2nd Brain Labs</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
