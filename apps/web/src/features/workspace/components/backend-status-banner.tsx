import { CircleAlert, Loader2 } from "lucide-react";
import type { BackendStatus } from "../hooks/use-backend-status";

/** Explains a cold start of the free backend, so a slow first answer doesn't look like a broken app. */
export function BackendStatusBanner({ status }: { status: BackendStatus }) {
  if (status === "waking") {
    return (
      <div
        role="status"
        className="flex items-center gap-2.5 border-b border-line bg-accent-tint px-6 py-2 text-[13px] text-ink"
      >
        <Loader2 aria-hidden="true" className="size-4 shrink-0 animate-spin text-accent" />
        <span>
          <strong className="font-semibold">Waking up the backend.</strong> The free server sleeps when nobody
          uses it, so the first visit can take up to a minute. You can start typing meanwhile.
        </span>
      </div>
    );
  }
  if (status === "unreachable") {
    return (
      <div
        role="alert"
        className="flex items-center gap-2.5 border-b border-line bg-subtle px-6 py-2 text-[13px] text-ink"
      >
        <CircleAlert aria-hidden="true" className="size-4 shrink-0 text-danger" />
        <span>The backend isn&apos;t responding. Try reloading the page in a minute.</span>
      </div>
    );
  }
  return null;
}
