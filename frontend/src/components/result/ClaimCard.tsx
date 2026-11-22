import { GitCompareArrows, ShieldAlert } from "lucide-react";
import { Notice } from "@/components/ui/Notice";
import { Tag } from "@/components/ui/Tag";
import { cx } from "@/lib/cx";
import { plural } from "@/lib/format";
import type { ClaimResult } from "@/lib/types";
import { EvidenceChain } from "./EvidenceChain";
import { StrengthMeter } from "./StrengthMeter";
import { VerdictChip, verdictStripe } from "./VerdictBadge";

interface ClaimCardProps {
  claim: ClaimResult;
  index: number;
  total: number;
  anchor: string;
}

/** Returns the sub-anchor IDs used by ResultView's table of contents. */
export function claimAnchors(anchor: string) {
  return {
    claim: anchor,
    assessment: `${anchor}-ocena`,
    evidence: `${anchor}-materialy`,
  };
}

export function ClaimCard({ claim, index, total, anchor }: ClaimCardProps) {
  const ids = claimAnchors(anchor);

  return (
    <article
      id={ids.claim}
      data-claim-anchor={anchor}
      aria-labelledby={`${ids.claim}-tytul`}
      className={cx("scroll-mt-6 border-l-4 bg-surface px-6 py-6 shadow-card", verdictStripe(claim.verdict))}
    >
      {total > 1 ? (
        <p className="eyebrow mb-2">Twierdzenie {index} z {total}</p>
      ) : null}

      <h2 id={`${ids.claim}-tytul`} className="text-xl font-bold leading-snug">
        {claim.text}
      </h2>

      <p className="mt-3 flex flex-wrap items-center gap-x-3.5 gap-y-2">
        <VerdictChip verdict={claim.verdict} />
        {claim.risk === "high" ? (
          <Tag tone="warn" icon={ShieldAlert}>
            Wysokie ryzyko
          </Tag>
        ) : null}
      </p>

      {claim.conflict ? (
        <div className="mt-4">
          <Notice tone="warn" icon={GitCompareArrows} title="Źródła podają rozbieżne informacje">
            <p>Przeczytaj materiały z obu stron, zanim wyrobisz sobie zdanie.</p>
          </Notice>
        </div>
      ) : null}

      <section id={ids.assessment} aria-labelledby={`${ids.assessment}-tytul`} className="mt-6 scroll-mt-6">
        <h3 id={`${ids.assessment}-tytul`} className="text-lg font-semibold">
          Interpretacja i siła podstawy
        </h3>
        <p className="mt-1 text-sm text-muted">
          Ten opis przygotował model językowy na podstawie cytatów poniżej. Może zawierać błędy.
        </p>
        {claim.justification ? (
          <p className="mt-2 leading-relaxed whitespace-pre-line">{claim.justification}</p>
        ) : null}
        <div className="mt-4">
          <StrengthMeter strength={claim.strength} id={`${ids.assessment}-sila`} />
        </div>
        {claim.missing ? (
          <div className="mt-4">
            <h4 className="font-semibold">Czego nie udało się ustalić</h4>
            <p className="mt-1 whitespace-pre-line">{claim.missing}</p>
          </div>
        ) : null}
      </section>

      <section id={ids.evidence} aria-labelledby={`${ids.evidence}-tytul`} className="mt-6 scroll-mt-6">
        <h3 id={`${ids.evidence}-tytul`} className="text-lg font-semibold">
          Materiały źródłowe{" "}
          {claim.evidence.length > 0 ? (
            <span className="font-normal text-muted">
              ({claim.evidence.length}{" "}
              {plural(claim.evidence.length, "materiał", "materiały", "materiałów")})
            </span>
          ) : null}
        </h3>
        <p className="mt-1 mb-4 text-sm text-muted">
          Dosłowne cytaty ze źródeł, sprawdzone automatycznie. Otwórz źródło, aby przeczytać całość.
        </p>
        <EvidenceChain evidence={claim.evidence} />
      </section>
    </article>
  );
}
