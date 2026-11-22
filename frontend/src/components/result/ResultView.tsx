"use client";

import { ArrowLeft, Copy, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useConversationOf } from "@/components/chat/conversationStore";
import { useStartNewSession } from "@/components/chat/useStartNewSession";
import { SideButton, SideLink } from "@/components/layout/SideLinks";
import { formatDateTime } from "@/lib/format";
import type { CheckResponse } from "@/lib/types";
import { ClaimCard } from "./ClaimCard";
import { IncidentMatches } from "./IncidentMatches";
import { InputRecap } from "./InputRecap";
import { RelatedMaterials } from "./RelatedMaterials";
import { StatusPanel } from "./StatusPanel";
import { TechnicalDetails } from "./TechnicalDetails";
import { WarningCards } from "./Warnings";

const ANCHORS = {
  input: "sprawdzana-tresc",
  summary: "w-skrocie",
  related: "powiazane-materialy",
  incidents: "podobne-przypadki",
  limitations: "ograniczenia",
  technical: "szczegoly-techniczne",
  warnings: "ostrzezenia",
} as const;

const claimAnchor = (index: number) => `twierdzenie-${index + 1}`;

function CopyLinkButton() {
  const [message, setMessage] = useState("");
  const [fallback, setFallback] = useState<string | null>(null);
  const fallbackRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (fallback !== null) fallbackRef.current?.select();
  }, [fallback]);

  async function copy() {
    const url = window.location.href.split("#")[0];
    try {
      await navigator.clipboard.writeText(url);
      setFallback(null);
      setMessage("Skopiowano link do schowka.");
    } catch {
      setFallback(url);
      setMessage("Nie udało się skopiować. Zaznaczyłem link – skopiuj go ręcznie.");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <SideButton icon={Copy} onClick={copy}>
        Skopiuj link do wyniku
      </SideButton>
      {fallback !== null ? (
        <input
          ref={fallbackRef}
          readOnly
          value={fallback}
          aria-label="Link do wyniku"
          className="min-h-11 w-full border border-line-strong bg-surface px-3 text-sm"
        />
      ) : null}
      <p role="status" className="text-sm text-muted empty:hidden">
        {message}
      </p>
    </div>
  );
}

/** Links back to the conversation that asked for this check, when this browser has it saved. */
function useBackToChatHref(checkId: string): string {
  const conversation = useConversationOf(checkId);
  if (!conversation) return "/";
  return `/?${new URLSearchParams({ rozmowa: conversation, wynik: checkId }).toString()}`;
}

interface ResultViewProps {
  result: CheckResponse;
  /** Move focus to the heading, e.g. right after a check finished on the home page. */
  focusHeading?: boolean;
}

export function ResultView({ result, focusHeading = false }: ResultViewProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const checkedAt = formatDateTime(result.created_at);
  const startNewSession = useStartNewSession();
  const backToChat = useBackToChatHref(result.id);

  useEffect(() => {
    if (focusHeading) headingRef.current?.focus();
  }, [focusHeading]);

  return (
    <div className="grid gap-8 px-5 py-8 sm:p-10 xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] xl:gap-10">
      <div className="flex min-w-0 flex-col gap-7">
        <section aria-labelledby="wynik-tytul" className="bg-subtle px-5 py-8 sm:p-10">
          {checkedAt ? (
            <p className="text-sm text-muted">
              Sprawdzono: {checkedAt}. Od tego czasu informacje mogły się zmienić.
            </p>
          ) : null}
          <h1
            id="wynik-tytul"
            ref={headingRef}
            tabIndex={-1}
            className="mt-2 text-[1.875rem] leading-tight font-bold outline-none"
          >
            Wynik sprawdzenia
          </h1>
          <div className="title-rule my-4" />
          <div className="flex flex-col gap-6">
            <InputRecap input={result.input} id={ANCHORS.input} level={2} />
            {result.summary ? (
              <section id={ANCHORS.summary} aria-labelledby={`${ANCHORS.summary}-tytul`} className="scroll-mt-6">
                <h2 id={`${ANCHORS.summary}-tytul`} className="text-xl font-bold">
                  W skrócie <span className="font-normal text-muted">(interpretacja systemu)</span>
                </h2>
                <p className="mt-2 leading-relaxed whitespace-pre-line">{result.summary}</p>
              </section>
            ) : null}
          </div>
        </section>

        <StatusPanel result={result} />

        {result.claims.map((claim, index) => (
          <ClaimCard
            key={index}
            claim={claim}
            index={index + 1}
            total={result.claims.length}
            anchor={claimAnchor(index)}
          />
        ))}

        <RelatedMaterials materials={result.related_materials} id={ANCHORS.related} level={2} />
        <IncidentMatches matches={result.incident_matches} id={ANCHORS.incidents} level={2} />

        {result.limitations.length > 0 ? (
          <section
            id={ANCHORS.limitations}
            aria-labelledby={`${ANCHORS.limitations}-tytul`}
            className="scroll-mt-6 border-l-4 border-line-mid pl-5"
          >
            <h2 id={`${ANCHORS.limitations}-tytul`} className="text-xl font-bold">
              Ograniczenia tej odpowiedzi
            </h2>
            <ul className="mt-2 list-disc space-y-1 pl-6">
              {result.limitations.map((limitation, index) => (
                <li key={index}>{limitation}</li>
              ))}
            </ul>
          </section>
        ) : null}

        <TechnicalDetails result={result} id={ANCHORS.technical} />
      </div>

      {/* Pinned on wide screens, so the actions stay in reach while the result scrolls. */}
      <div className="flex min-w-0 flex-col gap-8 xl:sticky xl:top-6 xl:self-start">
        <nav aria-labelledby="dzialania-tytul" className="flex flex-col gap-2">
          <h2 id="dzialania-tytul" className="eyebrow mb-1.5">
            Działania
          </h2>
          <div className="mb-4">
            <SideLink href={backToChat} icon={ArrowLeft}>
              Wróć do czatu
            </SideLink>
          </div>
          <CopyLinkButton />
          <SideButton icon={Plus} highlight onClick={startNewSession}>
            Zacznij nową sesję
          </SideButton>
        </nav>
        <WarningCards
          warnings={result.warnings}
          moderatorCase={result.moderator_case}
          headingId={ANCHORS.warnings}
        />
      </div>
    </div>
  );
}
