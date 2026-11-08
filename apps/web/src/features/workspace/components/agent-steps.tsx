import { Check, Loader2, X } from "lucide-react";
import type { AgentStep } from "../types";
import { formatSeconds } from "@/lib/utils";

/**
 * The LangGraph nodes an answer went through, one row per node.
 *
 * The rows share one grid (each row is a subgrid), so the node-name column is
 * as wide as the longest name, e.g. "verify_citations", and never overlaps
 * the summary.
 */
export function AgentSteps({ steps }: { steps: AgentStep[] }) {
  return (
    <ol className="grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-1.5 font-mono text-xs">
      {steps.map((step) => (
        <li key={step.id} className="col-span-4 grid grid-cols-subgrid items-center">
          <StepIcon status={step.status} />
          <span className="text-ink">{step.node}</span>
          <span className="min-w-0 text-ink-muted">{step.summary}</span>
          <span className="shrink-0 text-ink-faint">{formatSeconds(step.durationMs)}</span>
        </li>
      ))}
    </ol>
  );
}

function StepIcon({ status }: { status: AgentStep["status"] }) {
  if (status === "done") {
    return <Check aria-label="Done" className="size-3.5 shrink-0 text-success" strokeWidth={2.4} />;
  }
  if (status === "failed") {
    return <X aria-label="Failed" className="size-3.5 shrink-0 text-danger" strokeWidth={2.4} />;
  }
  return <Loader2 aria-label="Running" className="size-3.5 shrink-0 animate-spin text-accent" />;
}
