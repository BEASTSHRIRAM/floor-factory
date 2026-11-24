"use client";

/* The inspector: agent-orchestrator's SessionInspectorShellView with
 * its Summary / Reviews / Activity views (vendored, unmodified),
 * composed around Floor detail — a job's brief, sealed bids, review
 * passes and appeal, or an agent's record. Their shell owns the tab
 * bar and layout; the Floor adapter supplies the models. */

import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import {
  AgentAvatar,
  InspectorActivityTimelineView,
  InspectorReviewsView,
  InspectorSection,
  SessionInspectorShellView,
  SessionInspectorSummaryView,
  inspectorEmptyClass,
  type ExternalLinkProps,
  type InspectorReviewLabels,
  type InspectorTab,
  type InspectorView,
} from "../../vendor/ao/product-ui";
import { FileTextIcon, GitPullRequestIcon, MessageSquareIcon, XIcon } from "../../vendor/ao/product-ui/icons";
import { credits, pick } from "../../lib/api";
import type { Agent, Job, Presence } from "../../lib/types";
import { agentTimeline, jobReviewGroups, jobTimeline, presenceLabel, type FloorEventLogItem } from "./adapter";

const FloorExternalLink: ComponentType<ExternalLinkProps> = ({ ariaLabel, children, className, href, title }) => (
  <a aria-label={ariaLabel} className={className} href={href} title={title}>
    {children}
  </a>
);

const REVIEW_LABELS: InspectorReviewLabels = {
  aoSource: "Floor review",
  bot: "reviewer",
  earlierPass: "Earlier pass",
  githubSource: "External",
  loadingReviews: "Loading reviews…",
  loadMoreReviews: (n) => `Load ${n} more`,
  noPastReviewSummaries: "No past review summaries.",
  notInjected: "Not injected",
  openComments: "Open comments",
  openInAOBrowser: "Open in browser",
  openInSystemBrowser: "Open in system browser",
  openInlineComments: (n) => `${n} findings`,
  requestRereviewPR: "Request re-review",
  reviewActions: "Review actions",
  reviews: "Reviews",
  reviewedAt: (t) => `Reviewed ${t}`,
  resolvedComments: (n) => `${n} resolved`,
  rereviewRequested: "Re-review requested",
  rereviewRequestFailed: "Re-review failed",
  resolveComment: "Resolve",
  resolvedReview: "Resolved",
  resolveReviewFailed: "Resolve failed",
  sendToWorkerAgent: "Send to worker",
  sentToWorkerAgent: "Sent to worker",
  sendToWorkerAgentError: "Could not send to worker",
  workerAgentWorkingOnFeedback: "Worker is addressing feedback",
  showLatestReviewOnly: "Show latest only",
  showLess: "Show less",
  showMore: "Show more",
  commentNumber: (n) => `Finding ${n}`,
  unresolvedCount: (n) => `${n} unresolved`,
  viewInFile: "View in file",
  viewInFileWorkInProgress: "View in file (work in progress)",
  viewOnPR: "View on job",
};

function Fact({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 px-2 py-1">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className={`min-w-0 text-right text-xs text-foreground ${mono ? "font-mono tabular-nums" : ""}`}>{children}</span>
    </div>
  );
}

function JobSummary({ job, events }: { job: Job; events: FloorEventLogItem[] }) {
  const bids = job.bids ?? [];
  const orders = (job.work_orders as Record<string, unknown>[] | undefined) ?? [];
  const brief = pick(job as Record<string, unknown>, "brief", "description") as string | undefined;
  const criteria = (job as Record<string, unknown>).acceptance_criteria as string[] | undefined;
  const timeline = jobTimeline(events, job.id, 8);
  return (
    <SessionInspectorSummaryView
      activityTitle="Recent activity"
      activity={
        timeline.length ? (
          <InspectorActivityTimelineView events={timeline} />
        ) : (
          <p className={inspectorEmptyClass}>No events recorded for this job yet.</p>
        )
      }
      workers={
        job.winner ? (
          <InspectorSection title="Awarded to">
            <div className="flex items-center gap-2.5 px-2 py-1.5">
              <AgentAvatar provider={job.winner} />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-foreground">{job.winner}</div>
                <div className="text-2xs text-muted-foreground">
                  {orders[0]
                    ? `${credits(pick(orders[0], "agreed_price_credits", "price_credits"))} agreed · via Synapse MCP tools only`
                    : "Works through Synapse MCP tools only"}
                </div>
              </div>
            </div>
          </InspectorSection>
        ) : undefined
      }
      context={
        <InspectorSection title="Job">
          <Fact label="Status">{job.status}</Fact>
          {job.system && <Fact label="System">{job.system}</Fact>}
          {job.budget_credits !== undefined && (
            <Fact label="Budget cap" mono>
              {credits(job.budget_credits)}
            </Fact>
          )}
          {job.severity && <Fact label="Review severity">{job.severity}</Fact>}
          <Fact label="Sealed bids" mono>
            {bids.length}
          </Fact>
          {orders[0] && <Fact label="Work order plan">{String(orders[0].plan ?? "—")}</Fact>}
        </InspectorSection>
      }
      branch={
        brief ? (
          <InspectorSection title="Brief" surface={false}>
            <p className="px-1 text-xs leading-relaxed text-muted-foreground">{brief}</p>
            {criteria && criteria.length > 0 && (
              <ul className="mt-2 list-disc px-5 text-xs leading-relaxed text-muted-foreground">
                {criteria.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            )}
          </InspectorSection>
        ) : undefined
      }
      usage={
        bids.length ? (
          <InspectorSection title="Sealed bids">
            {bids.map((b, i) => {
              const who = String(pick(b as Record<string, unknown>, "agent_name", "agent_id") ?? "Agent");
              const price = pick(b as Record<string, unknown>, "price_credits", "price");
              const conf = pick(b as Record<string, unknown>, "confidence", "conf");
              const win = !!job.winner && who === job.winner;
              return (
                <div key={i} className="px-2 py-1.5">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs font-medium text-foreground">
                      {who}
                      {win && <span className="ml-2 text-2xs font-semibold text-success">WINNER</span>}
                    </span>
                    <span className="font-mono text-xs tabular-nums text-foreground">
                      {price !== undefined ? credits(price) : "—"}
                      {conf !== undefined && <span className="text-muted-foreground"> · conf {Number(conf).toFixed(2)}</span>}
                    </span>
                  </div>
                </div>
              );
            })}
          </InspectorSection>
        ) : undefined
      }
    />
  );
}

function AgentSummary({ agent, events, presence }: { agent: Agent; events: FloorEventLogItem[]; presence?: Presence }) {
  const p = presenceLabel(agent, presence);
  const timeline = agentTimeline(events, agent.name, 10);
  return (
    <SessionInspectorSummaryView
      activityTitle="Recent activity"
      activity={
        timeline.length ? (
          <InspectorActivityTimelineView events={timeline} />
        ) : (
          <p className={inspectorEmptyClass}>No events recorded for this agent yet.</p>
        )
      }
      context={
        <InspectorSection title="Agent">
          <Fact label="Presence">{p.text}</Fact>
          <Fact label="Role">{agent.role ?? agent.tier ?? "worker"}</Fact>
          <Fact label="Generation" mono>
            Gen {agent.generation}
          </Fact>
          <Fact label="Reputation" mono>
            {agent.reputation}/100
          </Fact>
          <Fact label="Balance" mono>
            {credits(agent.balance_credits)}
          </Fact>
          {agent.model && <Fact label="Model">{agent.model}</Fact>}
          {agent.current_job && <Fact label="Current job">{agent.current_job}</Fact>}
        </InspectorSection>
      }
      usage={
        agent.mutation_note ? (
          <InspectorSection title="Mutation">
            <p className="px-2 py-1.5 text-xs leading-relaxed text-muted-foreground">{agent.mutation_note}</p>
          </InspectorSection>
        ) : undefined
      }
    />
  );
}

export default function FloorInspector({
  job,
  agent,
  events,
  presence,
  onClose,
}: {
  job: Job | null;
  agent: Agent | null;
  events: FloorEventLogItem[];
  presence?: Presence;
  onClose: () => void;
}) {
  const [view, setView] = useState<InspectorView>("summary");
  const selectionKey = job ? `job-${job.id}` : agent ? `agent-${agent.id}` : "none";
  useEffect(() => {
    setView("summary");
  }, [selectionKey]);

  if (!job && !agent) return null;

  const tabs: InspectorTab[] = job
    ? [
        { id: "summary", label: "Summary", icon: <FileTextIcon className="size-icon-sm" /> },
        { id: "reviews", label: "Reviews", icon: <GitPullRequestIcon className="size-icon-sm" /> },
        { id: "artifacts", label: "Activity", icon: <MessageSquareIcon className="size-icon-sm" /> },
      ]
    : [
        { id: "summary", label: "Summary", icon: <FileTextIcon className="size-icon-sm" /> },
        { id: "artifacts", label: "Activity", icon: <MessageSquareIcon className="size-icon-sm" /> },
      ];

  const fullTimeline = job ? jobTimeline(events, job.id, 60) : agentTimeline(events, agent?.name ?? "", 60);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start gap-2 px-3 pb-1 pt-3">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-foreground">{job ? job.title : agent?.name}</div>
          <div className="truncate text-2xs text-muted-foreground">
            {job ? `Job #${job.id} · ${job.status}` : `Agent · Gen ${agent?.generation} · rep ${agent?.reputation}/100`}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-interactive-hover hover:text-foreground"
        >
          <XIcon className="size-icon-sm" />
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <SessionInspectorShellView
          ariaLabel={job ? `Job ${job.title} details` : `Agent ${agent?.name} details`}
          activeView={view}
          onViewChange={setView}
          tabs={tabs}
          browserPoppedOut={false}
          summaryView={
            job ? <JobSummary job={job} events={events} /> : <AgentSummary agent={agent!} events={events} presence={presence} />
          }
          reviewsView={
            job ? (
              <InspectorReviewsView
                externalLink={FloorExternalLink}
                groups={jobReviewGroups(job, events)}
                isLoading={false}
                labels={REVIEW_LABELS}
                renderAvatar={(harness) => <AgentAvatar provider={harness} />}
                renderMarkdown={(body) => <span className="whitespace-pre-wrap">{body}</span>}
              />
            ) : undefined
          }
          artifactsView={
            <div className="px-3 py-2">
              {fullTimeline.length ? (
                <InspectorActivityTimelineView events={fullTimeline} />
              ) : (
                <p className={inspectorEmptyClass}>No events recorded yet.</p>
              )}
            </div>
          }
        />
      </div>
    </div>
  );
}
