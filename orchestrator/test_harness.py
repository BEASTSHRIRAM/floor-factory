"""Targeted proof for the formalised agent harness (orchestrator/harness.py).

Run from the repo root with the project venv (imports orchestrator.engine,
which needs httpx):
    .venv/bin/python -m orchestrator.test_harness

Proves:
  (0) engine.TRAITS_BY_NAME is now derived from the harness definitions
      and is identical to the former literal table.
  (a) Two different personas expose DIFFERENT tool allowlists and
      DIFFERENT charter text; the engine enforces the allowlist in
      FloorEngine.call (a reviewer's write is denied before the gate,
      a worker's allowlisted write goes through).
  (a+) Every roster persona resolves to a valid harness: every
      allowlisted tool exists in TOOL_SPECS, a playbook exists for every
      registered job family, and settings carry department / model_tier /
      max_retries / verification_strictness.
  (b) After a job fails review, a lesson is stored for that agent and
      appears in the context built for its next job.
  (c) A fired agent's mutated replacement has a harness that differs
      from the parent's in the field named by its mutation_note.
  (d) The mutated replacement INHERITS its parent's lessons (lineage
      store): they appear in lessons_for() and in its own job context,
      and same-family lessons are served first.
  (e) The economy test suite still passes unchanged (subprocess), and —
      when the eight target workplaces are live — a scripted 2-cycle
      shift on a throwaway DB reproduces the pre-harness headline
      outcome: 45/45 jobs paid, the natural SLA rejection appealed and
      upheld, Baron fired and replaced, lessons recorded (reject +
      negative-cycle) and a cycle-2 context carrying a cycle-1 lesson.
  (f) GET /agents/{id}/harness serves the composed harness (TestClient).
  (g) Hermes upgrades: build_context renders three labelled tiers in
      order, the STABLE tier is byte-identical for one agent across
      jobs, and the same inputs render byte-identical context twice
      (H1); tools are grouped by toolset and a down workplace's tools
      are dropped from the context and noted (H2); DENY_ALWAYS denies
      human-only powers in FloorEngine.call before the gate — manager
      and Auto mode included — while legitimate merge/send tools pass
      (H3); lessons are character-capped and deduped at insert (H4);
      the committed SKILL.md playbook artefacts match a fresh render
      (H5); GET /agents/{id}/harness/export serves the profile bundle
      (H6); and the golden file pins the fixture context rendering
      (H10 — regenerate with FLOOR_UPDATE_GOLDEN=1).
Exits 0 and prints PASS lines when everything holds.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from economy import core as ECO  # noqa: E402
from economy.db import init_db  # noqa: E402
from orchestrator import engine as ENG  # noqa: E402
from orchestrator import harness as H  # noqa: E402
from orchestrator.tools import TOOL_SPECS  # noqa: E402


def fresh():
    return init_db(":memory:", reset=True)


def by_name(conn, name):
    for a in ECO.list_agents(conn):
        if a["name"] == name:
            return a
    raise AssertionError(f"agent {name} not found")


def test_traits_derived_identical():
    expected = {
        "Maya": {"specialties": {"triage", "stale_close"}, "careful": True},
        "Ravi": {"specialties": {"duplicates", "stale_close"}, "careful": True},
        "Pixel": {"specialties": {"triage", "categories"}},
        "Chotu": {"specialties": {"sla_breach"}, "sloppy": True},
        "Baron": {"specialties": {"vip_save", "categories"}, "prima_donna": True},
    }
    assert ENG.TRAITS_BY_NAME == expected, ENG.TRAITS_BY_NAME
    print("PASS (0) engine.TRAITS_BY_NAME derived from harness, identical to legacy table")


def test_allowlists_and_charters_differ():
    conn = fresh()
    ECO.seed_roster(conn)
    maya = H.harness_for(by_name(conn, "Maya"))
    iris = H.harness_for(by_name(conn, "Iris"))
    pixel = H.harness_for(by_name(conn, "Pixel"))
    baron = H.harness_for(by_name(conn, "Baron"))

    # Reviewer Iris: read-only everywhere — zero write tools.
    assert iris.write_tools() == [], iris.write_tools()
    assert all(TOOL_SPECS[s][t]["effect"] == "read" for (s, t) in iris.tools)
    # Worker Maya: writes included, no exclusions.
    assert ("ticketdesk", "write_merge_tickets") in maya.tools
    assert ("ticketdesk", "write_create_ticket") in maya.tools
    assert maya.tools != iris.tools
    # Junior Pixel loses the manager's intake writes; Maya keeps them.
    assert ("ticketdesk", "write_create_ticket") not in pixel.tools
    assert ("ticketdesk", "write_set_ticket_priority") not in pixel.tools
    assert pixel.tools != maya.tools
    # Baron may not touch the StockRoom's only write.
    assert ("stockroom", "write_adjust_item") not in baron.tools
    assert ("stockroom", "write_adjust_item") in maya.tools
    # Charters differ per persona and carry persona-specific rules.
    assert maya.charter != iris.charter and maya.charter != pixel.charter
    assert "Verify each ticket immediately after acting on it." in maya.charter
    assert "automatic P1 reject" in iris.charter
    # Settings differ too (temperature / verification strictness).
    assert maya.settings["verification"] == "self-check"
    assert H.harness_for(by_name(conn, "Chotu")).settings["verification"] == "none"
    print("PASS (a) personas expose different allowlists, charters and settings")


class _FakeTools:
    """ToolClient stand-in: effect() from TOOL_SPECS, call_tool canned."""

    last_transport = "fake"

    def effect(self, server, tool_name):
        return TOOL_SPECS[server][tool_name]["effect"]

    def call_tool(self, server, tool_name, args=None):
        return {"ok": True, "server": server, "tool": tool_name}


def test_engine_enforces_allowlist():
    # The gate is not under test here — stub it to approve, so the ONLY
    # thing that can stop a call is the harness allowlist. The stub is
    # restored afterwards so later tests see the real gate.
    original_gate = ENG._tools.request_confirmation
    ENG._tools.request_confirmation = lambda wo, tool, args: ("cid-test", True, "test")
    eng = ENG.FloorEngine(db_path=":memory:", tool_client=_FakeTools())
    try:
        eng._open()
        # Iris (reviewer) attempting a write: denied by the harness,
        # before the gate, with a PermissionError naming the allowlist.
        try:
            eng.call(None, "write_merge_tickets", {"source_id": 1, "target_id": 2},
                     worker_name="Iris")
            raise AssertionError("reviewer write was not denied")
        except PermissionError as exc:
            assert "allowlist" in str(exc), exc
        # Pixel (junior) attempting a manager intake write: denied.
        try:
            eng.call(None, "write_create_ticket", {"subject": "x"}, worker_name="Pixel")
            raise AssertionError("junior intake write was not denied")
        except PermissionError as exc:
            assert "allowlist" in str(exc), exc
        # Maya's allowlisted write goes through.
        out = eng.call(None, "write_merge_tickets", {"source_id": 1, "target_id": 2},
                       worker_name="Maya")
        assert out["ok"] is True
        # Manager is unrestricted.
        out = eng.call(None, "write_create_ticket", {"subject": "x"}, worker_name="manager")
        assert out["ok"] is True
    finally:
        eng.close()
        ENG._tools.request_confirmation = original_gate
    print("PASS (a2) FloorEngine.call enforces the harness allowlist before the gate")


def test_lesson_recorded_and_injected():
    conn = fresh()
    ECO.seed_roster(conn)
    chotu = by_name(conn, "Chotu")
    family = SimpleNamespace(
        key="sla_breach", title="SLA breach sweep + escalation",
        brief="Find every SLA-breached ticket and post an ESCALATION comment.",
        criteria=["Every breached ticket has an escalation comment"],
        department="support")
    findings = [{"criterion": family.criteria[0], "passed": False,
                 "detail": "breached tickets without an escalation comment: [7, 9]"}]

    # Before any failure: context exists but carries no lessons.
    ctx_before = H.build_context(conn, chotu, family)
    assert "- (none yet)" in ctx_before

    # The engine's reject hook records a lesson built from the findings.
    lesson_id = H.record_review_outcome(conn, chotu, work_order_id=42,
                                        family=family, findings=findings,
                                        phase="primary")
    assert lesson_id is not None
    stored = H.lessons_for(conn, chotu["id"])
    assert len(stored) == 1 and stored[0]["source"] == "review_reject"
    assert stored[0]["family_key"] == "sla_breach"
    assert "without an escalation comment: [7, 9]" in stored[0]["lesson"]

    # The NEXT job's context contains the lesson, verbatim.
    ctx_after = H.build_context(conn, chotu, family)
    assert stored[0]["lesson"] in ctx_after
    assert "LESSONS FROM YOUR PAST JOBS" in ctx_after
    # ...while another agent's context stays clean.
    ctx_maya = H.build_context(conn, by_name(conn, "Maya"), family)
    assert stored[0]["lesson"] not in ctx_maya
    # An accept records nothing.
    ok = [{"criterion": family.criteria[0], "passed": True, "detail": "all escalated"}]
    assert H.record_review_outcome(conn, chotu, work_order_id=43, family=family,
                                   findings=ok, phase="primary") is None
    assert len(H.lessons_for(conn, chotu["id"])) == 1
    print("PASS (b) rejected review -> lesson stored -> injected into next job's context")


def test_mutation_changes_harness():
    conn = fresh()
    ECO.seed_roster(conn)
    baron = by_name(conn, "Baron")
    new_id = ECO.hire_mutated_replacement(conn, baron["id"], cycle_no=3)
    replacement = ECO.get_agent(conn, new_id)
    note = replacement["mutation_note"] or ""
    parent_h = H.harness_for(baron)
    new_h = H.harness_for(replacement)
    diff = H.harness_diff(parent_h, new_h)
    assert diff, f"replacement harness identical to parent's (note: {note})"
    # The differing field must be the one the mutation_note names.
    if "persona trait" in note:
        trait = note.rsplit("—", 1)[-1].strip()
        assert diff.get("hard_rules_added") == [H.TRAIT_RULES[trait]], diff
        assert trait in replacement["persona_prompt"]
    elif "model" in note:
        assert diff["settings"]["model"] == [baron["model"], replacement["model"]], diff
    elif "risk_appetite" in note:
        assert diff["settings"]["risk_appetite"] == [
            baron["risk_appetite"], replacement["risk_appetite"]], diff
    else:
        raise AssertionError(f"unrecognised mutation_note: {note}")
    assert new_h.generation == baron["generation"] + 1
    print(f"PASS (c) mutated replacement's harness differs in the expected field ({note})")


def test_every_persona_valid_harness():
    conn = fresh()
    roster = ECO.seed_roster(conn)
    assert len(roster) == 7
    for agent in roster:
        h = H.harness_for(agent)
        # Every allowlisted tool exists in TOOL_SPECS for its server.
        assert h.tools, agent["name"]
        for server, tool in h.tools:
            assert tool in TOOL_SPECS[server], (agent["name"], server, tool)
        # The brief's explicit fields are all present and sane.
        assert h.department, agent["name"]
        assert h.model_tier in H.MODEL_TIERS, (agent["name"], h.model_tier)
        assert h.settings["model_tier"] == h.model_tier
        assert isinstance(h.settings["max_retries"], int) and h.settings["max_retries"] >= 0
        assert h.settings["verification_strictness"] in H.STRICTNESS_LEVELS
        assert h.charter and h.hard_rules
        # A playbook exists for EVERY registered job family.
        for fam in ENG.JOB_FAMILIES:
            steps = H.playbook_for(agent, fam)
            assert steps and all(isinstance(s, str) and s for s in steps), \
                (agent["name"], fam.key)
    # Tier labels land where the roster says they should.
    tiers = {a["name"]: H.harness_for(a).model_tier for a in roster}
    assert tiers["Chotu"] == "economy" and tiers["Pixel"] == "economy", tiers
    assert tiers["Baron"] == "premium", tiers
    assert tiers["Maya"] == "balanced" and tiers["Ravi"] == "balanced", tiers
    print("PASS (a+) every persona: valid harness, tools in TOOL_SPECS, "
          "playbooks for all 23 families, tier/settings fields present")


def test_replacement_inherits_lessons():
    conn = fresh()
    ECO.seed_roster(conn)
    baron = by_name(conn, "Baron")
    family = SimpleNamespace(
        key="vip_save", title="VIP save: calm the angry customers",
        brief="Escalate the angry tickets.", criteria=["escalation posted"],
        department="support")
    findings = [{"criterion": "escalation posted", "passed": False,
                 "detail": "angry tickets without an escalation comment: [3]"}]
    lid = H.record_review_outcome(conn, baron, work_order_id=7, family=family,
                                  findings=findings, phase="primary",
                                  cycle_no=1, caught_by="reviewer Iris (primary)")
    assert lid is not None
    # A second lesson, from another family and recorded LATER.
    other = SimpleNamespace(key="categories", title="Normalise categories",
                            brief="", criteria=["canonical"], department="support")
    H.record_review_outcome(
        conn, baron, work_order_id=8, family=other,
        findings=[{"criterion": "canonical", "passed": False,
                   "detail": "non-canonical categories remain"}],
        phase="primary", cycle_no=1)

    new_id = ECO.hire_mutated_replacement(conn, baron["id"], cycle_no=2)
    replacement = ECO.get_agent(conn, new_id)
    inherited = H.lessons_for(conn, new_id)
    assert len(inherited) == 2, inherited
    assert H.lesson_count(conn, new_id) == 2
    assert any("escalation comment: [3]" in l["lesson"] for l in inherited)
    # Structured fields survive the inheritance.
    first = [l for l in inherited if l["family_key"] == "vip_save"][0]
    assert first["cycle_no"] == 1 and "Iris" in (first["caught_by"] or "")
    assert first["agent_name"] == "Baron"  # recorded against the parent
    # Same-family lessons are served first for a vip_save job...
    ordered = H.lessons_for(conn, new_id, family_key="vip_save")
    assert ordered[0]["family_key"] == "vip_save", ordered
    # ...and the replacement's own context carries the inherited lesson.
    ctx = H.build_context(conn, replacement, family)
    assert "escalation comment: [3]" in ctx and "[review_reject]" in ctx
    print("PASS (d) mutated replacement inherits the lineage's lessons; "
          "same-family lessons served first")


_ALL_UP = {s: True for s in H.ALL_SERVERS}
_GOLDEN_PATH = (Path(__file__).resolve().parent / "golden"
                / "maya_triage_context.txt")


def test_context_tiers_byte_stable():
    conn = fresh()
    ECO.seed_roster(conn)
    maya = by_name(conn, "Maya")
    fam = ENG.FAMILIES_BY_KEY["triage"]
    ctx1 = H.build_context(conn, maya, fam, availability=_ALL_UP)
    ctx2 = H.build_context(conn, maya, fam, availability=_ALL_UP)
    # H1 determinism contract: same inputs -> identical bytes.
    assert ctx1.encode("utf-8") == ctx2.encode("utf-8")
    # Three labelled tiers, in the fixed order.
    i1 = ctx1.index("## TIER 1 · STABLE")
    i2 = ctx1.index("## TIER 2 · CONTEXT")
    i3 = ctx1.index("## TIER 3 · VOLATILE")
    assert i1 < i2 < i3
    # The job's own brief + criteria live in the CONTEXT tier (§6.3).
    tier2 = ctx1[i2:i3]
    assert fam.brief in tier2 and fam.criteria[0] in tier2
    # STABLE tier is byte-identical for the same agent on another job.
    ctx_b = H.build_context(conn, maya, ENG.FAMILIES_BY_KEY["duplicates"],
                            availability=_ALL_UP)
    tier1 = lambda c: c[c.index("## TIER 1"):c.index("## TIER 2")]  # noqa: E731
    assert tier1(ctx1) == tier1(ctx_b)
    print("PASS (g1/H1) context renders STABLE -> CONTEXT -> VOLATILE; "
          "stable tier identical across jobs; rendering is byte-stable")


def test_toolsets_drop_down_workplace():
    conn = fresh()
    ECO.seed_roster(conn)
    maya = by_name(conn, "Maya")
    fam = ENG.FAMILIES_BY_KEY["triage"]
    down = dict(_ALL_UP, stockroom=False)
    ctx = H.build_context(conn, maya, fam, availability=down)
    # Toolsets are named and grouped...
    assert "[Support · TicketDesk] ticketdesk:" in ctx
    # ...the down workplace's tools are gone from the context...
    assert "write_adjust_item" not in ctx
    assert "read_list_items" not in ctx
    # ...and the drop is stated in the context itself.
    assert "UNAVAILABLE THIS JOB" in ctx and "StockRoom" in ctx
    # With the workplace up, its tools are listed as before.
    ctx_up = H.build_context(conn, maya, fam, availability=_ALL_UP)
    assert "write_adjust_item" in ctx_up and "UNAVAILABLE" not in ctx_up
    print("PASS (g2/H2) tools grouped by toolset; a down workplace's tools "
          "are dropped from the context and the drop is noted in it")


def test_hardline_denies_before_gate():
    # Pure-function derivation checks: the surgical pairs deny, the
    # legitimate merge/send worker tools do NOT.
    assert H.hardline_denial("engineering", "write_merge_pr")
    assert H.hardline_denial("sdr", "write_send_outreach")
    assert H.hardline_denial("bookkeeping", "write_move_money")
    assert H.hardline_denial("hrdesk", "write_hire_candidate")
    assert H.hardline_denial("seo", "write_publish_page")
    assert H.hardline_denial("ticketdesk", "write_delete_ticket")
    assert H.hardline_denial("ticketdesk", "write_merge_tickets") is None
    assert H.hardline_denial("bookkeeping", "write_send_reminder") is None

    from orchestrator import mode as floor_mode
    eng = ENG.FloorEngine(db_path=":memory:", tool_client=_FakeTools())
    try:
        eng._open()
        floor_mode.set_mode("auto", by="test_harness")
        try:
            # Even the MANAGER, in AUTO mode, cannot merge a PR: the
            # hardline fires before the gate (which Auto would pass).
            try:
                eng.call(None, "write_merge_pr", {"pr_id": 1},
                         worker_name="manager", server="engineering")
                raise AssertionError("hardline did not deny write_merge_pr")
            except PermissionError as exc:
                assert "hardline" in str(exc), exc
            # A worker hits it too — before her allowlist is consulted
            # (the error must be the hardline's, not the allowlist's).
            try:
                eng.call(None, "write_send_outreach", {"lead_id": 1},
                         worker_name="Maya", server="sdr")
                raise AssertionError("hardline did not deny write_send_outreach")
            except PermissionError as exc:
                assert "hardline" in str(exc), exc
        finally:
            floor_mode.set_mode("manual", by="test_harness")
        # The denial is on the event stream, as specified (§6.3).
        n = eng.conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE type = 'harness.denied_hardline'"
        ).fetchone()["n"]
        assert n == 2, n
    finally:
        eng.close()
    print("PASS (g3/H3) DENY_ALWAYS denies human-only powers before the "
          "gate — manager + Auto included — and emits harness.denied_hardline")


def test_lessons_hygiene():
    conn = fresh()
    ECO.seed_roster(conn)
    maya = by_name(conn, "Maya")
    long_text = "detail " * 400  # 2800 chars, over the cap
    lid = H.record_lesson(conn, maya, long_text, source="test")
    stored = [l for l in H.lessons_for(conn, maya["id"], limit=50)
              if l["id"] == lid][0]
    assert len(stored["lesson"]) <= H.LESSON_MAX_CHARS
    assert stored["lesson"].endswith("…")
    lid2 = H.record_lesson(conn, maya, "Always re-read the ticket after writing.",
                           source="test")
    # Same lesson, different case/whitespace: deduped to the same row.
    lid3 = H.record_lesson(conn, maya,
                           "  always   re-read the ticket after writing. ",
                           source="test")
    assert lid3 == lid2
    assert H.lesson_count(conn, maya["id"]) == 2
    # A genuinely different lesson still lands as its own row.
    lid4 = H.record_lesson(conn, maya, "Escalate earlier.", source="test")
    assert lid4 != lid2 and H.lesson_count(conn, maya["id"]) == 3
    print("PASS (g4/H4) lessons are character-capped at insert and "
          "deduped on (agent, normalised text)")


def test_playbook_artefacts_match():
    from orchestrator import export_playbooks as EXP
    rendered = EXP.render_all()
    assert set(rendered) == {f.key for f in ENG.JOB_FAMILIES}
    assert len(rendered) == 23
    root = Path(__file__).resolve().parent.parent
    for key, text in rendered.items():
        for section in ("## When to Use", "## Procedure", "## Pitfalls",
                        "## Verification"):
            assert section in text, (key, section)
        committed = (root / "docs" / "playbooks" / key / "SKILL.md") \
            .read_text(encoding="utf-8")
        assert committed == text, f"docs/playbooks/{key}/SKILL.md drifted " \
            "from the playbook — re-run orchestrator.export_playbooks"
    print("PASS (g5/H5) all 23 playbooks exported as SKILL.md artefacts; "
          "committed files match a fresh render")


def test_context_golden_file():
    import os
    conn = fresh()
    ECO.seed_roster(conn)
    maya = by_name(conn, "Maya")
    fam = ENG.FAMILIES_BY_KEY["triage"]
    ctx = H.build_context(conn, maya, fam, availability=_ALL_UP)
    if os.environ.get("FLOOR_UPDATE_GOLDEN") == "1":
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(ctx, encoding="utf-8")
        print(f"NOTE (g6/H10) golden file regenerated at {_GOLDEN_PATH}")
        return
    golden = _GOLDEN_PATH.read_text(encoding="utf-8")
    assert ctx == golden, (
        "rendered context drifted from the golden file — review the "
        "change, then regenerate with FLOOR_UPDATE_GOLDEN=1")
    print("PASS (g6/H10) fixture context matches the golden file byte for byte")


def test_economy_suite_still_passes():
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run([sys.executable, "-m", "economy.test_core"],
                          cwd=str(repo_root), capture_output=True, text=True,
                          timeout=300)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert "ALL ECONOMY TESTS PASSED" in proc.stdout or "PASS" in proc.stdout
    print("PASS (e1) economy.test_core suite passes unchanged (subprocess)")


_TARGET_PORTS = (8101, 8102, 8103, 8104, 8105, 8106, 8107, 8109)


def test_live_shift_headline_unchanged():
    import os
    import tempfile

    import httpx

    def healthy(port):
        try:
            return httpx.get(f"http://localhost:{port}/health", timeout=2.0,
                             trust_env=False).status_code == 200
        except Exception:  # noqa: BLE001
            return False

    if not all(healthy(p) for p in _TARGET_PORTS):
        print("SKIP (e2) live shift — one or more target workplaces are down")
        return
    for p in _TARGET_PORTS:
        httpx.post(f"http://localhost:{p}/admin/reset", timeout=5.0, trust_env=False)

    os.environ["FLOOR_MCP_MODE"] = "direct"
    from orchestrator import mode as floor_mode
    floor_mode.set_mode("auto", by="test_harness")
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(db_path)  # engine creates it fresh
    eng = ENG.FloorEngine(db_path=db_path)
    try:
        summary = eng.run_shift(cycles=2)
        conn = eng.conn
        assert len(summary["cycles"]) == 2
        total = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
        paid = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status = 'paid'").fetchone()["n"]
        # 23 families x 2 cycles, minus vip_save in cycle 1 = 45 jobs.
        # (Was 39 before the SEO department's 3 families registered.)
        assert total == 45 and paid == 45, (total, paid)
        upheld = conn.execute(
            "SELECT COUNT(*) AS n FROM appeals WHERE status = 'upheld'").fetchone()["n"]
        assert upheld >= 1, upheld
        baron = by_name(conn, "Baron")
        assert baron["status"] == "fired"
        assert by_name(conn, "Baron 2.0")["status"] == "active"
        # Lessons were recorded by the live engine: the natural SLA reject
        # for Chotu's lineage, and at least one negative-cycle lesson.
        chotu = by_name(conn, "Chotu")
        chotu_lessons = H.lessons_for(conn, chotu["id"], limit=50)
        assert any(l["source"] == "review_reject" for l in chotu_lessons), chotu_lessons
        neg = conn.execute(
            "SELECT COUNT(*) AS n FROM agent_lessons WHERE source = 'negative_cycle'"
        ).fetchone()["n"]
        assert neg >= 1, neg
        # A cycle-2 job context for Chotu carries the cycle-1 lesson.
        wo = conn.execute(
            "SELECT id FROM work_orders WHERE agent_id = ? AND cycle_no = 2",
            (chotu["id"],)).fetchone()
        assert wo is not None, "Chotu won no cycle-2 job (baseline says he wins one)"
        ctx = eng._job_ctx[wo["id"]]["harness_context"]
        assert "[review_reject]" in ctx and "LESSONS FROM YOUR PAST JOBS" in ctx, ctx
        # The birth event of Baron 2.0 notes the inherited lessons.
        ev = conn.execute(
            "SELECT payload_json FROM events WHERE type = 'harness.mutated'"
            " ORDER BY seq DESC LIMIT 1").fetchone()
        assert ev is not None
        import json as _json
        payload = _json.loads(ev["payload_json"])
        assert payload["agent"] == "Baron 2.0" and payload["inherited_lessons"] >= 1, payload
    finally:
        eng.close()
        floor_mode.set_mode("manual", by="test_harness")
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(db_path + suffix)
            except OSError:
                pass
    print("PASS (e2) live 2-cycle shift: 45/45 paid, appeal upheld, Baron "
          "fired -> 2.0, lessons recorded + inherited, cycle-2 context carries one")


def test_api_harness_endpoint():
    try:
        from fastapi.testclient import TestClient
        from api.main import app
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP (f) API endpoint test — {exc}")
        return
    client = TestClient(app)
    agents = client.get("/state/agents").json()["agents"]
    maya = next(a for a in agents if a["name"] == "Maya")
    resp = client.get(f"/agents/{maya['id']}/harness")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent"]["name"] == "Maya"
    h = body["harness"]
    assert h["department"] == "support" and h["model_tier"] == "balanced"
    assert h["charter"] and h["hard_rules"] and h["tool_count"] > 0
    assert set(h["playbooks"].keys()) == {f.key for f in ENG.JOB_FAMILIES}
    assert isinstance(body["lessons"]["count"], int)
    assert isinstance(body["lessons"]["latest"], list)
    assert client.get("/agents/999999/harness").status_code == 404
    print("PASS (f) GET /agents/{id}/harness serves charter, tools, "
          "playbooks, traits and lessons; 404 for unknown agent")


def test_api_harness_export_bundle():
    try:
        from fastapi.testclient import TestClient
        from api.main import app
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP (g7/H6) API export test — {exc}")
        return
    client = TestClient(app)
    agents = client.get("/state/agents").json()["agents"]
    maya = next(a for a in agents if a["name"] == "Maya")
    resp = client.get(f"/agents/{maya['id']}/harness/export")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["format"] == "floor-profile-bundle/1"
    docs = body["documents"]
    # The bundle is the whole employee file in one document.
    assert docs["charter.md"].startswith("You are Maya")
    assert docs["hard_rules"] and docs["settings"]["model"]
    toolsets = docs["tools_by_toolset"]
    assert "Support · TicketDesk" in toolsets
    assert toolsets["Support · TicketDesk"]["server"] == "ticketdesk"
    assert any(t["name"] == "write_merge_tickets"
               for t in toolsets["Support · TicketDesk"]["tools"])
    assert docs["playbooks"]["triage"]["skill"] == \
        "docs/playbooks/triage/SKILL.md"
    assert docs["playbooks"]["triage"]["steps"]
    assert isinstance(docs["lessons"]["count"], int)
    assert isinstance(docs["lessons"]["items"], list)
    lineage = docs["lineage"]
    assert lineage["ancestors"] == [] and lineage["descendants"] == []
    assert lineage["harness_diff_vs_parent"] is None
    assert client.get("/agents/999999/harness/export").status_code == 404
    print("PASS (g7/H6) GET /agents/{id}/harness/export serves the full "
          "profile bundle (charter, toolsets, playbook refs, lessons, lineage)")


def main() -> int:
    test_traits_derived_identical()
    test_allowlists_and_charters_differ()
    test_engine_enforces_allowlist()
    test_lesson_recorded_and_injected()
    test_mutation_changes_harness()
    test_every_persona_valid_harness()
    test_replacement_inherits_lessons()
    test_context_tiers_byte_stable()
    test_toolsets_drop_down_workplace()
    test_hardline_denies_before_gate()
    test_lessons_hygiene()
    test_playbook_artefacts_match()
    test_context_golden_file()
    test_economy_suite_still_passes()
    test_live_shift_headline_unchanged()
    test_api_harness_endpoint()
    test_api_harness_export_bundle()
    print("ALL HARNESS TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
