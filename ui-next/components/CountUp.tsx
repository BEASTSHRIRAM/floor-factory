"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";

/** Number that tweens to its new value with GSAP; jumps instantly when the
 *  user prefers reduced motion. */
export default function CountUp({
  value,
  format,
}: {
  value: number;
  format: (n: number) => string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      shown.current = value;
      el.textContent = format(value);
      return;
    }
    const obj = { v: shown.current };
    const tween = gsap.to(obj, {
      v: value,
      duration: 0.9,
      ease: "power2.out",
      overwrite: true,
      onUpdate: () => {
        shown.current = obj.v;
        if (ref.current) ref.current.textContent = format(Math.round(obj.v));
      },
      onComplete: () => {
        shown.current = value;
        if (ref.current) ref.current.textContent = format(value);
      },
    });
    return () => {
      tween.kill();
    };
    // format is stable (module-level formatters); value drives the tween.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <span ref={ref}>{format(value)}</span>;
}
