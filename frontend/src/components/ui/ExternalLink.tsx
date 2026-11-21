import { ExternalLink as ExternalLinkIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { safeHttpUrl } from "@/lib/links";

interface ExternalLinkProps {
  href: string | null | undefined;
  children: ReactNode;
  className?: string;
}

/** Renders a link only for http(s) addresses; any other value falls back to plain text. */
export function ExternalLink({ href, children, className }: ExternalLinkProps) {
  const safe = safeHttpUrl(href);
  if (!safe) return <span className={className}>{children}</span>;
  return (
    <a
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
      className={cx("link", className)}
    >
      {children}
      <ExternalLinkIcon
        aria-hidden="true"
        className="ml-1 inline size-4 align-[-0.15em]"
      />
      <span className="sr-only"> (otwiera się w nowej karcie)</span>
    </a>
  );
}
