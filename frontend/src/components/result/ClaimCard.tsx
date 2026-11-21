import { GitCompareArrows, ShieldAlert } from "lucide-react";
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
  /** Prefix for the anchors the result's table of contents links to. */
  anchor: string;
}

export function claimAnchors(anchor: string) {
  return {
    claim: anchor,
    assessment: `${anchor}-ocena`,
    evidence: `${anchor}-materialy`,
  };
}

export function ClaimCard({ claim, index, total, anchor }: ClaimCardProps) {
  const ids = claimAnchors(anchor);
  const headingId = `${anchor}-tytul`;

  return (
    <article
      id={ids.claim}
      aria-labelledby={headingId}
      data-claim-anchor={ids.claim}
      className="flex scroll-mt-6 flex-col gap-7"
    >
      <div className="bg-subtle">
        <header className="px-5 pt-8 pb-6 sm:px-10 sm:pt-9">
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {total > 1 ? `Twierdzenie ${index} z ${total}` : "Sprawdzane twierdzenie"}
            {claim.risk === "high" ? (
              <Tag tone="warn" icon={ShieldAlert}>
                Temat wysokiego ryzyka
              </Tag>
            ) : null}
          </p>
          <h2 id={headingId} className="mt-1.5 text-[1.5rem] leading-snug font-bold sm:text-[1.625rem]">
            {claim.text}
          </h2>
        </header>

        <VerdictBanner verdict={claim.verdict} label={claim.verdict_label} />

        <div className="flex flex-col gap-6 px-5 pt-7 pb-9 sm:px-10">
          {claim.conflict ? (
            <Notice tone="warn" icon={GitCompareArrows} title="Źródła podają rozbieżne informacje">
              <p>Przeczytaj materiały z obu stron, zanim wyrobisz sobie zdanie.</p>
            </Notice>
          ) : null}

          <section id={ids.assessment} className="scroll-mt-6">
            <h3 className="text-[1.0625rem] font-bold">Interpretacja systemu</h3>
            <p className="mt-1 text-sm text-muted">
              Opis przygotował model językowy na podstawie źródeł poniżej. Może zawierać
              błędy.
            </p>
            <p className="mt-3 leading-relaxed whitespace-pre-line">{claim.justification}</p>
          </section>

          <StrengthMeter strength={claim.strength} />

          {claim.missing ? (
            <section>
              <h3 className="text-[1.0625rem] font-bold">Czego nie udało się ustalić</h3>
              <p className="mt-1.5 leading-relaxed whitespace-pre-line">{claim.missing}</p>
            </section>
          ) : null}
        </div>
      </div>

      <section
        id={ids.evidence}
        aria-labelledby={`${ids.evidence}-tytul`}
        className="scroll-mt-6 bg-subtle px-6 py-7"
      >
        <h3 id={`${ids.evidence}-tytul`} className="text-xl font-semibold">
          Materiały źródłowe
          {total > 1 ? <span className="sr-only"> do twierdzenia {index}</span> : null}
        </h3>
        <p className="mt-1 mb-4.5 text-sm text-muted">
          Dosłowne cytaty ze źródeł. Otwórz źródło, aby przeczytać całość.
        </p>
        <EvidenceChain evidence={claim.evidence} />
      </section>
    </article>
  );
}
