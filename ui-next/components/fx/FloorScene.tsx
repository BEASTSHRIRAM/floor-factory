"use client";

/**
 * FloorScene — THE FLOOR's ambient floor strip.
 *
 * Deliberately NOT a WebGL scene: this is a plain Canvas 2D render
 * (zero extra bundle, no three.js) drawn as a pseudo-3D floor — a
 * perspective grid with one glowing pod per agent. Performance and
 * smooth demo playback win over visual flash; the strip is ambience,
 * never the centrepiece.
 *
 * - One pod per agent, in roster order (labels live in the org chart;
 *   the canvas carries no text, by design).
 * - Colour by status: active/idle = teal-blue, bidding = amber pulse,
 *   working/in-review = pink pulse, fired = red, sunk below the floor
 *   line and tilted.
 * - Pod orb radius scales gently with reputation (0..100).
 * - Idle bobbing via a single rAF loop; DPR capped at 1.5.
 * - prefers-reduced-motion: one static frame, no loop.
 * - SSR-safe: renders an empty <canvas> on the server / first paint;
 *   all drawing happens in effects. The app dynamic-imports this with
 *   ssr:false anyway.
 *
 * Contract: FloorScene({ agents }) — Agent from lib/types.
 */
import { useEffect, useRef } from "react";
import type { Agent } from "../../lib/types";

interface PodPalette {
  core: string;
  glow: string;
  plinth: string;
}

const PALETTES: Record<string, PodPalette> = {
  active: { core: "#38e1c6", glow: "rgba(45, 190, 200, 0.55)", plinth: "#1d3a4a" },
  bidding: { core: "#fbbf24", glow: "rgba(251, 191, 36, 0.55)", plinth: "#4a3a1d" },
  working: { core: "#f472b6", glow: "rgba(236, 114, 171, 0.55)", plinth: "#4a1d38" },
  fired: { core: "#ef4444", glow: "rgba(239, 68, 68, 0.35)", plinth: "#3a1d1d" },
};

function paletteFor(status: string): { pal: PodPalette; pulse: boolean } {
  const s = (status || "idle").toLowerCase();
  if (s === "fired" || s === "terminated") return { pal: PALETTES.fired, pulse: false };
  if (s.includes("bid")) return { pal: PALETTES.bidding, pulse: true };
  if (s.includes("work") || s.includes("review") || s.includes("execut"))
    return { pal: PALETTES.working, pulse: true };
  return { pal: PALETTES.active, pulse: false };
}

interface PodLayout {
  x: number; // floor-plane coords, roughly -1..1 across
  z: number; // depth row, 0 = front
  agent: Agent;
  phase: number;
}

/** Lay pods on a shallow grid: front row first, up to a few rows deep. */
function layoutPods(agents: Agent[]): PodLayout[] {
  const n = agents.length;
  if (n === 0) return [];
  const cols = n <= 3 ? n : n <= 8 ? 4 : Math.ceil(Math.sqrt(n * 1.8));
  return agents.map((agent, i) => {
    const row = Math.floor(i / cols);
    const col = i % cols;
    const inRow = Math.min(cols, n - row * cols);
    const x = inRow === 1 ? 0 : -0.82 + (1.64 * col) / (inRow - 1);
    return { x, z: row, agent, phase: (i * 1.37) % (Math.PI * 2) };
  });
}

function drawScene(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  pods: PodLayout[],
  t: number, // seconds; 0 for the static frame
) {
  ctx.clearRect(0, 0, w, h);

  // Backdrop: deep floor gradient.
  const bg = ctx.createLinearGradient(0, 0, 0, h);
  bg.addColorStop(0, "#070b14");
  bg.addColorStop(0.55, "#0a101d");
  bg.addColorStop(1, "#0d1524");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  const horizon = h * 0.3;
  const floorH = h - horizon;
  const cx = w / 2;
  // Perspective projection: world (x in -1..1, z depth 0..1) -> screen.
  const project = (x: number, z: number) => {
    const persp = 1 / (1 + z * 0.9);
    return {
      x: cx + x * w * 0.46 * persp + x * w * 0.1 * (1 - persp),
      y: horizon + floorH * (1 - persp) + floorH * 0.16 * persp,
      s: persp,
    };
  };

  // Floor grid: converging verticals + receding horizontals.
  ctx.lineWidth = 1;
  for (let i = -6; i <= 6; i++) {
    const top = project(i / 6, 1);
    ctx.strokeStyle = "rgba(80, 140, 190, 0.10)";
    ctx.beginPath();
    ctx.moveTo(top.x, horizon);
    ctx.lineTo(top.x + (top.x - cx) * 0.4, h + 4);
    ctx.stroke();
  }
  for (let j = 0; j <= 5; j++) {
    const z = j / 5;
    const l = project(-1, z);
    const r = project(1, z);
    ctx.strokeStyle = `rgba(80, 140, 190, ${0.05 + 0.09 * (1 - z)})`;
    ctx.beginPath();
    ctx.moveTo(l.x - w * 0.06, l.y);
    ctx.lineTo(r.x + w * 0.06, r.y);
    ctx.stroke();
  }
  // Horizon glow line.
  const hg = ctx.createLinearGradient(0, 0, w, 0);
  hg.addColorStop(0, "rgba(56,225,198,0)");
  hg.addColorStop(0.5, "rgba(56,225,198,0.28)");
  hg.addColorStop(1, "rgba(56,225,198,0)");
  ctx.fillStyle = hg;
  ctx.fillRect(0, horizon - 0.5, w, 1);

  // Pods, back rows first so front pods overlap correctly.
  const sorted = [...pods].sort((a, b) => b.z - a.z);
  for (const pod of sorted) {
    const { pal, pulse } = paletteFor(pod.agent.status);
    const fired = pal === PALETTES.fired;
    const base = project(pod.x, pod.z * 0.42);
    const repScale =
      0.82 + (Math.max(0, Math.min(100, pod.agent.reputation || 0)) / 100) * 0.36;
    const R = 15 * base.s * repScale + 5;
    const bob = fired ? 0 : Math.sin(t * 1.4 + pod.phase) * 2.2 * base.s;
    const sink = fired ? R * 0.85 : 0;
    const orbY = base.y - R * 1.55 + bob + sink;
    const orbX = base.x + (fired ? R * 0.18 : 0);

    // Pulse ring for bidding / working.
    if (pulse) {
      const pr = R * (1.25 + 0.35 * (0.5 + 0.5 * Math.sin(t * 2.6 + pod.phase)));
      ctx.strokeStyle = pal.glow;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.ellipse(base.x, base.y - R * 0.32, pr, pr * 0.3, 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Ground shadow.
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.beginPath();
    ctx.ellipse(base.x, base.y, R * 1.05, R * 0.3, 0, 0, Math.PI * 2);
    ctx.fill();

    // Plinth (a low cylinder: side + top ellipse). Fired plinths sit lower.
    const plinthTop = base.y - R * 0.34 + (fired ? R * 0.5 : 0);
    ctx.fillStyle = pal.plinth;
    ctx.beginPath();
    ctx.ellipse(base.x, plinthTop, R * 0.92, R * 0.28, 0, 0, Math.PI);
    ctx.lineTo(base.x - R * 0.92, plinthTop - R * 0.22);
    ctx.ellipse(base.x, plinthTop - R * 0.22, R * 0.92, R * 0.28, 0, Math.PI, 0, true);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "rgba(140, 190, 230, 0.16)";
    ctx.beginPath();
    ctx.ellipse(base.x, plinthTop - R * 0.22, R * 0.92, R * 0.28, 0, 0, Math.PI * 2);
    ctx.fill();

    // Orb: radial-gradient sphere with a soft outer glow. Fired orbs are
    // tilted (squashed, rotated ellipse) and dimmed.
    ctx.save();
    ctx.shadowColor = pal.glow;
    ctx.shadowBlur = fired ? 6 : 16 * base.s;
    const grad = ctx.createRadialGradient(orbX - R * 0.35, orbY - R * 0.4, R * 0.1, orbX, orbY, R);
    grad.addColorStop(0, "#ffffff");
    grad.addColorStop(0.25, pal.core);
    grad.addColorStop(1, "rgba(6,10,18,0.92)");
    ctx.fillStyle = grad;
    ctx.globalAlpha = fired ? 0.72 : 0.96;
    ctx.beginPath();
    if (fired) {
      ctx.ellipse(orbX, orbY, R, R * 0.74, -0.38, 0, Math.PI * 2);
    } else {
      ctx.arc(orbX, orbY, R, 0, Math.PI * 2);
    }
    ctx.fill();
    ctx.restore();

    // Generation pips under the plinth for gen >= 2.
    const gen = Math.max(1, Math.floor(pod.agent.generation || 1));
    if (gen > 1) {
      ctx.fillStyle = "rgba(230, 240, 255, 0.55)";
      const pips = Math.min(gen - 1, 4);
      for (let p = 0; p < pips; p++) {
        ctx.beginPath();
        ctx.arc(base.x + (p - (pips - 1) / 2) * 6, base.y + R * 0.42, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  if (pods.length === 0) {
    ctx.fillStyle = "rgba(150, 175, 205, 0.35)";
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("THE FLOOR — awaiting roster", cx, horizon + floorH * 0.55);
  }
}

export default function FloorScene({ agents }: { agents: Agent[] }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const agentsRef = useRef<Agent[]>(agents);
  agentsRef.current = agents;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    let raf = 0;
    let stopped = false;

    const render = (tSec: number) => {
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width));
      const h = Math.max(1, Math.round(rect.height));
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawScene(ctx, w, h, layoutPods(agentsRef.current), tSec);
    };

    if (reduced) {
      render(0);
      const onResize = () => render(0);
      window.addEventListener("resize", onResize);
      return () => window.removeEventListener("resize", onResize);
    }

    const loop = (ms: number) => {
      if (stopped) return;
      render(ms / 1000);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
    };
  }, []);

  const fired = agents.filter((a) => (a.status || "").toLowerCase() === "fired").length;
  return (
    <canvas
      ref={canvasRef}
      className="floor-scene-canvas"
      style={{ display: "block", width: "100%", height: "100%" }}
      role="img"
      aria-label={`Factory floor: ${agents.length} agents on shift${fired ? `, ${fired} fired` : ""}`}
    />
  );
}
