"use client";

import { ArrowUp, Paperclip } from "lucide-react";
import { useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

interface ComposerProps {
  onSend: (text: string) => void;
  onAttach: (files: File[]) => void;
  /** Number of files the next answer can use. */
  usableFileCount: number;
  disabled?: boolean;
}

/** Question box. Enter sends, Shift+Enter adds a new line. */
export function Composer({ onSend, onAttach, usableFileCount, disabled = false }: ComposerProps) {
  const [text, setText] = useState("");
  const textareaId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canSend = text.trim().length > 0 && !disabled;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSend(text);
    setText("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: don't send while an IME (e.g. Chinese input) is still composing.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border border-line-stronger bg-surface py-3 pr-3 pl-4">
      <label htmlFor={textareaId} className="sr-only">
        Ask a question
      </label>
      <textarea
        id={textareaId}
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your documents…"
        className="w-full resize-none bg-transparent text-[15px] outline-none placeholder:text-ink-faint"
      />
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-label="Attach files"
          onClick={() => fileInputRef.current?.click()}
          className="flex size-9 cursor-pointer items-center justify-center rounded-lg border border-line text-ink-muted hover:bg-subtle"
        >
          <Paperclip aria-hidden="true" className="size-[17px]" />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          accept={siteConfig.upload.acceptedExtensions.join(",")}
          onChange={(event) => {
            if (event.target.files) onAttach([...event.target.files]);
            event.target.value = "";
          }}
        />
        <span className="flex h-9 items-center rounded-lg border border-line bg-subtle px-2.5 text-xs">
          Knowledge base · {usableFileCount} {usableFileCount === 1 ? "file" : "files"}
        </span>
        <button
          type="submit"
          aria-label="Send"
          disabled={!canSend}
          className={cn(
            "ml-auto flex size-10 items-center justify-center rounded-[10px] text-white transition-colors",
            canSend
              ? "cursor-pointer bg-accent hover:bg-accent-strong"
              : "cursor-not-allowed bg-line-stronger",
          )}
        >
          <ArrowUp aria-hidden="true" className="size-[18px]" strokeWidth={2} />
        </button>
      </div>
    </form>
  );
}
