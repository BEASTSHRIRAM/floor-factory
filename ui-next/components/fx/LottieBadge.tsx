"use client";

/**
 * LottieBadge — small animated badge for payroll / fired / hired / empty
 * moments in the org chart and payroll dialog.
 *
 * Uses lottie-react with LOCAL, hand-authored JSON assets served from
 * public/lottie/ (no remote Lottie URLs, no external files):
 *   payroll.json — three gold coins rise and pop inside a teal ring burst
 *   fired.json   — a red stamp slams in with an X
 *   hired.json   — a teal plus pops with pink/gold sparkles
 *   empty.json   — three idle dots pulsing in sequence (loops)
 *
 * The JSON is fetched once per kind (module-level cache) and parsed by
 * lottie-web. While loading — or if the fetch ever fails — a static
 * glyph fallback renders at the same size so layout never jumps.
 * prefers-reduced-motion: the animation is parked on a representative
 * late frame instead of playing.
 *
 * Contract: LottieBadge({ kind, size = 40 }).
 */
import { useEffect, useRef, useState } from "react";
import Lottie, { type LottieRefCurrentProps } from "lottie-react";

export type LottieBadgeKind = "payroll" | "fired" | "hired" | "empty";

const GLYPH_FALLBACK: Record<LottieBadgeKind, string> = {
  payroll: "₡",
  fired: "✕",
  hired: "★",
  empty: "·",
};

const cache = new Map<LottieBadgeKind, object>();

async function loadBadge(kind: LottieBadgeKind): Promise<object> {
  const hit = cache.get(kind);
  if (hit) return hit;
  const res = await fetch(`/lottie/${kind}.json`);
  if (!res.ok) throw new Error(`lottie ${kind}: ${res.status}`);
  const data = (await res.json()) as object;
  cache.set(kind, data);
  return data;
}

export default function LottieBadge({
  kind,
  size = 40,
}: {
  kind: LottieBadgeKind;
  size?: number;
}) {
  const [data, setData] = useState<object | null>(() => cache.get(kind) ?? null);
  const [failed, setFailed] = useState(false);
  const lottieRef = useRef<LottieRefCurrentProps | null>(null);

  useEffect(() => {
    let alive = true;
    const cached = cache.get(kind);
    if (cached) {
      setData(cached);
      return;
    }
    loadBadge(kind)
      .then((d) => {
        if (alive) setData(d);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [kind]);

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!data || failed) {
    return (
      <span
        className={`lottie-badge lottie-badge-fallback lottie-badge-${kind}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: size,
          height: size,
          fontSize: Math.round(size * 0.5),
          lineHeight: 1,
          flex: "none",
        }}
        aria-hidden="true"
      >
        {GLYPH_FALLBACK[kind]}
      </span>
    );
  }

  const totalFrames = (data as { op?: number }).op ?? 60;
  return (
    <span
      className={`lottie-badge lottie-badge-${kind}`}
      style={{ display: "inline-block", width: size, height: size, flex: "none" }}
      aria-hidden="true"
    >
      <Lottie
        lottieRef={lottieRef}
        animationData={data}
        autoplay={!reduced}
        loop={kind === "empty"}
        style={{ width: size, height: size }}
        onDOMLoaded={() => {
          if (reduced) lottieRef.current?.goToAndStop(Math.floor(totalFrames * 0.75), true);
        }}
      />
    </span>
  );
}
