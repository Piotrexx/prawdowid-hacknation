import { Check, Info, X, type LucideIcon } from "lucide-react";
import { cx } from "@/lib/cx";
import { plural } from "@/lib/format";
import { STANCE_LABELS } from "@/lib/labels";
import type { Evidence, Stance } from "@/lib/types";
import { SourceMeta } from "./SourceMeta";

const STANCE_ORDER: Stance[] = ["supports", "refutes", "context"];

const STANCE_STYLES: Record<Stance, { icon: LucideIcon; rail: string; text: string }> = {
  supports: { icon: Check, rail: "border-ok-line", text: "text-ok-fg" },
  refutes: { icon: X, rail: "border-bad-line", text: "text-bad-fg" },
  context: { icon: Info, rail: "border-calm-line", text: "text-calm-fg" },
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
      <p className="text-muted">
        Brak materiałów źródłowych, które dotyczą tego twierdzenia.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {groupByStance(evidence).map(([stance, items]) => {
        const style = STANCE_STYLES[stance];
        const Icon = style.icon;
        return (
          <section key={stance}>
            <h5 className={cx("flex items-center gap-2 font-semibold", style.text)}>
              <Icon aria-hidden="true" className="size-5 shrink-0" />
              {STANCE_LABELS[stance]}{" "}
              <span className="font-normal text-muted">
                ({items.length} {plural(items.length, "materiał", "materiały", "materiałów")})
              </span>
            </h5>
            <ol className={cx("mt-3 ml-2 space-y-5 border-l-2 pl-5", style.rail)}>
              {items.map((item) => (
                <li key={item.id} className="relative">
                  <span
                    aria-hidden="true"
                    className={cx(
                      "absolute top-2 -left-[1.6875rem] size-3 rounded-full border-2 bg-surface",
                      style.rail,
                    )}
                  />
                  <blockquote className="rounded-lg border border-line bg-surface px-4 py-3 text-[1.0625rem] leading-relaxed">
                    „{item.quote}”
                  </blockquote>
                  <div className="mt-2">
                    <SourceMeta source={item.source} archival={item.archival} />
                  </div>
                </li>
              ))}
            </ol>
          </section>
        );
      })}
    </div>
  );
}
