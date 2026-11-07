"use client";

import { Copy, ShieldAlert, ShieldCheck, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import Markdown, { type Components } from "react-markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/ui/logo";
import { linkifyCitations, parseCitationHref } from "../lib/citations";
import type { AssistantMessage as AssistantMessageType } from "../types";
import { AgentRunCard } from "./agent-run-card";
import { CitationChip } from "./citation-chip";

interface AssistantMessageProps {
  message: AssistantMessageType;
  /** Citation number currently shown in the evidence panel for this message, if any. */
  activeSourceIndex: number | null;
  onSelectCitation: (messageId: string, sourceIndex: number) => void;
  onFollowUp: (question: string) => void;
}

export function AssistantMessage({
  message,
  activeSourceIndex,
  onSelectCitation,
  onFollowUp,
}: AssistantMessageProps) {
  const [copied, setCopied] = useState(false);
  // Feedback is kept locally for now. Send it to the backend once it exposes a feedback endpoint.
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const markdownComponents: Components = {
    a({ href, children }) {
      const citation = parseCitationHref(href);
      if (citation === null) {
        return (
          <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">
            {children}
          </a>
        );
      }
      return (
        <CitationChip
          index={citation}
          source={message.sources.find((source) => source.index === citation)}
          active={activeSourceIndex === citation}
          onSelect={(index) => onSelectCitation(message.id, index)}
        />
      );
    },
    p: ({ children }) => <p className="mb-2.5 last:mb-0">{children}</p>,
    ol: ({ children }) => <ol className="mb-2.5 list-decimal pl-5 last:mb-0">{children}</ol>,
    ul: ({ children }) => <ul className="mb-2.5 list-disc pl-5 last:mb-0">{children}</ul>,
    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  };

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked (e.g. insecure context); copying is optional.
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {message.run.steps.length > 0 && <AgentRunCard run={message.run} />}

      <div className="flex gap-3">
        <LogoMark className="size-7 text-sm" />
        <div className="min-w-0 flex-1">
          <div className="text-[15px] leading-[1.7]">
            <Markdown components={markdownComponents}>{linkifyCitations(message.content)}</Markdown>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {message.grounded ? (
              <Badge tone="success" className="py-1">
                <ShieldCheck aria-hidden="true" className="size-3.5" />
                Grounded · every claim cited
              </Badge>
            ) : (
              <Badge tone="warning" className="py-1">
                <ShieldAlert aria-hidden="true" className="size-3.5" />
                Not found in your files
              </Badge>
            )}
            <Button variant="ghost" size="sm" onClick={copyAnswer}>
              <Copy aria-hidden="true" className="size-3.5" />
              {copied ? "Copied" : "Copy"}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Good answer"
              aria-pressed={feedback === "up"}
              onClick={() => setFeedback((value) => (value === "up" ? null : "up"))}
              className={feedback === "up" ? "text-accent" : undefined}
            >
              <ThumbsUp aria-hidden="true" className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Bad answer"
              aria-pressed={feedback === "down"}
              onClick={() => setFeedback((value) => (value === "down" ? null : "down"))}
              className={feedback === "down" ? "text-danger" : undefined}
            >
              <ThumbsDown aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </div>
      </div>

      {message.followUps.length > 0 && (
        <div className="flex flex-wrap gap-2 pl-10">
          {message.followUps.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => onFollowUp(question)}
              className="cursor-pointer rounded-full border border-line-strong bg-surface px-3.5 py-2 text-[13px] hover:bg-subtle"
            >
              {question}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
