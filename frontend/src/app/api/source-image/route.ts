import type { NextRequest } from "next/server";
import { findCatalogSource } from "@/lib/sourceCatalog";

/**
 * Returns the source's social-card image (`twitter:image`, then `og:image`)
 * through our own origin. Browsers block reading those meta tags cross-origin,
 * and proxying keeps hotlink protection from breaking the cards.
 */

const META_CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const META_FAILURE_TTL_MS = 10 * 60 * 1000;
const IMAGE_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60;
const FETCH_TIMEOUT_MS = 7_000;
const MAX_HTML_BYTES = 600_000;
const MAX_IMAGE_BYTES = 3_000_000;

const SOCIAL_IMAGE_KEYS = [
  "twitter:image",
  "twitter:image:src",
  "og:image:secure_url",
  "og:image",
  "image",
];

interface MetaCacheEntry {
  imageUrl: string | null;
  expiresAt: number;
}

const metaCache = new Map<string, MetaCacheEntry>();

function decodeEntities(value: string): string {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) => {
      const code = Number.parseInt(hex, 16);
      return Number.isFinite(code) && code <= 0x10ffff ? String.fromCodePoint(code) : "";
    })
    .replace(/&#(\d+);/g, (_, digits: string) => {
      const code = Number.parseInt(digits, 10);
      return Number.isFinite(code) && code <= 0x10ffff ? String.fromCodePoint(code) : "";
    });
}

function parseMetaTags(html: string): Map<string, string> {
  const values = new Map<string, string>();
  const attributePattern = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;

  for (const tag of html.match(/<meta\b[^>]*>/gi) ?? []) {
    const attributes = new Map<string, string>();
    for (const match of tag.matchAll(attributePattern)) {
      attributes.set(
        match[1].toLowerCase(),
        decodeEntities(match[2] ?? match[3] ?? ""),
      );
    }
    const key = (attributes.get("property") ?? attributes.get("name") ?? "").toLowerCase();
    const content = attributes.get("content")?.trim();
    if (key && content && !values.has(key)) values.set(key, content);
  }

  return values;
}

function isPublicHttpUrl(value: URL): boolean {
  if (value.protocol !== "http:" && value.protocol !== "https:") return false;
  const host = value.hostname.toLowerCase();
  if (host === "localhost" || host === "0.0.0.0" || host === "[::1]" || host === "::1") {
    return false;
  }
  if (/^127\./.test(host) || /^10\./.test(host) || /^192\.168\./.test(host)) return false;
  if (/^172\.(1[6-9]|2\d|3[01])\./.test(host)) return false;
  return true;
}

function resolveSocialImage(html: string, pageUrl: string): string | null {
  const meta = parseMetaTags(html);

  for (const key of SOCIAL_IMAGE_KEYS) {
    const raw = meta.get(key);
    if (!raw) continue;
    try {
      const url = new URL(decodeEntities(raw), pageUrl);
      if (isPublicHttpUrl(url)) return url.toString();
    } catch {
      // A malformed value should not hide the next candidate.
    }
  }

  const linkImage = /<link\b[^>]*rel=["']image_src["'][^>]*href=["']([^"']+)["'][^>]*>/i.exec(
    html,
  );
  if (linkImage) {
    try {
      const url = new URL(decodeEntities(linkImage[1]), pageUrl);
      if (isPublicHttpUrl(url)) return url.toString();
    } catch {
      // Ignore and fall back to the monogram artwork.
    }
  }

  return null;
}

async function discoverImage(pageUrl: string): Promise<string | null> {
  const cached = metaCache.get(pageUrl);
  if (cached && cached.expiresAt > Date.now()) return cached.imageUrl;

  let imageUrl: string | null = null;
  try {
    const response = await fetch(pageUrl, {
      cache: "no-store",
      redirect: "follow",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      headers: {
        Accept: "text/html,application/xhtml+xml",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5",
        "User-Agent": "PrawdowidBot/0.1 (source preview cards)",
      },
    });
    if (response.ok) {
      const html = (await response.text()).slice(0, MAX_HTML_BYTES);
      imageUrl = resolveSocialImage(html, response.url || pageUrl);
    }
  } catch {
    // Offline, blocked or too slow: the card falls back to its monogram.
  }

  metaCache.set(pageUrl, {
    imageUrl,
    expiresAt: Date.now() + (imageUrl ? META_CACHE_TTL_MS : META_FAILURE_TTL_MS),
  });
  return imageUrl;
}

function sniffImageType(bytes: Uint8Array): string | null {
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return "image/jpeg";
  }
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    return "image/png";
  }
  if (bytes.length >= 6 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) {
    return "image/gif";
  }
  if (
    bytes.length >= 12 &&
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return "image/webp";
  }
  if (bytes.length >= 12 && bytes[4] === 0x66 && bytes[5] === 0x74 && bytes[6] === 0x79 && bytes[7] === 0x70) {
    return "image/avif";
  }
  return null;
}

async function readLimited(response: Response, limit: number): Promise<Uint8Array | null> {
  const contentLength = Number(response.headers.get("content-length") ?? "0");
  if (contentLength > limit) return null;
  if (!response.body) return null;

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } catch {
    return null;
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

function notFound(): Response {
  return new Response(null, {
    status: 404,
    headers: { "Cache-Control": "public, max-age=300" },
  });
}

export async function GET(request: NextRequest): Promise<Response> {
  const slug = request.nextUrl.searchParams.get("source") ?? "";
  const source = findCatalogSource(slug);
  if (!source) return notFound();

  const imageUrl = await discoverImage(source.url);
  if (!imageUrl) return notFound();

  let imageResponse: Response;
  try {
    imageResponse = await fetch(imageUrl, {
      cache: "no-store",
      redirect: "follow",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      headers: {
        Accept: "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
        "User-Agent": "PrawdowidBot/0.1 (source preview cards)",
      },
    });
  } catch {
    return notFound();
  }

  if (!imageResponse.ok) return notFound();

  const bytes = await readLimited(imageResponse, MAX_IMAGE_BYTES);
  if (!bytes || bytes.byteLength === 0) return notFound();

  const declaredType = (imageResponse.headers.get("content-type") ?? "")
    .split(";")[0]
    .trim()
    .toLowerCase();
  const contentType = declaredType.startsWith("image/")
    ? declaredType
    : sniffImageType(bytes);
  if (!contentType) return notFound();

  const body = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
  return new Response(body, {
    headers: {
      "Content-Type": contentType,
      "Content-Length": String(bytes.byteLength),
      "Cache-Control": `public, max-age=86400, s-maxage=${IMAGE_CACHE_TTL_SECONDS}, stale-while-revalidate=86400`,
      "X-Content-Type-Options": "nosniff",
    },
  });
}
