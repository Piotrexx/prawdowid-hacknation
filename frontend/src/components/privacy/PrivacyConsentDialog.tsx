"use client";

import { Database, FileText, Shield, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/Button";
import { cx } from "@/lib/cx";
import { recordConsent } from "@/lib/api";
import { PRIVACY_POLICY_VERSION, peekConsent, rememberConsent } from "@/lib/consent";
import { ensureSessionId } from "@/lib/session";

const POINTS = [
  {
    icon: Shield,
    title: "Dane osobowe są maskowane",
    body:
      "Zanim treść trafi do analizy, zastępujemy rozpoznane dane osobowe znacznikami " +
      "(np. [EMAIL], [PESEL], [TELEFON]).",
  },
  {
    icon: Database,
    title: "Zapisujemy przebieg sprawdzenia",
    body:
      "Zapisujemy fragment sprawdzanej treści (do 1 500 znaków), znalezione źródła i wynik, " +
      "powiązane z losowym numerem sesji. Nie zbieramy Twojego imienia ani adresu e-mail.",
  },
  {
    icon: FileText,
    title: "Model językowy działa u dostawcy",
    body:
      "Treść po zamaskowaniu jest wysyłana do modelu językowego, aby wydzielić twierdzenia " +
      "i ocenić dowody. Wyszukiwanie w katalogu źródeł odbywa się lokalnie.",
  },
  {
    icon: Trash2,
    title: "Możesz to usunąć w każdej chwili",
    body:
      "Dane sesji usuwamy automatycznie po 30 dniach, a na Twoje żądanie – natychmiast.",
  },
];

/** Ciasteczka nie zmieniają się same, więc nie ma czego subskrybować –
 *  przerysowanie wywołuje akceptacja zgody (zwykły stan komponentu). */
function subscribeToConsent(): () => void {
  return () => {};
}

/** Na serwerze udajemy, że zgoda już jest: okno pojawia się dopiero po hydratacji,
 *  więc serwer i klient renderują to samo i nie ma ostrzeżenia o niezgodności. */
function serverConsent(): string {
  return PRIVACY_POLICY_VERSION;
}

/** Okno zgody na politykę prywatności. Pokazuje się raz na wersję polityki;
 *  akceptacja jest zapisywana w ciasteczku i na serwerze (sam fakt zgody). */
export function PrivacyConsentDialog() {
  const storedConsent = useSyncExternalStore(subscribeToConsent, peekConsent, serverConsent);
  const [accepted, setAccepted] = useState(false);
  const [closing, setClosing] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const acceptRef = useRef<HTMLButtonElement>(null);
  const open = !accepted && storedConsent !== PRIVACY_POLICY_VERSION;

  useEffect(() => {
    if (!open) return;
    acceptRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  // Zgoda jest warunkiem korzystania, więc okna nie zamyka się Escape'em ani kliknięciem w tło.
  // Fokus trzymamy w oknie, żeby czytnik ekranu nie wyszedł poza treść zgody.
  const trapFocus = useCallback((event: React.KeyboardEvent) => {
    if (event.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  function accept() {
    // Ciasteczko ustawiamy niezależnie od wyniku zapisu w bazie: brak sieci
    // nie może zamknąć drogi do usługi, a zgoda i tak została wyrażona.
    // Backend dostaje je przy każdym kolejnym żądaniu.
    rememberConsent();
    // Zapis w bazie jest best-effort i nie blokuje zamknięcia okna; przy awarii
    // ponowimy go przy następnej zmianie wersji polityki.
    void recordConsent(ensureSessionId(), PRIVACY_POLICY_VERSION).catch(() => {});
    setClosing(true);
  }

  if (!open) return null;

  return (
    <div
      className={cx(
        "fixed inset-0 z-50 flex items-end justify-center bg-ink/60 sm:items-center sm:p-6",
        closing ? "overlay-exit" : "overlay-enter",
      )}
      onKeyDown={trapFocus}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="zgoda-tytul"
        aria-describedby="zgoda-opis"
        // Nagłówek i stopka stoją, przewija się tylko środek – okno nie rozciąga się na cały ekran.
        className={cx(
          "flex max-h-[88dvh] w-full max-w-2xl flex-col border border-line-mid bg-surface shadow-card sm:max-h-[80dvh]",
          closing ? "dialog-exit" : "dialog-enter",
        )}
        // Okno znika po animacji wyjścia. Przy ograniczonych animacjach trwa ona 0,01 ms,
        // więc zdarzenie i tak przychodzi od razu i nic się nie blokuje.
        onAnimationEnd={() => {
          if (closing) setAccepted(true);
        }}
      >
        <div className="shrink-0 border-b border-line px-6 py-4">
          <p className="eyebrow">Prywatność</p>
          <h2 id="zgoda-tytul" className="mt-0.5 text-2xl leading-snug font-bold">
            Zanim zaczniesz sprawdzać
          </h2>
          <span aria-hidden="true" className="title-rule mt-2.5" />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          <p id="zgoda-opis" className="text-muted">
            Prawdowid to prototyp hackathonowy. Żeby z niego korzystać, potwierdź, że wiesz,
            jak przetwarzamy treści, które wklejasz.
          </p>

          <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
            {POINTS.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-2.5 border border-line bg-subtle px-3.5 py-3">
                <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-accent" />
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="mt-0.5 text-sm text-muted">{body}</p>
                </div>
              </li>
            ))}
          </ul>

          <p className="mt-4 text-sm text-muted">
            Szczegóły znajdziesz w polityce prywatności. Nie wklejaj danych objętych
            tajemnicą zawodową ani dokumentów poufnych.
          </p>
        </div>

        <div className="shrink-0 flex flex-col gap-3 border-t border-line bg-page px-6 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:flex-row sm:items-center sm:justify-between sm:pb-4">
          <p className="text-sm text-muted">Wersja polityki: {PRIVACY_POLICY_VERSION}</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Link
              href="/prywatnosc"
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-accent bg-surface px-4 font-semibold text-accent transition-colors hover:bg-info-bg"
            >
              Przeczytaj politykę
            </Link>
            <Button ref={acceptRef} variant="primary" large onClick={accept} disabled={closing}>
              Rozumiem i zaczynam
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
