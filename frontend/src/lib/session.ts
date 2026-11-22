import { deleteCookie, readCookie, writeCookie } from "./cookies";

/** Nazwa ciasteczka musi odpowiadać SESSION_COOKIE w backend/app/api/deps.py. */
export const SESSION_COOKIE = "prawdowid_session";
/** Stary klucz w localStorage – czytamy go raz, żeby nie zgubić historii użytkownikom. */
const LEGACY_STORAGE_KEY = "prawdowid_session";
const VALID_ID = /^[A-Za-z0-9_-]{8,64}$/;

// Używane, gdy ciasteczka są zablokowane (tryb prywatny, zablokowana pamięć).
let memoryId: string | null = null;

function generateId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // randomUUID istnieje tylko w bezpiecznym kontekście; demo po zwykłym http potrzebuje tej ścieżki.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Numer sesji z czasów, gdy trzymaliśmy go w localStorage. */
function legacyId(): string | null {
  try {
    const stored = window.localStorage.getItem(LEGACY_STORAGE_KEY);
    if (stored && VALID_ID.test(stored)) return stored;
  } catch {
    // Brak dostępu do localStorage – nie ma czego przenosić.
  }
  return null;
}

function dropLegacyId(): void {
  try {
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    // Nic nie było zapisane.
  }
}

export function peekSessionId(): string | null {
  const fromCookie = readCookie(SESSION_COOKIE);
  if (fromCookie && VALID_ID.test(fromCookie)) return fromCookie;
  // Przeniesienie ze starej wersji: numer z localStorage trafia do ciasteczka.
  const legacy = legacyId();
  if (legacy) {
    writeCookie(SESSION_COOKIE, legacy);
    dropLegacyId();
    memoryId = legacy;
    return legacy;
  }
  return memoryId;
}

export function ensureSessionId(): string {
  const existing = peekSessionId();
  if (existing) return existing;
  const id = generateId();
  memoryId = id;
  writeCookie(SESSION_COOKIE, id);
  return id;
}

export function clearSessionId(): void {
  memoryId = null;
  deleteCookie(SESSION_COOKIE);
  dropLegacyId();
}
