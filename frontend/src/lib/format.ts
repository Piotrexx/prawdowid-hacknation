const LOCALE = "pl-PL";

const dateFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const shortDateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const timeFormat = new Intl.DateTimeFormat(LOCALE, {
  hour: "2-digit",
  minute: "2-digit",
});

const integerFormat = new Intl.NumberFormat(LOCALE);

function parseDateTime(value: string): Date | null {
  // Naive datetimes (no offset) are produced by the server in UTC.
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Calendar date ("2026-03-05" or a full timestamp) → "5 marca 2026". */
export function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  return Number.isNaN(date.getTime()) ? null : dateFormat.format(date);
}

export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = parseDateTime(value);
  return date ? dateTimeFormat.format(date) : null;
}

export function formatShortDateTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = parseDateTime(value);
  return date ? shortDateTimeFormat.format(date) : null;
}

export function formatTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = parseDateTime(value);
  return date ? timeFormat.format(date) : null;
}

export function formatInteger(value: number): string {
  return integerFormat.format(value);
}

export function formatSeconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "brak danych";
  const seconds = ms / 1000;
  const digits = seconds < 10 ? 1 : 0;
  return `${seconds.toLocaleString(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} s`;
}

export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "brak danych";
  return `${value.toLocaleString(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })} USD`;
}

/** Fraction in the 0–1 range → "12,5%". */
export function formatPercent(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined) return "brak danych";
  return `${(fraction * 100).toLocaleString(LOCALE, { maximumFractionDigits: 1 })}%`;
}

export function formatFileSize(bytes: number): string {
  const megabytes = bytes / (1024 * 1024);
  if (megabytes >= 1) {
    return `${megabytes.toLocaleString(LOCALE, { maximumFractionDigits: 1 })} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Polish plural: plural(5, "zapis", "zapisy", "zapisów") → "zapisów". */
export function plural(count: number, one: string, few: string, many: string): string {
  const abs = Math.abs(count);
  if (abs === 1) return one;
  const lastDigit = abs % 10;
  const lastTwo = abs % 100;
  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 12 || lastTwo > 14)) return few;
  return many;
}
