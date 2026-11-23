# THE FLOOR — Mission Control (Next.js)

The Next.js + React rebuild of THE FLOOR's mission-control UI. The original
vanilla UI in [`../ui/`](../ui/) is untouched and remains the **fallback**:
it has zero dependencies and can be served by the factory API as-is. This
app is the richer front-end — same API, same panels, plus GSAP motion,
Lottie badges, and a lightweight 3D floor strip.

## Run

```bash
cd ui-next
npm install
npm run dev        # http://localhost:3000
# or
npm run build && npm run start   # production, port 3000
```

The factory API must be running separately (default
`http://localhost:8000`). Point the UI at another API base with:

```bash
NEXT_PUBLIC_FLOOR_API=http://localhost:8000 npm run dev
```

## Stack

- **Next.js (App Router) + React + TypeScript** — a single client page;
  all data comes from the factory API (REST snapshots + SSE `/events`),
  exactly like the vanilla UI. Parsing is shape-tolerant (`lib/api.ts`):
  unknown shapes render empty, never crash.
- **GSAP + @gsap/react** — entrance animations, header number count-ups,
  the bid ticker, and card state transitions (fired shake, hired drop-in).
  Transform/opacity only, and everything is skipped or shortened under
  `prefers-reduced-motion`.
- **FX layer** (`components/fx/`, built by the FX agent):
  - `FloorScene` — a React Three Fiber **lightweight strip** under the
    header. Deliberately subtle: no post-processing, capped DPR, kept
    short so demo playback stays at a smooth 60fps. It is a garnish,
    not the centrepiece.
  - `LottieBadge` — small Lottie status badges (payroll / fired / hired /
    empty), animations in `public/lottie/`.
  - Until the FX agent lands, `components/fx/` contains minimal stubs
    with the same props interface so the app builds standalone.

## Layout

Header (cycle, paid out, jobs done/failed, active agents, connection,
Run Shift / Reset) → 3D floor strip → three panels: Org Chart (management
row, worker cards, Graveyard), Job Board (five status columns + bid
ticker), Ledger + Narration feeds. Cycle close opens the payroll overlay
as a native `<dialog>`.

Dark trading-floor theme, full width with a slim gutter, legible
secondary text — same design tokens as the vanilla UI.
