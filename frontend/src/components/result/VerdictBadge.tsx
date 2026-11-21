import {
  CircleCheck,
  CircleHelp,
  CircleX,
  MessageSquareQuote,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { cx } from "@/lib/cx";
import { VERDICT_LABELS } from "@/lib/labels";
import type { Verdict } from "@/lib/types";

interface VerdictStyle {
  icon: LucideIcon;
  box: string;
  text: string;
}

// "Brak wystarczających dowodów" is an honest answer, so it gets a calm neutral tone, not an error tone.
const VERDICT_STYLES: Record<Verdict, VerdictStyle> = {
  potwierdzone: { icon: CircleCheck, box: "border-ok-line bg-ok-bg", text: "text-ok-fg" },
  falszywe: { icon: CircleX, box: "border-bad-line bg-bad-bg", text: "text-bad-fg" },
  wprowadzajace_w_blad: {
    icon: TriangleAlert,
    box: "border-warn-line bg-warn-bg",
    text: "text-warn-fg",
  },
  brak_wystarczajacych_dowodow: {
    icon: CircleHelp,
    box: "border-calm-line bg-calm-bg",
    text: "text-calm-fg",
  },
  nie_podlega_weryfikacji: {
    icon: MessageSquareQuote,
    box: "border-info-line bg-info-bg",
    text: "text-info-fg",
  },
};

function styleFor(verdict: Verdict): VerdictStyle {
  return VERDICT_STYLES[verdict] ?? VERDICT_STYLES.brak_wystarczajacych_dowodow;
}

function labelFor(verdict: Verdict, label?: string): string {
  return label?.trim() || VERDICT_LABELS[verdict] || verdict;
}

interface VerdictProps {
  verdict: Verdict;
  label?: string;
}

/** Full-width verdict row for a claim card: icon, text label and colour together. */
export function VerdictBanner({ verdict, label }: VerdictProps) {
  const style = styleFor(verdict);
  const Icon = style.icon;
  return (
    <p
      className={cx(
        "flex items-center gap-3 border-y px-5 py-3 text-xl font-semibold",
        style.box,
        style.text,
      )}
    >
      <Icon aria-hidden="true" className="size-7 shrink-0" />
      <span>
        <span className="sr-only">Ocena: </span>
        {labelFor(verdict, label)}
      </span>
    </p>
  );
}

export function VerdictBadge({ verdict, label }: VerdictProps) {
  const style = styleFor(verdict);
  const Icon = style.icon;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-sm font-medium",
        style.box,
        style.text,
      )}
    >
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {labelFor(verdict, label)}
    </span>
  );
}
