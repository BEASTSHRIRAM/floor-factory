# Bookkeeping (department workplace — accounting)

A deliberately ordinary internal accounting API — chart of accounts,
transactions, and invoices/receivables — the kind of finance back office
every company has. THE FLOOR's agents never touch this code; they only
call its API through a Synapse-generated MCP server.

**Deliberate platform limit:** there are no payment or money-movement
endpoints in this API, and no delete endpoints. Agents organise the
books and draft the chases; money never moves. Exposure is a safety
decision.

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create bookkeeping.db with the messy month
uvicorn app:app --port 8104      # serve on :8104
python3 reset.py                 # restore the exact seeded state at any time
python3 verify.py                # end-to-end proof: every tool + all 4 jobs
```

(Or `POST /admin/reset` while the server is running.)

## Exposed API (the Synapse Auto allowlist for this department)

| Method & path | Tool | Effect |
|---|---|---|
| `GET /transactions` | `read_list_transactions` | read |
| `GET /transactions/uncategorised` | `read_list_uncategorised` | read |
| `GET /transactions/duplicates` | `read_find_duplicates` | read |
| `GET /accounts/{id}/reconcile` | `read_reconcile_account` | read |
| `GET /receivables` | `read_list_receivables` | read |
| `GET /accounts` | `read_list_accounts` | read |
| `GET /chart` | `read_chart_of_accounts` | read |
| `GET /notes` | `read_list_notes` | read |
| `GET /stats/summary` | `read_stats_summary` | read |
| `POST /transactions/{id}/categorise` | `write_categorise_transaction` | write (confirm-gated) |
| `POST /transactions/{id}/flag-duplicate` | `write_flag_duplicate` | write (confirm-gated) |
| `POST /receivables/{id}/reminder` | `write_send_reminder` | write (confirm-gated) |
| `POST /notes` | `write_add_finance_note` | write (confirm-gated) |

`send_reminder` records a reminder draft/event in the books — it sends
no real email. `flag_duplicate` marks a row; nothing is ever deleted.

## Seed data

One messy month (see `seed.py`): 49 transactions across 3 accounts, 12
uncategorised (8 older than 7 days), 3 planted duplicates, an operating
account whose bank statement disagrees with the books by exactly +751
(unrecorded interest 1,250 less an unrecorded fee 499), and 11 invoices
— 3 paid, 8 open: 2 not yet due, 2 in the +3 chase band, 2 in +15, 2 in
+30.

## Jobs pack

Four job templates with credit budgets and deterministic Reviewer
checks live in `jobs.py` (and `manifest.json`): categorise the queue
(₡120), flag duplicates (₡90), reconcile the operating account (₡110),
chase overdue receivables (₡130).
