const STORAGE_KEY = "prawdowid_session";
const VALID_ID = /^[A-Za-z0-9_-]{8,64}$/;

// Used when localStorage is unavailable (private mode, blocked storage).
let memoryId: string | null = null;

function generateId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // randomUUID exists only in secure contexts; plain-http LAN demos need this path.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function peekSessionId(): string | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && VALID_ID.test(stored)) return stored;
  } catch {
    // Fall through to the in-memory id.
  }
  return memoryId;
}

export function ensureSessionId(): string {
  const existing = peekSessionId();
  if (existing) return existing;
  const id = generateId();
  memoryId = id;
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // The in-memory id still lets the user delete their data during this visit.
  }
  return id;
}

export function clearSessionId(): void {
  memoryId = null;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing was stored, so there is nothing to remove.
  }
}
