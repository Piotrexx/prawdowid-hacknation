import {
  CircleCheck,
  CircleHelp,
  CircleX,
  MessageSquareQuote,
  TriangleAlert,
  User,
  type LucideIcon,
} from "lucide-react";
import { cx } from "@/lib/cx";
import type { VerdictLabel } from "@/lib/types";

const VERDICT_LABELS: Record<VerdictLabel, string> = {
  fake_news: "Fake news",
  prawdziwe: "Prawdziwe",
  niepewne: "Niepewne",
  satyna: "Satyra",
  opinia: "Opinia",
};

interface VerdictStyle {
  icon: LucideIcon;
  box: string;
  text: string;
}

const VERDICT_STYLES: Record<VerdictLabel, VerdictStyle> = {
  fake_news: { icon: CircleX, box: "border-bad-line bg-bad-bg", text: "text-bad-fg" },
  prawdziwe: { icon: CircleCheck, box: "border-ok-line bg-ok-bg", text: "text-ok-fg" },
  niepewne: { icon: CircleHelp, box: "border-calm-line bg-calm-bg", text: "text-calm-fg" },
  satyna: { icon: TriangleAlert, box: "border-warn-line bg-warn-bg", text: "text-warn-fg" },
  opinia: { icon: User, box: "border-info-line bg-info-bg", text: "text-info-fg" },
};

function styleFor(verdict: VerdictLabel): VerdictStyle {
  return VERDICT_STYLES[verdict] ?? VERDICT_STYLES.niepewne;
}

function labelFor(verdict: VerdictLabel): string {
  return VERDICT_LABELS[verdict] || verdict;
}

interface VerdictBadgeProps {
  verdict: VerdictLabel;
  confidence?: number | null;
  justification?: string | null;
}

export function VerdictBadge({ verdict, confidence, justification }: VerdictBadgeProps) {
  const style = styleFor(verdict);
  const Icon = style.icon;

  return (
    <div className={cx("space-y-3", style.box, "rounded-xl border p-5")}>
      <div className="flex items-start gap-4">
        <div className={cx("flex-shrink-0 p-3 rounded-full", style.text)}>
          <Icon aria-hidden="true" className="size-8" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <span className={cx("text-2xl font-bold", style.text)}>
              {labelFor(verdict)}
            </span>
            {confidence !== null && confidence !== undefined && (
              <span className={cx("px-3 py-1 rounded-full text-sm font-medium border", style.box, style.text)}>
                Pewność: {Math.round(confidence * 100)}%
              </span>
            )}
          </div>
          {justification && (
            <p className="mt-3 text-base leading-relaxed whitespace-pre-line">{justification}</p>
          )}
        </div>
      </div>
    </div>
  );
}