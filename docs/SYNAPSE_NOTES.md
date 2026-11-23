# SYNAPSE_NOTES.md — Synapse CLI research for Vibe-a-thon (THE FLOOR build)

Researched 2026-11-19. Every factual claim cites its source inline. Anything the sources
do not state is marked **NOT FOUND IN SOURCES** — do not treat those gaps as filled.

**Sources used**
- **[GUIDE]** Vibe-a-thon Participant Guide (local file: `~/workspace/vibeathon/Vibe-a-thon-Participant-Guide.pdf`)
- **[README]** Synapse CLI GitHub README — https://github.com/2ndbrainlabs-ai/synapse-cli-ts
- **[DOCS]** Synapse getting-started docs — https://synapse.2ndbrainlabs.ai/docs
- **[PRODUCT]** 2nd Brain Labs Synapse product page — https://2ndbrainlabs.ai/synapse
- **[ORG]** Public repo list of the GitHub org — https://github.com/orgs/2ndbrainlabs-ai/repositories
- **[ISSUES]** CLI issue tracker — https://github.com/2ndbrainlabs-ai/synapse-cli-ts/issues

> ⚠️ **READ FIRST — the sources disagree with each other in places.**
> The DOCS site still documents the older (v1-style) flow (`synapse analyze` →
> `synapse build --query … --output mcp_server.py`). The README states the **v1 engine
> was removed; v2 is the only engine**, and v1-only flags (`-o/--output`, `--no-validate`,
> `--no-docs`, `-g/--generate`) now **stop the build with an error** [README]. The GUIDE's
> cheat sheet matches the v2 README. **Treat the README + GUIDE as authoritative; treat
> DOCS command examples with suspicion.** Specific conflicts are flagged per-section below.

---

## 1. Getting started, verified

### Install

```bash
npm install -g @2ndbrainlabs-ai/synapse-cli
synapse --version        # verify
```

- This exact install command appears in all three sources [GUIDE] [README] [DOCS].
- No-install alternative: `npx @2ndbrainlabs-ai/synapse-cli init` — npx fetches and runs
  the CLI on demand; every later command then needs the `npx @2ndbrainlabs-ai/synapse-cli`
  prefix, with a slower cold start each time [DOCS].
- `synapse update` updates the CLI to the latest npm release [README].

### Node version requirement — SOURCES CONFLICT

- GUIDE: "You need **Node.js 20 or later**" [GUIDE].
- README: "Requires **Node.js 20+**" [README].
- DOCS: "Requirements: **Node.js 18 or higher**" [DOCS].
- **Recommendation: install Node 20+** (two of three sources, including the README and the
  hackathon guide, require it; the README also notes Amazon Bedrock local mode requires
  Node 20+ [README]).

### Getting a Synapse API key (console)

From DOCS ("How to get your Synapse API Key") [DOCS]:

1. Go to the **Console** page (top-right of the navbar after logging in at
   https://synapse.2ndbrainlabs.ai — listed as the Console URL in [README]'s endpoints table).
2. Click **API Keys** in the left sidebar.
3. Click **Create API Key**, give it a name, and confirm.
4. **Copy the key immediately — it is shown only once and cannot be retrieved later.**
5. Store it (see below).

README adds: "Before running `synapse init`, generate your Synapse API key by following
the docs" [README]. GUIDE: "Get a Synapse API key from the Synapse console, following the
configuration docs. Skip this step if you only plan to build with `--local`" [GUIDE].

Key storage options [DOCS] [README]:

```bash
# Option A — store globally via CLI (recommended by DOCS)
synapse config --global --key <YOUR_API_KEY>

# Option B — environment variable (highest precedence)
export SYNAPSE_API_KEY=<YOUR_API_KEY>

# Verify what is saved / in use
synapse config
```

- **Precedence:** `SYNAPSE_API_KEY` env var (highest) → project key in
  `.synapse/config.json` → global key in `~/.synapse/config.json` [DOCS] [README].
- Keys are encrypted at rest using Fernet symmetric encryption with a machine-derived
  key; `synapse config` shows only the first 5 characters + asterisks [DOCS] [README].
- `synapse config set-key` checks the key with the backend **before** saving it; a key the
  backend rejects is not saved. Run it with no argument to type the key at a masked prompt
  (keeps it out of shell history) [README].
- Keys are Ed25519 envelope keys, per-request quota, revocation in under 30 seconds
  [README]. Rotate via: create new key in console → `synapse config set-key` →
  `synapse config keys` → `synapse config revoke <old id>` [README].

### `synapse init` — what it does / asks

```bash
cd my-project
synapse init            # one-time: paste your API key
synapse init --force    # reinitialize an existing project (overwrites config)
```

- README quick start: "`synapse init` — one-time: **paste your API key**" [README].
- DOCS: run it inside the project directory; it creates a `.synapse/` configuration folder
  and securely stores your API key, producing `.synapse/config.json` in the project root
  [DOCS].
- README command table: init "Uses the key from `SYNAPSE_API_KEY`, the project or
  `~/.synapse` (or prompts for one) and **checks it with the backend**" [README]. So if a
  key is already available via env/config, init may not prompt at all.
- `synapse init` is **not required for `--local` builds** [README] [GUIDE].

### First build

```bash
synapse build           # scans the code, then asks: Auto or Custom?
```

- Without `--auto`/`--custom`, the picker defaults to Auto [README].
- After the build, Synapse prints a JSON snippet — copy it into your MCP client config
  (see §6) [README] [GUIDE].

---

## 2. Auto vs Custom mode in practice

Both modes run on the **v2 engine**. The CLI detects the project language and extracts
its surface locally with tree-sitter; generation runs on the Synapse backend (hosted) or
on your own model (`--local`) [README].

| | **Auto** (`--auto`) | **Custom** (`--custom`) |
|---|---|---|
| What it does | Finds your HTTP routes and exposes the ones you pick as MCP tools that call your deployed API | Composes internal functions you pick (or describe with `--query`) into **one** MCP tool |
| Languages it reads | 6: Python, TypeScript (`.ts`, `.tsx`), Java, C#, Go, Rust | **Python only** |
| Hosted output | **No file written.** Endpoint config is saved to your Synapse account and served by the `@2ndbrainlabs-ai/synapse-mcp` runner via `npx` | A Python file, `<tool_name>_server.py`, in the project root |
| `--local` output | A Python file, `synapse_auto_server.py`. **Python projects only**; for other languages `--local --smart-names` names the tools but writes **no file** | A Python file, `<tool_name>_server.py`. Python projects only |

Source: the mode table in [README]; the same table appears (garbled) in [GUIDE].

Hard rules that apply to both modes [README]:

- **Every generated server file is Python.** The CLI never generates TypeScript or
  JavaScript servers.
- **Plain JavaScript files (`.js`, `.jsx`) are not scanned at all.**
- Language detection: a marker file at the project root (`pyproject.toml`,
  `requirements.txt`, `tsconfig.json`, `pom.xml`, `go.mod`, `Cargo.toml`, …) decides the
  language; otherwise the most common source extension wins.
- `--smart-names` (Auto only) reads each selected handler's source plus your README to
  produce better tool names/descriptions. GUIDE: "Agents pick the right tool more often
  with good names" [GUIDE].
- Auto mode endpoint selection without a terminal (CI, pipes, `--yes`): either flag
  implies `--auto` [README]:
  ```bash
  synapse build --auto --all-endpoints
  synapse build --auto --endpoints "GET /patients,POST /patients"
  synapse build --auto --endpoints "/patients,get_patient_by_id"   # by path or tool name
  ```
  Without a terminal and without either flag, the build **stops with an error** instead
  of exposing nothing [README].
- `synapse build` exits non-zero whenever the build doesn't finish (failed composition,
  no endpoints selected, invalid API key, unreachable backend, server error, or a scan
  paused by `--max-time` or Ctrl-C — resume with `--resume`) [README].
- Custom mode invocation for describing the tool yourself [README] [GUIDE]:
  ```bash
  synapse build --custom --query "Expose user auth and profile lookup as one MCP tool"
  synapse build --custom -q "<description>"     # GUIDE cheat-sheet form
  ```

**How build works internally (v2)** [README]:
1. **Scan (local).** Language detection + extraction of HTTP routes (and, in Custom mode,
   public functions) with tree-sitter, on your machine. Result saved in `.synapse/` and
   reused by later builds until `--discover` (see §5).
2. **Pick.** Choose Auto or Custom, then the endpoints/functions to expose.
3. **Generate.** Auto hosted → endpoint config saved to your account; Auto `--local` →
   passthrough server file written. Custom → extracted manifest + your description go to
   the backend (hosted) or your model (`--local`), which composes the tool; the result is
   checked and written to your project as a Python file.

**What leaves your machine** (matters for sensitive demo code) [README]:
- Hosted Auto: per selected endpoint — name, description (from docstring), HTTP method,
  route path, header names with `${ENV}` placeholders, example payload.
- Hosted Auto + `--smart-names`: the above **plus handler source (up to 3,000 chars each)**
  and up to 6,000 chars of README/`docs/`.
- Hosted Custom: module/function names, signatures, trimmed docstrings, file paths, line
  numbers, route metadata, your workflow description. **Function bodies are not sent.**
- `--local`: the same content classes go to **your chosen model provider**; nothing goes
  to Synapse except telemetry. Auto without `--smart-names` calls no model at all.

---

## 3. `--local` mode with Groq

`--local` runs codegen in-process on your own LLM key: no Synapse account, no quota, no
code upload to Synapse, no signup. It is a **per-invocation flag** — no project config
pins a repo to local mode, and `synapse init` is not required [README] [GUIDE].

### Exact steps (Groq)

From the README's copy-paste quickstart [README] (identical flow in [GUIDE] and [DOCS]):

```bash
export GROQ_API_KEY=gsk_…
synapse model set groq
synapse build --local
```

- Groq endpoint used by Synapse: `https://api.groq.com/openai/v1`, chat-completions style
  [README].
- Verify what a local build would use before building [README] [DOCS]:
  ```bash
  synapse model          # provider + model + resolved key and WHERE it came from
  synapse model list     # every provider, its default model, key status
  ```
  `synapse model` reports the key source as one of `flag`, `env <VAR>`, `stored`, or
  `(not set)`; if a required key is missing, Synapse names the variable to set instead of
  failing mid-build [README].
- Key supply order for local builds: `--llm-api-key` flag → provider env var
  (`GROQ_API_KEY`) → `SYNAPSE_LLM_API_KEY` universal fallback → a `--save-key` stored
  value [README]. By default keys are **never written to disk**; `--save-key` is explicit
  opt-in and stores the key Fernet-encrypted, machine-bound [README].
- Pin models per stage — the pipeline uses a cheap model for high-volume **triage** and a
  strong one for **generate** (codegen); stages are `triage`, `generate`, `verify`, and
  `fallback_generate` [README]:
  ```bash
  synapse model set groq --generate "openai/gpt-oss-120b" --triage "llama-3.1-8b-instant"
  synapse model set groq --model <id>    # one --model pins every stage
  ```
- Model ids are **not validated** against a built-in list — any id the provider accepts
  works [README]. ⚠️ README warns that **Groq retired the Kimi and Llama-4-Scout model
  ids during 2026** — don't pin those [README].

### Which Groq models are strong enough?

- The only concrete Groq model pairing in the official sources is the docs/README
  example: **`openai/gpt-oss-120b` for the generate (codegen) stage** and
  **`llama-3.1-8b-instant` for triage** [README] [DOCS]. That is the officially
  exemplified strong-model choice on Groq; start there.
- The built-in **default** model ids Synapse uses for Groq if you pin nothing:
  **NOT FOUND IN SOURCES** (they are shown by `synapse model list` at runtime; neither the
  README nor the docs page prints them). Check with `synapse model list` in the smoke test.
- Why strength matters: "every stage of local codegen is a single **forced tool call**
  returning JSON that matches a strict schema" [README]. Groq is a full chat-completions
  provider for Synapse (no JSON-mode fallback needed, unlike Ollama) [README].

### The `returned no emit_tool_plan call` failure

- GUIDE's error table: "**returned no emit_tool_plan call** → Your local model is too
  small; switch to a stronger one" [GUIDE].
- README, verbatim diagnosis: "Model capability, not API capability. The JSON fallback
  makes weaker models *reachable*, not *competent*. Codegen needs a model that can hold a
  strict schema; small local models often can't, and fail with
  `returned no emit_tool_plan call`. **The fix is a stronger model**, and the error message
  says so" [README].
- Mechanism [README]: codegen stages are forced tool calls (`tool_choice`) returning
  schema-conformant JSON (the `emit_tool_plan` call). Providers that ignore `tool_choice`
  get a JSON fallback path (schema inlined in the prompt), and extraction accepts either a
  `tool_calls` entry or a JSON object in content — but a model that can't follow the
  schema still fails. Fix = pin a stronger generate-stage model (on Groq, per the official
  example: `openai/gpt-oss-120b`).
- Note: **local Auto mode without `--smart-names` calls no model at all** (it writes a
  passthrough server), so this failure is primarily a **Custom-mode / `--smart-names`**
  risk [README].
- ⚠️ **Source conflict on local Auto:** DOCS' local-mode page states "**--auto requires
  the hosted service** — use `--custom` (the default in local mode) instead" [DOCS],
  while the README states both modes work locally and Auto writes a passthrough server
  [README]. Unresolvable from sources alone — the smoke test (§8) must settle it
  empirically before we rely on local Auto.

---

## 4. Quota and cost

Free tier [README] [GUIDE]:

- **10 MCP servers** and **100,000 indexed lines** per account.
- `synapse info` shows project state and current quota usage [README] [GUIDE].

What counts [README]:

- **Indexed lines** = the lines of source files a **hosted** build scans
  ("`synapse analyze` counts every Python file"). Each run reports **only the lines added
  since the last accepted report**, so **rebuilding an unchanged repo costs nothing**.
- A rebuild that updates an existing server **does not use up another MCP server** from
  quota — the server id is retained (see §5) [README].
- **`--local` builds are never counted** [README] [GUIDE].
- Quota reporting is sent even with `SYNAPSE_TELEMETRY=0` (the free-tier limit is
  enforced from it); telemetry-off sends the line count alone. Not sent for `--local`
  builds [README].
- GUIDE tip: "Plan for quota… Rebuilding an unchanged repo costs nothing, and --local
  builds are never counted" [GUIDE].

**When `--local` is the safer choice for the live demo:**
- It removes the hosted backend from the critical path entirely: no quota check, no
  Synapse account dependency, codegen runs in-process on your Groq key [README]. For a
  Python project (our case), local mode still produces a real server file.
- Caveats: local mode produces a file **only for Python projects** (§2), and Custom-mode
  local codegen depends on your model's schema-following ability (§3).
- Hosted builds depend on the Synapse gRPC backend (`grpc.synapse.2ndbrainlabs.ai:443`)
  and REST API (`https://api.synapse.2ndbrainlabs.ai`) being reachable [README] — a live
  demo risk that `--local` avoids for the build step. (Hosted *runtime* still needs the
  hosted runner path; see §6.)

---

## 5. `synapse build --discover` — the Track 3 live-update flow

### How rescan/update works [README]

- The first `synapse build` in a project scans the code and saves what it found to
  **`.synapse/surface_cache.json`** (endpoints and functions per file, **no source code**).
- Later builds, hosted or `--local`, **reuse that cached surface** and print when it was
  discovered, e.g.:
  ```
  Using the endpoints discovered on Oct 30, 2026, 1:05 PM (12 endpoint(s)). Run synapse build --discover to rescan.
  ```
- **Code changes made since the scan are NOT picked up until you rescan.** This is the
  single most important fact for staging Track 3.
- `synapse build --discover` rescans; **only files whose contents changed are parsed
  again** (incremental, therefore fast) [README] [GUIDE].
- Special cases [README]:
  - A Custom build rescans if the saved surface came from an Auto build (Auto doesn't
    collect functions).
  - A saved surface with no endpoints is not reused; the build scans again.
  - `--resume` takes precedence: it finishes an unfinished scan, then updates the cache.
  - If `surface_cache.json` is missing/unreadable/from another repo, the build scans as
    if it were the first one. Deleting it is always safe.

### Server identity and client config stability [README]

- A hosted Auto build creates one MCP server for the project and records its id in
  `.synapse/config.json`. Later builds **update that same server**: new endpoints added,
  changed ones updated, removed ones deleted.
- **The server id — and therefore the `SYNAPSE_SERVER_ID` in your MCP client config —
  stays the same, and a rebuild doesn't consume another server from quota.**
- If the server was deleted (or the API key belongs to a different account), the build
  creates a new one and **tells you to update `SYNAPSE_SERVER_ID`** — watch for this
  message during the demo.
- `--new` creates a new server instead of updating; `--server-name <name>` selects the
  server by name (default: the folder name), so a different name gives the project a
  second server.
- GUIDE confirms: "Later builds update the same MCP server, so your client config keeps
  working" [GUIDE].

### Staging the Track 3 live-update moment reliably

Facts above imply this staging plan (plan = our synthesis; mechanics = sourced):

1. **Before the demo:** build both systems hosted Auto; leave both MCP clients connected
   with the printed snippets (server ids stable across rebuilds).
2. **Rehearse the exact endpoint addition** on a copy of the target service: add the new
   endpoint → `synapse build --discover` → confirm the CLI reports the new endpoint count
   and does **not** print a "new server / update SYNAPSE_SERVER_ID" warning.
3. **On stage:** add the endpoint live, run `synapse build --discover` (incremental —
   only the changed file is reparsed, so it should be quick), then have the agent call
   the new tool.
4. **Client-side caveat:** GUIDE says if the agent can't see the tools, **restart the
   client** [GUIDE]. For our own LangGraph client (see §6), plan to re-list tools /
   re-establish the MCP session after the rebuild rather than assuming a hot refresh —
   whether the hosted runner pushes tool-list changes to an already-connected client is
   **NOT FOUND IN SOURCES**.
5. **Failure fallback:** if `--discover` misbehaves on stage, deleting
   `.synapse/surface_cache.json` and rebuilding forces a clean full scan (safe per
   [README]) — but that costs demo time; keep it as plan C.
6. Keep the second system's server untouched during the update beat so at least one
   system stays live throughout.

---

## 6. Connecting the generated server to a CUSTOM agent (our LangGraph Python app)

Synapse's docs only describe Claude Desktop / Cursor / Windsurf configs [DOCS] [GUIDE].
There is **no LangGraph-specific guidance in any Synapse source** — that part is
**NOT FOUND IN SOURCES**. What the sources do establish is the shape of the connection,
which any MCP client (including a Python MCP client used from LangGraph) consumes:

### Hosted Auto builds — the npx runner [DOCS]

After a hosted build, Synapse prints a ready-made JSON snippet. The full example from
DOCS (from the console no-code flow, same runner shape):

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "@2ndbrainlabs-ai/synapse-mcp"],
      "env": {
        "SYNAPSE_API_KEY": "YOUR_SYNAPSE_API_KEY",
        "SYNAPSE_SERVER_ID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "SYNAPSE_API_URL": "https://api.synapse.2ndbrainlabs.ai"
      }
    }
  }
}
```

- The snippet runs the `@2ndbrainlabs-ai/synapse-mcp` runner through `npx`, carrying your
  `SYNAPSE_SERVER_ID` [GUIDE]. This is a **command/args/env (stdio-style) MCP server
  definition** — the standard `mcpServers` shape. The word "stdio" itself is never used in
  the Synapse sources: **transport is implied by the snippet shape, not stated**.
- GUIDE: "Always use the snippet Synapse prints rather than writing one by hand, since
  it carries the right server id and command for your build" [GUIDE].
- Env secrets: `${VAR_NAME}` placeholders in endpoint headers/payloads/URLs are resolved
  from the client's local environment at runtime and never exposed to the model; DOCS
  auto-adds them as empty entries in the snippet's `env` block for you to fill in [DOCS].
  `{param}` single-brace segments in URLs become required string tool parameters [DOCS].
- README's endpoints table lists a hosted MCP endpoint: **Hosted MCP servers:
  `https://mcp.synapse.2ndbrainlabs.ai`** [README]. Whether/how a custom client connects
  to that URL directly (protocol, auth headers, session model) is **NOT FOUND IN
  SOURCES** — the only documented consumption path for hosted servers is the npx runner
  snippet.

### Local-file builds — Custom and `--local` [DOCS] [GUIDE]

Custom builds and `--local` builds write a Python server file into the project
(`<tool_name>_server.py` or `synapse_auto_server.py`); the client config points at the
file [GUIDE]:

```json
{
  "mcpServers": {
    "my-project": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

(DOCS shows this shape with `mcp_server.py`; use your venv interpreter, e.g.
`.venv/bin/python3`, as the command if you set up a venv [DOCS].)

- DOCS setup step 1 (optional): create a Python venv for the generated server
  (`uv venv`), and install the generated server's dependencies, e.g. `pip install mcp`,
  inside it [DOCS]. So the generated Python server depends on the Python **`mcp`**
  package.
- For our LangGraph app this means: launch the generated file as a subprocess MCP server
  (command + args + env) via the MCP Python client, or launch the hosted runner the same
  way with the printed env block. LangGraph-side adapter specifics (e.g. which adapter
  library, session handling) are **NOT FOUND IN SOURCES** — Synapse sources treat the
  client as a black box that consumes the standard `mcpServers` snippet.
- **Prerequisite for Auto-mode tools to work at runtime:** "check that your app's API is
  running and reachable" — Auto tools call your **deployed/running API** [GUIDE] [README].
  The target FastAPI app must be up (and at the base URL the build assumed) whenever the
  agent calls a tool. The exact mechanism by which the hosted runner learns the API base
  URL is **NOT FOUND IN SOURCES**.
- Verification pattern from DOCS: after connecting, ask the agent "What tools do you have
  access to?" and confirm the Synapse tools are listed; the Console's **Manage MCP
  Servers** page also lists your server and its exposed tools [DOCS].

---

## 7. Common errors — guide + README, with fixes

Combined from [GUIDE]'s error table and [README]'s troubleshooting table (identical
where they overlap), plus README build-behaviour notes:

| Message | Fix |
|---|---|
| `Not Initialized` (on `build`) | Run `synapse init` [GUIDE] [README] |
| `Quota Exceeded` | Check `synapse info`. Free tier = 10 MCP servers + 100,000 indexed lines; or build with `--local` [GUIDE] [README] |
| `AUTH_INVALID` / "Your Synapse API key is invalid or expired" | Save a valid key with `synapse config set-key`, or set `SYNAPSE_API_KEY` (env overrides saved keys) [GUIDE] [README] |
| `Endpoint Selection Required` | No terminal to pick endpoints in. Add `--all-endpoints` or `--endpoints <list>` [GUIDE] [README] |
| `returned no emit_tool_plan call` | Local model too weak to hold the strict schema — switch to a stronger model (see §3) [GUIDE] [README] |
| `SERVER_ERROR` / "The Synapse server hit an internal error" | Synapse-side problem, not your code or key. Report it with the `Session:` id [GUIDE] [README] |
| Backend error mid-build | The CLI retries transient errors. Quote the `Session:` id when opening an issue [README] |
| `v1 engine removed` / `Option removed` | The v1 engine and its flags (`-o/--output`, `--no-validate`, `--no-docs`, `-g/--generate`, `--engine v1`) were removed. Run `synapse build` without them [README] |
| Build exits non-zero, no clear message | Build didn't finish: failed composition, no endpoints selected, invalid key, unreachable backend, server error, or scan paused by `--max-time`/Ctrl-C → resume with `synapse build --resume` [README] |
| Agent can't see the tools after connecting | Restart the MCP client; check that your app's API is running and reachable [GUIDE] |
| Build uses stale endpoints after code changes | Expected behaviour — builds reuse `.synapse/surface_cache.json`. Run `synapse build --discover` [README] |
| "Update SYNAPSE_SERVER_ID" after a rebuild | The old server was deleted (or key belongs to another account); a new server was created — update the client config env [README] |

**GitHub issues worth knowing:** the CLI repo's issue tracker currently shows **0 open
issues** [ISSUES] — there is no public issue history to mine for gotchas. (Closed-issue
contents were not enumerated by the tracker view fetched; treat "no known issues" as
"no *open* issues", not as proof of a bug-free tool.)

**Other source gaps found while researching:**
- The README's Documentation section links an **Examples** repo
  (github.com/2ndbrainlabs-ai/synapse-examples), but the GitHub org currently lists
  **exactly one public repository** — `synapse-cli-ts` [ORG] — and the examples URL
  returns 404. **The examples repo is not publicly available as of 2026-11-19.**
- The README links an **API reference** at synapse.2ndbrainlabs.ai/docs/api; that URL
  returns 404 as of 2026-11-19.
- The **npm package page** (npmjs.com/package/@2ndbrainlabs-ai/synapse-cli) could not be
  fetched (HTTP 403), so npm-page-specific facts (current published version, weekly
  downloads) are **NOT FOUND IN SOURCES**. [PRODUCT] states, as of Oct 2026: 120 MCP
  servers built with Synapse, 1,466 CLI downloads, 4 releases shipped; the CLI is free
  and open source under **Apache 2.0** [PRODUCT] [README].

---

## 8. 30-minute smoke-test script (run today, tiny FastAPI app)

Goal: prove the whole path end-to-end — install → init → build → MCP client sees tools →
agent calls one tool — and empirically settle the two open questions (Groq default models;
whether local Auto really writes a file). Timings are targets, not source claims.

**Prep (min 0–5)** — target app: a tiny FastAPI service (~4 endpoints, e.g. items CRUD)
in its own folder with a `requirements.txt` (root marker file makes language detection
deterministic [README]).

```bash
node --version            # expect v20+ (see §1 conflict)
python3 --version
cd ~/workspace/vibeathon-floor/smoke-app        # tiny FastAPI app lives here
uv venv && source .venv/bin/activate            # optional but recommended [DOCS]
pip install fastapi uvicorn mcp                 # mcp = generated server's dependency [DOCS]
```

**Install + key (min 5–10)**

```bash
npm install -g @2ndbrainlabs-ai/synapse-cli
synapse --version
# Get the API key from the Console (API Keys → Create API Key — shown once) [DOCS]
synapse config --global --key <YOUR_API_KEY>
synapse config            # confirm: key source + first-5-chars display
synapse info              # baseline quota (expect 10 servers / 100,000 lines free) [README]
```

**Hosted Auto path (min 10–18)** — start the app first; Auto tools call the running API.

```bash
uvicorn main:app --port 8000 &                  # app must stay up for tool calls [GUIDE]
synapse init                                    # paste key if prompted; creates .synapse/
synapse build --auto --all-endpoints            # non-interactive; implies --auto [README]
# → copy the printed JSON snippet verbatim (npx runner + SYNAPSE_SERVER_ID) [GUIDE]
```

**Client sees tools + one real call (min 18–24)** — minimal Python MCP client using the
printed snippet's command/args/env (stdio-shape config, §6):

```bash
# point a minimal MCP client (Python mcp package) at the snippet's command/args/env,
# list tools → expect one tool per exposed endpoint,
# then call one read-only tool (e.g. GET /items) and check the JSON result
# matches curl http://localhost:8000/items
```

**Local + Groq path (min 24–28)** — settles §3's open questions:

```bash
export GROQ_API_KEY=gsk_…
synapse model set groq
synapse model list        # RECORD the Groq default model ids (NOT FOUND IN SOURCES today)
synapse model             # confirm provider + key source = env GROQ_API_KEY
synapse build --local --custom -q "Expose the item lookup functions as one MCP tool"
# → expect <tool_name>_server.py in the project root [README]
synapse build --local --auto --all-endpoints
# → does synapse_auto_server.py appear? (settles the DOCS-vs-README conflict in §3)
```

**Discover drill (min 28–30)** — rehearse the Track 3 beat while it's cheap:

```bash
# add one new endpoint to main.py, restart uvicorn, then:
synapse build --discover
# → expect: incremental rescan, new endpoint count printed,
#   NO "update SYNAPSE_SERVER_ID" warning (server id stable) [README]
# re-list tools in the client (restart/reconnect if needed [GUIDE]) and call the NEW tool.
```

**Pass criteria:** hosted snippet connects and lists tools; one tool call returns live API
data; local Custom build writes a Python server file; `--discover` adds the new endpoint
under the **same** server id. Anything failing → check §7's table before improvising.
