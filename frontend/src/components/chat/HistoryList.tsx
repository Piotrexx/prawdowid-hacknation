"use client";

import { History } from "lucide-react";
import Link from "next/link";
import { VERDICT_SEVERITY, VerdictChip, verdictStripe } from "@/components/result/VerdictBadge";
import { cx } from "@/lib/cx";
import { formatShortDateTime, formatTime } from "@/lib/format";
import { useHistory, type HistoryEntry } from "@/lib/history";
import { checkPath } from "@/lib/links";

function sameDay(a: Date, b: Date): boolean {
  return a.toDateString() === b.toDateString();
}

/** "dziś, 14:05", "wczoraj, 9:30", otherwise a short date with time. */
function when(value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (sameDay(date, today)) return `dziś, ${formatTime(value)}`;
  if (sameDay(date, yesterday)) return `wczoraj, ${formatTime(value)}`;
  return formatShortDateTime(value);
}

function sortedVerdicts(entry: HistoryEntry) {
  return [...entry.verdicts].sort(
    (a, b) => VERDICT_SEVERITY.indexOf(a) - VERDICT_SEVERITY.indexOf(b),
  );
}

/** This browser's completed checks, newest first, as compact links for the app sidebar. */
export function HistoryList({ onNavigate }: { onNavigate?: () => void }) {
  const entries = useHistory();
  if (entries === null) return null;
  if (entries.length === 0) {
    return (
      <p className="flex gap-2.5 px-2 text-sm text-ink-soft">
        <History aria-hidden="true" className="mt-0.5 size-4.5 shrink-0 text-muted" />
        Tu pojawią się Twoje sprawdzenia.
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-0.5">
      {entries.map((entry) => {
        const verdicts = sortedVerdicts(entry);
        return (
          <li key={entry.id}>
            <Link
              href={checkPath(entry.id)}
              onClick={onNavigate}
              className={cx(
                "group flex flex-col gap-1.5 border-l-[3px] px-3 py-2.5 hover:bg-surface",
                verdictStripe(verdicts[0]),
              )}
            >
              <span className="line-clamp-2 text-sm leading-snug text-ink group-hover:text-accent group-hover:underline">
                {entry.preview}
              </span>
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                {verdicts[0] ? <VerdictChip verdict={verdicts[0]} uppercase /> : null}
                {verdicts.length > 1 ? (
                  <span className="text-xs text-muted">+{verdicts.length - 1}</span>
                ) : null}
                <span className="text-xs text-muted">{when(entry.createdAt)}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
