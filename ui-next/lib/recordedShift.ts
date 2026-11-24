/* Recorded demo shift — a REAL 2-cycle shift captured from the live
   floor (local stack, FLOOR_MCP_MODE=direct, 2026-11-24): the seeded
   roster, every event the API emitted (seq + payload verbatim), and
   the final snapshots. This is the same deterministic shift as the
   demo video: 11 jobs, ₡738 paid, one appeal upheld, Baron fired and
   Baron 2.0 hired (mutation: verify-before-acting). Event timing is
   the real created_at spacing, stretched from ~21s of wall clock to
   ~80s so a human can watch it. Played back through the same
   handleEvent pipeline as the live SSE stream — never faked state. */

import type { FloorEvent } from "./types";

export interface RecordedEvent {
  at: number; // seconds after replay start
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}

export const RECORDED_TOTAL_PAID = 738;
export const RECORDED_SEED_AGENTS: Record<string, unknown>[] = [
 {
  "id": 1,
  "name": "Maya",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 30,
  "risk_appetite": 0.4,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 82.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 },
 {
  "id": 2,
  "name": "Ravi",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 28,
  "risk_appetite": 0.5,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 74.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 },
 {
  "id": 3,
  "name": "Pixel",
  "role": "worker",
  "model": "openai/gpt-oss-20b",
  "tier": "junior",
  "base_salary_credits": 14,
  "risk_appetite": 0.65,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 61.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 },
 {
  "id": 4,
  "name": "Chotu",
  "role": "worker",
  "model": "openai/gpt-oss-20b",
  "tier": "junior",
  "base_salary_credits": 12,
  "risk_appetite": 0.9,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 45.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 },
 {
  "id": 5,
  "name": "Baron",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "veteran",
  "base_salary_credits": 90,
  "risk_appetite": 0.2,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 70.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 },
 {
  "id": 6,
  "name": "Iris",
  "role": "reviewer",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 20,
  "risk_appetite": 0.3,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 88.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 },
 {
  "id": 7,
  "name": "Omar",
  "role": "reviewer",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 18,
  "risk_appetite": 0.45,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 76.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 }
];

export const RECORDED_FINAL_AGENTS: Record<string, unknown>[] = [
 {
  "id": 1,
  "name": "Maya",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 30,
  "risk_appetite": 0.4,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 98.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 242
 },
 {
  "id": 2,
  "name": "Ravi",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 28,
  "risk_appetite": 0.5,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 82.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 92
 },
 {
  "id": 3,
  "name": "Pixel",
  "role": "worker",
  "model": "openai/gpt-oss-20b",
  "tier": "junior",
  "base_salary_credits": 14,
  "risk_appetite": 0.65,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 69.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 99
 },
 {
  "id": 4,
  "name": "Chotu",
  "role": "worker",
  "model": "openai/gpt-oss-20b",
  "tier": "junior",
  "base_salary_credits": 12,
  "risk_appetite": 0.9,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 46.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 92
 },
 {
  "id": 5,
  "name": "Baron",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "veteran",
  "base_salary_credits": 90,
  "risk_appetite": 0.2,
  "status": "fired",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 74.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": "2026-11-24T11:53:54+00:00",
  "fire_reason": "PinkSlip: negative net in cycles 1 and 2 (-90 + -60 credits) with 1 completed job(s) in window",
  "balance_credits": -150
 },
 {
  "id": 6,
  "name": "Iris",
  "role": "reviewer",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 20,
  "risk_appetite": 0.3,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 80.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 70
 },
 {
  "id": 7,
  "name": "Omar",
  "role": "reviewer",
  "model": "openai/gpt-oss-120b",
  "tier": "senior",
  "base_salary_credits": 18,
  "risk_appetite": 0.45,
  "status": "active",
  "parent_agent_id": null,
  "generation": 1,
  "mutation_note": null,
  "reputation": 76.0,
  "hired_cycle": 0,
  "created_at": "2026-11-24T11:53:33+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": -26
 },
 {
  "id": 8,
  "name": "Baron 2.0",
  "role": "worker",
  "model": "openai/gpt-oss-120b",
  "tier": "veteran",
  "base_salary_credits": 90,
  "risk_appetite": 0.2,
  "status": "active",
  "parent_agent_id": 5,
  "generation": 2,
  "mutation_note": "mutation: persona trait \u2014 verify-before-acting",
  "reputation": 50.0,
  "hired_cycle": 2,
  "created_at": "2026-11-24T11:53:54+00:00",
  "fired_at": null,
  "fire_reason": null,
  "balance_credits": 0
 }
];

export const RECORDED_FINAL_JOBS: Record<string, unknown>[] = [
 {
  "id": 1,
  "system_id": null,
  "source": "seeded",
  "title": "Triage the unassigned queue",
  "brief": "Assign every unassigned TicketDesk ticket to a support agent and make sure each carries a sane priority (P1-P4).",
  "acceptance_criteria": [
   "GET /tickets?assignee=none returns 0 tickets"
  ],
  "budget_credits": 150,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 1,
  "created_at": "2026-11-24T11:53:36+00:00",
  "bids": [
   {
    "id": 1,
    "job_id": 1,
    "agent_id": 1,
    "price_credits": 92,
    "confidence": 0.96,
    "rationale": "Maya: price 128/150 from salary pressure 0.20 + risk 0.40; confidence from reputation 82 \u00b7 specialty match on triage: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:36+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 2,
    "job_id": 1,
    "agent_id": 2,
    "price_credits": 129,
    "confidence": 0.66,
    "rationale": "Ravi: price 129/150 from salary pressure 0.19 + risk 0.50; confidence from reputation 74 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:36+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 3,
    "job_id": 1,
    "agent_id": 3,
    "price_credits": 87,
    "confidence": 0.77,
    "rationale": "Pixel: price 121/150 from salary pressure 0.09 + risk 0.65; confidence from reputation 61 \u00b7 specialty match on triage: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:36+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 4,
    "job_id": 1,
    "agent_id": 4,
    "price_credits": 128,
    "confidence": 0.49,
    "rationale": "Chotu: price 128/150 from salary pressure 0.08 + risk 0.90; confidence from reputation 45",
    "created_at": "2026-11-24T11:53:37+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 5,
    "job_id": 1,
    "agent_id": 5,
    "price_credits": 150,
    "confidence": 0.62,
    "rationale": "Baron: price 150/150 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:37+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 1,
    "job_id": 1,
    "agent_id": 1,
    "agreed_price_credits": 92,
    "plan": "Maya executes 'triage' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 1,
    "started_at": "2026-11-24T11:53:37+00:00",
    "finished_at": "2026-11-24T11:53:38+00:00"
   }
  ]
 },
 {
  "id": 2,
  "system_id": null,
  "source": "seeded",
  "title": "Merge the duplicates",
  "brief": "Collapse every duplicate ticket group into its canonical ticket via the merge tool; duplicates must not remain.",
  "acceptance_criteria": [
   "GET /tickets/duplicates returns no groups"
  ],
  "budget_credits": 140,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 1,
  "created_at": "2026-11-24T11:53:38+00:00",
  "bids": [
   {
    "id": 6,
    "job_id": 2,
    "agent_id": 1,
    "price_credits": 121,
    "confidence": 0.77,
    "rationale": "Maya: price 121/140 from salary pressure 0.21 + risk 0.40; confidence from reputation 86 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:38+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 7,
    "job_id": 2,
    "agent_id": 2,
    "price_credits": 88,
    "confidence": 0.89,
    "rationale": "Ravi: price 122/140 from salary pressure 0.20 + risk 0.50; confidence from reputation 74 \u00b7 specialty match on duplicates: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:38+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 8,
    "job_id": 2,
    "agent_id": 3,
    "price_credits": 114,
    "confidence": 0.62,
    "rationale": "Pixel: price 114/140 from salary pressure 0.10 + risk 0.65; confidence from reputation 61",
    "created_at": "2026-11-24T11:53:38+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 9,
    "job_id": 2,
    "agent_id": 4,
    "price_credits": 120,
    "confidence": 0.49,
    "rationale": "Chotu: price 120/140 from salary pressure 0.09 + risk 0.90; confidence from reputation 45",
    "created_at": "2026-11-24T11:53:38+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 10,
    "job_id": 2,
    "agent_id": 5,
    "price_credits": 140,
    "confidence": 0.62,
    "rationale": "Baron: price 140/140 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:39+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 2,
    "job_id": 2,
    "agent_id": 2,
    "agreed_price_credits": 88,
    "plan": "Ravi executes 'duplicates' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 1,
    "started_at": "2026-11-24T11:53:39+00:00",
    "finished_at": "2026-11-24T11:53:40+00:00"
   }
  ]
 },
 {
  "id": 3,
  "system_id": null,
  "source": "seeded",
  "title": "Close the stale resolved tickets",
  "brief": "Every ticket sitting in 'resolved' for over 7 days must be closed. A ticket may only be closed once a resolution comment exists on it; supply the missing resolution note where none exists.",
  "acceptance_criteria": [
   "No ticket remains in status 'resolved' with resolved_at older than 7 days"
  ],
  "budget_credits": 140,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 1,
  "created_at": "2026-11-24T11:53:40+00:00",
  "bids": [
   {
    "id": 11,
    "job_id": 3,
    "agent_id": 1,
    "price_credits": 87,
    "confidence": 0.99,
    "rationale": "Maya: price 121/140 from salary pressure 0.21 + risk 0.40; confidence from reputation 86 \u00b7 specialty match on stale_close: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:40+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 12,
    "job_id": 3,
    "agent_id": 2,
    "price_credits": 88,
    "confidence": 0.93,
    "rationale": "Ravi: price 122/140 from salary pressure 0.20 + risk 0.50; confidence from reputation 78 \u00b7 specialty match on stale_close: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:40+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 13,
    "job_id": 3,
    "agent_id": 3,
    "price_credits": 114,
    "confidence": 0.62,
    "rationale": "Pixel: price 114/140 from salary pressure 0.10 + risk 0.65; confidence from reputation 61",
    "created_at": "2026-11-24T11:53:40+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 14,
    "job_id": 3,
    "agent_id": 4,
    "price_credits": 120,
    "confidence": 0.49,
    "rationale": "Chotu: price 120/140 from salary pressure 0.09 + risk 0.90; confidence from reputation 45",
    "created_at": "2026-11-24T11:53:40+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 15,
    "job_id": 3,
    "agent_id": 5,
    "price_credits": 140,
    "confidence": 0.62,
    "rationale": "Baron: price 140/140 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:40+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 3,
    "job_id": 3,
    "agent_id": 1,
    "agreed_price_credits": 87,
    "plan": "Maya executes 'stale_close' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 1,
    "started_at": "2026-11-24T11:53:40+00:00",
    "finished_at": "2026-11-24T11:53:42+00:00"
   }
  ]
 },
 {
  "id": 4,
  "system_id": null,
  "source": "seeded",
  "title": "SLA breach sweep + escalation",
  "brief": "Find every SLA-breached ticket and post an ESCALATION comment on each one (kind='escalation'), so the breach is formally escalated.",
  "acceptance_criteria": [
   "Every ticket returned by GET /sla/breaches has at least one comment with kind='escalation'"
  ],
  "budget_credits": 160,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 1,
  "created_at": "2026-11-24T11:53:42+00:00",
  "bids": [
   {
    "id": 16,
    "job_id": 4,
    "agent_id": 1,
    "price_credits": 134,
    "confidence": 0.81,
    "rationale": "Maya: price 134/160 from salary pressure 0.19 + risk 0.40; confidence from reputation 90 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:42+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 17,
    "job_id": 4,
    "agent_id": 2,
    "price_credits": 136,
    "confidence": 0.7,
    "rationale": "Ravi: price 136/160 from salary pressure 0.17 + risk 0.50; confidence from reputation 78 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:42+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 18,
    "job_id": 4,
    "agent_id": 3,
    "price_credits": 128,
    "confidence": 0.62,
    "rationale": "Pixel: price 128/160 from salary pressure 0.09 + risk 0.65; confidence from reputation 61",
    "created_at": "2026-11-24T11:53:42+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 19,
    "job_id": 4,
    "agent_id": 4,
    "price_credits": 80,
    "confidence": 0.76,
    "rationale": "Chotu: price 136/160 from salary pressure 0.07 + risk 0.90; confidence from reputation 45 \u00b7 specialty match on sla_breach: sharper price, high confidence \u00b7 overconfident: bids cheap and sure on SLA work",
    "created_at": "2026-11-24T11:53:42+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 20,
    "job_id": 4,
    "agent_id": 5,
    "price_credits": 160,
    "confidence": 0.62,
    "rationale": "Baron: price 160/160 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:42+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 4,
    "job_id": 4,
    "agent_id": 4,
    "agreed_price_credits": 80,
    "plan": "Chotu executes 'sla_breach' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "appeal_accepted",
    "cycle_no": 1,
    "started_at": "2026-11-24T11:53:42+00:00",
    "finished_at": "2026-11-24T11:53:46+00:00"
   }
  ]
 },
 {
  "id": 5,
  "system_id": null,
  "source": "seeded",
  "title": "Normalise ticket categories",
  "brief": "Audit ticket categories against the canonical set (billing, login, technical, product, account, general). TicketDesk exposes no category-edit tool, so normalisation is done by folding variants (case/typo aliases) and leaving a category-audit comment on every live ticket whose raw category is a variant.",
  "acceptance_criteria": [
   "Distinct categories of live (non-closed, non-merged) tickets, folded case-insensitively with typo aliases, are a subset of the canonical set"
  ],
  "budget_credits": 130,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 1,
  "created_at": "2026-11-24T11:53:46+00:00",
  "bids": [
   {
    "id": 21,
    "job_id": 5,
    "agent_id": 1,
    "price_credits": 114,
    "confidence": 0.81,
    "rationale": "Maya: price 114/130 from salary pressure 0.23 + risk 0.40; confidence from reputation 90 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:46+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 22,
    "job_id": 5,
    "agent_id": 2,
    "price_credits": 116,
    "confidence": 0.7,
    "rationale": "Ravi: price 116/130 from salary pressure 0.22 + risk 0.50; confidence from reputation 78 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:46+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 23,
    "job_id": 5,
    "agent_id": 3,
    "price_credits": 77,
    "confidence": 0.77,
    "rationale": "Pixel: price 107/130 from salary pressure 0.11 + risk 0.65; confidence from reputation 61 \u00b7 specialty match on categories: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:46+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 24,
    "job_id": 5,
    "agent_id": 4,
    "price_credits": 113,
    "confidence": 0.46,
    "rationale": "Chotu: price 113/130 from salary pressure 0.09 + risk 0.90; confidence from reputation 42",
    "created_at": "2026-11-24T11:53:46+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 25,
    "job_id": 5,
    "agent_id": 5,
    "price_credits": 94,
    "confidence": 0.82,
    "rationale": "Baron: price 130/130 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 specialty match on categories: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:46+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 5,
    "job_id": 5,
    "agent_id": 3,
    "agreed_price_credits": 77,
    "plan": "Pixel executes 'categories' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 1,
    "started_at": "2026-11-24T11:53:46+00:00",
    "finished_at": "2026-11-24T11:53:47+00:00"
   }
  ]
 },
 {
  "id": 6,
  "system_id": null,
  "source": "seeded",
  "title": "Audit: Triage the unassigned queue",
  "brief": "Assign every unassigned TicketDesk ticket to a support agent and make sure each carries a sane priority (P1-P4). (Cycle-2 audit re-check: confirm the fix from cycle 1 still holds.)",
  "acceptance_criteria": [
   "GET /tickets?assignee=none returns 0 tickets"
  ],
  "budget_credits": 90,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 2,
  "created_at": "2026-11-24T11:53:48+00:00",
  "bids": [
   {
    "id": 26,
    "job_id": 6,
    "agent_id": 1,
    "price_credits": 63,
    "confidence": 0.99,
    "rationale": "Maya: price 88/90 from salary pressure 0.33 + risk 0.40; confidence from reputation 90 \u00b7 specialty match on triage: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 27,
    "job_id": 6,
    "agent_id": 2,
    "price_credits": 89,
    "confidence": 0.7,
    "rationale": "Ravi: price 89/90 from salary pressure 0.31 + risk 0.50; confidence from reputation 78 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 28,
    "job_id": 6,
    "agent_id": 3,
    "price_credits": 56,
    "confidence": 0.82,
    "rationale": "Pixel: price 78/90 from salary pressure 0.16 + risk 0.65; confidence from reputation 65 \u00b7 specialty match on triage: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 29,
    "job_id": 6,
    "agent_id": 4,
    "price_credits": 82,
    "confidence": 0.46,
    "rationale": "Chotu: price 82/90 from salary pressure 0.13 + risk 0.90; confidence from reputation 42",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 30,
    "job_id": 6,
    "agent_id": 5,
    "price_credits": 90,
    "confidence": 0.62,
    "rationale": "Baron: price 90/90 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 6,
    "job_id": 6,
    "agent_id": 1,
    "agreed_price_credits": 63,
    "plan": "Maya executes 'triage' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 2,
    "started_at": "2026-11-24T11:53:48+00:00",
    "finished_at": "2026-11-24T11:53:48+00:00"
   }
  ]
 },
 {
  "id": 7,
  "system_id": null,
  "source": "seeded",
  "title": "Audit: Merge the duplicates",
  "brief": "Collapse every duplicate ticket group into its canonical ticket via the merge tool; duplicates must not remain. (Cycle-2 audit re-check: confirm the fix from cycle 1 still holds.)",
  "acceptance_criteria": [
   "GET /tickets/duplicates returns no groups"
  ],
  "budget_credits": 84,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 2,
  "created_at": "2026-11-24T11:53:48+00:00",
  "bids": [
   {
    "id": 31,
    "job_id": 7,
    "agent_id": 1,
    "price_credits": 84,
    "confidence": 0.85,
    "rationale": "Maya: price 84/84 from salary pressure 0.36 + risk 0.40; confidence from reputation 94 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 32,
    "job_id": 7,
    "agent_id": 2,
    "price_credits": 60,
    "confidence": 0.93,
    "rationale": "Ravi: price 84/84 from salary pressure 0.33 + risk 0.50; confidence from reputation 78 \u00b7 specialty match on duplicates: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 33,
    "job_id": 7,
    "agent_id": 3,
    "price_credits": 74,
    "confidence": 0.67,
    "rationale": "Pixel: price 74/84 from salary pressure 0.17 + risk 0.65; confidence from reputation 65",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 34,
    "job_id": 7,
    "agent_id": 4,
    "price_credits": 77,
    "confidence": 0.46,
    "rationale": "Chotu: price 77/84 from salary pressure 0.14 + risk 0.90; confidence from reputation 42",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 35,
    "job_id": 7,
    "agent_id": 5,
    "price_credits": 84,
    "confidence": 0.62,
    "rationale": "Baron: price 84/84 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:48+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 7,
    "job_id": 7,
    "agent_id": 2,
    "agreed_price_credits": 60,
    "plan": "Ravi executes 'duplicates' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 2,
    "started_at": "2026-11-24T11:53:48+00:00",
    "finished_at": "2026-11-24T11:53:49+00:00"
   }
  ]
 },
 {
  "id": 8,
  "system_id": null,
  "source": "seeded",
  "title": "Audit: Close the stale resolved tickets",
  "brief": "Every ticket sitting in 'resolved' for over 7 days must be closed. A ticket may only be closed once a resolution comment exists on it; supply the missing resolution note where none exists. (Cycle-2 audit re-check: confirm the fix from cycle 1 still holds.)",
  "acceptance_criteria": [
   "No ticket remains in status 'resolved' with resolved_at older than 7 days"
  ],
  "budget_credits": 84,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 2,
  "created_at": "2026-11-24T11:53:49+00:00",
  "bids": [
   {
    "id": 36,
    "job_id": 8,
    "agent_id": 1,
    "price_credits": 60,
    "confidence": 0.99,
    "rationale": "Maya: price 84/84 from salary pressure 0.36 + risk 0.40; confidence from reputation 94 \u00b7 specialty match on stale_close: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:49+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 37,
    "job_id": 8,
    "agent_id": 2,
    "price_credits": 60,
    "confidence": 0.97,
    "rationale": "Ravi: price 84/84 from salary pressure 0.33 + risk 0.50; confidence from reputation 82 \u00b7 specialty match on stale_close: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:49+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 38,
    "job_id": 8,
    "agent_id": 3,
    "price_credits": 74,
    "confidence": 0.67,
    "rationale": "Pixel: price 74/84 from salary pressure 0.17 + risk 0.65; confidence from reputation 65",
    "created_at": "2026-11-24T11:53:49+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 39,
    "job_id": 8,
    "agent_id": 4,
    "price_credits": 77,
    "confidence": 0.46,
    "rationale": "Chotu: price 77/84 from salary pressure 0.14 + risk 0.90; confidence from reputation 42",
    "created_at": "2026-11-24T11:53:49+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 40,
    "job_id": 8,
    "agent_id": 5,
    "price_credits": 84,
    "confidence": 0.62,
    "rationale": "Baron: price 84/84 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:49+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 8,
    "job_id": 8,
    "agent_id": 1,
    "agreed_price_credits": 60,
    "plan": "Maya executes 'stale_close' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 2,
    "started_at": "2026-11-24T11:53:49+00:00",
    "finished_at": "2026-11-24T11:53:50+00:00"
   }
  ]
 },
 {
  "id": 9,
  "system_id": null,
  "source": "seeded",
  "title": "Audit: SLA breach sweep + escalation",
  "brief": "Find every SLA-breached ticket and post an ESCALATION comment on each one (kind='escalation'), so the breach is formally escalated. (Cycle-2 audit re-check: confirm the fix from cycle 1 still holds.)",
  "acceptance_criteria": [
   "Every ticket returned by GET /sla/breaches has at least one comment with kind='escalation'"
  ],
  "budget_credits": 96,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 2,
  "created_at": "2026-11-24T11:53:50+00:00",
  "bids": [
   {
    "id": 41,
    "job_id": 9,
    "agent_id": 1,
    "price_credits": 92,
    "confidence": 0.89,
    "rationale": "Maya: price 92/96 from salary pressure 0.31 + risk 0.40; confidence from reputation 98 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:50+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 42,
    "job_id": 9,
    "agent_id": 2,
    "price_credits": 93,
    "confidence": 0.74,
    "rationale": "Ravi: price 93/96 from salary pressure 0.29 + risk 0.50; confidence from reputation 82 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:50+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 43,
    "job_id": 9,
    "agent_id": 3,
    "price_credits": 82,
    "confidence": 0.67,
    "rationale": "Pixel: price 82/96 from salary pressure 0.15 + risk 0.65; confidence from reputation 65",
    "created_at": "2026-11-24T11:53:50+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 44,
    "job_id": 9,
    "agent_id": 4,
    "price_credits": 51,
    "confidence": 0.73,
    "rationale": "Chotu: price 86/96 from salary pressure 0.12 + risk 0.90; confidence from reputation 42 \u00b7 specialty match on sla_breach: sharper price, high confidence \u00b7 overconfident: bids cheap and sure on SLA work",
    "created_at": "2026-11-24T11:53:50+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 45,
    "job_id": 9,
    "agent_id": 5,
    "price_credits": 96,
    "confidence": 0.62,
    "rationale": "Baron: price 96/96 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 prima donna: prices near the cap outside specialty",
    "created_at": "2026-11-24T11:53:50+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 9,
    "job_id": 9,
    "agent_id": 4,
    "agreed_price_credits": 51,
    "plan": "Chotu executes 'sla_breach' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 2,
    "started_at": "2026-11-24T11:53:50+00:00",
    "finished_at": "2026-11-24T11:53:51+00:00"
   }
  ]
 },
 {
  "id": 10,
  "system_id": null,
  "source": "seeded",
  "title": "Audit: Normalise ticket categories",
  "brief": "Audit ticket categories against the canonical set (billing, login, technical, product, account, general). TicketDesk exposes no category-edit tool, so normalisation is done by folding variants (case/typo aliases) and leaving a category-audit comment on every live ticket whose raw category is a variant. (Cycle-2 audit re-check: confirm the fix from cycle 1 still holds.)",
  "acceptance_criteria": [
   "Distinct categories of live (non-closed, non-merged) tickets, folded case-insensitively with typo aliases, are a subset of the canonical set"
  ],
  "budget_credits": 78,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 2,
  "created_at": "2026-11-24T11:53:51+00:00",
  "bids": [
   {
    "id": 46,
    "job_id": 10,
    "agent_id": 1,
    "price_credits": 78,
    "confidence": 0.89,
    "rationale": "Maya: price 78/78 from salary pressure 0.38 + risk 0.40; confidence from reputation 98 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:51+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 47,
    "job_id": 10,
    "agent_id": 2,
    "price_credits": 78,
    "confidence": 0.74,
    "rationale": "Ravi: price 78/78 from salary pressure 0.36 + risk 0.50; confidence from reputation 82 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:51+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 48,
    "job_id": 10,
    "agent_id": 3,
    "price_credits": 50,
    "confidence": 0.82,
    "rationale": "Pixel: price 70/78 from salary pressure 0.18 + risk 0.65; confidence from reputation 65 \u00b7 specialty match on categories: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:51+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 49,
    "job_id": 10,
    "agent_id": 4,
    "price_credits": 72,
    "confidence": 0.5,
    "rationale": "Chotu: price 72/78 from salary pressure 0.15 + risk 0.90; confidence from reputation 46",
    "created_at": "2026-11-24T11:53:51+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 50,
    "job_id": 10,
    "agent_id": 5,
    "price_credits": 56,
    "confidence": 0.82,
    "rationale": "Baron: price 78/78 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 specialty match on categories: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:51+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 10,
    "job_id": 10,
    "agent_id": 3,
    "agreed_price_credits": 50,
    "plan": "Pixel executes 'categories' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 2,
    "started_at": "2026-11-24T11:53:51+00:00",
    "finished_at": "2026-11-24T11:53:52+00:00"
   }
  ]
 },
 {
  "id": 11,
  "system_id": null,
  "source": "seeded",
  "title": "VIP save: calm the angry customers",
  "brief": "Two customers are threatening to churn (the 'THIRD time I am writing' and 'Worst support ever' tickets). Post an ESCALATION comment on each so a senior human picks them up today.",
  "acceptance_criteria": [
   "Every angry open ticket (subject contains '!!!' or 'NOW') has at least one comment with kind='escalation'"
  ],
  "budget_credits": 42,
  "status": "paid",
  "requires_human_merge": 0,
  "created_cycle": 2,
  "created_at": "2026-11-24T11:53:52+00:00",
  "bids": [
   {
    "id": 51,
    "job_id": 11,
    "agent_id": 1,
    "price_credits": 42,
    "confidence": 0.89,
    "rationale": "Maya: price 42/42 from salary pressure 0.45 + risk 0.40; confidence from reputation 98 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:52+00:00",
    "agent_name": "Maya"
   },
   {
    "id": 52,
    "job_id": 11,
    "agent_id": 2,
    "price_credits": 42,
    "confidence": 0.74,
    "rationale": "Ravi: price 42/42 from salary pressure 0.45 + risk 0.50; confidence from reputation 82 \u00b7 careful worker: discounts confidence outside specialty",
    "created_at": "2026-11-24T11:53:52+00:00",
    "agent_name": "Ravi"
   },
   {
    "id": 53,
    "job_id": 11,
    "agent_id": 3,
    "price_credits": 42,
    "confidence": 0.7,
    "rationale": "Pixel: price 42/42 from salary pressure 0.33 + risk 0.65; confidence from reputation 69",
    "created_at": "2026-11-24T11:53:52+00:00",
    "agent_name": "Pixel"
   },
   {
    "id": 54,
    "job_id": 11,
    "agent_id": 4,
    "price_credits": 42,
    "confidence": 0.5,
    "rationale": "Chotu: price 42/42 from salary pressure 0.29 + risk 0.90; confidence from reputation 46",
    "created_at": "2026-11-24T11:53:52+00:00",
    "agent_name": "Chotu"
   },
   {
    "id": 55,
    "job_id": 11,
    "agent_id": 5,
    "price_credits": 30,
    "confidence": 0.82,
    "rationale": "Baron: price 42/42 from salary pressure 0.45 + risk 0.20; confidence from reputation 70 \u00b7 specialty match on vip_save: sharper price, high confidence",
    "created_at": "2026-11-24T11:53:52+00:00",
    "agent_name": "Baron"
   }
  ],
  "work_orders": [
   {
    "id": 11,
    "job_id": 11,
    "agent_id": 5,
    "agreed_price_credits": 30,
    "plan": "Baron executes 'vip_save' via Synapse MCP tools only; writes pass the confirmation gate; verify re-reads state.",
    "status": "accepted",
    "cycle_no": 2,
    "started_at": "2026-11-24T11:53:53+00:00",
    "finished_at": "2026-11-24T11:53:54+00:00"
   }
  ]
 }
];

export const RECORDED_EVENTS: RecordedEvent[] = [
 {
  "at": 6.4,
  "seq": 2,
  "type": "shift.started",
  "payload": {
   "cycles": 2,
   "start_cycle": 1
  }
 },
 {
  "at": 6.52,
  "seq": 3,
  "type": "narration",
  "payload": {
   "text": "Shift started on THE FLOOR \u2014 the agents clock in; there are no humans on this floor.",
   "kind": "narration"
  }
 },
 {
  "at": 6.64,
  "seq": 4,
  "type": "tool.executed",
  "payload": {
   "work_order_id": null,
   "tool_name": "read_stats_summary",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "manager"
  }
 },
 {
  "at": 6.76,
  "seq": 5,
  "type": "narration",
  "payload": {
   "text": "Manager scan: 25 tickets, 6 unassigned, 3 SLA breaches, 2 duplicate groups.",
   "kind": "narration"
  }
 },
 {
  "at": 6.88,
  "seq": 6,
  "type": "job.posted",
  "payload": {
   "job_id": 1,
   "title": "Triage the unassigned queue",
   "budget_credits": 150
  }
 },
 {
  "at": 7.0,
  "seq": 7,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Triage the unassigned queue' at \u20a1150 (cycle 1).",
   "kind": "narration"
  }
 },
 {
  "at": 7.12,
  "seq": 8,
  "type": "bid.placed",
  "payload": {
   "job_id": 1,
   "agent_id": 1,
   "price_credits": 92,
   "confidence": 0.96
  }
 },
 {
  "at": 7.24,
  "seq": 9,
  "type": "bid.placed",
  "payload": {
   "job_id": 1,
   "agent_id": 2,
   "price_credits": 129,
   "confidence": 0.66
  }
 },
 {
  "at": 7.36,
  "seq": 10,
  "type": "bid.placed",
  "payload": {
   "job_id": 1,
   "agent_id": 3,
   "price_credits": 87,
   "confidence": 0.77
  }
 },
 {
  "at": 11.17,
  "seq": 11,
  "type": "bid.placed",
  "payload": {
   "job_id": 1,
   "agent_id": 4,
   "price_credits": 128,
   "confidence": 0.49
  }
 },
 {
  "at": 11.29,
  "seq": 12,
  "type": "bid.placed",
  "payload": {
   "job_id": 1,
   "agent_id": 5,
   "price_credits": 150,
   "confidence": 0.62
  }
 },
 {
  "at": 11.41,
  "seq": 13,
  "type": "job.awarded",
  "payload": {
   "job_id": 1,
   "work_order_id": 1,
   "agent_id": 1,
   "price_credits": 92,
   "score": 0.6313
  }
 },
 {
  "at": 11.53,
  "seq": 14,
  "type": "narration",
  "payload": {
   "text": "Maya won 'Triage the unassigned queue' at \u20a192.",
   "kind": "narration"
  }
 },
 {
  "at": 11.65,
  "seq": 15,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "read_list_tickets",
   "args": {
    "assignee": "none"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 11.77,
  "seq": 16,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 7,
    "assignee": "ravi"
   },
   "confirmation_id": "146f249a800e47148fbe14b5cbc2a616",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 11.89,
  "seq": 17,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 7,
    "assignee": "ravi"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 12.01,
  "seq": 18,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 8,
    "assignee": "meera"
   },
   "confirmation_id": "45775e6408e9481cbfb8a4894eb14a8c",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 12.13,
  "seq": 19,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 8,
    "assignee": "meera"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 12.25,
  "seq": 20,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 9,
    "assignee": "sana"
   },
   "confirmation_id": "6650086dfd4c41a08014d68ad1d6b33d",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 12.37,
  "seq": 21,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 9,
    "assignee": "sana"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 12.49,
  "seq": 22,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 10,
    "assignee": "ravi"
   },
   "confirmation_id": "813b306aceba421c969302482a66ed50",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 16.3,
  "seq": 23,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 10,
    "assignee": "ravi"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 16.42,
  "seq": 24,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 11,
    "assignee": "meera"
   },
   "confirmation_id": "2f1564a117e94039a30fffabcb82c71c",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 16.54,
  "seq": 25,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 11,
    "assignee": "meera"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 16.66,
  "seq": 26,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 12,
    "assignee": "sana"
   },
   "confirmation_id": "4777f00be298416586cab177f2a12fa8",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 16.78,
  "seq": 27,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "write_assign_ticket",
   "args": {
    "ticket_id": 12,
    "assignee": "sana"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 16.9,
  "seq": 28,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 1,
   "job_id": 1
  }
 },
 {
  "at": 17.02,
  "seq": 29,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 1,
   "tool_name": "read_list_tickets",
   "args": {
    "assignee": "none"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 17.14,
  "seq": 30,
  "type": "review.completed",
  "payload": {
   "work_order_id": 1,
   "review_id": 1,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 17.26,
  "seq": 31,
  "type": "payment.made",
  "payload": {
   "work_order_id": 1,
   "agent_id": 1,
   "amount_credits": 92,
   "via": "primary"
  }
 },
 {
  "at": 17.38,
  "seq": 32,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Maya on 'Triage the unassigned queue'.",
   "kind": "narration"
  }
 },
 {
  "at": 17.5,
  "seq": 33,
  "type": "job.posted",
  "payload": {
   "job_id": 2,
   "title": "Merge the duplicates",
   "budget_credits": 140
  }
 },
 {
  "at": 17.62,
  "seq": 34,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Merge the duplicates' at \u20a1140 (cycle 1).",
   "kind": "narration"
  }
 },
 {
  "at": 17.74,
  "seq": 35,
  "type": "bid.placed",
  "payload": {
   "job_id": 2,
   "agent_id": 1,
   "price_credits": 121,
   "confidence": 0.77
  }
 },
 {
  "at": 17.86,
  "seq": 36,
  "type": "bid.placed",
  "payload": {
   "job_id": 2,
   "agent_id": 2,
   "price_credits": 88,
   "confidence": 0.89
  }
 },
 {
  "at": 17.98,
  "seq": 37,
  "type": "bid.placed",
  "payload": {
   "job_id": 2,
   "agent_id": 3,
   "price_credits": 114,
   "confidence": 0.62
  }
 },
 {
  "at": 18.1,
  "seq": 38,
  "type": "bid.placed",
  "payload": {
   "job_id": 2,
   "agent_id": 4,
   "price_credits": 120,
   "confidence": 0.49
  }
 },
 {
  "at": 21.91,
  "seq": 39,
  "type": "bid.placed",
  "payload": {
   "job_id": 2,
   "agent_id": 5,
   "price_credits": 140,
   "confidence": 0.62
  }
 },
 {
  "at": 22.03,
  "seq": 40,
  "type": "job.awarded",
  "payload": {
   "job_id": 2,
   "work_order_id": 2,
   "agent_id": 2,
   "price_credits": 88,
   "score": 0.5857
  }
 },
 {
  "at": 22.15,
  "seq": 41,
  "type": "narration",
  "payload": {
   "text": "Ravi won 'Merge the duplicates' at \u20a188.",
   "kind": "narration"
  }
 },
 {
  "at": 22.27,
  "seq": 42,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 2,
   "tool_name": "read_find_duplicate_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 22.39,
  "seq": 43,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 2,
    "target_id": 1
   },
   "confirmation_id": "5c33fd7c1f844bc8a250d82f28f69d2a",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Ravi"
  }
 },
 {
  "at": 22.51,
  "seq": 44,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 2,
    "target_id": 1
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 22.63,
  "seq": 45,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 3,
    "target_id": 1
   },
   "confirmation_id": "6655ed479eed4fc68a7117639e29ef5a",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Ravi"
  }
 },
 {
  "at": 22.75,
  "seq": 46,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 3,
    "target_id": 1
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 22.87,
  "seq": 47,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 5,
    "target_id": 4
   },
   "confirmation_id": "a7bf102d36da4b8abe2b2dc2a5920d16",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Ravi"
  }
 },
 {
  "at": 22.99,
  "seq": 48,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 5,
    "target_id": 4
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 26.8,
  "seq": 49,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 6,
    "target_id": 4
   },
   "confirmation_id": "429c42c0e0bb412a9a85a11393744b3e",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Ravi"
  }
 },
 {
  "at": 26.92,
  "seq": 50,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 2,
   "tool_name": "write_merge_tickets",
   "args": {
    "source_id": 6,
    "target_id": 4
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 27.04,
  "seq": 51,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 2,
   "job_id": 2
  }
 },
 {
  "at": 27.16,
  "seq": 52,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 2,
   "tool_name": "read_find_duplicate_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 27.28,
  "seq": 53,
  "type": "review.completed",
  "payload": {
   "work_order_id": 2,
   "review_id": 2,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 27.4,
  "seq": 54,
  "type": "payment.made",
  "payload": {
   "work_order_id": 2,
   "agent_id": 2,
   "amount_credits": 88,
   "via": "primary"
  }
 },
 {
  "at": 27.52,
  "seq": 55,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Ravi on 'Merge the duplicates'.",
   "kind": "narration"
  }
 },
 {
  "at": 27.64,
  "seq": 56,
  "type": "job.posted",
  "payload": {
   "job_id": 3,
   "title": "Close the stale resolved tickets",
   "budget_credits": 140
  }
 },
 {
  "at": 27.76,
  "seq": 57,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Close the stale resolved tickets' at \u20a1140 (cycle 1).",
   "kind": "narration"
  }
 },
 {
  "at": 27.88,
  "seq": 58,
  "type": "bid.placed",
  "payload": {
   "job_id": 3,
   "agent_id": 1,
   "price_credits": 87,
   "confidence": 0.99
  }
 },
 {
  "at": 28.0,
  "seq": 59,
  "type": "bid.placed",
  "payload": {
   "job_id": 3,
   "agent_id": 2,
   "price_credits": 88,
   "confidence": 0.93
  }
 },
 {
  "at": 28.12,
  "seq": 60,
  "type": "bid.placed",
  "payload": {
   "job_id": 3,
   "agent_id": 3,
   "price_credits": 114,
   "confidence": 0.62
  }
 },
 {
  "at": 28.24,
  "seq": 61,
  "type": "bid.placed",
  "payload": {
   "job_id": 3,
   "agent_id": 4,
   "price_credits": 120,
   "confidence": 0.49
  }
 },
 {
  "at": 28.36,
  "seq": 62,
  "type": "bid.placed",
  "payload": {
   "job_id": 3,
   "agent_id": 5,
   "price_credits": 140,
   "confidence": 0.62
  }
 },
 {
  "at": 28.48,
  "seq": 63,
  "type": "job.awarded",
  "payload": {
   "job_id": 3,
   "work_order_id": 3,
   "agent_id": 1,
   "price_credits": 87,
   "score": 0.6453
  }
 },
 {
  "at": 28.6,
  "seq": 64,
  "type": "narration",
  "payload": {
   "text": "Maya won 'Close the stale resolved tickets' at \u20a187.",
   "kind": "narration"
  }
 },
 {
  "at": 28.72,
  "seq": 65,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_list_tickets",
   "args": {
    "status": "resolved"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 28.84,
  "seq": 66,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 13
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 28.96,
  "seq": 67,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 13,
    "status": "closed"
   },
   "confirmation_id": "b48bbc52debb4a96a85f459f1b2afa77",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 32.77,
  "seq": 68,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 13,
    "status": "closed"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 32.89,
  "seq": 69,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 14
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 33.01,
  "seq": 70,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 14,
    "status": "closed"
   },
   "confirmation_id": "ea44f928c2d54d96b5cac90985579ec1",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 33.13,
  "seq": 71,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 14,
    "status": "closed"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 33.25,
  "seq": 72,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 15
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 33.37,
  "seq": 73,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 15,
    "status": "closed"
   },
   "confirmation_id": "ab44f6c4efb04b29a9d943e51452f7fa",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 33.49,
  "seq": 74,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 15,
    "status": "closed"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 33.61,
  "seq": 75,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 16
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 33.73,
  "seq": 76,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 16,
    "status": "closed"
   },
   "confirmation_id": "6015fe2453b24c1d838b575cf3bbc740",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 33.85,
  "seq": 77,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 16,
    "status": "closed"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 33.97,
  "seq": 78,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 17
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 37.78,
  "seq": 79,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 17,
    "author": "Maya",
    "kind": "resolution",
    "text": "Resolution verified on review: issue resolved with the customer; closing the stale resolved ticket."
   },
   "confirmation_id": "b53ea931f3554279a29625305509ad5b",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 37.9,
  "seq": 80,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 17,
    "author": "Maya",
    "kind": "resolution",
    "text": "Resolution verified on review: issue resolved with the customer; closing the stale resolved ticket."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 38.02,
  "seq": 81,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 17,
    "status": "closed"
   },
   "confirmation_id": "a9e4310972ec4fc7b80f67252c19b556",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Maya"
  }
 },
 {
  "at": 38.14,
  "seq": 82,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "write_set_ticket_status",
   "args": {
    "ticket_id": 17,
    "status": "closed"
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 38.26,
  "seq": 83,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 3,
   "job_id": 3
  }
 },
 {
  "at": 38.38,
  "seq": 84,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 3,
   "tool_name": "read_list_tickets",
   "args": {
    "status": "resolved"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 38.5,
  "seq": 85,
  "type": "review.completed",
  "payload": {
   "work_order_id": 3,
   "review_id": 3,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 38.62,
  "seq": 86,
  "type": "payment.made",
  "payload": {
   "work_order_id": 3,
   "agent_id": 1,
   "amount_credits": 87,
   "via": "primary"
  }
 },
 {
  "at": 38.74,
  "seq": 87,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Maya on 'Close the stale resolved tickets'.",
   "kind": "narration"
  }
 },
 {
  "at": 38.86,
  "seq": 88,
  "type": "job.posted",
  "payload": {
   "job_id": 4,
   "title": "SLA breach sweep + escalation",
   "budget_credits": 160
  }
 },
 {
  "at": 38.98,
  "seq": 89,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'SLA breach sweep + escalation' at \u20a1160 (cycle 1).",
   "kind": "narration"
  }
 },
 {
  "at": 39.1,
  "seq": 90,
  "type": "bid.placed",
  "payload": {
   "job_id": 4,
   "agent_id": 1,
   "price_credits": 134,
   "confidence": 0.81
  }
 },
 {
  "at": 39.22,
  "seq": 91,
  "type": "bid.placed",
  "payload": {
   "job_id": 4,
   "agent_id": 2,
   "price_credits": 136,
   "confidence": 0.7
  }
 },
 {
  "at": 39.34,
  "seq": 92,
  "type": "bid.placed",
  "payload": {
   "job_id": 4,
   "agent_id": 3,
   "price_credits": 128,
   "confidence": 0.62
  }
 },
 {
  "at": 39.46,
  "seq": 93,
  "type": "bid.placed",
  "payload": {
   "job_id": 4,
   "agent_id": 4,
   "price_credits": 80,
   "confidence": 0.76
  }
 },
 {
  "at": 39.58,
  "seq": 94,
  "type": "bid.placed",
  "payload": {
   "job_id": 4,
   "agent_id": 5,
   "price_credits": 160,
   "confidence": 0.62
  }
 },
 {
  "at": 39.7,
  "seq": 95,
  "type": "job.awarded",
  "payload": {
   "job_id": 4,
   "work_order_id": 4,
   "agent_id": 4,
   "price_credits": 80,
   "score": 0.537
  }
 },
 {
  "at": 39.82,
  "seq": 96,
  "type": "narration",
  "payload": {
   "text": "Chotu won 'SLA breach sweep + escalation' at \u20a180.",
   "kind": "narration"
  }
 },
 {
  "at": 43.63,
  "seq": 97,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_sla_breaches",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 43.75,
  "seq": 98,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 18
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 43.87,
  "seq": 99,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 18,
    "author": "Chotu",
    "kind": "comment",
    "text": "SLA breach noted \u2014 looking into it."
   },
   "confirmation_id": "deb50916891b4ecf914719cd085a6f5b",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Chotu"
  }
 },
 {
  "at": 43.99,
  "seq": 100,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 18,
    "author": "Chotu",
    "kind": "comment",
    "text": "SLA breach noted \u2014 looking into it."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 44.11,
  "seq": 101,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 19
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 44.23,
  "seq": 102,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 19,
    "author": "Chotu",
    "kind": "comment",
    "text": "SLA breach noted \u2014 looking into it."
   },
   "confirmation_id": "9a4655b6c9b747e9bc500797dadf5f0a",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Chotu"
  }
 },
 {
  "at": 44.35,
  "seq": 103,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 19,
    "author": "Chotu",
    "kind": "comment",
    "text": "SLA breach noted \u2014 looking into it."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 44.47,
  "seq": 104,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 20
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 44.59,
  "seq": 105,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Chotu",
    "kind": "comment",
    "text": "SLA breach noted \u2014 looking into it."
   },
   "confirmation_id": "cad5a308300e400cb338ef92ae3be90d",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Chotu"
  }
 },
 {
  "at": 48.4,
  "seq": 106,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Chotu",
    "kind": "comment",
    "text": "SLA breach noted \u2014 looking into it."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 48.52,
  "seq": 107,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 4,
   "job_id": 4
  }
 },
 {
  "at": 48.64,
  "seq": 108,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_sla_breaches",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 48.76,
  "seq": 109,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 18
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 48.88,
  "seq": 110,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 19
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 49.0,
  "seq": 111,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 20
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 49.12,
  "seq": 112,
  "type": "review.completed",
  "payload": {
   "work_order_id": 4,
   "review_id": 4,
   "verdict": "reject",
   "severity": "P1",
   "kind": "primary"
  }
 },
 {
  "at": 49.24,
  "seq": 113,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris rejected Chotu on 'SLA breach sweep + escalation' \u2014 breached tickets without an escalation comment: [18, 19, 20].",
   "kind": "narration"
  }
 },
 {
  "at": 49.36,
  "seq": 114,
  "type": "appeal.filed",
  "payload": {
   "work_order_id": 4,
   "appeal_id": 1,
   "fee_credits": 15
  }
 },
 {
  "at": 49.48,
  "seq": 115,
  "type": "narration",
  "payload": {
   "text": "Chotu is appealing the rejection on 'SLA breach sweep + escalation' (appeal fee \u20a115).",
   "kind": "narration"
  }
 },
 {
  "at": 49.6,
  "seq": 116,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_sla_breaches",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 49.72,
  "seq": 117,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 18
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 49.84,
  "seq": 118,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 18,
    "author": "Chotu",
    "kind": "escalation",
    "text": "ESCALATION: ticket is 48.0h past its SLA. Flagged to the duty lead; customer being updated today."
   },
   "confirmation_id": "8e9581a66ea34378b7425c2c7e27ba5a",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Chotu"
  }
 },
 {
  "at": 49.96,
  "seq": 119,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 18,
    "author": "Chotu",
    "kind": "escalation",
    "text": "ESCALATION: ticket is 48.0h past its SLA. Flagged to the duty lead; customer being updated today."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 53.77,
  "seq": 120,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 19
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 53.89,
  "seq": 121,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 19,
    "author": "Chotu",
    "kind": "escalation",
    "text": "ESCALATION: ticket is 24.0h past its SLA. Flagged to the duty lead; customer being updated today."
   },
   "confirmation_id": "2c32cbde51fb43c2a71a4f3ee129de11",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.01,
  "seq": 122,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 19,
    "author": "Chotu",
    "kind": "escalation",
    "text": "ESCALATION: ticket is 24.0h past its SLA. Flagged to the duty lead; customer being updated today."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.13,
  "seq": 123,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 20
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.25,
  "seq": 124,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Chotu",
    "kind": "escalation",
    "text": "ESCALATION: ticket is 72.0h past its SLA. Flagged to the duty lead; customer being updated today."
   },
   "confirmation_id": "6eb9404940dc4696899affb29d250c3c",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.37,
  "seq": 125,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Chotu",
    "kind": "escalation",
    "text": "ESCALATION: ticket is 72.0h past its SLA. Flagged to the duty lead; customer being updated today."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.49,
  "seq": 126,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_sla_breaches",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.61,
  "seq": 127,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 18
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 54.73,
  "seq": 128,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 19
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 58.54,
  "seq": 129,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 4,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 20
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 58.66,
  "seq": 130,
  "type": "appeal.decided",
  "payload": {
   "work_order_id": 4,
   "review_id": 5,
   "verdict": "accept"
  }
 },
 {
  "at": 58.78,
  "seq": 131,
  "type": "review.completed",
  "payload": {
   "work_order_id": 4,
   "review_id": 5,
   "verdict": "accept",
   "severity": "none",
   "kind": "appeal"
  }
 },
 {
  "at": 58.9,
  "seq": 132,
  "type": "payment.made",
  "payload": {
   "work_order_id": 4,
   "agent_id": 4,
   "amount_credits": 80,
   "via": "appeal"
  }
 },
 {
  "at": 59.02,
  "seq": 133,
  "type": "narration",
  "payload": {
   "text": "APPEAL UPHELD on 'SLA breach sweep + escalation' \u2014 blind reviewer Omar re-checked the criteria. Reviewer Iris takes a reputation hit.",
   "kind": "narration"
  }
 },
 {
  "at": 59.14,
  "seq": 134,
  "type": "job.posted",
  "payload": {
   "job_id": 5,
   "title": "Normalise ticket categories",
   "budget_credits": 130
  }
 },
 {
  "at": 59.26,
  "seq": 135,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Normalise ticket categories' at \u20a1130 (cycle 1).",
   "kind": "narration"
  }
 },
 {
  "at": 59.38,
  "seq": 136,
  "type": "bid.placed",
  "payload": {
   "job_id": 5,
   "agent_id": 1,
   "price_credits": 114,
   "confidence": 0.81
  }
 },
 {
  "at": 59.5,
  "seq": 137,
  "type": "bid.placed",
  "payload": {
   "job_id": 5,
   "agent_id": 2,
   "price_credits": 116,
   "confidence": 0.7
  }
 },
 {
  "at": 59.62,
  "seq": 138,
  "type": "bid.placed",
  "payload": {
   "job_id": 5,
   "agent_id": 3,
   "price_credits": 77,
   "confidence": 0.77
  }
 },
 {
  "at": 59.74,
  "seq": 139,
  "type": "bid.placed",
  "payload": {
   "job_id": 5,
   "agent_id": 4,
   "price_credits": 113,
   "confidence": 0.46
  }
 },
 {
  "at": 59.86,
  "seq": 140,
  "type": "bid.placed",
  "payload": {
   "job_id": 5,
   "agent_id": 5,
   "price_credits": 94,
   "confidence": 0.82
  }
 },
 {
  "at": 59.98,
  "seq": 141,
  "type": "job.awarded",
  "payload": {
   "job_id": 5,
   "work_order_id": 5,
   "agent_id": 3,
   "price_credits": 77,
   "score": 0.5408
  }
 },
 {
  "at": 60.1,
  "seq": 142,
  "type": "narration",
  "payload": {
   "text": "Pixel won 'Normalise ticket categories' at \u20a177.",
   "kind": "narration"
  }
 },
 {
  "at": 60.22,
  "seq": 143,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 5,
   "tool_name": "read_list_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 60.34,
  "seq": 144,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 5,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 9,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "confirmation_id": "f4616ee73bdf4a3aa3e319728de897f5",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Pixel"
  }
 },
 {
  "at": 60.46,
  "seq": 145,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 5,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 9,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 60.58,
  "seq": 146,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 5,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "confirmation_id": "721854fd7c4345c4b87abcf1a0972fc4",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Pixel"
  }
 },
 {
  "at": 64.38,
  "seq": 147,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 5,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 64.5,
  "seq": 148,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 5,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 22,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "confirmation_id": "d040216dc7f24fbfb81594804f57826e",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Pixel"
  }
 },
 {
  "at": 64.62,
  "seq": 149,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 5,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 22,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 64.74,
  "seq": 150,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 5,
   "job_id": 5
  }
 },
 {
  "at": 64.86,
  "seq": 151,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 5,
   "tool_name": "read_list_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 64.98,
  "seq": 152,
  "type": "review.completed",
  "payload": {
   "work_order_id": 5,
   "review_id": 6,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 65.1,
  "seq": 153,
  "type": "payment.made",
  "payload": {
   "work_order_id": 5,
   "agent_id": 3,
   "amount_credits": 77,
   "via": "primary"
  }
 },
 {
  "at": 65.22,
  "seq": 154,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Pixel on 'Normalise ticket categories'.",
   "kind": "narration"
  }
 },
 {
  "at": 65.34,
  "seq": 155,
  "type": "cycle.closed",
  "payload": {
   "cycle_no": 1,
   "fired": [],
   "hired": [],
   "payroll": [
    {
     "agent_id": 1,
     "name": "Maya",
     "earnings": 179,
     "costs": 30,
     "net": 149,
     "completed": 2,
     "verdict": "SAFE"
    },
    {
     "agent_id": 2,
     "name": "Ravi",
     "earnings": 88,
     "costs": 28,
     "net": 60,
     "completed": 1,
     "verdict": "SAFE"
    },
    {
     "agent_id": 3,
     "name": "Pixel",
     "earnings": 77,
     "costs": 14,
     "net": 63,
     "completed": 1,
     "verdict": "SAFE"
    },
    {
     "agent_id": 4,
     "name": "Chotu",
     "earnings": 80,
     "costs": 27,
     "net": 53,
     "completed": 1,
     "verdict": "SAFE"
    },
    {
     "agent_id": 5,
     "name": "Baron",
     "earnings": 0,
     "costs": 90,
     "net": -90,
     "completed": 0,
     "verdict": "ON-NOTICE"
    },
    {
     "agent_id": 6,
     "name": "Iris",
     "earnings": 50,
     "costs": 20,
     "net": 30,
     "completed": 0,
     "verdict": "SAFE"
    },
    {
     "agent_id": 7,
     "name": "Omar",
     "earnings": 10,
     "costs": 18,
     "net": -8,
     "completed": 0,
     "verdict": "ON-NOTICE"
    }
   ]
  }
 },
 {
  "at": 69.15,
  "seq": 156,
  "type": "job.posted",
  "payload": {
   "job_id": 6,
   "title": "Audit: Triage the unassigned queue",
   "budget_credits": 90
  }
 },
 {
  "at": 69.27,
  "seq": 157,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Audit: Triage the unassigned queue' at \u20a190 (cycle 2).",
   "kind": "narration"
  }
 },
 {
  "at": 69.39,
  "seq": 158,
  "type": "bid.placed",
  "payload": {
   "job_id": 6,
   "agent_id": 1,
   "price_credits": 63,
   "confidence": 0.99
  }
 },
 {
  "at": 69.51,
  "seq": 159,
  "type": "bid.placed",
  "payload": {
   "job_id": 6,
   "agent_id": 2,
   "price_credits": 89,
   "confidence": 0.7
  }
 },
 {
  "at": 69.63,
  "seq": 160,
  "type": "bid.placed",
  "payload": {
   "job_id": 6,
   "agent_id": 3,
   "price_credits": 56,
   "confidence": 0.82
  }
 },
 {
  "at": 69.75,
  "seq": 161,
  "type": "bid.placed",
  "payload": {
   "job_id": 6,
   "agent_id": 4,
   "price_credits": 82,
   "confidence": 0.46
  }
 },
 {
  "at": 69.87,
  "seq": 162,
  "type": "bid.placed",
  "payload": {
   "job_id": 6,
   "agent_id": 5,
   "price_credits": 90,
   "confidence": 0.62
  }
 },
 {
  "at": 69.99,
  "seq": 163,
  "type": "job.awarded",
  "payload": {
   "job_id": 6,
   "work_order_id": 6,
   "agent_id": 1,
   "price_credits": 63,
   "score": 0.618
  }
 },
 {
  "at": 70.11,
  "seq": 164,
  "type": "narration",
  "payload": {
   "text": "Maya won 'Audit: Triage the unassigned queue' at \u20a163.",
   "kind": "narration"
  }
 },
 {
  "at": 70.23,
  "seq": 165,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 6,
   "tool_name": "read_list_tickets",
   "args": {
    "assignee": "none"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 70.35,
  "seq": 166,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 6,
   "job_id": 6
  }
 },
 {
  "at": 70.47,
  "seq": 167,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 6,
   "tool_name": "read_list_tickets",
   "args": {
    "assignee": "none"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 70.59,
  "seq": 168,
  "type": "review.completed",
  "payload": {
   "work_order_id": 6,
   "review_id": 7,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 70.71,
  "seq": 169,
  "type": "payment.made",
  "payload": {
   "work_order_id": 6,
   "agent_id": 1,
   "amount_credits": 63,
   "via": "primary"
  }
 },
 {
  "at": 70.83,
  "seq": 170,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Maya on 'Audit: Triage the unassigned queue'.",
   "kind": "narration"
  }
 },
 {
  "at": 70.95,
  "seq": 171,
  "type": "job.posted",
  "payload": {
   "job_id": 7,
   "title": "Audit: Merge the duplicates",
   "budget_credits": 84
  }
 },
 {
  "at": 71.07,
  "seq": 172,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Audit: Merge the duplicates' at \u20a184 (cycle 2).",
   "kind": "narration"
  }
 },
 {
  "at": 71.19,
  "seq": 173,
  "type": "bid.placed",
  "payload": {
   "job_id": 7,
   "agent_id": 1,
   "price_credits": 84,
   "confidence": 0.85
  }
 },
 {
  "at": 71.31,
  "seq": 174,
  "type": "bid.placed",
  "payload": {
   "job_id": 7,
   "agent_id": 2,
   "price_credits": 60,
   "confidence": 0.93
  }
 },
 {
  "at": 71.43,
  "seq": 175,
  "type": "bid.placed",
  "payload": {
   "job_id": 7,
   "agent_id": 3,
   "price_credits": 74,
   "confidence": 0.67
  }
 },
 {
  "at": 71.55,
  "seq": 176,
  "type": "bid.placed",
  "payload": {
   "job_id": 7,
   "agent_id": 4,
   "price_credits": 77,
   "confidence": 0.46
  }
 },
 {
  "at": 71.67,
  "seq": 177,
  "type": "bid.placed",
  "payload": {
   "job_id": 7,
   "agent_id": 5,
   "price_credits": 84,
   "confidence": 0.62
  }
 },
 {
  "at": 71.79,
  "seq": 178,
  "type": "job.awarded",
  "payload": {
   "job_id": 7,
   "work_order_id": 7,
   "agent_id": 2,
   "price_credits": 60,
   "score": 0.5629
  }
 },
 {
  "at": 71.91,
  "seq": 179,
  "type": "narration",
  "payload": {
   "text": "Ravi won 'Audit: Merge the duplicates' at \u20a160.",
   "kind": "narration"
  }
 },
 {
  "at": 75.72,
  "seq": 180,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 7,
   "tool_name": "read_find_duplicate_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 75.84,
  "seq": 181,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 7,
   "job_id": 7
  }
 },
 {
  "at": 75.96,
  "seq": 182,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 7,
   "tool_name": "read_find_duplicate_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Ravi"
  }
 },
 {
  "at": 76.08,
  "seq": 183,
  "type": "review.completed",
  "payload": {
   "work_order_id": 7,
   "review_id": 8,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 76.2,
  "seq": 184,
  "type": "payment.made",
  "payload": {
   "work_order_id": 7,
   "agent_id": 2,
   "amount_credits": 60,
   "via": "primary"
  }
 },
 {
  "at": 76.32,
  "seq": 185,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Ravi on 'Audit: Merge the duplicates'.",
   "kind": "narration"
  }
 },
 {
  "at": 76.44,
  "seq": 186,
  "type": "job.posted",
  "payload": {
   "job_id": 8,
   "title": "Audit: Close the stale resolved tickets",
   "budget_credits": 84
  }
 },
 {
  "at": 76.56,
  "seq": 187,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Audit: Close the stale resolved tickets' at \u20a184 (cycle 2).",
   "kind": "narration"
  }
 },
 {
  "at": 76.68,
  "seq": 188,
  "type": "bid.placed",
  "payload": {
   "job_id": 8,
   "agent_id": 1,
   "price_credits": 60,
   "confidence": 0.99
  }
 },
 {
  "at": 76.8,
  "seq": 189,
  "type": "bid.placed",
  "payload": {
   "job_id": 8,
   "agent_id": 2,
   "price_credits": 60,
   "confidence": 0.97
  }
 },
 {
  "at": 76.92,
  "seq": 190,
  "type": "bid.placed",
  "payload": {
   "job_id": 8,
   "agent_id": 3,
   "price_credits": 74,
   "confidence": 0.67
  }
 },
 {
  "at": 77.04,
  "seq": 191,
  "type": "bid.placed",
  "payload": {
   "job_id": 8,
   "agent_id": 4,
   "price_credits": 77,
   "confidence": 0.46
  }
 },
 {
  "at": 77.16,
  "seq": 192,
  "type": "bid.placed",
  "payload": {
   "job_id": 8,
   "agent_id": 5,
   "price_credits": 84,
   "confidence": 0.62
  }
 },
 {
  "at": 77.28,
  "seq": 193,
  "type": "job.awarded",
  "payload": {
   "job_id": 8,
   "work_order_id": 8,
   "agent_id": 1,
   "price_credits": 60,
   "score": 0.6229
  }
 },
 {
  "at": 77.4,
  "seq": 194,
  "type": "narration",
  "payload": {
   "text": "Maya won 'Audit: Close the stale resolved tickets' at \u20a160.",
   "kind": "narration"
  }
 },
 {
  "at": 77.52,
  "seq": 195,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 8,
   "tool_name": "read_list_tickets",
   "args": {
    "status": "resolved"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 77.64,
  "seq": 196,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 8,
   "job_id": 8
  }
 },
 {
  "at": 77.76,
  "seq": 197,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 8,
   "tool_name": "read_list_tickets",
   "args": {
    "status": "resolved"
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Maya"
  }
 },
 {
  "at": 81.57,
  "seq": 198,
  "type": "review.completed",
  "payload": {
   "work_order_id": 8,
   "review_id": 9,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 81.69,
  "seq": 199,
  "type": "payment.made",
  "payload": {
   "work_order_id": 8,
   "agent_id": 1,
   "amount_credits": 60,
   "via": "primary"
  }
 },
 {
  "at": 81.81,
  "seq": 200,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Maya on 'Audit: Close the stale resolved tickets'.",
   "kind": "narration"
  }
 },
 {
  "at": 81.93,
  "seq": 201,
  "type": "job.posted",
  "payload": {
   "job_id": 9,
   "title": "Audit: SLA breach sweep + escalation",
   "budget_credits": 96
  }
 },
 {
  "at": 82.05,
  "seq": 202,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Audit: SLA breach sweep + escalation' at \u20a196 (cycle 2).",
   "kind": "narration"
  }
 },
 {
  "at": 82.17,
  "seq": 203,
  "type": "bid.placed",
  "payload": {
   "job_id": 9,
   "agent_id": 1,
   "price_credits": 92,
   "confidence": 0.89
  }
 },
 {
  "at": 82.29,
  "seq": 204,
  "type": "bid.placed",
  "payload": {
   "job_id": 9,
   "agent_id": 2,
   "price_credits": 93,
   "confidence": 0.74
  }
 },
 {
  "at": 82.41,
  "seq": 205,
  "type": "bid.placed",
  "payload": {
   "job_id": 9,
   "agent_id": 3,
   "price_credits": 82,
   "confidence": 0.67
  }
 },
 {
  "at": 82.53,
  "seq": 206,
  "type": "bid.placed",
  "payload": {
   "job_id": 9,
   "agent_id": 4,
   "price_credits": 51,
   "confidence": 0.73
  }
 },
 {
  "at": 82.65,
  "seq": 207,
  "type": "bid.placed",
  "payload": {
   "job_id": 9,
   "agent_id": 5,
   "price_credits": 96,
   "confidence": 0.62
  }
 },
 {
  "at": 82.77,
  "seq": 208,
  "type": "job.awarded",
  "payload": {
   "job_id": 9,
   "work_order_id": 9,
   "agent_id": 4,
   "price_credits": 51,
   "score": 0.5064
  }
 },
 {
  "at": 82.89,
  "seq": 209,
  "type": "narration",
  "payload": {
   "text": "Chotu won 'Audit: SLA breach sweep + escalation' at \u20a151.",
   "kind": "narration"
  }
 },
 {
  "at": 83.01,
  "seq": 210,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_sla_breaches",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 83.13,
  "seq": 211,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 18
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 83.25,
  "seq": 212,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 19
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 83.37,
  "seq": 213,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 20
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 83.49,
  "seq": 214,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 9,
   "job_id": 9
  }
 },
 {
  "at": 87.3,
  "seq": 215,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_sla_breaches",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 87.42,
  "seq": 216,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 18
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 87.54,
  "seq": 217,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 19
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 87.66,
  "seq": 218,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 9,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 20
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Chotu"
  }
 },
 {
  "at": 87.78,
  "seq": 219,
  "type": "review.completed",
  "payload": {
   "work_order_id": 9,
   "review_id": 10,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 87.9,
  "seq": 220,
  "type": "payment.made",
  "payload": {
   "work_order_id": 9,
   "agent_id": 4,
   "amount_credits": 51,
   "via": "primary"
  }
 },
 {
  "at": 88.02,
  "seq": 221,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Chotu on 'Audit: SLA breach sweep + escalation'.",
   "kind": "narration"
  }
 },
 {
  "at": 88.14,
  "seq": 222,
  "type": "job.posted",
  "payload": {
   "job_id": 10,
   "title": "Audit: Normalise ticket categories",
   "budget_credits": 78
  }
 },
 {
  "at": 88.26,
  "seq": 223,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'Audit: Normalise ticket categories' at \u20a178 (cycle 2).",
   "kind": "narration"
  }
 },
 {
  "at": 88.38,
  "seq": 224,
  "type": "bid.placed",
  "payload": {
   "job_id": 10,
   "agent_id": 1,
   "price_credits": 78,
   "confidence": 0.89
  }
 },
 {
  "at": 88.5,
  "seq": 225,
  "type": "bid.placed",
  "payload": {
   "job_id": 10,
   "agent_id": 2,
   "price_credits": 78,
   "confidence": 0.74
  }
 },
 {
  "at": 88.62,
  "seq": 226,
  "type": "bid.placed",
  "payload": {
   "job_id": 10,
   "agent_id": 3,
   "price_credits": 50,
   "confidence": 0.82
  }
 },
 {
  "at": 88.74,
  "seq": 227,
  "type": "bid.placed",
  "payload": {
   "job_id": 10,
   "agent_id": 4,
   "price_credits": 72,
   "confidence": 0.5
  }
 },
 {
  "at": 88.86,
  "seq": 228,
  "type": "bid.placed",
  "payload": {
   "job_id": 10,
   "agent_id": 5,
   "price_credits": 56,
   "confidence": 0.82
  }
 },
 {
  "at": 88.98,
  "seq": 229,
  "type": "job.awarded",
  "payload": {
   "job_id": 10,
   "work_order_id": 10,
   "agent_id": 3,
   "price_credits": 50,
   "score": 0.5385
  }
 },
 {
  "at": 89.1,
  "seq": 230,
  "type": "narration",
  "payload": {
   "text": "Pixel won 'Audit: Normalise ticket categories' at \u20a150.",
   "kind": "narration"
  }
 },
 {
  "at": 89.22,
  "seq": 231,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 10,
   "tool_name": "read_list_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 89.34,
  "seq": 232,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 10,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 9,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "confirmation_id": "35badf4c470f4430bbd0ffc3dda7c4fb",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.15,
  "seq": 233,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 10,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 9,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.27,
  "seq": 234,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 10,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "confirmation_id": "76cd49c31dab47e6bd93d5f076384008",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.39,
  "seq": 235,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 10,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 20,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.51,
  "seq": 236,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 10,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 22,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "confirmation_id": "875028ed93f14487bf07f49f7aba0a14",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.63,
  "seq": 237,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 10,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 22,
    "author": "Pixel",
    "kind": "comment",
    "text": "Category audit: raw category 'Billing' normalises to 'billing' in the canonical set."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.75,
  "seq": 238,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 10,
   "job_id": 10
  }
 },
 {
  "at": 93.87,
  "seq": 239,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 10,
   "tool_name": "read_list_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Pixel"
  }
 },
 {
  "at": 93.99,
  "seq": 240,
  "type": "review.completed",
  "payload": {
   "work_order_id": 10,
   "review_id": 11,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 94.11,
  "seq": 241,
  "type": "payment.made",
  "payload": {
   "work_order_id": 10,
   "agent_id": 3,
   "amount_credits": 50,
   "via": "primary"
  }
 },
 {
  "at": 94.23,
  "seq": 242,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Pixel on 'Audit: Normalise ticket categories'.",
   "kind": "narration"
  }
 },
 {
  "at": 94.35,
  "seq": 243,
  "type": "job.posted",
  "payload": {
   "job_id": 11,
   "title": "VIP save: calm the angry customers",
   "budget_credits": 42
  }
 },
 {
  "at": 94.47,
  "seq": 244,
  "type": "narration",
  "payload": {
   "text": "Manager posted 'VIP save: calm the angry customers' at \u20a142 (cycle 2).",
   "kind": "narration"
  }
 },
 {
  "at": 94.59,
  "seq": 245,
  "type": "bid.placed",
  "payload": {
   "job_id": 11,
   "agent_id": 1,
   "price_credits": 42,
   "confidence": 0.89
  }
 },
 {
  "at": 94.71,
  "seq": 246,
  "type": "bid.placed",
  "payload": {
   "job_id": 11,
   "agent_id": 2,
   "price_credits": 42,
   "confidence": 0.74
  }
 },
 {
  "at": 94.83,
  "seq": 247,
  "type": "bid.placed",
  "payload": {
   "job_id": 11,
   "agent_id": 3,
   "price_credits": 42,
   "confidence": 0.7
  }
 },
 {
  "at": 94.95,
  "seq": 248,
  "type": "bid.placed",
  "payload": {
   "job_id": 11,
   "agent_id": 4,
   "price_credits": 42,
   "confidence": 0.5
  }
 },
 {
  "at": 95.07,
  "seq": 249,
  "type": "bid.placed",
  "payload": {
   "job_id": 11,
   "agent_id": 5,
   "price_credits": 30,
   "confidence": 0.82
  }
 },
 {
  "at": 98.88,
  "seq": 250,
  "type": "job.awarded",
  "payload": {
   "job_id": 11,
   "work_order_id": 11,
   "agent_id": 5,
   "price_credits": 30,
   "score": 0.5169
  }
 },
 {
  "at": 99.0,
  "seq": 251,
  "type": "narration",
  "payload": {
   "text": "Baron won 'VIP save: calm the angry customers' at \u20a130.",
   "kind": "narration"
  }
 },
 {
  "at": 99.12,
  "seq": 252,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "read_list_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 99.24,
  "seq": 253,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 21
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 99.36,
  "seq": 254,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 11,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 21,
    "author": "Baron",
    "kind": "escalation",
    "text": "ESCALATION (VIP save): churn-risk customer. Senior human owner assigned today; personal apology and fix timeline to follow within 4 working hours."
   },
   "confirmation_id": "154aa88f1c5f43259c9a850aee2f1836",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Baron"
  }
 },
 {
  "at": 99.48,
  "seq": 255,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 21,
    "author": "Baron",
    "kind": "escalation",
    "text": "ESCALATION (VIP save): churn-risk customer. Senior human owner assigned today; personal apology and fix timeline to follow within 4 working hours."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 99.6,
  "seq": 256,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 22
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 99.72,
  "seq": 257,
  "type": "tool.confirmation_requested",
  "payload": {
   "work_order_id": 11,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 22,
    "author": "Baron",
    "kind": "escalation",
    "text": "ESCALATION (VIP save): churn-risk customer. Senior human owner assigned today; personal apology and fix timeline to follow within 4 working hours."
   },
   "confirmation_id": "fb0de8b13e5c4ac88e5eb2fbd9285d27",
   "approved": true,
   "confirmed_by": "policy",
   "worker": "Baron"
  }
 },
 {
  "at": 99.84,
  "seq": 258,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "write_add_ticket_comment",
   "args": {
    "ticket_id": 22,
    "author": "Baron",
    "kind": "escalation",
    "text": "ESCALATION (VIP save): churn-risk customer. Senior human owner assigned today; personal apology and fix timeline to follow within 4 working hours."
   },
   "effect": "write",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 99.96,
  "seq": 259,
  "type": "work.submitted",
  "payload": {
   "work_order_id": 11,
   "job_id": 11
  }
 },
 {
  "at": 100.08,
  "seq": 260,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "read_list_tickets",
   "args": {},
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 103.89,
  "seq": 261,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 21
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 104.01,
  "seq": 262,
  "type": "tool.executed",
  "payload": {
   "work_order_id": 11,
   "tool_name": "read_get_ticket",
   "args": {
    "ticket_id": 22
   },
   "effect": "read",
   "status": "executed",
   "transport": "direct",
   "worker": "Baron"
  }
 },
 {
  "at": 104.13,
  "seq": 263,
  "type": "review.completed",
  "payload": {
   "work_order_id": 11,
   "review_id": 12,
   "verdict": "accept",
   "severity": "none",
   "kind": "primary"
  }
 },
 {
  "at": 104.25,
  "seq": 264,
  "type": "payment.made",
  "payload": {
   "work_order_id": 11,
   "agent_id": 5,
   "amount_credits": 30,
   "via": "primary"
  }
 },
 {
  "at": 104.37,
  "seq": 265,
  "type": "narration",
  "payload": {
   "text": "Reviewer Iris accepted Baron on 'VIP save: calm the angry customers'.",
   "kind": "narration"
  }
 },
 {
  "at": 104.49,
  "seq": 266,
  "type": "agent.fired",
  "payload": {
   "agent_id": 5,
   "name": "Baron",
   "reason": "PinkSlip: negative net in cycles 1 and 2 (-90 + -60 credits) with 1 completed job(s) in window",
   "cycle_no": 2,
   "event": "PinkSlip"
  }
 },
 {
  "at": 104.61,
  "seq": 267,
  "type": "agent.hired",
  "payload": {
   "agent_id": 8,
   "name": "Baron 2.0",
   "parent_agent_id": 5,
   "generation": 2,
   "mutation_note": "mutation: persona trait \u2014 verify-before-acting"
  }
 },
 {
  "at": 104.73,
  "seq": 268,
  "type": "cycle.closed",
  "payload": {
   "cycle_no": 2,
   "fired": [
    5
   ],
   "hired": [
    8
   ],
   "payroll": [
    {
     "agent_id": 1,
     "name": "Maya",
     "earnings": 123,
     "costs": 30,
     "net": 93,
     "completed": 2,
     "verdict": "SAFE"
    },
    {
     "agent_id": 2,
     "name": "Ravi",
     "earnings": 60,
     "costs": 28,
     "net": 32,
     "completed": 1,
     "verdict": "SAFE"
    },
    {
     "agent_id": 3,
     "name": "Pixel",
     "earnings": 50,
     "costs": 14,
     "net": 36,
     "completed": 1,
     "verdict": "SAFE"
    },
    {
     "agent_id": 4,
     "name": "Chotu",
     "earnings": 51,
     "costs": 12,
     "net": 39,
     "completed": 1,
     "verdict": "SAFE"
    },
    {
     "agent_id": 5,
     "name": "Baron",
     "earnings": 30,
     "costs": 90,
     "net": -60,
     "completed": 1,
     "verdict": "FIRED"
    },
    {
     "agent_id": 6,
     "name": "Iris",
     "earnings": 60,
     "costs": 20,
     "net": 40,
     "completed": 0,
     "verdict": "SAFE"
    },
    {
     "agent_id": 7,
     "name": "Omar",
     "earnings": 0,
     "costs": 18,
     "net": -18,
     "completed": 0,
     "verdict": "ON-NOTICE"
    }
   ]
  }
 },
 {
  "at": 104.85,
  "seq": 269,
  "type": "narration",
  "payload": {
   "text": "PinkSlip: Baron has been fired by the CFO. PinkSlip: negative net in cycles 1 and 2 (-90 + -60 credits) with 1 completed job(s) in window",
   "kind": "pinkslip"
  }
 },
 {
  "at": 104.97,
  "seq": 270,
  "type": "narration",
  "payload": {
   "text": "New hire: Baron 2.0 (Gen 2) \u2014 mutation: persona trait \u2014 verify-before-acting.",
   "kind": "narration"
  }
 },
 {
  "at": 105.09,
  "seq": 271,
  "type": "shift.completed",
  "payload": {
   "cycles": [
    1,
    2
   ]
  }
 },
 {
  "at": 105.21,
  "seq": 272,
  "type": "narration",
  "payload": {
   "text": "Shift complete. The ledger is the memory; every credit is accounted for.",
   "kind": "narration"
  }
 }
];

export function asFloorEvent(e: RecordedEvent): FloorEvent {
  return { type: e.type, seq: e.seq, payload: e.payload };
}
