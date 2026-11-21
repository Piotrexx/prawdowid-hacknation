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
    <div className={cx("mx-auto w-full px-4 py-8 sm:py-10", wide ? "max-w-5xl" : "max-w-[46rem]")}>
      {/* gov.pl sets page titles in heavy Open Sans over a short blue rule. */}
      <h1 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl">
        {title}
      </h1>
      <div aria-hidden="true" className="mt-4 h-1 w-16 bg-accent" />
      {lead ? <p className="mt-4 max-w-[40rem] text-lg text-muted">{lead}</p> : null}
      <div className="mt-8">{children}</div>
    </div>
  );
}
