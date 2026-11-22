import { ShieldAlert } from "lucide-react";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { cx } from "@/lib/cx";
import { plural } from "@/lib/format";
import { STANCE_LABELS } from "@/lib/labels";
import type { ClaimResult } from "@/lib/types";
import { StrengthMeter } from "./StrengthMeter";
import { VerdictChip, verdictStripe } from "./VerdictBadge";

interface ClaimCardProps {
  claim: ClaimResult;
  index: number;
  total: number;
  anchor: string;
}

function claimAnchors(anchor: string) {
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

      <section id={ids.assessment} aria-labelledby={`${ids.assessment}-tytul`} className="mt-6 scroll-mt-6">
        <h3 id={`${ids.assessment}-tytul`} className="text-lg font-semibold">
          Interpretacja i siła podstawy
        </h3>
        {claim.justification ? (
          <p className="mt-2 leading-relaxed whitespace-pre-line">{claim.justification}</p>
        ) : null}
        <div className="mt-4">
          <StrengthMeter strength={claim.strength} id={`${ids.assessment}-sila`} />
        </div>
      </section>

      {claim.evidence.length > 0 ? (
        <section id={ids.evidence} aria-labelledby={`${ids.evidence}-tytul`} className="mt-6 scroll-mt-6">
          <h3 id={`${ids.evidence}-tytul`} className="text-lg font-semibold">
            Materiały źródłowe{" "}
            <span className="font-normal text-muted">
              ({claim.evidence.length}{" "}
              {plural(claim.evidence.length, "materiał", "materiały", "materiałów")})
            </span>
          </h3>
          <ul className="mt-3 flex flex-col gap-3">
            {claim.evidence.map((item) => (
              <li
                key={item.id}
                className="border border-line bg-subtle px-4.5 py-3.5 text-sm"
              >
                <p className="mb-1 flex items-center gap-2">
                  <Tag tone={item.stance === "refutes" ? "bad" : item.stance === "supports" ? "ok" : undefined}>
                    {STANCE_LABELS[item.stance] ?? item.stance}
                  </Tag>
                  <span className="text-muted">{item.source.publisher}</span>
                </p>
                <ExternalLink href={item.source.url} className="inline-block py-1 font-semibold">
                  {item.source.title || item.source.url}
                </ExternalLink>
                {item.source.rating ? (
                  <p className="mt-0.5 text-muted">Ocena: {item.source.rating}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section id={ids.evidence} className="mt-6 scroll-mt-6">
          <p className="text-sm text-muted">
            Brak materiałów źródłowych dla tego twierdzenia w Google Fact Check.
          </p>
        </section>
      )}
    </article>
  );
}
