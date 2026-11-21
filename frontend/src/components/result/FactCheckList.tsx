import { ExternalLink, ShieldCheck, AlertCircle, HelpCircle } from "lucide-react";
import type { FactCheckResult } from "@/lib/types";

const VERDICT_ICONS: Record<string, typeof ShieldCheck> = {
  Fałsz: AlertCircle,
  Prawda: ShieldCheck,
  "Częściowo prawda": HelpCircle,
  "Częściowo fałsz": HelpCircle,
  "Bez dowodów": HelpCircle,
};

const VERDICT_COLORS: Record<string, string> = {
  Fałsz: "text-bad-fg border-bad-fg bg-bad-bg",
  Prawda: "text-good-fg border-good-fg bg-good-bg",
  "Częściowo prawda": "text-warn-fg border-warn-fg bg-warn-bg",
  "Częściowo fałsz": "text-warn-fg border-warn-fg bg-warn-bg",
  "Bez dowodów": "text-muted border-line bg-surface",
};

interface FactCheckListProps {
  checks: FactCheckResult[];
}

export function FactCheckList({ checks }: FactCheckListProps) {
  return (
    <section aria-labelledby="factcheck-heading" className="space-y-4">
      <h3 id="factcheck-heading" className="text-xl font-semibold flex items-center gap-2">
        <ShieldCheck className="size-5" />
        Powiązane sprawdzenia faktów (Google Fact Check Tools)
      </h3>
      <div className="space-y-3">
        {checks.map((check, index) => {
          const Icon = VERDICT_ICONS[check.rating] || HelpCircle;
          const colorClass = VERDICT_COLORS[check.rating] || VERDICT_COLORS["Bez dowodów"];

          return (
            <article key={index} className="rounded-xl border bg-surface p-4 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium leading-relaxed">{check.claim}</p>
                  {check.claimant && (
                    <p className="text-sm text-muted mt-1">
                      Twierdzenie: <span className="font-medium">{check.claimant}</span>
                      {check.claim_date ? ` (${check.claim_date})` : ""}
                    </p>
                  )}
                </div>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium border ${colorClass} shrink-0`}>
                  <Icon className="size-3.5" />
                  {check.rating || "Brak oceny"}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-sm text-muted border-t border-line pt-3">
                <span className="font-medium">{check.publisher_name}</span>
                {check.publisher_site && (
                  <span className="font-mono">{check.publisher_site}</span>
                )}
                {check.claim_review_url && (
                  <a
                    href={check.claim_review_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-accent hover:underline"
                  >
                    <ExternalLink className="size-3.5" />
                    Pełne sprawdzenie
                  </a>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <p className="text-sm text-muted">
        Wyniki pochodzą z Google Fact Check Tools API. Kliknij „Pełne sprawdzenie”, by przejść do oryginału.
      </p>
    </section>
  );
}