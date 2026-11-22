import {
  AtSign,
  Clock,
  Hash,
  Lock,
  Phone,
  Shield,
  Trash2,
  Wifi,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { PageShell } from "@/components/layout/PageShell";
import { PrivacyConsentCard } from "@/components/privacy/PrivacyConsentCard";

export const metadata: Metadata = {
  title: "Prywatność i ochrona danych – Prawdowid",
};

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-4">
      <h2 id={id} className="text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

interface PiiCardProps {
  icon: ReactNode;
  label: string;
  example: string;
  replacement: string;
}

function PiiCard({ icon, label, example, replacement }: PiiCardProps) {
  return (
    <div className="border border-line bg-surface px-4 py-3.5">
      <div className="flex items-center gap-2.5">
        <span className="text-accent">{icon}</span>
        <span className="font-semibold">{label}</span>
      </div>
      <p className="mt-2 text-sm text-muted">
        Przykład:{" "}
        <code className="rounded bg-subtle px-1 py-0.5 font-mono text-xs">{example}</code>
        {" → "}
        <code className="rounded bg-subtle px-1 py-0.5 font-mono text-xs text-accent">
          {replacement}
        </code>
      </p>
    </div>
  );
}

export default function PrivacyPage() {
  return (
    <PageShell
      title="Prywatność i ochrona danych"
      lead="Prawdowid automatycznie maskuje dane osobowe przed wysłaniem treści do weryfikacji. Poniżej znajdziesz opis całego procesu."
    >
      <div className="space-y-12 text-base leading-relaxed">
        <PrivacyConsentCard />

        <Section id="maskowanie" title="Automatyczne maskowanie danych osobowych">
          <p className="text-muted">
            Zanim Twoja wiadomość trafi do systemu weryfikacji, Prawdowid wykrywa i zastępuje
            rozpoznawalne dane osobowe bezpiecznymi znacznikami. Dzieje się to{" "}
            <strong>w Twojej przeglądarce</strong>, zanim cokolwiek zostanie wysłane na serwer.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <PiiCard
              icon={<AtSign className="size-5" />}
              label="Adres e-mail"
              example="jan.kowalski@example.pl"
              replacement="[ADRES_EMAIL]"
            />
            <PiiCard
              icon={<Hash className="size-5" />}
              label="Numer PESEL"
              example="85010100000"
              replacement="[PESEL]"
            />
            <PiiCard
              icon={<Phone className="size-5" />}
              label="Numer telefonu"
              example="+48 123 456 789"
              replacement="[NUMER_TELEFONU]"
            />
            <PiiCard
              icon={<Wifi className="size-5" />}
              label="Adres IP"
              example="192.168.0.1"
              replacement="[ADRES_IP]"
            />
          </div>
          <p className="text-sm text-muted">
            Gdy Prawdowid zamaskuje dane, zobaczysz pod swoją wiadomością informację z listą
            zamaskowanych kategorii. Oryginalna treść pozostaje tylko u Ciebie w przeglądarce
            i nie jest nigdzie wysyłana.
          </p>
        </Section>

        <Section id="jak-dziala" title="Jak przetwarzamy dane">
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              Wklejasz tekst lub link. Dane osobowe są maskowane lokalnie, w Twojej
              przeglądarce.
            </li>
            <li>
              Zanonimizowana treść trafia na serwer Prawdowid. Dla linków pobieramy artykuł
              narzędziem trafilatura.
            </li>
            <li>
              Z treści wyciągamy słowa kluczowe (model Bielik) i przeszukujemy bazę Google
              Fact Check Tools.
            </li>
            <li>
              Model językowy (DeepSeek) formułuje werdykt i uzasadnienie na podstawie
              zebranych sprawdzeń faktów.
            </li>
            <li>
              Wynik i krótki fragment treści (do 1 500 znaków) są zapisywane w bazie danych
              powiązanej z Twoim numerem sesji.
            </li>
          </ol>
        </Section>

        <Section id="retencja" title="Retencja danych">
          <div className="flex gap-3 border border-line bg-surface px-4 py-3.5">
            <Clock className="mt-0.5 size-5 shrink-0 text-accent" />
            <div>
              <p className="font-semibold">Automatyczne usuwanie po 30 dniach</p>
              <p className="mt-0.5 text-sm text-muted">
                Każde sprawdzenie jest automatycznie usuwane z bazy danych po domyślnym czasie
                retencji (30 dni). Możesz usunąć swoje dane wcześniej.
              </p>
            </div>
          </div>
          <p className="text-sm text-muted">
            Numer sesji jest generowany losowo przy pierwszym odwiedzeniu strony i
            przechowywany w ciasteczku (<code className="rounded bg-subtle px-1 py-0.5 font-mono text-xs">
            prawdowid_session</code>), razem z wersją zaakceptowanej polityki prywatności
            (<code className="rounded bg-subtle px-1 py-0.5 font-mono text-xs">
            prawdowid_privacy_consent</code>). Ciasteczka nie służą do reklam ani analityki –
            wiążą Twoje sprawdzenia z sesją i pozwalają je usunąć. Nie łączymy sesji z Twoją
            tożsamością.
          </p>
        </Section>

        <Section id="bezpieczenstwo" title="Zabezpieczenia techniczne">
          <ul className="space-y-3">
            <li className="flex gap-3">
              <Shield className="mt-0.5 size-5 shrink-0 text-accent" />
              <div>
                <p className="font-semibold">Ochrona przed prompt injection</p>
                <p className="text-sm text-muted">
                  Instrukcje znalezione w analizowanych materiałach są izolowane od poleceń
                  systemowych. System ignoruje próby manipulacji i odnotowuje zdarzenia
                  bezpieczeństwa.
                </p>
              </div>
            </li>
            <li className="flex gap-3">
              <Lock className="mt-0.5 size-5 shrink-0 text-accent" />
              <div>
                <p className="font-semibold">Minimalizacja danych</p>
                <p className="text-sm text-muted">
                  Zapisujemy tylko fragment treści niezbędny do wyświetlenia wyniku. Pełna
                  treść artykułów ani pliki graficzne nie są trwale przechowywane.
                </p>
              </div>
            </li>
          </ul>
        </Section>

        <Section id="usuwanie" title="Usuwanie danych sesji">
          <div className="flex gap-3 border border-line bg-surface px-4 py-3.5">
            <Trash2 className="mt-0.5 size-5 shrink-0 text-muted" />
            <div>
              <p className="font-semibold">Możesz usunąć swoje sprawdzenia</p>
              <p className="mt-0.5 text-sm text-muted">
                Na stronie{" "}
                <Link href="/o-systemie" className="text-link underline-offset-2 hover:underline">
                  Jak to działa
                </Link>{" "}
                znajdziesz przycisk usunięcia danych powiązanych z Twoją sesją. Dane są
                kasowane natychmiast i nieodwracalnie.
              </p>
            </div>
          </div>
        </Section>

        <Section id="ai-disclosure" title="Gdzie przetwarzane są dane przez modele AI">
          <p className="text-muted">
            Prawdowid korzysta z zewnętrznych modeli językowych. Treść weryfikowana przez
            DeepSeek jest przesyłana do serwerów DeepSeek zgodnie z ich{" "}
            <a
              href="https://www.deepseek.com/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-link underline-offset-2 hover:underline"
            >
              polityką prywatności
            </a>
            . Lokalne modele (Bielik przez Ollama) przetwarzają dane w obrębie infrastruktury
            Prawdowid.
          </p>
          <p className="text-sm text-muted">
            Nie wklejaj treści zawierających tajemnicę zawodową, tajne dane osobowe ani
            poufnych dokumentów.
          </p>
        </Section>
      </div>
    </PageShell>
  );
}
