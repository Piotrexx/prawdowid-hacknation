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
      <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h1>
      {lead ? <p className="mt-3 max-w-[40rem] text-lg text-muted">{lead}</p> : null}
      <div className="mt-8">{children}</div>
    </div>
  );
}
