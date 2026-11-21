import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

interface DisclosureProps {
  summary: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}

export function Disclosure({ summary, children, className, id }: DisclosureProps) {
  return (
    <details id={id} className={cx("group", className)}>
      <summary className="link inline-flex min-h-11 items-center gap-1.5 rounded font-semibold">
        <ChevronRight
          aria-hidden="true"
          className="size-5 shrink-0 transition-transform group-open:rotate-90"
        />
        {summary}
      </summary>
      <div className="pt-2 pb-1">{children}</div>
    </details>
  );
}
