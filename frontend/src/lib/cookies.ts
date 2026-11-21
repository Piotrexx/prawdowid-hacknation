/** Ciasteczka zamiast localStorage: ten sam identyfikator widzi przeglądarka i backend,
 *  więc zgodę oraz numer sesji można powiązać po stronie serwera.
 *
 *  Ciasteczka ustawiamy z JavaScriptu, więc nie mogą być HttpOnly – frontend musi je czytać.
 *  Nie trzymamy w nich nic poufnego: tylko losowy numer sesji i wersję zaakceptowanej polityki.
 */

/** Rok. Retencję danych i tak wymusza backend (RETENTION_DAYS), to tylko górny limit. */
const DEFAULT_MAX_AGE_S = 60 * 60 * 24 * 365;

function isSecureContext(): boolean {
  try {
    return window.location.protocol === "https:";
  } catch {
    return false;
  }
}

export function readCookie(name: string): string | null {
  try {
    const prefix = `${encodeURIComponent(name)}=`;
    for (const part of document.cookie.split(";")) {
      const entry = part.trim();
      if (entry.startsWith(prefix)) {
        return decodeURIComponent(entry.slice(prefix.length));
      }
    }
  } catch {
    // Brak dostępu do document.cookie (SSR, zablokowane ciasteczka).
  }
  return null;
}

export function writeCookie(name: string, value: string, maxAgeSeconds = DEFAULT_MAX_AGE_S): void {
  try {
    // SameSite=Lax wystarcza, dopóki frontend i backend są w tej samej witrynie
    // (localhost:3000 i localhost:8000 to ta sama witryna, inny port).
    // Przy wdrożeniu na osobne domeny trzeba zmienić na SameSite=None; Secure.
    const attributes = [
      `${encodeURIComponent(name)}=${encodeURIComponent(value)}`,
      "path=/",
      `max-age=${maxAgeSeconds}`,
      "SameSite=Lax",
    ];
    if (isSecureContext()) attributes.push("Secure");
    document.cookie = attributes.join("; ");
  } catch {
    // Zablokowane ciasteczka nie mogą uniemożliwić korzystania z usługi.
  }
}

export function deleteCookie(name: string): void {
  try {
    document.cookie = `${encodeURIComponent(name)}=; path=/; max-age=0; SameSite=Lax`;
  } catch {
    // Nic nie było zapisane, więc nie ma czego usuwać.
  }
}
