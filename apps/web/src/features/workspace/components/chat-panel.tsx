"use client";

import { CircleAlert, Loader2, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { LogoMark } from "@/components/ui/logo";
import { siteConfig } from "@/config/site";
import type { CitationFocus } from "../lib/workspace-reducer";
import type { ChatMessage } from "../types";
import { AssistantMessage } from "./assistant-message";
import { Composer } from "./composer";

interface ChatPanelProps {
  title: string;
  messages: ChatMessage[];
  focus: CitationFocus | null;
  pending: boolean;
  error: string | null;
  usableFileCount: number;
  totalFileCount: number;
  suggestedQuestions: string[];
  onSend: (text: string) => void;
  onAttach: (files: File[]) => void;
  onSelectCitation: (messageId: string, sourceIndex: number) => void;
  onDismissError: () => void;
}

export function ChatPanel({
  title,
  messages,
  focus,
  pending,
  error,
  usableFileCount,
  totalFileCount,
  suggestedQuestions,
  onSend,
  onAttach,
  onSelectCitation,
  onDismissError,
}: ChatPanelProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const renderedCount = useRef(messages.length);

  // Scroll to the newest message when one is added, but not on first load.
  useEffect(() => {
    const grew = messages.length > renderedCount.current;
    renderedCount.current = messages.length;
    if (grew || pending) endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  return (
    <main className="flex min-w-0 flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-6 py-3.5">
        <h1 className="text-base font-semibold">{title}</h1>
        <Badge>
          Answering from {usableFileCount} of {totalFileCount} files
        </Badge>
      </div>

      <div className="mx-auto flex w-full max-w-[780px] flex-1 flex-col gap-5 px-6 py-6" aria-live="polite">
        {messages.length === 0 && !pending && (
          <EmptyState suggestedQuestions={suggestedQuestions} onPick={onSend} />
        )}

        {messages.map((message) =>
          message.role === "user" ? (
            <div
              key={message.id}
              className="max-w-[82%] self-end rounded-2xl rounded-br-[4px] border border-line bg-surface px-4 py-3 whitespace-pre-wrap"
            >
              {message.content}
            </div>
          ) : (
            <AssistantMessage
              key={message.id}
              message={message}
              activeSourceIndex={focus?.messageId === message.id ? focus.sourceIndex : null}
              onSelectCitation={onSelectCitation}
              onFollowUp={onSend}
            />
          ),
        )}

        {pending && (
          <div className="flex items-center gap-3 text-sm text-ink-muted">
            <LogoMark className="size-7 text-sm" />
            <Loader2 aria-hidden="true" className="size-4 animate-spin text-accent" />
            Searching your files and drafting an answer…
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="mx-auto w-full max-w-[780px] px-6 pb-6">
        {error && (
          <div
            role="alert"
            className="mb-3 flex items-start gap-2 rounded-lg border border-danger-line bg-danger-soft px-3 py-2 text-sm text-danger"
          >
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span className="flex-1">{error}</span>
            <button
              type="button"
              aria-label="Dismiss error"
              onClick={onDismissError}
              className="cursor-pointer rounded p-0.5 hover:bg-danger-line/50"
            >
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
        )}
        <Composer onSend={onSend} onAttach={onAttach} usableFileCount={usableFileCount} disabled={pending} />
        <p className="mt-2 text-center text-xs text-ink-faint">
          Answers come only from your files and the sales database. Check cited sources before acting.
        </p>
      </div>
    </main>
  );
}

function EmptyState({
  suggestedQuestions,
  onPick,
}: {
  suggestedQuestions: string[];
  onPick: (q: string) => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <LogoMark className="size-10 text-xl" />
      <h2 className="font-display text-2xl font-semibold tracking-tight">Ask your documents anything</h2>
      <p className="max-w-md text-ink-muted">{siteConfig.tagline}</p>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {suggestedQuestions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className="cursor-pointer rounded-full border border-line-strong bg-surface px-3.5 py-2 text-[13px] hover:bg-subtle"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
