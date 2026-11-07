import Link from "next/link";
import { siteConfig } from "@/config/site";
import { Badge } from "@/components/ui/badge";
import { LogoMark } from "@/components/ui/logo";
import { cn } from "@/lib/utils";

interface AppHeaderProps {
  /** href of the current page, used to highlight its nav item. */
  activeHref: string;
  /** Shown on the right so visitors know whether answers come from a live backend. */
  apiMode: "mock" | "live";
}

export function AppHeader({ activeHref, apiMode }: AppHeaderProps) {
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-line bg-surface px-6 py-2.5">
      <Link href="/" className="flex items-center gap-2.5">
        <LogoMark />
        <span className="font-display text-lg font-semibold tracking-tight text-ink">{siteConfig.name}</span>
        <Badge tone="accent" className="py-px text-[11px]">
          Demo
        </Badge>
      </Link>

      <nav aria-label="Main" className="flex flex-wrap gap-1 md:ml-4">
        {siteConfig.nav.map((item) => {
          const isActive = item.href === activeHref;
          if (!item.available) {
            return (
              <span
                key={item.href}
                aria-disabled="true"
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-ink-faint"
              >
                {item.label}
                <span className="text-[11px] text-ink-faint">Soon</span>
              </span>
            );
          }
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "rounded-lg px-3 py-2 text-sm",
                isActive ? "bg-muted font-medium text-ink" : "text-ink-muted hover:bg-muted hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1.5 text-xs text-ink-muted">
          <span
            aria-hidden="true"
            className={cn("size-[7px] rounded-full", apiMode === "live" ? "bg-success" : "bg-warning")}
          />
          {apiMode === "live" ? "Backend connected" : "Sample data (no backend)"}
        </span>
        <a
          href={siteConfig.repoUrl}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-line-strong px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-subtle"
        >
          View source
        </a>
      </div>
    </header>
  );
}
