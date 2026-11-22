/** Returns the URL only when it is an absolute http(s) address; anything else is not linkable. */
export function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!/^https?:\/\//i.test(trimmed)) return null;
  try {
    const url = new URL(trimmed);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export function checkPath(id: string): string {
  return `/analiza/${encodeURIComponent(id)}`;
}

/** True when the whole input is one http(s) address, so it should be sent as `url`. */
export function isSingleUrl(value: string): boolean {
  return /^https?:\/\/\S+$/i.test(value) && safeHttpUrl(value) !== null;
}

export type TextPart = { type: "text"; value: string } | { type: "link"; href: string };

/** Splits plain text into text and link parts so links can be rendered without HTML injection. */
export function splitLinks(text: string): TextPart[] {
  const parts: TextPart[] = [];
  const pattern = /https?:\/\/[^\s<>"']+/gi;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    // Punctuation that ends a sentence is not part of the address.
    const raw = match[0].replace(/[.,;:!?)\]]+$/, "");
    const href = safeHttpUrl(raw);
    if (!href) continue;
    if (start > cursor) parts.push({ type: "text", value: text.slice(cursor, start) });
    parts.push({ type: "link", href: raw });
    cursor = start + raw.length;
  }
  if (cursor < text.length) parts.push({ type: "text", value: text.slice(cursor) });
  return parts;
}
