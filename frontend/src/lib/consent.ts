import { deleteCookie, readCookie, writeCookie } from "./cookies";

/** Wersja polityki prywatności, na którą zbieramy zgodę.
 *  Musi odpowiadać PRIVACY_POLICY_VERSION w backend/app/config.py.
 *  Zmiana wersji sprawia, że pytamy o zgodę ponownie. */
export const PRIVACY_POLICY_VERSION = "2026-11-21";

/** Nazwa ciasteczka musi odpowiadać CONSENT_COOKIE w backend/app/api/deps.py. */
export const CONSENT_COOKIE = "prawdowid_privacy_consent";
/** Stary klucz w localStorage – czytamy go raz, żeby nie pytać ponownie osób,
 *  które zgodę już wyraziły. */
const LEGACY_STORAGE_KEY = "prawdowid_privacy_consent";

function legacyConsent(): string | null {
  try {
    return window.localStorage.getItem(LEGACY_STORAGE_KEY);
  } catch {
    return null;
  }
}

function dropLegacyConsent(): void {
  try {
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    // Nic nie było zapisane.
  }
}

/** Ciasteczko ze zgodą służy do tego, by nie pytać przy każdym wejściu, a backend
 *  widzi je przy każdym żądaniu. Wiążący zapis jest w bazie (POST /api/v1/consent). */
export function peekConsent(): string | null {
  const fromCookie = readCookie(CONSENT_COOKIE);
  if (fromCookie) return fromCookie;
  const legacy = legacyConsent();
  if (legacy) {
    writeCookie(CONSENT_COOKIE, legacy);
    dropLegacyConsent();
    return legacy;
  }
  return null;
}

export function hasConsentCookie(version = PRIVACY_POLICY_VERSION): boolean {
  return peekConsent() === version;
}

export function rememberConsent(version = PRIVACY_POLICY_VERSION): void {
  writeCookie(CONSENT_COOKIE, version);
}

export function forgetConsent(): void {
  deleteCookie(CONSENT_COOKIE);
  dropLegacyConsent();
}
