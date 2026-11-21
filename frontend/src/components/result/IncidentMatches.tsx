import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { formatDate } from "@/lib/format";
import type { IncidentMatch } from "@/lib/types";

const MATCH_TYPE_LABELS: Record<IncidentMatch["match_type"], string> = {
  url: "Ten sam adres",
  domain: "Ta sama domena",
  content: "Podobna treść",
};

interface IncidentMatchesProps {
  matches: IncidentMatch[];
  id: string;
  level?: 2 | 3;
}

export function IncidentMatches({ matches, id, level = 3 }: IncidentMatchesProps) {
  if (matches.length === 0) return null;
  const Heading = level === 2 ? "h2" : "h3";

  return (
    <section id={id} aria-labelledby={`${id}-tytul`} className="scroll-mt-6 bg-subtle px-6 py-7">
      <Heading id={`${id}-tytul`} className="text-xl font-semibold">
        Podobne znane przypadki (kontekst)
      </Heading>
      <p className="mt-1 mb-4.5 text-sm text-muted">
        To dopasowanie jest tylko kontekstem. Nie przesądza o ocenie tej treści.
      </p>
      <ul className="flex flex-col gap-2">
        {matches.map((match) => (
          <li
            key={match.incident_id}
            className="border border-dashed border-line-strong bg-surface px-4.5 py-4"
          >
            <p>{match.note}</p>
            <p className="mt-2 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-sm text-muted">
              <ExternalLink href={match.url} className="inline-block py-1.5 font-semibold">
                {match.title || match.url}
              </ExternalLink>
              <span>{match.publisher}</span>
              <span>{formatDate(match.date) ?? "brak daty"}</span>
              <Tag>{MATCH_TYPE_LABELS[match.match_type] ?? match.match_type}</Tag>
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
