# THE FLOOR — playbook artefacts

Every job family's playbook, exported as a SKILL.md artefact by `orchestrator/export_playbooks.py` (H5 — playbooks as reviewable files, not just code constants). Regenerate with:

    .venv/bin/python -m orchestrator.export_playbooks

| Family | Department | Server | Artefact |
|---|---|---|---|
| triage — Triage the unassigned queue | support | ticketdesk | [triage/SKILL.md](triage/SKILL.md) |
| duplicates — Merge the duplicates | support | ticketdesk | [duplicates/SKILL.md](duplicates/SKILL.md) |
| stale_close — Close the stale resolved tickets | support | ticketdesk | [stale_close/SKILL.md](stale_close/SKILL.md) |
| sla_breach — SLA breach sweep + escalation | support | ticketdesk | [sla_breach/SKILL.md](sla_breach/SKILL.md) |
| categories — Normalise ticket categories | support | ticketdesk | [categories/SKILL.md](categories/SKILL.md) |
| vip_save — VIP save: calm the angry customers | support | ticketdesk | [vip_save/SKILL.md](vip_save/SKILL.md) |
| cluster_failures — Cluster the overnight failures | qa | qa | [cluster_failures/SKILL.md](cluster_failures/SKILL.md) |
| quarantine_flaky — Quarantine the flaky tests | qa | qa | [quarantine_flaky/SKILL.md](quarantine_flaky/SKILL.md) |
| regression_verdict — Regression verdict for the overnight run | qa | qa | [regression_verdict/SKILL.md](regression_verdict/SKILL.md) |
| categorise_queue — Categorise the uncategorised queue | bookkeeping | bookkeeping | [categorise_queue/SKILL.md](categorise_queue/SKILL.md) |
| flag_duplicates — Flag the duplicate transactions | bookkeeping | bookkeeping | [flag_duplicates/SKILL.md](flag_duplicates/SKILL.md) |
| reconcile_operating — Reconcile the operating account | bookkeeping | bookkeeping | [reconcile_operating/SKILL.md](reconcile_operating/SKILL.md) |
| chase_receivables — Chase overdue receivables (+3/+15/+30) | bookkeeping | bookkeeping | [chase_receivables/SKILL.md](chase_receivables/SKILL.md) |
| research_score_new_leads — Research and score the new-lead batch | sdr | sdr | [research_score_new_leads/SKILL.md](research_score_new_leads/SKILL.md) |
| draft_qualified_outreach — Draft outreach for qualified accounts | sdr | sdr | [draft_qualified_outreach/SKILL.md](draft_qualified_outreach/SKILL.md) |
| work_issue — Work an engineering issue and open a PR | engineering | engineering | [work_issue/SKILL.md](work_issue/SKILL.md) |
| triage_unlabelled — Triage the unlabelled issues | engineering | engineering | [triage_unlabelled/SKILL.md](triage_unlabelled/SKILL.md) |
| screen_batch — Screen the new applicant batch | hr | hrdesk | [screen_batch/SKILL.md](screen_batch/SKILL.md) |
| schedule_interviews — Schedule interviews for screening passers | hr | hrdesk | [schedule_interviews/SKILL.md](schedule_interviews/SKILL.md) |
| onboarding_paperwork — Complete onboarding paperwork for this week's joiners | hr | hrdesk | [onboarding_paperwork/SKILL.md](onboarding_paperwork/SKILL.md) |
| audit_top_pages — Audit the top landing pages | seo | seo | [audit_top_pages/SKILL.md](audit_top_pages/SKILL.md) |
| content_brief — Write a content brief for 'best trail running shoes for monsoon' | seo | seo | [content_brief/SKILL.md](content_brief/SKILL.md) |
| internal_link_plan — Internal-link fix plan for orphan pages | seo | seo | [internal_link_plan/SKILL.md](internal_link_plan/SKILL.md) |
