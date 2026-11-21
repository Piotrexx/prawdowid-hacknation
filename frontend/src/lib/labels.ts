import type {
  CaseStatus,
  CheckStatus,
  RetrievalMode,
  SourceType,
  Stance,
  StoragePolicy,
  StrengthLevel,
  Verdict,
} from "./types";

export const VERDICT_LABELS: Record<Verdict, string> = {
  potwierdzone: "Potwierdzone",
  falszywe: "Fałszywe",
  wprowadzajace_w_blad: "Wprowadzające w błąd",
  brak_wystarczajacych_dowodow: "Brak wystarczających dowodów",
  nie_podlega_weryfikacji: "Nie podlega weryfikacji",
};

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  official: "Źródło urzędowe",
  legal: "Akt prawny",
  statistics: "Dane statystyczne",
  international: "Organizacja międzynarodowa",
  factcheck: "Organizacja fact-checkingowa",
  media: "Media",
};

export const SOURCE_TYPES = Object.keys(SOURCE_TYPE_LABELS) as SourceType[];

export const STANCE_LABELS: Record<Stance, string> = {
  supports: "Potwierdza",
  refutes: "Zaprzecza",
  context: "Kontekst",
};

export const STRENGTH_LABELS: Record<StrengthLevel, string> = {
  mocna: "mocna",
  umiarkowana: "umiarkowana",
  slaba: "słaba",
  brak: "brak",
};

export const STORAGE_LABELS: Record<StoragePolicy, string> = {
  full_text: "pełny tekst",
  excerpt: "fragment i link",
  structured: "dane strukturalne",
};

export const RETRIEVAL_LABELS: Record<RetrievalMode, string> = {
  hybrid: "hybrydowe (słowa kluczowe i znaczenie)",
  bm25: "słowa kluczowe (BM25)",
  none: "bez wyszukiwania",
};

export const CHECK_STATUS_LABELS: Record<CheckStatus, string> = {
  completed: "Zakończone",
  needs_clarification: "Prośba o doprecyzowanie",
  out_of_scope: "Poza zakresem",
  error: "Problem techniczny",
};

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  open: "Otwarta",
  in_review: "W trakcie",
  resolved: "Zamknięta",
};

export const CASE_STATUSES = Object.keys(CASE_STATUS_LABELS) as CaseStatus[];

const CHANNEL_LABELS: Record<string, string> = {
  web: "Strona WWW",
};

const INPUT_KIND_LABELS: Record<string, string> = {
  text: "Tekst",
  url: "Link",
  image: "Obraz",
};

/** Labels for open-ended backend keys: fall back to the raw key instead of guessing. */
export function labelFor(map: Record<string, string>, key: string): string {
  return map[key] ?? key;
}

export function channelLabel(channel: string): string {
  return labelFor(CHANNEL_LABELS, channel);
}

export function inputKindLabel(kind: string): string {
  return labelFor(INPUT_KIND_LABELS, kind);
}

export function languageLabel(code: string): string {
  try {
    const name = new Intl.DisplayNames("pl", { type: "language" }).of(code);
    if (name && name !== code) return name;
  } catch {
    // Unknown or malformed language tag: show the code itself.
  }
  return code.toUpperCase();
}
