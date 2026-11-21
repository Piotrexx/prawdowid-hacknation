import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

interface PageShellProps {
  title: string;
  lead?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}

export function PageShell({ title, lead, wide = false, children }: PageShellProps) {
  return (
    <div className="px-5 py-8 sm:p-10">
      <div className={cx("w-full", wide ? "max-w-none" : "max-w-[52rem]")}>
        <h1 className="text-[1.75rem] leading-tight font-bold tracking-[-0.01em] text-balance sm:text-[1.875rem]">
          {title}
        </h1>
        <span aria-hidden="true" className="title-rule my-4" />
        {lead ? (
          <p className="max-w-[44rem] text-base leading-relaxed text-ink-soft">{lead}</p>
        ) : null}
        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}
