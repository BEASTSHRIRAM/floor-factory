"""Export every job family's playbook as a SKILL.md artefact (H5).

Hermes treats skills as procedural memory stored as FILES (the
agentskills.io SKILL.md shape: When to Use / Procedure / Pitfalls /
Verification), progressively disclosed and reviewable as artefacts
instead of living only as code constants (research_competitors.md
§6.2/§6.3 H5). This generator renders one SKILL.md per registered job
family into docs/playbooks/<family_key>/SKILL.md, plus an index:

* When to Use  — the family's title + brief (engine.JobFamily).
* Procedure    — the family's base playbook steps
                 (orchestrator.harness.FAMILY_PLAYBOOKS).
* Pitfalls     — the failure modes the deterministic checks catch:
                 every acceptance criterion restated as the rejection
                 it produces, plus explicit warnings already written
                 into the playbook steps themselves (e.g. sla_breach's
                 "a plain comment does NOT count").
* Verification — the deterministic check list itself: the family's
                 acceptance criteria, one Reviewer finding per
                 criterion, recomputed from live workplace state.

Output is deterministic (families in registry order, fixed layout), so
re-running the generator is byte-stable; test_harness asserts the
committed artefacts match a fresh render.

Run:  .venv/bin/python -m orchestrator.export_playbooks
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import engine as ENG  # noqa: E402
from orchestrator import harness as H  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "playbooks"

_PITFALL_MARKERS = ("NOT", "never", "must not", "does not count", "only when")


def _pitfalls(family, steps: list[str]) -> list[str]:
    out: list[str] = []
    for step in steps:
        if any(m in step for m in _PITFALL_MARKERS):
            out.append(f"From the procedure itself: {step}")
    for criterion in family.criteria:
        out.append(f"The Reviewer rejects the job when this does not hold: "
                   f"{criterion}")
    return out


def render_skill(family) -> str:
    """The SKILL.md text for one job family (pure; no I/O)."""
    steps = list(H.FAMILY_PLAYBOOKS.get(family.key)
                 or H._generic_playbook(family))
    lines = [
        "---",
        f"name: floor-{family.key}",
        f"description: {family.title} — THE FLOOR job family "
        f"'{family.key}' ({family.department}, server {family.server}).",
        "---",
        "",
        f"# {family.title}",
        "",
        f"Job family `{family.key}` · department `{family.department}` · "
        f"tool server `{family.server}` · budget ₡{family.budget}.",
        "",
        "## When to Use",
        "",
        family.brief,
        "",
        "## Procedure",
        "",
    ]
    lines.extend(f"{i}. {step}" for i, step in enumerate(steps, start=1))
    lines += ["", "## Pitfalls", ""]
    lines.extend(f"- {p}" for p in _pitfalls(family, steps))
    lines += ["", "## Verification", "",
              "The Reviewer runs deterministic checks against live workplace "
              "state — one finding per acceptance criterion below; a failed "
              "check is an automatic reject, and the failed findings become "
              "the worker's next lesson.", ""]
    lines.extend(f"- {c}" for c in family.criteria)
    lines.append("")
    return "\n".join(lines)


def render_all() -> dict[str, str]:
    """{family_key: SKILL.md text} for every registered job family."""
    return {fam.key: render_skill(fam) for fam in ENG.JOB_FAMILIES}


def render_index(skills: dict[str, str]) -> str:
    lines = [
        "# THE FLOOR — playbook artefacts",
        "",
        "Every job family's playbook, exported as a SKILL.md artefact by "
        "`orchestrator/export_playbooks.py` (H5 — playbooks as reviewable "
        "files, not just code constants). Regenerate with:",
        "",
        "    .venv/bin/python -m orchestrator.export_playbooks",
        "",
        "| Family | Department | Server | Artefact |",
        "|---|---|---|---|",
    ]
    for fam in ENG.JOB_FAMILIES:
        lines.append(f"| {fam.key} — {fam.title} | {fam.department} | "
                     f"{fam.server} | [{fam.key}/SKILL.md]({fam.key}/SKILL.md) |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    skills = render_all()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, text in skills.items():
        folder = OUT_DIR / key
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(text, encoding="utf-8")
    (OUT_DIR / "README.md").write_text(render_index(skills), encoding="utf-8")
    print(f"wrote {len(skills)} SKILL.md artefacts + index to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
