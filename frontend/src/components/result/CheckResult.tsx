import { useId, type ReactNode, type Ref } from "react";
import type { CheckResponse } from "@/lib/types";
import { ClaimCard } from "./ClaimCard";
import { IncidentMatches } from "./IncidentMatches";
import { InputRecap } from "./InputRecap";
import { ModeratorCaseBox } from "./ModeratorCaseBox";
import { RelatedMaterials } from "./RelatedMaterials";
import { STATUS_TITLES, StatusPanel } from "./StatusPanel";
import { TechnicalDetails } from "./TechnicalDetails";
import { Warnings } from "./Warnings";

interface CheckResultProps {
  result: CheckResponse;
  headingRef?: Ref<HTMLHeadingElement>;
  /** Page-specific buttons shown inside the panel for states that are not verdicts. */
  statusActions?: ReactNode;
}

export function CheckResult({ result, headingRef, statusActions }: CheckResultProps) {
  const id = useId();
  const completed = result.status === "completed";
  const claims = completed ? result.claims : [];

  return (
    <div className="space-y-6">
      <h2
        ref={headingRef}
        tabIndex={-1}
        className="text-2xl font-semibold tracking-tight sm:text-3xl"
      >
        {STATUS_TITLES[result.status] ?? STATUS_TITLES.error}
      </h2>

      <StatusPanel result={result} actions={statusActions} />
      <InputRecap input={result.input} />
      <Warnings warnings={result.warnings} />

      {completed && result.summary ? (
        <section aria-labelledby={`${id}-summary`}>
          <h3 id={`${id}-summary`} className="font-semibold text-muted">
            W skrócie (interpretacja systemu)
          </h3>
          <p className="mt-1 text-lg leading-relaxed whitespace-pre-line">
            {result.summary}
          </p>
        </section>
      ) : null}

      {completed && claims.length === 0 ? (
        <p className="rounded-lg border border-line bg-surface p-4">
          System nie wydzielił z tej treści twierdzeń, które da się sprawdzić.
        </p>
      ) : null}

      {claims.map((claim, index) => (
        <ClaimCard key={claim.id} claim={claim} index={index + 1} total={claims.length} />
      ))}

      <RelatedMaterials materials={result.related_materials} />
      <IncidentMatches matches={result.incident_matches} />
      <ModeratorCaseBox info={result.moderator_case} />

      {result.limitations.length > 0 ? (
        <section aria-labelledby={`${id}-limits`}>
          <h3 id={`${id}-limits`} className="text-xl font-semibold">
            Ograniczenia tej odpowiedzi
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            {result.limitations.map((limitation, index) => (
              <li key={index}>{limitation}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="border-t border-line pt-4 font-medium">
        Nie musisz wierzyć na słowo. Zawsze warto otworzyć źródła i przeczytać je
        samodzielnie.
      </p>

      <TechnicalDetails result={result} />
    </div>
  );
}
