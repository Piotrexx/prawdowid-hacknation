import { Archive } from "lucide-react";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { formatDate } from "@/lib/format";
import { SOURCE_TYPE_LABELS } from "@/lib/labels";
import type { SourceRef } from "@/lib/types";

interface SourceMetaProps {
  source: SourceRef;
  archival?: boolean;
}

export function SourceMeta({ source, archival = false }: SourceMetaProps) {
  const published = formatDate(source.published_at);
  const retrieved = formatDate(source.retrieved_at);
  const typeLabel = SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type;
  const smallPrint = [
    source.source_name && source.source_name !== source.publisher
      ? `Źródło w katalogu: ${source.source_name}`
      : null,
    source.license ? `Licencja: ${source.license}` : null,
    retrieved ? `Pobrano: ${retrieved}` : null,
  ].filter(Boolean);

  return (
    <div className="space-y-1.5 text-sm">
      <p className="flex flex-wrap items-center gap-x-3.5 gap-y-1 text-muted">
        <ExternalLink href={source.url} className="inline-block py-1.5 font-semibold">
          {source.title || source.url}
        </ExternalLink>
        <span>{source.publisher}</span>
        <span>{published ?? "brak daty"}</span>
      </p>
      <p className="flex flex-wrap gap-1.5">
        <Tag>{typeLabel}</Tag>
        {archival ? (
          <Tag tone="warn" icon={Archive}>
            Materiał archiwalny
          </Tag>
        ) : null}
      </p>
      {source.claim_reviewed ? (
        <p>
          <span className="font-semibold">Sprawdzane twierdzenie:</span>{" "}
          {source.claim_reviewed}
        </p>
      ) : null}
      {source.rating ? (
        <p>
          <span className="font-semibold">Ocena redakcji:</span> {source.rating}
        </p>
      ) : null}
      {smallPrint.length > 0 ? (
        <p className="text-xs text-muted">{smallPrint.join(" · ")}</p>
      ) : null}
    </div>
  );
}
