"""ICP rubric for the SDR department — the single source of truth.

The worker's scoring job and the Reviewer's deterministic checks BOTH use
this module: the check recomputes the expected score from the account's
stored firmographics and fails any recorded score that disagrees. A score
is therefore not an opinion — it is a claim about account data, and it is
checkable.

Rubric (max 100):
  size      50-500 employees .................... +30
            20-49 or 501-1000 employees ......... +15
            otherwise ........................... +0
  industry  saas/fintech/ecommerce/logistics/
            healthtech .......................... +25
            edtech/manufacturing (adjacent) ..... +10
            otherwise ........................... +0
  signals   each stored tech/buying signal ...... points per SIGNAL_POINTS,
            total signal points capped at ....... +45

QUALIFY_THRESHOLD: a lead may be qualified only at score >= 60.
"""
from __future__ import annotations

TARGET_INDUSTRIES = {"saas", "fintech", "ecommerce", "logistics", "healthtech"}
ADJACENT_INDUSTRIES = {"edtech", "manufacturing"}

SIGNAL_POINTS = {
    "recent_funding": 15,
    "hiring_sales_team": 15,
    "expanding_new_market": 15,
    "uses_competitor_crm": 10,
    "high_web_engagement": 10,
    "tech_stack_fit": 10,
}
SIGNAL_CAP = 45

# Human phrases that count as "referencing" a signal in an outreach draft.
# The draft check is a deterministic string match against these phrases —
# a draft must mention at least one fact that is true of THIS account.
SIGNAL_PHRASES = {
    "recent_funding": ["funding", "raised", "series a", "series b"],
    "hiring_sales_team": ["hiring", "sales team", "growing your sales"],
    "expanding_new_market": ["expanding", "expansion", "new market"],
    "uses_competitor_crm": ["current crm", "competitor crm", "switching"],
    "high_web_engagement": ["visited", "pricing page", "website"],
    "tech_stack_fit": ["tech stack", "integrat"],
}

QUALIFY_THRESHOLD = 60


def size_points(employee_count: int) -> int:
    if 50 <= employee_count <= 500:
        return 30
    if 20 <= employee_count <= 49 or 501 <= employee_count <= 1000:
        return 15
    return 0


def industry_points(industry: str) -> int:
    ind = (industry or "").strip().lower()
    if ind in TARGET_INDUSTRIES:
        return 25
    if ind in ADJACENT_INDUSTRIES:
        return 10
    return 0


def signal_points(signals: list) -> int:
    return min(SIGNAL_CAP, sum(SIGNAL_POINTS.get(s, 0) for s in signals or []))


def compute_score(account: dict) -> tuple[int, list[str]]:
    """Expected ICP score + human-readable reasons for an account dict
    (keys: employee_count, industry, tech_signals)."""
    size = size_points(int(account.get("employee_count") or 0))
    ind = industry_points(account.get("industry") or "")
    sig = signal_points(account.get("tech_signals") or [])
    reasons = [
        f"size: {account.get('employee_count')} employees -> +{size}",
        f"industry: {account.get('industry')} -> +{ind}",
        f"signals: {', '.join(account.get('tech_signals') or []) or 'none'} -> +{sig}",
    ]
    return size + ind + sig, reasons


def draft_references_signal(draft_text: str, signals: list) -> str | None:
    """Return the first stored signal the draft text references, else None."""
    text = (draft_text or "").lower()
    for signal in signals or []:
        for phrase in SIGNAL_PHRASES.get(signal, []):
            if phrase in text:
                return signal
    return None
