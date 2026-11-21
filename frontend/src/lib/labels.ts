import type { CheckStatus, VerdictLabel } from "./types";

export const VERDICT_LABELS: Record<VerdictLabel, string> = {
  fake_news: "Fake news",
  prawdziwe: "Prawdziwe",
  niepewne: "Niepewne",
  satyna: "Satyra",
  opinia: "Opinia",
};

export const CHECK_STATUS_LABELS: Record<CheckStatus, string> = {
  completed: "Zakończone",
  needs_clarification: "Prośba o doprecyzowanie",
  out_of_scope: "Poza zakresem",
  error: "Problem techniczny",
};

const CHANNEL_LABELS: Record<string, string> = {
  web: "Strona WWW",
};

const INPUT_KIND_LABELS: Record<string, string> = {
  url: "Link",
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