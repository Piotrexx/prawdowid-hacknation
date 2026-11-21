import { Check, Info, X, type LucideIcon } from "lucide-react";
import { cx } from "@/lib/cx";
import { plural } from "@/lib/format";
import { STANCE_LABELS } from "@/lib/labels";
import type { Evidence, Stance } from "@/lib/types";
import { SourceMeta } from "./SourceMeta";

const STANCE_ORDER: Stance[] = ["supports", "refutes", "context"];

const STANCE_STYLES: Record<Stance, { icon: LucideIcon; text: string }> = {
  supports: { icon: Check, text: "text-ok-fg" },
  refutes: { icon: X, text: "text-bad-fg" },
  context: { icon: Info, text: "text-calm-fg" },
};

function groupByStance(evidence: Evidence[]): Array<[Stance, Evidence[]]> {
  return STANCE_ORDER.map((stance): [Stance, Evidence[]] => [
    stance,
    evidence.filter((item) =>
      // An unknown stance is safest shown as context, never as support or refutation.
      stance === "context"
        ? item.stance !== "supports" && item.stance !== "refutes"
        : item.stance === stance,
    ),
  ]).filter(([, items]) => items.length > 0);
}

export function EvidenceChain({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) {
    return (
      <p className="text-ink-soft">
        Brak materiałów źródłowych, które dotyczą tego twierdzenia.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {groupByStance(evidence).map(([stance, items]) => {
        const style = STANCE_STYLES[stance];
        const Icon = style.icon;
        return (
          <section key={stance}>
            <h4 className={cx("mb-2.5 flex items-center gap-2 text-[0.9375rem] font-bold", style.text)}>
              <Icon aria-hidden="true" className="size-4.5 shrink-0" strokeWidth={2.4} />
              {STANCE_LABELS[stance]}{" "}
              <span className="font-normal text-muted">
                ({items.length} {plural(items.length, "materiał", "materiały", "materiałów")})
              </span>
            </h4>
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li key={item.id} className="border border-line bg-surface px-4.5 py-4">
                  <blockquote className="text-[0.9375rem] leading-relaxed">
                    „{item.quote}”
                  </blockquote>
                  <div className="mt-2.5">
                    <SourceMeta source={item.source} archival={item.archival} />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
