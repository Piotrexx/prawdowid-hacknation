import { useId, type ReactNode, type Ref } from "react";
import type { CheckResponse } from "@/lib/types";
import { FactCheckList } from "./FactCheckList";
import { InputRecap } from "./InputRecap";
import { KeywordsDisplay } from "./KeywordsDisplay";
import { STATUS_TITLES, StatusPanel } from "./StatusPanel";
import { TechnicalDetails } from "./TechnicalDetails";
import { VerdictBadge } from "./VerdictBadge";

interface CheckResultProps {
  result: CheckResponse;
  headingRef?: Ref<HTMLHeadingElement>;
  statusActions?: ReactNode;
}

export function CheckResult({ result, headingRef, statusActions }: CheckResultProps) {
  const id = useId();
  const completed = result.status === "completed";

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

      {completed && result.verdict && (
        <section aria-labelledby={`${id}-verdict`} className="space-y-4">
          <h3 id={`${id}-verdict`} className="text-xl font-semibold">
            Werdykt
          </h3>
          <VerdictBadge
            verdict={result.verdict}
            confidence={result.confidence}
            justification={result.justification}
          />
        </section>
      )}

      {completed && result.main_topic && (
        <section aria-labelledby={`${id}-topic`} className="space-y-2">
          <h3 id={`${id}-topic`} className="font-semibold text-muted">
            Główne zagadnienie
          </h3>
          <p className="text-lg leading-relaxed">{result.main_topic}</p>
        </section>
      )}

      {completed && result.keywords.length > 0 && (
        <KeywordsDisplay keywords={result.keywords} />
      )}

      {completed && result.fact_check_results.length > 0 && (
        <FactCheckList checks={result.fact_check_results} />
      )}

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