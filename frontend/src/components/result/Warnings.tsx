import { SideCard } from "@/components/layout/SideLinks";
import { Tag } from "@/components/ui/Tag";
import { plural } from "@/lib/format";
import type { ModeratorCaseInfo, Warning, WarningCode } from "@/lib/types";

type Tone = "neutral" | "info" | "warn" | "bad";

/** Codes intentionally not shown to the end user (still logged server-side for observability). */
const HIDDEN_WARNING_CODES: ReadonlySet<WarningCode> = new Set(["keywords_degraded"]);

const WARNING_CARDS: Partial<Record<WarningCode, { title: string; badge: string; tone: Tone }>> = {
  pii_masked: { title: "Ukryto dane osobowe", badge: "Prywatność", tone: "info" },
  incident_match: { title: "Znany incydent", badge: "Uwaga", tone: "warn" },
  archival_material: { title: "Materiał archiwalny", badge: "Informacja", tone: "neutral" },
  injection_detected: { title: "Uwaga dotycząca bezpieczeństwa", badge: "Bezpieczeństwo", tone: "bad" },
  source_status: { title: "Uwaga dotycząca źródeł", badge: "Uwaga", tone: "warn" },
  retrieval_degraded: { title: "Ograniczone wyszukiwanie", badge: "Uwaga", tone: "warn" },
  image_limits: { title: "Ograniczony odczyt obrazu", badge: "Informacja", tone: "neutral" },
  image_manipulation: { title: "Możliwa edycja zdjęcia", badge: "Uwaga", tone: "bad" },
  image_edit_software: { title: "Ślad programu do edycji", badge: "Informacja", tone: "warn" },
  ai_generated: { title: "Obraz wygenerowany przez AI", badge: "Uwaga", tone: "bad" },
  ai_edited: { title: "Obraz edytowany z użyciem AI", badge: "Uwaga", tone: "warn" },
  content_credentials: { title: "Content Credentials (C2PA)", badge: "Informacja", tone: "info" },
  image_analysis_unavailable: {
    title: "Nie sprawdzono autentyczności zdjęcia",
    badge: "Informacja",
    tone: "neutral",
  },
  input_truncated: { title: "Treść została skrócona", badge: "Informacja", tone: "neutral" },
  factcheck_unavailable: { title: "Baza fact-checków niedostępna", badge: "Uwaga", tone: "warn" },
};

const FALLBACK = { title: "Uwaga", badge: "Informacja", tone: "neutral" as Tone };

export function warningCard(code: WarningCode) {
  return WARNING_CARDS[code] ?? FALLBACK;
}

function Card({ title, badge, tone, children }: {
  title: string;
  badge: string;
  tone: Tone;
  children: string;
}) {
  return (
    <SideCard title={<span className="font-semibold">{title}</span>} badge={<Tag tone={tone}>{badge}</Tag>}>
      <p className="text-sm text-ink-soft">{children}</p>
    </SideCard>
  );
}

function ModeratorCard({ info }: { info: ModeratorCaseInfo }) {
  if (info.state === "recommended") {
    // A recommendation only: nothing was queued, so it must not look like a handed-over case.
    return (
      <Card title="Zalecamy ocenę przez człowieka" badge="Zalecenie" tone="neutral">
        {`${info.message ? `${info.message} ` : ""}To tylko zalecenie. Ta sprawa nie została przekazana moderatorowi.`}
      </Card>
    );
  }
  if (info.state !== "created" && info.state !== "updated") return null;

  const details = [
    info.message || "Ta treść trafiła do kolejki moderatora.",
    info.occurrences != null && info.occurrences > 1
      ? `Podobne zgłoszenie pojawiło się już ${info.occurrences} ${plural(info.occurrences, "raz", "razy", "razy")}.`
      : null,
    info.notified ? "Moderator dostał powiadomienie." : null,
  ].filter(Boolean);

  return (
    <Card
      title={
        info.case_id !== null
          ? `Sprawa nr ${info.case_id} czeka na moderatora`
          : "Sprawa czeka na moderatora"
      }
      badge="Moderacja"
      tone="info"
    >
      {details.join(" ")}
    </Card>
  );
}

interface WarningCardsProps {
  warnings: Warning[];
  moderatorCase?: ModeratorCaseInfo;
  headingId: string;
  level?: 2 | 3;
}

/** Drops warning codes that are intentionally never shown to the end user. */
export function visibleWarnings(warnings: Warning[]): Warning[] {
  return warnings.filter((warning) => !HIDDEN_WARNING_CODES.has(warning.code));
}

export function hasWarningCards(warnings: Warning[], moderatorCase?: ModeratorCaseInfo): boolean {
  const moderatorShown =
    moderatorCase !== undefined &&
    ["recommended", "created", "updated"].includes(moderatorCase.state);
  return visibleWarnings(warnings).length > 0 || moderatorShown;
}

/** "Warto wiedzieć": the check's warnings and moderator status as small cards. */
export function WarningCards({ warnings, moderatorCase, headingId, level = 2 }: WarningCardsProps) {
  if (!hasWarningCards(warnings, moderatorCase)) return null;
  const Heading = level === 2 ? "h2" : "h3";

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <Heading id={headingId} className="eyebrow mb-1.5">
        Warto wiedzieć
      </Heading>
      {moderatorCase ? <ModeratorCard info={moderatorCase} /> : null}
      {visibleWarnings(warnings).map((warning, index) => {
        const card = WARNING_CARDS[warning.code] ?? FALLBACK;
        return (
          <Card key={`${warning.code}-${index}`} title={card.title} badge={card.badge} tone={card.tone}>
            {warning.message}
          </Card>
        );
      })}
    </section>
  );
}
