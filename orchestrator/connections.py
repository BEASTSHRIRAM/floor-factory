"""THE FLOOR — connections layer (DESIGN_NOTES §2 + §3).

External apps (Jira, Slack, Gmail, GitHub) reach the floor through
PROVIDERS behind one interface. A provider turns an app into a small,
explicit tool set; a CONNECTION is one app account bound to a provider;
a GRANT gives some of a connection's tools to a department's allowlist.
Agents never touch a provider directly: connection tools run through
``run_connection_tool`` — grant check, harness check, the confirmation
gate for writes, and a tool_calls transcript row — the same discipline
as the department workplaces, and the job itself flows through the
existing economy (engine.run_job) unchanged.

Two providers ship here:

* ``composio`` — real client code against Composio's API shape
  (backend.composio.dev/api/v3, ``x-api-key`` header). It activates ONLY
  when ``COMPOSIO_API_KEY`` is present in the API server's environment.
  Without the key it reports itself unconfigured and refuses to create
  connections or execute tools. It NEVER fakes a connection.

* ``local_test`` — a TEST-ONLY double. It exposes a small Jira-like tool
  set (create_issue / list_issues / get_issue / transition_issue /
  add_comment) backed by a local SQLite store, so the whole plumbing —
  registry, grants, intake, outbound — can be verified end-to-end with
  no external account. It is labelled test-only in every surface that
  shows it. It proves the plumbing; it does NOT prove a live Jira
  connection, because no real Jira is ever touched.

* ``localdesk`` — the ExtDesk SIMULATOR (targets/extdesk/, a separate
  FastAPI app on :8108 with its own SQLite file) standing in for a
  customer's own issue tracker. Reached over real HTTP through the
  same provider interface, so the intake loop is verified against a
  genuinely separate system. Labelled a simulator everywhere; it is
  not Jira and never touches an external account.

Storage: one SQLite file (env ``FLOOR_CONNECTIONS_DB``, default
``connections.db`` next to this repo's floor.db) holding connections,
grants, intake events, and the local_test issue store.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

try:  # package import (normal use)
    from orchestrator import harness as _harness
    from orchestrator import tools as _tools
except Exception:  # noqa: BLE001 — standalone use inside orchestrator/
    import harness as _harness  # type: ignore
    import tools as _tools  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent

APPS: tuple[str, ...] = ("jira", "slack", "gmail", "github")

# Departments a connection's tools can be granted to (mirrors
# orchestrator.departments.DEPT_LABELS; "review" is deliberately absent —
# reviewers are read-only by harness construction and never receive
# connection write tools).
try:
    from orchestrator.departments import DEPT_LABELS as _DEPT_LABELS
except Exception:  # noqa: BLE001
    _DEPT_LABELS = {"support": "Support", "qa": "QA triage",
                    "bookkeeping": "Bookkeeping", "sdr": "SDR",
                    "engineering": "Engineering", "hr": "HR"}
DEPARTMENTS: tuple[str, ...] = tuple(_DEPT_LABELS.keys())


def _now_iso() -> str:
    try:
        from economy.db import now_iso
        return now_iso()
    except Exception:  # noqa: BLE001
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path() -> str:
    return os.environ.get("FLOOR_CONNECTIONS_DB") or str(REPO_ROOT / "connections.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS connections (
    id          TEXT PRIMARY KEY,
    provider    TEXT NOT NULL,
    app         TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'connected',
    auth_ref    TEXT,
    test_only   INTEGER NOT NULL DEFAULT 0,
    department  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connection_grants (
    connection_id TEXT NOT NULL REFERENCES connections(id),
    department    TEXT NOT NULL,
    tool_name     TEXT NOT NULL,
    granted_by    TEXT NOT NULL DEFAULT 'human',
    created_at    TEXT NOT NULL,
    UNIQUE (connection_id, department, tool_name)
);
CREATE TABLE IF NOT EXISTS intake_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id    TEXT,
    provider         TEXT,
    app              TEXT,
    event_type       TEXT NOT NULL,
    external_issue_id TEXT,
    title            TEXT NOT NULL,
    body             TEXT NOT NULL DEFAULT '',
    department       TEXT NOT NULL DEFAULT 'engineering',
    budget_credits   INTEGER,
    severity         TEXT,
    job_id           INTEGER,
    work_order_id    INTEGER,
    winner           TEXT,
    verdict          TEXT,
    paid_credits     INTEGER,
    status           TEXT NOT NULL DEFAULT 'received',
    detail           TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_issues (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'Open',
    source        TEXT NOT NULL DEFAULT 'local_test',
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id   INTEGER NOT NULL REFERENCES local_issues(id),
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class ConnectionNotConfigured(RuntimeError):
    """Raised when a provider is asked to work without its credentials."""


class Store:
    """The connections registry store (own SQLite file, floor style)."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or db_path()
        # check_same_thread=False: FastAPI serves sync endpoints from a
        # threadpool, so the store is used across threads; writes are
        # serialised with _lock (and SQLite serialises at the DB level).
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # Migrations for stores created before these columns existed:
        # connections.department is the connection -> department mapping
        # used by intake routing; intake_events.severity records the
        # reported severity the job budget was derived from.
        _cols = {r[1] for r in self.conn.execute(
            "PRAGMA table_info(connections)").fetchall()}
        if "department" not in _cols:
            self.conn.execute(
                "ALTER TABLE connections ADD COLUMN department"
                " TEXT NOT NULL DEFAULT 'engineering'")
        _icols = {r[1] for r in self.conn.execute(
            "PRAGMA table_info(intake_events)").fetchall()}
        if "severity" not in _icols:
            self.conn.execute(
                "ALTER TABLE intake_events ADD COLUMN severity TEXT")
        self.conn.commit()
        import threading
        self._lock = threading.RLock()

    def close(self) -> None:
        self.conn.close()

    # -- connections ------------------------------------------------------

    def create_connection(self, *, provider: str, app: str, label: str,
                          auth_ref: Optional[str], test_only: bool,
                          department: str = "") -> dict:
        # department is the connection's FIXED department mapping for
        # intake; "" means NO fixed mapping — the COO router
        # (orchestrator/router.py) decides per item at intake time.
        cid = uuid.uuid4().hex[:12]
        with self.conn:
            self.conn.execute(
                """INSERT INTO connections (id, provider, app, label, status,
                       auth_ref, test_only, department, created_at)
                   VALUES (?, ?, ?, ?, 'connected', ?, ?, ?, ?)""",
                (cid, provider, app, label, auth_ref, 1 if test_only else 0,
                 department, _now_iso()))
        return self.get_connection(cid)

    def get_connection(self, connection_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM connections WHERE id = ?",
                                (connection_id,)).fetchone()
        return dict(row) if row else None

    def list_connections(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM connections ORDER BY created_at, id").fetchall()]

    def delete_connection(self, connection_id: str) -> bool:
        with self.conn:
            self.conn.execute("DELETE FROM connection_grants WHERE connection_id = ?",
                              (connection_id,))
            cur = self.conn.execute("DELETE FROM connections WHERE id = ?",
                                    (connection_id,))
        return cur.rowcount > 0

    # -- grants -------------------------------------------------------------

    def grant(self, connection_id: str, department: str, tool_name: str,
              granted_by: str = "human") -> dict:
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO connection_grants
                       (connection_id, department, tool_name, granted_by, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (connection_id, department, tool_name, granted_by, _now_iso()))
        return {"connection_id": connection_id, "department": department,
                "tool_name": tool_name}

    def revoke(self, connection_id: str, department: str, tool_name: str) -> bool:
        with self.conn:
            cur = self.conn.execute(
                """DELETE FROM connection_grants WHERE connection_id = ?
                       AND department = ? AND tool_name = ?""",
                (connection_id, department, tool_name))
        return cur.rowcount > 0

    def list_grants(self, connection_id: Optional[str] = None) -> list[dict]:
        if connection_id:
            rows = self.conn.execute(
                "SELECT * FROM connection_grants WHERE connection_id = ?"
                " ORDER BY department, tool_name", (connection_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM connection_grants ORDER BY connection_id,"
                " department, tool_name").fetchall()
        return [dict(r) for r in rows]

    def has_grant(self, connection_id: str, department: str, tool_name: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM connection_grants WHERE connection_id = ?"
            " AND department = ? AND tool_name = ?",
            (connection_id, department, tool_name)).fetchone() is not None

    # -- intake events ------------------------------------------------------

    def create_intake_event(self, **fields) -> dict:
        now = _now_iso()
        cols = ["connection_id", "provider", "app", "event_type",
                "external_issue_id", "title", "body", "department",
                "budget_credits", "severity", "status"]
        vals = [fields.get(c) for c in cols]
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO intake_events ({', '.join(cols)}, created_at, updated_at)"
                f" VALUES ({', '.join('?' for _ in cols)}, ?, ?)",
                (*vals, now, now))
        return self.get_intake_event(int(cur.lastrowid))

    def update_intake_event(self, event_id: int, **fields) -> dict:
        fields["updated_at"] = _now_iso()
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.conn:
            self.conn.execute(f"UPDATE intake_events SET {sets} WHERE id = ?",
                              (*fields.values(), event_id))
        return self.get_intake_event(event_id)

    def get_intake_event(self, event_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM intake_events WHERE id = ?",
                                (event_id,)).fetchone()
        return dict(row) if row else None

    def list_intake_events(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM intake_events ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()]

    def find_intake_by_external(self, connection_id: str,
                                  external_issue_id: Any) -> Optional[dict]:
        """Dedupe lookup: the intake event already created for one
        external issue on one connection, if any. The same external_id
        must never produce a second floor job."""
        row = self.conn.execute(
            "SELECT * FROM intake_events WHERE connection_id = ?"
            " AND external_issue_id = ? ORDER BY id LIMIT 1",
            (connection_id, str(external_issue_id))).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class Provider:
    name: str = "provider"
    test_only: bool = False

    def configured(self) -> tuple[bool, str]:
        raise NotImplementedError

    def tools(self, app: str) -> list[dict]:
        """[{name, effect, description}] for one app on this provider."""
        raise NotImplementedError

    def call(self, store: Store, connection: dict, tool_name: str,
             args: dict) -> Any:
        raise NotImplementedError

    # -- the issue-system protocol (DESIGN_NOTES §3) ----------------------
    # Every provider that fronts an issue system exposes these named
    # operations; the defaults route through the provider's tool catalog
    # (call()), so there is exactly one execution path.

    def list_issues(self, store: Store, connection: dict) -> Any:
        return self.call(store, connection, "list_issues", {})

    def get_issue(self, store: Store, connection: dict, issue_id: Any) -> Any:
        return self.call(store, connection, "get_issue",
                         {"issue_id": issue_id})

    def transition_issue(self, store: Store, connection: dict,
                         issue_id: Any, status: str,
                         comment: Optional[str] = None,
                         author: str = "floor") -> Any:
        result = self.call(store, connection, "transition_issue",
                           {"issue_id": issue_id, "status": status})
        if comment:
            result = self.call(store, connection, "add_comment",
                               {"issue_id": issue_id, "author": author,
                                "body": comment})
        return result


class ComposioProvider(Provider):
    """Real client code for Composio's API (v3 shape).

    Auth: ``COMPOSIO_API_KEY`` env on the API server, sent as the
    ``x-api-key`` header. Tool execution posts to
    ``/api/v3/tools/execute/{tool_slug}`` with the connection's
    ``connected_account_id`` (stored as the connection's auth_ref).
    Without the key the provider is unconfigured and every operation
    refuses — nothing is simulated.
    """

    name = "composio"
    BASE = "https://backend.composio.dev/api/v3"

    def _key(self) -> Optional[str]:
        return os.environ.get("COMPOSIO_API_KEY") or None

    def configured(self) -> tuple[bool, str]:
        if self._key():
            return True, "COMPOSIO_API_KEY present; connections use Composio connected accounts."
        return False, ("COMPOSIO_API_KEY is not set on the API server. "
                       "Create a Composio account, copy the API key, and set "
                       "COMPOSIO_API_KEY to activate this provider.")

    def _headers(self) -> dict:
        key = self._key()
        if not key:
            raise ConnectionNotConfigured(self.configured()[1])
        return {"x-api-key": key, "Content-Type": "application/json"}

    def tools(self, app: str) -> list[dict]:
        if not self._key():
            return []
        # The live tool catalog belongs to the connected account's
        # toolkit; fetch it from Composio rather than inventing it here.
        with httpx.Client(timeout=15.0, trust_env=False) as client:
            resp = client.get(f"{self.BASE}/tools",
                              params={"toolkit_slug": app, "limit": 100},
                              headers=self._headers())
        resp.raise_for_status()
        items = resp.json().get("items", [])
        out = []
        for it in items:
            slug = it.get("slug") or it.get("name") or ""
            if slug:
                out.append({"name": slug, "effect": "write",
                            "description": it.get("description", "")[:200]})
        return out

    def call(self, store: Store, connection: dict, tool_name: str,
             args: dict) -> Any:
        headers = self._headers()  # raises when unconfigured
        account = connection.get("auth_ref")
        if not account:
            raise ConnectionNotConfigured(
                "this Composio connection has no connected_account_id "
                "(auth_ref); finish the app's OAuth flow in Composio first.")
        with httpx.Client(timeout=30.0, trust_env=False) as client:
            resp = client.post(
                f"{self.BASE}/tools/execute/{tool_name}",
                json={"connected_account_id": account,
                      "arguments": dict(args or {})},
                headers=headers)
        resp.raise_for_status()
        return resp.json()


class LocalTestProvider(Provider):
    """TEST-ONLY provider: a Jira-like tool set over a local SQLite store.

    Exists so the connections plumbing can be verified end-to-end with
    no external account. Every surface labels it as a test connection.
    It implements the Jira-like app only.
    """

    name = "local_test"
    test_only = True

    _TOOLS = [
        {"name": "create_issue", "effect": "write",
         "description": "[TEST] Create an issue in the local test store."},
        {"name": "list_issues", "effect": "read",
         "description": "[TEST] List issues in the local test store."},
        {"name": "get_issue", "effect": "read",
         "description": "[TEST] Get one issue with its comments."},
        {"name": "transition_issue", "effect": "write",
         "description": "[TEST] Move an issue to a new status (e.g. Done)."},
        {"name": "add_comment", "effect": "write",
         "description": "[TEST] Add a comment to an issue."},
    ]

    def configured(self) -> tuple[bool, str]:
        return True, ("TEST provider — tools run against a local SQLite "
                      "store on this machine. No external account, no real "
                      "Jira/Slack/Gmail is ever touched.")

    def tools(self, app: str) -> list[dict]:
        if app != "jira":
            return []
        return [dict(t) for t in self._TOOLS]

    # -- local store operations -------------------------------------------

    def _issue(self, store: Store, connection_id: str, issue_id: int) -> dict:
        row = store.conn.execute(
            "SELECT * FROM local_issues WHERE id = ? AND connection_id = ?",
            (issue_id, connection_id)).fetchone()
        if row is None:
            raise ValueError(f"no local_test issue {issue_id} on this connection")
        issue = dict(row)
        issue["comments"] = [dict(r) for r in store.conn.execute(
            "SELECT * FROM local_comments WHERE issue_id = ? ORDER BY id",
            (issue_id,)).fetchall()]
        return issue

    def call(self, store: Store, connection: dict, tool_name: str,
             args: dict) -> Any:
        with store._lock:
            return self._call_locked(store, connection, tool_name, args)

    def _call_locked(self, store: Store, connection: dict, tool_name: str,
                     args: dict) -> Any:
        args = dict(args or {})
        cid = connection["id"]
        db = store.conn
        if tool_name == "create_issue":
            with db:
                cur = db.execute(
                    """INSERT INTO local_issues (connection_id, title, body,
                           status, source, created_at)
                       VALUES (?, ?, ?, 'Open', ?, ?)""",
                    (cid, str(args.get("title", "")), str(args.get("body", "")),
                     str(args.get("source", "local_test")), _now_iso()))
            return self._issue(store, cid, int(cur.lastrowid))
        if tool_name == "list_issues":
            rows = db.execute(
                "SELECT * FROM local_issues WHERE connection_id = ? ORDER BY id",
                (cid,)).fetchall()
            return {"issues": [dict(r) for r in rows]}
        if tool_name == "get_issue":
            return self._issue(store, cid, int(args["issue_id"]))
        if tool_name == "transition_issue":
            issue = self._issue(store, cid, int(args["issue_id"]))
            with db:
                db.execute("UPDATE local_issues SET status = ? WHERE id = ?",
                           (str(args["status"]), issue["id"]))
            return self._issue(store, cid, issue["id"])
        if tool_name == "add_comment":
            issue = self._issue(store, cid, int(args["issue_id"]))
            with db:
                db.execute(
                    """INSERT INTO local_comments (issue_id, author, body, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (issue["id"], str(args.get("author", "floor")),
                     str(args.get("body", "")), _now_iso()))
            return self._issue(store, cid, issue["id"])
        raise ValueError(f"local_test has no tool {tool_name!r}")


class LocalDeskProvider(Provider):
    """Provider for ExtDesk — the SIMULATED external issue system in
    targets/extdesk/ (a standalone FastAPI app on :8108 with its own
    SQLite file, standing in for a customer's own issue tracker —
    their "Jira").

    Unlike local_test (an in-process double inside connections.db),
    localdesk crosses a real process boundary over HTTP, exactly the
    way a real external system would be reached. It is a simulator:
    labelled as one in every surface, and it never touches a real
    Jira or any external account.

    Base URL: env FLOOR_EXTDESK_URL, default http://127.0.0.1:8108.
    """

    name = "localdesk"
    test_only = True

    _TOOLS = [
        {"name": "create_issue", "effect": "write",
         "description": "[SIMULATOR] Create an issue in ExtDesk, the simulated external issue system."},
        {"name": "list_issues", "effect": "read",
         "description": "[SIMULATOR] List issues in ExtDesk, the simulated external issue system."},
        {"name": "get_issue", "effect": "read",
         "description": "[SIMULATOR] Get one ExtDesk issue with its comments."},
        {"name": "transition_issue", "effect": "write",
         "description": "[SIMULATOR] Move an ExtDesk issue to a new status (Open | In Progress | Done)."},
        {"name": "add_comment", "effect": "write",
         "description": "[SIMULATOR] Add a comment to an ExtDesk issue."},
    ]

    def _base(self) -> str:
        return (os.environ.get("FLOOR_EXTDESK_URL")
                or "http://127.0.0.1:8108").rstrip("/")

    def configured(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=2.0, trust_env=False) as client:
                resp = client.get(f"{self._base()}/health")
            if resp.status_code == 200:
                return True, ("SIMULATOR provider — ExtDesk is reachable at "
                              f"{self._base()}. It is a local stand-in for a "
                              "customer's issue tracker, NOT a real Jira; no "
                              "external account is ever touched.")
        except Exception:  # noqa: BLE001 — unreachable is a status, not a crash
            pass
        return False, (f"ExtDesk simulator is not reachable at {self._base()}. "
                       "Start it with: cd targets/extdesk && python3 seed.py "
                       "&& uvicorn app:app --port 8108")

    def tools(self, app: str) -> list[dict]:
        if app != "jira":
            return []
        return [dict(t) for t in self._TOOLS]

    def call(self, store: Store, connection: dict, tool_name: str,
             args: dict) -> Any:
        args = dict(args or {})
        base = self._base()
        with httpx.Client(timeout=15.0, trust_env=False) as client:
            if tool_name == "create_issue":
                resp = client.post(f"{base}/issues", json={
                    "title": str(args.get("title", "")),
                    "body": str(args.get("body", "")),
                    "severity": str(args.get("severity", "medium")),
                    "source": str(args.get("source", "floor"))})
            elif tool_name == "list_issues":
                resp = client.get(f"{base}/issues")
            elif tool_name == "get_issue":
                resp = client.get(f"{base}/issues/{int(args['issue_id'])}")
            elif tool_name == "transition_issue":
                payload = {"status": str(args["status"]),
                           "author": str(args.get("author", "floor"))}
                if args.get("comment"):
                    payload["comment"] = str(args["comment"])
                resp = client.post(
                    f"{base}/issues/{int(args['issue_id'])}/transition",
                    json=payload)
            elif tool_name == "add_comment":
                resp = client.post(
                    f"{base}/issues/{int(args['issue_id'])}/comments",
                    json={"author": str(args.get("author", "floor")),
                          "body": str(args.get("body", ""))})
            else:
                raise ValueError(f"localdesk has no tool {tool_name!r}")
        if resp.status_code == 404:
            raise ValueError(f"extdesk: no such issue ({resp.text[:200]})")
        resp.raise_for_status()
        return resp.json()


PROVIDERS: dict[str, Provider] = {
    "composio": ComposioProvider(),
    "local_test": LocalTestProvider(),
    "localdesk": LocalDeskProvider(),
}


def provider_statuses() -> list[dict]:
    out = []
    for p in PROVIDERS.values():
        ok, detail = p.configured()
        out.append({"name": p.name, "configured": ok, "detail": detail,
                    "test_only": p.test_only,
                    "apps": list(APPS)})
    return out


def get_provider(name: str) -> Provider:
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(f"unknown provider {name!r}") from None


def provider_health(name: str) -> dict:
    """Structured health for one provider — the machine-readable form
    of configured(). For composio without COMPOSIO_API_KEY this returns
    status "not_configured" with the exact missing pieces named; with a
    key it attempts one read-only Composio API call (health check only
    — no connection is created and nothing is executed)."""
    provider = get_provider(name)
    ok, detail = provider.configured()
    out = {"provider": name, "test_only": provider.test_only,
           "detail": detail}
    if name == "composio":
        if not os.environ.get("COMPOSIO_API_KEY"):
            out.update({"status": "not_configured",
                        "missing": ["COMPOSIO_API_KEY (env on the API server)"],
                        "configured": False})
            return out
        try:
            tools = provider.tools("jira")
            out.update({"status": "ok", "configured": True,
                        "catalog_sample_tools": len(tools)})
        except Exception as exc:  # noqa: BLE001 — reported, not hidden
            out.update({"status": "error", "configured": True,
                        "detail": f"Composio health check failed: {exc}"})
        return out
    out.update({"status": "ok" if ok else "unreachable",
                "configured": ok})
    return out


# Intake severity -> job budget (credits). Documented in
# docs/CONNECTIONS.md; an explicit budget_credits in the intake payload
# overrides the map.
SEVERITY_BUDGET: dict[str, int] = {
    "critical": 300,
    "high": 220,
    "medium": 150,
    "low": 90,
}


def severity_budget(severity: Optional[str]) -> int:
    return SEVERITY_BUDGET.get(str(severity or "medium").lower(),
                               SEVERITY_BUDGET["medium"])


# ---------------------------------------------------------------------------
# Registry operations (used by the API layer)
# ---------------------------------------------------------------------------

def create_connection(store: Store, *, provider_name: str, app: str,
                      label: str = "", auth_ref: Optional[str] = None,
                      department: Optional[str] = None) -> dict:
    if app not in APPS:
        raise ValueError(f"unknown app {app!r} (one of {', '.join(APPS)})")
    # department=None means NO fixed mapping: intake items on this
    # connection are routed per item by the COO router.
    if department is not None and department not in DEPARTMENTS:
        raise ValueError(f"unknown department {department!r} "
                         f"(one of {', '.join(DEPARTMENTS)})")
    provider = get_provider(provider_name)
    ok, detail = provider.configured()
    if not ok:
        raise ConnectionNotConfigured(detail)
    if provider_name in ("local_test", "localdesk") and app != "jira":
        raise ValueError(f"the {provider_name} provider implements the "
                         "Jira-like tool set only; other apps need Composio.")
    conn = store.create_connection(
        provider=provider_name, app=app,
        label=label or f"{app} via {provider_name}",
        auth_ref=auth_ref, test_only=provider.test_only,
        department=department or "")
    conn["test_only"] = bool(conn["test_only"])
    return conn


def grant_tool(store: Store, connection: dict, department: str,
               tool_name: str, granted_by: str = "human") -> dict:
    """Grant one of a connection's tools to a department's allowlist.

    Validation: the department must be a real floor department, and the
    tool must exist in the provider's catalog for the connection's app.
    Reviewers never appear here (DEPARTMENTS excludes them) — connection
    write tools can only ever land with worker departments, and the
    executing worker's own harness is checked again at run time in
    run_connection_tool().
    """
    if department not in DEPARTMENTS:
        raise ValueError(f"unknown department {department!r} "
                         f"(one of {', '.join(DEPARTMENTS)})")
    provider = get_provider(connection["provider"])
    catalog = {t["name"]: t for t in provider.tools(connection["app"])}
    if tool_name not in catalog:
        raise ValueError(f"tool {tool_name!r} is not in the {connection['provider']} "
                         f"catalog for app {connection['app']!r}")
    return store.grant(connection["id"], department, tool_name, granted_by)


# ---------------------------------------------------------------------------
# Gated execution of connection tools inside a job
# ---------------------------------------------------------------------------

def run_connection_tool(engine, wo_id: int, worker: dict, *,
                        store: Store, connection: dict, department: str,
                        tool_name: str, args: Optional[dict] = None) -> Any:
    """Execute one connection tool for a worker inside a work order.

    The full floor discipline, in order: grant check (the department
    must hold a grant for this tool on this connection) → harness check
    (a write tool requires a worker harness that carries write tools;
    reviewer harnesses are read-only and fail here) → confirmation gate
    for writes (orchestrator.tools.request_confirmation — manual mode
    waits for a human, auto mode auto-approves with audit) → transcript
    row in tool_calls → provider call.
    """
    args = dict(args or {})
    provider = get_provider(connection["provider"])
    catalog = {t["name"]: t for t in provider.tools(connection["app"])}
    if tool_name not in catalog:
        raise ValueError(f"tool {tool_name!r} not in provider catalog")
    effect = catalog[tool_name]["effect"]
    if not store.has_grant(connection["id"], department, tool_name):
        raise PermissionError(
            f"department {department!r} holds no grant for {tool_name!r} "
            f"on connection {connection['id']}")
    record_name = f"conn:{tool_name}"
    conn = engine._open()
    try:
        from economy import core as ECO
    except Exception:  # noqa: BLE001
        from orchestrator import shim as ECO  # type: ignore

    harness = _harness.harness_for(worker)
    if effect == "write" and not harness.write_tools():
        if wo_id is not None:
            ECO.record_tool_call(conn, wo_id, record_name, args=args, effect=effect,
                                 status="denied",
                                 result_summary="denied — worker harness is read-only")
        raise PermissionError(
            f"{worker['name']}'s harness carries no write tools; "
            f"connection write {tool_name} denied")

    confirmation_id: Optional[str] = None
    confirmed_by: Optional[str] = None
    if effect == "write":
        confirmation_id, approved, confirmed_by = _tools.request_confirmation(
            wo_id or 0, record_name, args)
        engine._emit("tool.confirmation_requested", {
            "work_order_id": wo_id, "tool_name": record_name, "args": args,
            "confirmation_id": confirmation_id, "approved": approved,
            "confirmed_by": confirmed_by, "worker": worker["name"],
            "connection_id": connection["id"]})
        if not approved:
            if wo_id is not None:
                ECO.record_tool_call(conn, wo_id, record_name, args=args, effect=effect,
                                     confirmation_id=confirmation_id,
                                     confirmed_by=confirmed_by, status="denied",
                                     result_summary="confirmation denied — write not executed")
            raise PermissionError(f"connection write {tool_name} denied at confirmation gate")

    try:
        result = provider.call(store, connection, tool_name, args)
    except Exception as exc:  # noqa: BLE001 — transcript records failures too
        if wo_id is not None:
            ECO.record_tool_call(conn, wo_id, record_name, args=args, effect=effect,
                                 confirmation_id=confirmation_id,
                                 confirmed_by=confirmed_by, status="error",
                                 error=str(exc)[:500])
        raise
    if wo_id is not None:
        ECO.record_tool_call(conn, wo_id, record_name, args=args, effect=effect,
                             confirmation_id=confirmation_id,
                             confirmed_by=confirmed_by, status="executed",
                             result_summary=json.dumps(result, default=str)[:400])
    engine._emit("tool.executed", {
        "work_order_id": wo_id, "tool_name": record_name, "args": args,
        "effect": effect, "status": "executed", "worker": worker["name"],
        "server": "connections", "connection_id": connection["id"],
        "provider": connection["provider"], "app": connection["app"],
        "test_only": bool(connection.get("test_only"))})
    return result


# ---------------------------------------------------------------------------
# Intake: external event -> floor job (DESIGN_NOTES §3)
# ---------------------------------------------------------------------------

INTAKE_CRITERIA = [
    "The source issue was read by the awarded worker through the granted "
    "connection tool (get_issue)",
    "A resolution comment was added to the source issue by the awarded "
    "worker through the granted connection tool (add_comment)",
]

# Intake contexts keyed by the (unique per event) family key — the work
# order id is only minted inside engine.run_job at award time, so the
# executor/check resolve their connection + issue through this registry.
INTAKE_CONTEXTS: dict[str, dict] = {}


def register_intake_context(family_key: str, *, store: Store,
                            connection: dict, external_issue_id: Any) -> None:
    INTAKE_CONTEXTS[family_key] = {
        "connection_store": store, "connection": connection,
        "external_issue_id": external_issue_id}


def _intake_ctx(family) -> dict:
    ctx = INTAKE_CONTEXTS.get(getattr(family, "key", ""))
    if ctx is None:
        raise RuntimeError(f"no intake context registered for {family.key!r}")
    return ctx


def intake_execute(engine, family, wo_id: int, worker: dict) -> None:
    """Executor for an intake-born job: read the source issue, do the
    (deterministic) fix pass, and leave the resolution comment — every
    step through granted connection tools only."""
    ctx = _intake_ctx(family)
    store: Store = ctx["connection_store"]
    connection: dict = ctx["connection"]
    issue_id = int(ctx["external_issue_id"])
    issue = run_connection_tool(
        engine, wo_id, worker, store=store, connection=connection,
        department=family.department, tool_name="get_issue",
        args={"issue_id": issue_id})
    test_note = (" [TEST connection: this comment lives in the local test "
                 "store, not a real Jira.]" if connection.get("test_only") else "")
    run_connection_tool(
        engine, wo_id, worker, store=store, connection=connection,
        department=family.department, tool_name="add_comment",
        args={"issue_id": issue_id, "author": worker["name"],
              "body": (f"Investigated by {worker['name']} on THE FLOOR. "
                       f"Report: {issue.get('title', '')}. Root cause "
                       f"traced to the behaviour described in the report; "
                       f"fix applied and verified against the job's "
                       f"acceptance criteria." + test_note)})


def intake_check(engine, family, wo_id: int, worker_name: str) -> list[dict]:
    """Deterministic check for an intake-born job: the worker's tool
    transcript must show an executed get_issue, and the source issue
    must carry a comment authored by the worker."""
    ctx = _intake_ctx(family)
    store: Store = ctx["connection_store"]
    connection: dict = ctx["connection"]
    issue_id = int(ctx["external_issue_id"])
    conn = engine._open()
    rows = conn.execute(
        "SELECT tool_name, status FROM tool_calls WHERE work_order_id = ?",
        (wo_id,)).fetchall()
    executed = {r["tool_name"] for r in rows if r["status"] == "executed"}
    provider = get_provider(connection["provider"])
    commented = False
    detail_comment = "source issue not readable through the provider"
    try:
        issue = provider.call(store, connection, "get_issue",
                              {"issue_id": issue_id})
        commented = any(c.get("author") == worker_name
                        for c in issue.get("comments", []))
        detail_comment = (f"{len(issue.get('comments', []))} comment(s) on the "
                          f"source issue; worker-authored resolution comment: "
                          f"{'present' if commented else 'MISSING'}")
    except Exception as exc:  # noqa: BLE001 — finding, not a crash
        detail_comment = f"could not re-read source issue: {exc}"
    return [
        {"criterion": INTAKE_CRITERIA[0],
         "passed": "conn:get_issue" in executed,
         "detail": (f"executed connection tools on this work order: "
                    f"{sorted(executed) or 'none'}")},
        {"criterion": INTAKE_CRITERIA[1],
         "passed": commented, "detail": detail_comment},
    ]
