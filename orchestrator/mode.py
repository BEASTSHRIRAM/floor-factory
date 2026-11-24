"""THE FLOOR — floor mode: ``manual`` (default) | ``auto``.

The mode is the human's trust dial for the whole floor. It changes ONLY the
write-confirmation flow (ARCHITECTURE §4.3); it never changes what the
agents are allowed to do:

* ``manual`` — every write tool call waits at the confirmation gate for a
  human decision (API: ``POST /approvals/{confirmation_id}``). Unresolved
  writes are denied after ``FLOOR_CONFIRM_TIMEOUT_S``. This is the default.
* ``auto`` — the floor runs fully agentic inside human-set limits (see
  ``docs/MODES.md``): write confirmations auto-approve, and EVERY
  auto-approval is written to the audit trail (a ``confirmation.auto_approved``
  event + the ``tool_calls`` row's ``confirmed_by='auto'``). Nothing is
  silently approved. The auto-run loop additionally enforces a deterministic
  budget cap set by the human — the cap is code, never the LLM.

HARD LIMITS THAT HOLD IN BOTH MODES (mode is an approval-flow switch,
never a capability switch):

* Tool allowlists are unchanged. Tools that do not exist stay nonexistent:
  there is no money-movement tool, no merge tool, and no hire/reject
  decision tool anywhere on this floor — auto mode cannot invent them.
* The deterministic Reviewer checks are unchanged; auto mode approves
  *writes*, it does not grade work.
* Firing/hiring/payroll stay the deterministic economy rules they already
  were; the LLM still never does money math.

State is held server-side in this module (the API process owns it). It is
seeded at boot from the environment and changed at runtime via the API
(``POST /mode``), which emits a ``mode.changed`` event per change:

* ``FLOOR_MODE=manual|auto`` wins if set.
* Else, a legacy ``POLICY_AUTO_APPROVE_WRITES`` that is *explicitly* set
  seeds the initial mode (``true`` -> auto, ``false`` -> manual), so an
  existing deployment's configured behaviour survives the upgrade.
* Else the default is ``manual`` — the safe default. (This deliberately
  changes the old implicit default, under which unset policy env meant
  auto-approve.)

On process restart the mode returns to its env-seeded value; the
``mode.changed`` events in the event log remain the durable record.
"""
from __future__ import annotations

import os
import threading

MODES = ("manual", "auto")

_lock = threading.Lock()
_changed_by = "system"  # who set the current mode most recently


def _initial_mode() -> str:
    env_mode = os.environ.get("FLOOR_MODE", "").strip().lower()
    if env_mode in MODES:
        return env_mode
    policy = os.environ.get("POLICY_AUTO_APPROVE_WRITES")
    if policy is not None:
        return "manual" if policy.strip().lower() in ("false", "0", "no", "off") else "auto"
    return "manual"


_mode = _initial_mode()


def get_mode() -> str:
    """Current floor mode: 'manual' | 'auto'."""
    with _lock:
        return _mode


def set_mode(new_mode: str, by: str = "human") -> tuple[str, str]:
    """Set the floor mode. Returns (previous_mode, new_mode)."""
    global _mode, _changed_by
    new_mode = str(new_mode).strip().lower()
    if new_mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {new_mode!r}")
    with _lock:
        previous = _mode
        _mode = new_mode
        _changed_by = by
        return previous, new_mode


def changed_by() -> str:
    """Who set the current mode ('system' = env-seeded at boot)."""
    with _lock:
        return _changed_by
