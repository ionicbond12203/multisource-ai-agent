import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

/** Square brand mark showing the first letter of the product name. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-[30px] shrink-0 items-center justify-center rounded-lg bg-accent font-display text-[17px] font-semibold text-white",
        className,
      )}
    >
      {siteConfig.name.charAt(0)}
    </span>
  );
}
