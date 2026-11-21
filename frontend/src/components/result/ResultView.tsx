"use client";

import { ArrowRight, Copy, FileText } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { SideButton, SideLink } from "@/components/layout/SideLinks";
import { cx } from "@/lib/cx";
import { formatDateTime } from "@/lib/format";
import type { CheckResponse } from "@/lib/types";
import { ClaimCard, claimAnchors } from "./ClaimCard";
import { IncidentMatches } from "./IncidentMatches";
import { InputRecap } from "./InputRecap";
import { RelatedMaterials } from "./RelatedMaterials";
import { StatusPanel } from "./StatusPanel";
import { TechnicalDetails } from "./TechnicalDetails";
import { VerdictChip } from "./VerdictBadge";
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

/** Follows which claim is on screen, so the table of contents can expand it. */
function useActiveClaim(count: number): string | null {
  const [active, setActive] = useState<string | null>(count > 0 ? claimAnchor(0) : null);

  useEffect(() => {
    if (count === 0) return;
    const elements = Array.from(document.querySelectorAll<HTMLElement>("[data-claim-anchor]"));
    const visible = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const anchor = (entry.target as HTMLElement).dataset.claimAnchor!;
          if (entry.isIntersecting) visible.set(anchor, entry.boundingClientRect.top);
          else visible.delete(anchor);
        }
        const first = [...visible.entries()].sort((a, b) => a[1] - b[1])[0];
        if (first) setActive(first[0]);
      },
      { rootMargin: "-20% 0px -50% 0px" },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [count]);

  return active;
}

function TocLink({
  href,
  current = false,
  nested = false,
  children,
}: {
  href: string;
  current?: boolean;
  nested?: boolean;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      aria-current={current ? "true" : undefined}
      className={cx(
        "flex min-h-11 items-center gap-2 border-l-[3px] py-1.5 pr-2 text-[0.9375rem] hover:text-accent hover:underline",
        nested ? "pl-7 text-sm" : "pl-4",
        current ? "border-accent font-bold text-accent" : "border-transparent text-ink",
      )}
    >
      {children}
    </a>
  );
}

function TableOfContents({ result, active }: { result: CheckResponse; active: string | null }) {
  const claims = result.claims;
  return (
    <nav aria-labelledby="spis-tytul" className="bg-surface py-6 shadow-card">
      <h2 id="spis-tytul" className="eyebrow mb-3 px-5">
        Wynik sprawdzenia
      </h2>
      <ul className="flex flex-col">
        <li>
          <TocLink href={`#${ANCHORS.input}`}>Sprawdzana treść</TocLink>
        </li>
        {result.summary ? (
          <li>
            <TocLink href={`#${ANCHORS.summary}`}>W skrócie</TocLink>
          </li>
        ) : null}
        {claims.map((claim, index) => {
          const anchor = claimAnchor(index);
          const ids = claimAnchors(anchor);
          const isActive = active === anchor;
          return (
            <li key={anchor}>
              <TocLink href={`#${ids.claim}`} current={isActive}>
                <span className="min-w-0 flex-1">
                  {claims.length > 1 ? `Twierdzenie ${index + 1}` : "Twierdzenie"}
                </span>
                <VerdictChip verdict={claim.verdict} />
              </TocLink>
              {isActive ? (
                <ul>
                  <li>
                    <TocLink href={`#${ids.assessment}`} nested>
                      Interpretacja i siła podstawy
                    </TocLink>
                  </li>
                  <li>
                    <TocLink href={`#${ids.evidence}`} nested>
                      Materiały źródłowe
                    </TocLink>
                  </li>
                </ul>
              ) : null}
            </li>
          );
        })}
        {result.related_materials.length > 0 ? (
          <li>
            <TocLink href={`#${ANCHORS.related}`}>Powiązane materiały</TocLink>
          </li>
        ) : null}
        {result.incident_matches.length > 0 ? (
          <li>
            <TocLink href={`#${ANCHORS.incidents}`}>Podobne przypadki</TocLink>
          </li>
        ) : null}
        {result.limitations.length > 0 ? (
          <li>
            <TocLink href={`#${ANCHORS.limitations}`}>Ograniczenia</TocLink>
          </li>
        ) : null}
        <li>
          <TocLink href={`#${ANCHORS.technical}`}>Szczegóły techniczne</TocLink>
        </li>
      </ul>
    </nav>
  );
}

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

interface ResultViewProps {
  result: CheckResponse;
  /** Move focus to the heading, e.g. right after a check finished on the home page. */
  focusHeading?: boolean;
}

export function ResultView({ result, focusHeading = false }: ResultViewProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const active = useActiveClaim(result.claims.length);
  const checkedAt = formatDateTime(result.created_at);

  useEffect(() => {
    if (focusHeading) headingRef.current?.focus();
  }, [focusHeading]);

  return (
    <div className="grid gap-8 px-5 py-8 sm:p-10 xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] xl:gap-10 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,2.4fr)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-7 xl:order-1 2xl:order-2">
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

      <aside aria-label="Spis treści wyniku" className="hidden min-w-0 2xl:order-1 2xl:block">
        <div className="2xl:sticky 2xl:top-6">
          <TableOfContents result={result} active={active} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col gap-8 xl:order-2 2xl:order-3">
        <nav aria-labelledby="dzialania-tytul" className="flex flex-col gap-2">
          <h2 id="dzialania-tytul" className="eyebrow mb-1.5">
            Działania
          </h2>
          <CopyLinkButton />
          <SideLink href={`#${ANCHORS.input}`} icon={FileText}>
            Pokaż sprawdzaną treść
          </SideLink>
          <SideLink href="/" icon={ArrowRight} highlight>
            Sprawdź coś innego
          </SideLink>
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
