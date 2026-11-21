import { useId } from "react";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { formatDate } from "@/lib/format";
import type { IncidentMatch } from "@/lib/types";

const MATCH_TYPE_LABELS: Record<IncidentMatch["match_type"], string> = {
  url: "Ten sam adres",
  domain: "Ta sama domena",
  content: "Podobna treść",
};

export function IncidentMatches({ matches }: { matches: IncidentMatch[] }) {
  const headingId = useId();
  if (matches.length === 0) return null;

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="text-xl font-semibold">
        Podobne znane przypadki (kontekst)
      </h3>
      <p className="mt-1 text-muted">
        To dopasowanie jest tylko kontekstem. Nie przesądza o ocenie tej treści.
      </p>
      <ul className="mt-4 space-y-3">
        {matches.map((match) => (
          <li
            key={match.incident_id}
            className="rounded-lg border border-dashed border-line-strong bg-surface p-4"
          >
            <p>{match.note}</p>
            <p>
              <ExternalLink href={match.url} className="inline-block py-2 font-medium">
                {match.title || match.url}
              </ExternalLink>
            </p>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-muted">
              <span>
                {match.publisher}
                {" · "}
                {formatDate(match.date) ?? "brak daty"}
              </span>
              <Tag>{MATCH_TYPE_LABELS[match.match_type] ?? match.match_type}</Tag>
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
