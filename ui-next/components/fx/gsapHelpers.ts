/**
 * gsapHelpers — small, typed GSAP helpers for THE FLOOR's card moments.
 *
 * Plain functions taking an HTMLElement; no React coupling. Every helper
 * is reduced-motion aware: with prefers-reduced-motion, no tween runs —
 * the element is placed directly in its final state (or left untouched
 * for countUp, which just sets the final number).
 *
 * Signatures:
 *   animateFiredCard(el)            -> Timeline | null
 *   animateHiredCard(el)            -> Timeline | null
 *   countUp(el, to, {duration, format}) -> Tween | null
 */
import gsap from "gsap";

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Firing moment: a short shake, a stamp-like scale slam, then the card
 * sinks, tilts and desaturates into its graveyard state.
 */
export function animateFiredCard(el: HTMLElement): gsap.core.Timeline | null {
  if (typeof window === "undefined" || !el) return null;
  gsap.killTweensOf(el);
  if (prefersReducedMotion()) {
    gsap.set(el, { opacity: 0.62, rotate: -1.5, y: 8, filter: "grayscale(0.65)" });
    return null;
  }
  const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
  tl.to(el, { x: -5, duration: 0.05, repeat: 5, yoyo: true, ease: "power1.inOut" })
    .set(el, { x: 0 })
    .fromTo(
      el,
      { scale: 1.045 },
      { scale: 1, duration: 0.16, ease: "power4.in" },
      "stamp",
    )
    .to(
      el,
      {
        y: 10,
        rotate: -1.8,
        opacity: 0.62,
        filter: "grayscale(0.65)",
        duration: 0.55,
        ease: "power2.inOut",
      },
      "stamp+=0.08",
    );
  return tl;
}

/**
 * New-hire moment: the replacement card drops in from above with a
 * soft overshoot and a one-shot accent glow that fades away.
 */
export function animateHiredCard(el: HTMLElement): gsap.core.Timeline | null {
  if (typeof window === "undefined" || !el) return null;
  gsap.killTweensOf(el);
  if (prefersReducedMotion()) {
    gsap.set(el, { clearProps: "transform,opacity,boxShadow" });
    return null;
  }
  const tl = gsap.timeline({ defaults: { ease: "back.out(1.6)" } });
  tl.fromTo(
    el,
    { y: -16, scale: 0.92, opacity: 0 },
    { y: 0, scale: 1, opacity: 1, duration: 0.5 },
  ).fromTo(
    el,
    { boxShadow: "0 0 0 rgba(56, 225, 198, 0.0)" },
    {
      boxShadow: "0 0 22px rgba(56, 225, 198, 0.45)",
      duration: 0.22,
      yoyo: true,
      repeat: 1,
      ease: "power1.inOut",
    },
    "-=0.15",
  );
  return tl;
}

export interface CountUpOptions {
  /** Seconds. Default 0.9. */
  duration?: number;
  /** Starting value. Default: the number currently in the element, else 0. */
  from?: number;
  /** Formatter for each frame. Default: locale-grouped integer. */
  format?: (value: number) => string;
}

const defaultFormat = (v: number) => Math.round(v).toLocaleString("en-US");

/**
 * Animate an element's text content from its current number up (or
 * down) to `to`. Sets textContent only — safe for balances and totals.
 */
export function countUp(
  el: HTMLElement,
  to: number,
  opts: CountUpOptions = {},
): gsap.core.Tween | null {
  if (typeof window === "undefined" || !el) return null;
  const format = opts.format ?? defaultFormat;
  if (prefersReducedMotion()) {
    el.textContent = format(to);
    return null;
  }
  const parsed = Number((el.textContent || "").replace(/[^0-9.-]/g, ""));
  const state = { v: opts.from ?? (Number.isFinite(parsed) ? parsed : 0) };
  el.textContent = format(state.v);
  return gsap.to(state, {
    v: to,
    duration: opts.duration ?? 0.9,
    ease: "power2.out",
    overwrite: true,
    onUpdate: () => {
      el.textContent = format(state.v);
    },
    onComplete: () => {
      el.textContent = format(to);
    },
  });
}
