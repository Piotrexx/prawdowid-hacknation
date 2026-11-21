import { ApiError } from "./api";
import { plural } from "./format";

export function retryHint(seconds: number | undefined): string {
  if (seconds === undefined || seconds <= 0) return "Spróbuj ponownie za chwilę.";
  if (seconds < 90) {
    return `Spróbuj ponownie za ${seconds} ${plural(seconds, "sekundę", "sekundy", "sekund")}.`;
  }
  const minutes = Math.ceil(seconds / 60);
  return `Spróbuj ponownie za około ${minutes} ${plural(minutes, "minutę", "minuty", "minut")}.`;
}

/** Plain-language description of a failed request. Never phrased as a verification result. */
export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) return "Coś poszło nie tak. Spróbuj ponownie.";
  switch (error.kind) {
    case "network":
      return "Nie udało się połączyć z serwerem. Sprawdź połączenie z internetem i spróbuj ponownie.";
    case "timeout":
      return "Serwer nie odpowiedział na czas. Spróbuj ponownie za chwilę.";
    case "rate_limit":
      return `Za dużo zapytań w krótkim czasie. ${retryHint(error.retryAfterSeconds)}`;
    case "validation":
      return error.detail ?? "Serwer nie przyjął tych danych. Sprawdź je i spróbuj ponownie.";
    case "not_found":
      return "Nie znaleziono tych danych.";
    case "unauthorized":
      return "Brak dostępu. Podaj prawidłowy token.";
    default:
      return "Serwer zgłosił błąd. Spróbuj ponownie za chwilę.";
  }
}
