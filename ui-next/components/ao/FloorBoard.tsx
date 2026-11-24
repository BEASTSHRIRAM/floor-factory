"use client";

/* The board: agent-orchestrator's own SessionsBoardGridView +
 * SessionCardView (vendored, unmodified), fed Floor jobs through the
 * adapter — the same composition their renderer builds in
 * SessionsBoardAdapters. Four of their five kanban columns are used:
 * building / needs_review / ready / archive. */

import type { ComponentType } from "react";
import {
  AgentAvatar,
  SessionCardView,
  SessionsBoardGridView,
  getKanbanColumnView,
  type BoardSessionPresentation,
  type ExternalLinkProps,
  type KanbanColumn,
} from "../../vendor/ao/product-ui";
import { jobCardFooter, jobToBoardSession, relTime } from "./adapter";
import type { Job } from "../../lib/types";

const FloorExternalLink: ComponentType<ExternalLinkProps> = ({ ariaLabel, children, className, href, stopPropagation, title }) => (
  <a
    aria-label={ariaLabel}
    className={className}
    href={href}
    title={title}
    onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}
  >
    {children}
  </a>
);

const CARD_LABELS = {
  formatTime: (ts: string) => relTime(ts),
  intakeIssue: (id: string) => `Job #${id}`,
  updatedAt: (ts: string) => `Updated ${relTime(ts)}`,
  pr: {
    short: "Work order",
    states: { closed: "Closed", open: "Open", draft: "Draft", merged: "Done" } as const,
    progress: (p: { total: number }) => `${p.total} work orders`,
  },
};

const COLUMNS: KanbanColumn[] = ["building", "needs_review", "ready", "archive"];

export default function FloorBoard({
  jobs,
  selectedId,
  onSelect,
}: {
  jobs: Job[];
  selectedId: string | null;
  onSelect: (job: Job) => void;
}) {
  const sessions = jobs.map(jobToBoardSession);
  const byId = new Map(jobs.map((j) => [j.id, j]));
  return (
    <SessionsBoardGridView<BoardSessionPresentation>
      columns={COLUMNS.map((c) => getKanbanColumnView(c))}
      labels={{ columnAria: (label) => `${label} column` }}
      sessions={sessions}
      renderSessionCard={(session) => {
        const job = byId.get(session.id);
        if (!job) return null;
        const footer = jobCardFooter(job);
        const failed = session.kanbanColumn === "archive";
        return (
          <SessionCardView
            session={session}
            externalLink={FloorExternalLink}
            labels={CARD_LABELS}
            renderAvatar={(provider) => <AgentAvatar provider={provider} />}
            onOpen={() => onSelect(job)}
            selected={selectedId === job.id ? true : undefined}
            usage={
              job.budget_credits !== undefined
                ? { accessibleLabel: `Budget cap ${job.budget_credits} credits`, compactLabel: `₡${job.budget_credits} cap` }
                : undefined
            }
            error={failed ? "Rejected in review — no payment made." : undefined}
            footer={
              <div className="flex items-center gap-2 border-t border-border px-3.5 py-2 text-2xs text-muted-foreground">
                <span className="shrink-0 rounded-full border border-border bg-interactive-hover px-1.5 py-0.5 font-medium text-foreground">
                  {job.department_label ?? "Support"}
                </span>
                {footer && <span className="min-w-0 truncate">{footer}</span>}
              </div>
            }
          />
        );
      }}
    />
  );
}
