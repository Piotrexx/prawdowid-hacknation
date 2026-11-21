import { BookOpenText, Bot, GitCompareArrows, ShieldAlert } from "lucide-react";
import { useId } from "react";
import { Notice } from "@/components/ui/Notice";
import { Tag } from "@/components/ui/Tag";
import type { ClaimResult } from "@/lib/types";
import { EvidenceChain } from "./EvidenceChain";
import { StrengthMeter } from "./StrengthMeter";
import { VerdictBanner } from "./VerdictBadge";

interface ClaimCardProps {
  claim: ClaimResult;
  index: number;
  total: number;
}

export function ClaimCard({ claim, index, total }: ClaimCardProps) {
  const headingId = useId();

  return (
    <article
      aria-labelledby={headingId}
      className="overflow-hidden rounded-xl border border-line bg-surface"
    >
      <header className="px-5 pt-5 pb-4">
        <p className="flex flex-wrap items-center gap-2 text-muted">
          {total > 1 ? `Twierdzenie ${index} z ${total}` : "Sprawdzane twierdzenie"}
          {claim.risk === "high" ? (
            <Tag tone="warn" icon={ShieldAlert}>
              Temat wysokiego ryzyka
            </Tag>
          ) : null}
        </p>
        <h3 id={headingId} className="mt-1 text-xl leading-snug font-semibold">
          {claim.text}
        </h3>
      </header>

      <VerdictBanner verdict={claim.verdict} label={claim.verdict_label} />

      <div className="space-y-6 px-5 py-5">
        {claim.conflict ? (
          <Notice tone="warn" icon={GitCompareArrows} title="Źródła podają rozbieżne informacje">
            <p>Przeczytaj materiały z obu stron, zanim wyrobisz sobie zdanie.</p>
          </Notice>
        ) : null}

        <section>
          <h4 className="flex items-center gap-2 text-lg font-semibold">
            <Bot aria-hidden="true" className="size-5 shrink-0 text-muted" />
            Interpretacja systemu
          </h4>
          <p className="mt-1 text-muted">
            Ten opis przygotował model językowy na podstawie źródeł poniżej. Może
            zawierać błędy.
          </p>
          <p className="mt-3 text-lg leading-relaxed whitespace-pre-line">
            {claim.justification}
          </p>
        </section>

        <StrengthMeter strength={claim.strength} />

        {claim.missing ? (
          <section>
            <h4 className="font-semibold">Czego nie udało się ustalić</h4>
            <p className="mt-1 whitespace-pre-line">{claim.missing}</p>
          </section>
        ) : null}
      </div>

      <section className="border-t border-line bg-page px-5 py-5">
        <h4 className="flex items-center gap-2 text-lg font-semibold">
          <BookOpenText aria-hidden="true" className="size-5 shrink-0 text-muted" />
          Materiały źródłowe
        </h4>
        <p className="mt-1 mb-4 text-muted">
          Dosłowne cytaty ze źródeł. Otwórz źródło, aby przeczytać całość.
        </p>
        <EvidenceChain evidence={claim.evidence} />
      </section>
    </article>
  );
}
