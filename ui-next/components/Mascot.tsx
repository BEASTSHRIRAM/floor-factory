"use client";

/* The Foreman as a living avatar: one component, a pose + motion
 * state machine over the four approved WebP poses. The state is not
 * decoration — in the console it is driven by the live event stream
 * (see FloorClient): work in flight reads `working`, a payment.made
 * event flashes `paid`, an agent.fired event flashes `pinkslip`, an
 * active auto run reads `auto`, everything else settles to `idle`.
 * Motion is pure CSS transforms on the raster poses with an opacity
 * crossfade on pose swap (keyframes in app/globals.css, loaded on
 * every surface); prefers-reduced-motion collapses it to the static
 * pose. No new imagery is generated. */

import { useState } from "react";

export type MascotState = "idle" | "working" | "paid" | "pinkslip" | "auto";

const POSE_SRCS = [
  "/mascot/foreman.webp",
  "/mascot/working.webp",
  "/mascot/payroll.webp",
  "/mascot/pinkslip.webp",
] as const;

const POSE_FOR: Record<MascotState, string> = {
  idle: "/mascot/foreman.webp",
  working: "/mascot/working.webp",
  paid: "/mascot/payroll.webp",
  pinkslip: "/mascot/pinkslip.webp",
  auto: "/mascot/working.webp",
};

const STATE_LABEL: Record<MascotState, string> = {
  idle: "The Foreman — the floor is idle",
  working: "The Foreman — work in progress on the floor",
  paid: "The Foreman — a payment just landed",
  pinkslip: "The Foreman — a PinkSlip was just issued",
  auto: "The Foreman — auto run active, the floor is running itself",
};

export default function Mascot({
  state,
  size = 36,
  hoverable = false,
  className = "",
  label,
}: {
  state: MascotState;
  size?: number;
  /** Landing hero: hovering swaps to the Foreman thumbs-up pose with a bounce. */
  hoverable?: boolean;
  className?: string;
  label?: string;
}) {
  const [hovered, setHovered] = useState(false);
  const activeSrc = hoverable && hovered ? POSE_FOR.idle : POSE_FOR[state];
  const decorative = label === "";
  const text = label ?? STATE_LABEL[state];
  return (
    <span
      className={`mascot mascot--${state}${hoverable && hovered ? " mascot--hover" : ""} ${className}`}
      style={{ width: size, height: size }}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : text}
      aria-hidden={decorative || undefined}
      title={decorative ? undefined : text}
      onMouseEnter={hoverable ? () => setHovered(true) : undefined}
      onMouseLeave={hoverable ? () => setHovered(false) : undefined}
    >
      <span className="mascot-float">
        <span className="mascot-stack">
          {POSE_SRCS.map((src) => (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              key={src}
              src={src}
              alt=""
              aria-hidden="true"
              draggable={false}
              className={src === activeSrc ? "is-active" : undefined}
            />
          ))}
        </span>
      </span>
      {state === "auto" && <span className="mascot-auto-dot" aria-hidden="true" />}
    </span>
  );
}
