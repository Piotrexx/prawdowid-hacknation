import {
  CircleCheck,
  CircleHelp,
  CircleX,
  MessageSquareQuote,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { cx } from "@/lib/cx";
import { SHORT_VERDICT_LABELS, VERDICT_LABELS } from "@/lib/labels";
import type { Verdict } from "@/lib/types";

interface VerdictStyle {
  icon: LucideIcon;
  band: string;
  chip: string;
}

const VERDICT_STYLES: Record<Verdict, VerdictStyle> = {
  potwierdzone: {
    icon: CircleCheck,
    band: "border-ok-line bg-ok-bg text-ok-fg",
    chip: "bg-ok-bg text-ok-fg",
  },
  falszywe: {
    icon: CircleX,
    band: "border-bad-line bg-bad-bg text-bad-fg",
    chip: "bg-bad-bg text-bad-fg",
  },
  wprowadzajace_w_blad: {
    icon: TriangleAlert,
    band: "border-warn-line bg-warn-bg text-warn-fg",
    chip: "bg-warn-bg text-warn-fg",
  },
  brak_wystarczajacych_dowodow: {
    icon: CircleHelp,
    band: "border-calm-line bg-calm-bg text-calm-fg",
    chip: "bg-calm-bg text-calm-fg",
  },
  nie_podlega_weryfikacji: {
    icon: MessageSquareQuote,
    band: "border-info-line bg-info-bg text-info-fg",
    chip: "bg-info-bg text-info-fg",
  },
};

export const VERDICT_SEVERITY: Verdict[] = [
  "falszywe",
  "wprowadzajace_w_blad",
  "brak_wystarczajacych_dowodow",
  "nie_podlega_weryfikacji",
  "potwierdzone",
];

const VERDICT_STRIPES: Record<Verdict, string> = {
  potwierdzone: "border-l-ok-fg",
  falszywe: "border-l-bad-fg",
  wprowadzajace_w_blad: "border-l-warn-fg",
  brak_wystarczajacych_dowodow: "border-l-calm-fg",
  nie_podlega_weryfikacji: "border-l-info-fg",
};

export function verdictStripe(verdict: Verdict | undefined): string {
  return (verdict && VERDICT_STRIPES[verdict]) || "border-l-line-mid";
}

function styleFor(verdict: Verdict): VerdictStyle {
  return VERDICT_STYLES[verdict] ?? VERDICT_STYLES.brak_wystarczajacych_dowodow;
}

interface VerdictProps {
  verdict: Verdict;
  label?: string;
}

/** Full-width verdict row (for the result page header). */
export function VerdictBanner({ verdict, label }: VerdictProps) {
  const style = styleFor(verdict);
  const Icon = style.icon;
  return (
    <p
      className={cx(
        "flex items-center gap-3 border-y px-5 py-3.5 text-xl font-bold sm:px-10",
        style.band,
      )}
    >
      <Icon aria-hidden="true" className="size-6.5 shrink-0" />
      <span>
        <span className="sr-only">Ocena: </span>
        {label ?? VERDICT_LABELS[verdict] ?? verdict}
      </span>
    </p>
  );
}

interface VerdictBadgeProps {
  verdict: Verdict;
  confidence?: number | null;
  justification?: string | null;
}

/** Full verdict badge with optional confidence and justification (used on the About page). */
export function VerdictBadge({ verdict, confidence: _confidence, justification: _justification }: VerdictBadgeProps) {
  const style = styleFor(verdict);
  const Icon = style.icon;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold tracking-[0.02em] uppercase",
        style.chip,
      )}
    >
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {VERDICT_LABELS[verdict] ?? verdict}
    </span>
  );
}

/** Compact, icon-free chip for lists and the table of contents. */
export function VerdictChip({ verdict, uppercase = false }: VerdictProps & { uppercase?: boolean }) {
  return (
    <span
      className={cx(
        "inline-block shrink-0 px-3 py-1.5 text-xs font-bold whitespace-nowrap",
        uppercase && "tracking-[0.02em] uppercase",
        styleFor(verdict).chip,
      )}
    >
      {SHORT_VERDICT_LABELS[verdict] ?? VERDICT_LABELS[verdict] ?? verdict}
    </span>
  );
}
