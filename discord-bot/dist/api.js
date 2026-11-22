import { Buffer } from "node:buffer";
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const API_BASE = `${API_URL}/api/v1`;
const REQUEST_TIMEOUT_MS = 150_000;
export class BackendError extends Error {
}
const VERSION_RE = /Wymagana wersja: ([^.]+)\./;
function sessionIdFor(userId) {
    return `discord-${userId}`;
}
async function postJson(path, body) {
    return fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
}
async function postImage(sessionId, file, filename, contentType) {
    const form = new FormData();
    form.append("file", new Blob([new Uint8Array(file)], { type: contentType }), filename);
    form.append("session_id", sessionId);
    return fetch(`${API_BASE}/checks/image`, {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
}
async function ensureConsent(sessionId, policyVersion) {
    const resp = await postJson("/consent", {
        session_id: sessionId,
        policy_version: policyVersion,
        accepted: true,
    });
    if (!resp.ok) {
        throw new BackendError("Nie udało się zapisać zgody na politykę prywatności.");
    }
}
/** Backend odrzuca zgłoszenie kodem 428, dopóki sesja nie zaakceptuje polityki prywatności
 * (wersja jest w treści błędu) – łapiemy to raz, rejestrujemy zgodę i powtarzamy żądanie. */
async function withConsentRetry(sessionId, send) {
    let resp = await send();
    if (resp.status === 428) {
        const text = await resp.text();
        const match = VERSION_RE.exec(text);
        if (!match) {
            throw new BackendError("Backend wymaga zgody na politykę prywatności, ale nie udało się ustalić jej wersji.");
        }
        await ensureConsent(sessionId, match[1]);
        resp = await send();
    }
    if (!resp.ok) {
        throw new BackendError(`Backend zwrócił błąd ${resp.status}.`);
    }
    return (await resp.json());
}
export async function checkText(userId, text) {
    const sessionId = sessionIdFor(userId);
    return withConsentRetry(sessionId, () => postJson("/checks", { text, session_id: sessionId }));
}
export async function checkUrl(userId, url) {
    const sessionId = sessionIdFor(userId);
    return withConsentRetry(sessionId, () => postJson("/checks", { url, session_id: sessionId }));
}
export async function checkImage(userId, file, filename, contentType) {
    const sessionId = sessionIdFor(userId);
    return withConsentRetry(sessionId, () => postImage(sessionId, file, filename, contentType));
}
//# sourceMappingURL=api.js.map