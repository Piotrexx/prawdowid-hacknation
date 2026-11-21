import { SideCard } from "@/components/layout/SideLinks";
import { Tag } from "@/components/ui/Tag";
import { plural } from "@/lib/format";
import type { ModeratorCaseInfo, Warning, WarningCode } from "@/lib/types";

type Tone = "neutral" | "info" | "warn" | "bad";

const WARNING_CARDS: Record<WarningCode, { title: string; badge: string; tone: Tone }> = {
  pii_masked: { title: "Ukryto dane osobowe", badge: "Prywatność", tone: "info" },
  incident_match: { title: "Znany incydent", badge: "Uwaga", tone: "warn" },
  archival_material: { title: "Materiał archiwalny", badge: "Informacja", tone: "neutral" },
  injection_detected: { title: "Uwaga dotycząca bezpieczeństwa", badge: "Bezpieczeństwo", tone: "bad" },
  source_status: { title: "Uwaga dotycząca źródeł", badge: "Uwaga", tone: "warn" },
  retrieval_degraded: { title: "Ograniczone wyszukiwanie", badge: "Uwaga", tone: "warn" },
  image_limits: { title: "Ograniczony odczyt obrazu", badge: "Informacja", tone: "neutral" },
  input_truncated: { title: "Treść została skrócona", badge: "Informacja", tone: "neutral" },
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

export function hasWarningCards(warnings: Warning[], moderatorCase?: ModeratorCaseInfo): boolean {
  const moderatorShown =
    moderatorCase !== undefined &&
    ["recommended", "created", "updated"].includes(moderatorCase.state);
  return warnings.length > 0 || moderatorShown;
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
      {warnings.map((warning, index) => {
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
