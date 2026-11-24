# Third-party attribution

## agent-orchestrator (OrchestratorInc) — Apache License 2.0

THE FLOOR's console (`/console`) is built on the frontend of
[agent-orchestrator](https://github.com/OrchestratorInc/agent-orchestrator):

- `vendor/ao/product-ui/` — their portable presentation package
  `@aoagents/product-ui` (SessionsBoardView, SessionCardView,
  SessionInspectorView, AgentAvatar, icons, session models and
  presentation helpers), copied verbatim except for removed test files.
- `vendor/ao/button.tsx` — their renderer Button component; the only
  edit is the `cn` import path, repointed at the vendored product-ui
  utils.
- `app/console/ao.css` — their design tokens
  (`frontend/src/styles/tokens.css`, dark `:root` block only) and the
  Tailwind `@theme` bridge, custom utilities and keyframes from
  `frontend/src/renderer/styles.css`, plus `components/ui/button.css`.
  Their light theme was not imported: this console is dark only. A
  clearly-marked "CLAUDE RECOLOUR" block at the end of the file
  re-points their palette tokens at the Claude design system
  (`DESIGN.md`); no token names or component CSS were changed.
- `vendor/ao/LICENSE` — the Apache License 2.0 text as shipped in
  their repository.

Floor-specific code (the state engine, the data adapter in
`components/ao/adapter.ts`, the payroll statement, the recorded-demo
replay) is original to THE FLOOR and lives outside `vendor/ao/`.

## Claude design system (Anthropic)

`DESIGN.md` in this directory is the Claude design-system analysis
fetched with `npx getdesign@latest add claude`. It is the console's
design source of truth for colour and type voice; the dark
translation applied in `ao.css` is documented in
`~/workspace/vibeathon-floor/console_v3_report.md` (repo-external
build report).
