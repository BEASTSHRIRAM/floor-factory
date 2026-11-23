"""Orchestrator: THE FLOOR's shift loop (ARCHITECTURE §3 topology).

engine.FloorEngine runs the full market loop — Manager posts jobs, workers
bid by persona, winners execute through Synapse MCP tools behind a
confirmation gate, deterministic verification drives reviews, blind appeals
re-check criteria, and economy.cycle_close fires/hires. LLM narration is
optional (llm.py); the fallback economy shim lives in shim.py and is used
only if the real economy package cannot be imported.
"""
from .engine import ECONOMY_SOURCE, JOB_FAMILIES, FloorEngine, reset_floor, run_shift

__all__ = ["FloorEngine", "run_shift", "reset_floor", "JOB_FAMILIES", "ECONOMY_SOURCE"]
