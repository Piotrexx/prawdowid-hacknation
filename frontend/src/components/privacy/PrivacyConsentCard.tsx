"use client";

import { CheckCircle2, Cookie } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/Button";
import { recordConsent } from "@/lib/api";
import {
  PRIVACY_POLICY_VERSION,
  peekConsent,
  rememberConsent,
  subscribeConsent,
} from "@/lib/consent";
import { ensureSessionId } from "@/lib/session";

/** Zgoda na politykę i ciasteczka także na stronie polityki –
 *  można ją wyrazić bez wracania do wyskakującego okna. */
export function PrivacyConsentCard() {
  const consent = useSyncExternalStore(subscribeConsent, peekConsent, () => null);
  const accepted = consent === PRIVACY_POLICY_VERSION;

  function accept() {
    // Ciasteczko działa od razu; zapis w bazie jest best-effort (jak w oknie zgody).
    rememberConsent();
    void recordConsent(ensureSessionId(), PRIVACY_POLICY_VERSION).catch(() => {});
  }

  return (
    <section
      aria-labelledby="zgoda-polityka"
      className="rounded-xl border border-line bg-surface p-5"
    >
      <h2 id="zgoda-polityka" className="flex items-center gap-2 text-xl font-semibold">
        <Cookie aria-hidden="true" className="size-5 text-accent" />
        Zgoda na politykę prywatności i cookies
      </h2>

      {accepted ? (
        <div className="mt-3 flex gap-3 border border-ok-line bg-ok-bg px-4 py-3">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ok-fg" />
          <div>
            <p className="font-semibold text-ok-fg">Zgoda jest zapisana</p>
            <p className="mt-0.5 text-sm text-muted">
              Zaakceptowano wersję polityki {PRIVACY_POLICY_VERSION} w tej przeglądarce.
            </p>
          </div>
        </div>
      ) : (
        <>
          <p className="mt-2 text-muted">
            Prawdowid zapisuje w Twojej przeglądarce tylko dwa ciasteczka: losowy numer
            sesji (<code className="rounded bg-subtle px-1 py-0.5 font-mono text-xs">prawdowid_session</code>)
            i wersję zaakceptowanej polityki
            (<code className="rounded bg-subtle px-1 py-0.5 font-mono text-xs">prawdowid_privacy_consent</code>).
            Nie używamy ciasteczek reklamowych ani analitycznych.
          </p>
          <Button variant="primary" className="mt-4" onClick={accept}>
            <Cookie aria-hidden="true" className="size-5" />
            Akceptuję politykę prywatności i cookies
          </Button>
        </>
      )}
    </section>
  );
}
