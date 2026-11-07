"use client";

import { ChevronDown, Route } from "lucide-react";
import { useId, useState } from "react";
import type { AgentRun } from "../types";
import { cn, formatSeconds } from "@/lib/utils";
import { AgentSteps } from "./agent-steps";

/** Collapsible summary of how the agent produced an answer. */
export function AgentRunCard({ run, defaultOpen = true }: { run: AgentRun; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full cursor-pointer items-center gap-2.5 px-3.5 py-2.5 text-left"
      >
        <Route aria-hidden="true" className="size-4 text-accent" />
        <span className="font-medium">Agent run</span>
        <span className="text-xs text-ink-faint">
          {run.steps.length} steps · {formatSeconds(run.totalMs)}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn("ml-auto size-4 text-ink-muted transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div id={panelId} className="border-t border-muted px-3.5 pt-2 pb-3">
          <AgentSteps steps={run.steps} />
        </div>
      )}
    </div>
  );
}
