"use client";

import type { Agent, PresenceState } from "../lib/types";
import { isFired } from "../lib/api";

/* Agent avatar: a little employee tile. Monogram initials on a tinted
   rounded square — the tint is identity (hashed from the name, stable
   per agent), never status. Status lives on the presence dot in the
   tile's corner and nowhere else on the tile. Fired agents desaturate. */

const TINTS: { bg: string; fg: string }[] = [
  { bg: "rgba(99,102,241,.20)", fg: "#A5B4FC" },
  { bg: "rgba(34,211,238,.14)", fg: "#67E8F9" },
  { bg: "rgba(34,197,94,.14)", fg: "#86EFAC" },
  { bg: "rgba(245,158,11,.15)", fg: "#FCD34D" },
  { bg: "rgba(148,163,184,.16)", fg: "#CBD5E1" },
  { bg: "rgba(129,140,248,.16)", fg: "#C7D2FE" },
];

function tintFor(name: string): { bg: string; fg: string } {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return TINTS[h % TINTS.length];
}

function monogram(name: string): string {
  const parts = name.replace(/[^A-Za-z0-9. ]/g, "").split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1].replace(".", "")[0]).toUpperCase();
}

export default function Avatar({
  agent,
  presence,
  size = 30,
}: {
  agent: Agent;
  presence?: PresenceState;
  size?: number;
}) {
  const tint = tintFor(agent.name);
  const fired = isFired(agent);
  const st = fired ? "fired" : presence ?? "idle";
  const dot = Math.max(8, Math.round(size * 0.3));
  return (
    <span
      className={`avatar${fired ? " fired" : ""}`}
      style={{ width: size, height: size, background: tint.bg, color: tint.fg }}
      aria-hidden="true"
    >
      <span className="avatar-mono" style={{ fontSize: Math.round(size * 0.36) }}>
        {monogram(agent.name)}
      </span>
      <span
        className={`av-dot ${st}`}
        style={{ width: dot, height: dot }}
        title={st}
      />
    </span>
  );
}
