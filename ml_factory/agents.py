"""Experiment agents: personas that bid for experiment jobs.

This is the floor's economy in miniature, implemented as real code
over the campaign store — not hardcoded winners:

  - Every hypothesis becomes a job with a fixed compute budget (cap).
  - Every agent bids on every job: a fee plus a compute estimate.
    Total price = fee + compute estimate.
  - Award uses THE FLOOR's formula, unchanged:
        score = 0.5*(1 - price/cap) + 0.3*(reputation/100) + 0.2*confidence
  - The winner is paid its fee from the job budget when its run is
    accepted by Evaluation; compute actually burned is a separate
    ledger line (wage vs compute, as designed).
  - A discarded experiment writes a lesson into the agent's record;
    reputation moves with verified outcomes.

Each persona has a speciality (a model family). A specialist bids a
lower fee and higher confidence on its own family, and a higher fee /
lower confidence outside it — so the market, not a lookup table,
decides who runs what.
"""
from __future__ import annotations

# The floor's award formula (economy/core.py), reused verbatim in spirit:
#   score = 0.5*(1 - price/cap) + 0.3*(reputation/100) + 0.2*confidence
def bid_score(price: float, cap: float, reputation: float, confidence: float) -> float:
    return 0.5 * (1 - price / cap) + 0.3 * (reputation / 100.0) + 0.2 * confidence


class Agent:
    def __init__(self, agent_id: str, name: str, speciality: str,
                 reputation: float = 50.0):
        self.id = agent_id
        self.name = name
        self.speciality = speciality
        self.reputation = reputation
        self.lessons: list[str] = []
        self.jobs_won = 0
        self.jobs_kept = 0
        self.earnings = 0.0

    def bid(self, job: dict) -> dict:
        family = job["family"]
        specialist = family == self.speciality
        if specialist:
            fee = round(job["cap"] * 0.22, 2)
            compute_estimate = round(job["cap"] * 0.30, 2)
            confidence = 0.85
        else:
            fee = round(job["cap"] * 0.38, 2)
            compute_estimate = round(job["cap"] * 0.42, 2)
            confidence = 0.45
        price = round(fee + compute_estimate, 2)
        return {
            "agent_id": self.id,
            "fee": fee,
            "compute_estimate": compute_estimate,
            "price": price,
            "confidence": confidence,
            "score": round(bid_score(price, job["cap"], self.reputation, confidence), 6),
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "speciality": self.speciality,
            "reputation": round(self.reputation, 2),
            "lessons": list(self.lessons),
            "jobs_won": self.jobs_won, "jobs_kept": self.jobs_kept,
            "earnings": round(self.earnings, 2),
        }


def default_roster() -> list[Agent]:
    return [
        Agent("agent_forester", "Forester", "random_forest"),
        Agent("agent_booster", "Booster", "gradient_boosting"),
        Agent("agent_weaver", "Weaver", "mlp"),
    ]


def award_job(store, job: dict, agents: list[Agent]) -> dict:
    """Collect sealed bids from the whole roster and award by score."""
    bids = [a.bid(job) for a in agents]
    for b in bids:
        store.log("bid.placed", job_id=job["id"], agent_id=b["agent_id"],
                  price=b["price"], fee=b["fee"],
                  compute_estimate=b["compute_estimate"],
                  confidence=b["confidence"], score=b["score"])
    winner = max(bids, key=lambda b: b["score"])
    store.log("job.awarded", job_id=job["id"], agent_id=winner["agent_id"],
              price=winner["price"], score=winner["score"])
    for a in agents:
        if a.id == winner["agent_id"]:
            a.jobs_won += 1
    return winner
