import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

interface PageShellProps {
  title: string;
  lead?: ReactNode;
  wide?: boolean;
  /** Opcjonalna zawartość wyrównana do prawej, w tym samym rzędzie co tytuł. */
  headerAside?: ReactNode;
  children: ReactNode;
}

export function PageShell({ title, lead, wide = false, headerAside, children }: PageShellProps) {
  return (
    <div className="px-5 py-8 sm:p-10">
      <div className={cx("w-full", wide ? "max-w-none" : "max-w-[52rem]")}>
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-[1.75rem] leading-tight font-bold tracking-[-0.01em] text-balance sm:text-[1.875rem]">
              {title}
            </h1>
            <span aria-hidden="true" className="title-rule my-4" />
            {lead ? (
              <p className="max-w-[44rem] text-base leading-relaxed text-ink-soft">{lead}</p>
            ) : null}
          </div>
          {headerAside ? <div className="shrink-0">{headerAside}</div> : null}
        </div>
        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}
