/* Shared shapes for THE FLOOR API. The API is shape-tolerant on the server
   side and occasionally loose on the wire, so every field is optional and
   normalisation happens in lib/api.ts. */

export interface Agent {
  id: string;
  name: string;
  status: string; // idle | bidding | working | in_review | fired | ...
  reputation: number; // 0..100
  balance_credits: number;
  generation: number;
  tier: string;
  model?: string;
  role?: string;
  mutation_note?: string;
  current_job?: string;
  last_tool?: string;
  fired_at?: string | null;
  [key: string]: unknown;
}

export interface Bid {
  agent_name?: string;
  agent_id?: string | number;
  price_credits?: number;
  price?: number;
  confidence?: number;
  [key: string]: unknown;
}

export interface Job {
  id: string;
  title: string;
  status: string;
  budget_credits?: number;
  system?: string;
  winner?: string;
  severity?: string;
  bids?: Bid[];
  department?: string;
  department_label?: string;
  [key: string]: unknown;
}

export interface LedgerRow {
  id?: string | number;
  agent_name?: string;
  agent_id?: string | number;
  kind?: string;
  amount_credits?: number;
  amount?: number;
  note?: string;
  [key: string]: unknown;
}

export interface FloorEvent {
  type?: string;
  event?: string;
  seq?: number;
  id?: number;
  payload?: Record<string, unknown>;
  data?: Record<string, unknown>;
  message?: string;
  text?: string;
  [key: string]: unknown;
}

export interface PayrollRow {
  agent_name?: string;
  name?: string;
  earnings?: number;
  earned?: number;
  costs?: number;
  cost?: number;
  net?: number;
  verdict?: string;
  status?: string;
  [key: string]: unknown;
}

export interface PayrollPayload {
  cycle_no?: number;
  cycle?: number;
  rows?: PayrollRow[];
  agents?: PayrollRow[];
  payroll?: PayrollRow[];
  [key: string]: unknown;
}

export interface NarrationItem {
  key: number;
  text: string;
  cls?: string; // appeal | pinkslip | hire | ""
}

/* Live presence, derived in FloorClient from the event stream (never
   invented): tool.executed -> working (+tool name), bid.placed ->
   bidding, work.submitted -> review, appeal.filed -> appealing,
   payment/appeal.decided/review -> idle, agent.fired -> fired. */
export type PresenceState = "working" | "bidding" | "review" | "appealing" | "idle" | "fired";

export interface Presence {
  state: PresenceState;
  tool?: string;
}
