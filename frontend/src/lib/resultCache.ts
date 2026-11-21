import type { CheckResponse } from "./types";

/**
 * Hands a just-finished check to its result page, so navigating there does not fetch it again.
 * Memory only: a reload or a shared link always loads from the server.
 */
const results = new Map<string, CheckResponse>();
const MAX_RESULTS = 5;

export function cacheResult(result: CheckResponse): void {
  results.delete(result.id);
  results.set(result.id, result);
  while (results.size > MAX_RESULTS) {
    const oldest = results.keys().next().value;
    if (oldest === undefined) break;
    results.delete(oldest);
  }
}

export function cachedResult(id: string): CheckResponse | undefined {
  return results.get(id);
}
