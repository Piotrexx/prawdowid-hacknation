import Link from "next/link";
import type { ReactNode } from "react";
import { VerdictBadge } from "@/components/result/VerdictBadge";
import type { Verdict } from "@/lib/types";
import { HealthBlock } from "./HealthBlock";

const VERDICTS: Array<{ verdict: Verdict; meaning: string }> = [
  { verdict: "potwierdzone", meaning: "Źródła potwierdzają to twierdzenie." },
  { verdict: "falszywe", meaning: "Źródła zaprzeczają temu twierdzeniu." },
  {
    verdict: "wprowadzajace_w_blad",
    meaning:
      "W twierdzeniu jest część prawdy, ale brakuje ważnego kontekstu albo fakty są pokazane w mylący sposób.",
  },
  {
    verdict: "brak_wystarczajacych_dowodow",
    meaning:
      "W źródłach jest za mało materiału, żeby to ocenić. To uczciwe „nie wiem”. Nie oznacza, że twierdzenie jest fałszywe.",
  },
  {
    verdict: "nie_podlega_weryfikacji",
    meaning: "To opinia, ocena albo prognoza. Takich wypowiedzi nie da się sprawdzić w źródłach.",
  },
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-2xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Bullets({ items }: { items: ReactNode[] }) {
  return (
    <ul className="list-disc space-y-2 pl-6">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

export function AboutContent() {
  return (
    <div className="space-y-12 text-lg leading-relaxed">
      <Section id="co-robi" title="Co robi Prawdowid">
        <Bullets
          items={[
            "Dzieli wklejoną treść na pojedyncze twierdzenia.",
            "Szuka każdego twierdzenia w opisanym zbiorze źródeł.",
            "Pokazuje dosłowne cytaty ze źródeł i linki do nich.",
            "Oddziela materiał źródłowy od własnej interpretacji.",
            "Mówi wprost, czego nie udało się ustalić.",
          ]}
        />
      </Section>

      <Section id="czego-nie-robi" title="Czego Prawdowid nie robi">
        <Bullets
          items={[
            "Nie jest sędzią prawdy. Pokazuje, co mówią źródła. Ostateczna ocena należy do Ciebie.",
            <>
              Nie przeszukuje całego internetu. Odpowiada tylko na podstawie źródeł z{" "}
              <Link href="/zrodla" className="link">
                katalogu źródeł
              </Link>
              .
            </>,
            "Nie zgaduje. Gdy dowodów jest za mało, wstrzymuje się od oceny.",
            "Nie ocenia opinii ani prognoz.",
            "Nie zastępuje urzędu, prawnika ani lekarza.",
          ]}
        />
      </Section>

      <Section id="oceny" title="Pięć możliwych ocen">
        <p>Każde twierdzenie dostaje jedną z pięciu ocen:</p>
        <dl className="space-y-4">
          {VERDICTS.map(({ verdict, meaning }) => (
            <div key={verdict}>
              <dt>
                <VerdictBadge verdict={verdict} />
              </dt>
              <dd className="mt-1">{meaning}</dd>
            </div>
          ))}
        </dl>
        <p>
          Czasem zamiast oceny zobaczysz prośbę o więcej szczegółów, informację, że
          pytanie jest poza zakresem, albo komunikat o problemie technicznym. To nie
          są oceny.
        </p>
      </Section>

      <Section id="sila-podstawy" title="Co znaczy „siła podstawy”">
        <p>
          Siła podstawy mówi, jak solidne są materiały, na których opiera się ocena.
          Nie mówi, czy samo twierdzenie jest prawdziwe.
        </p>
        <p>
          Ma cztery poziomy: mocna, umiarkowana, słaba i brak. Przy każdej ocenie
          możesz rozwinąć listę „Skąd ta ocena siły?”. Zobaczysz tam, co wzmacnia
          podstawę, a co ją osłabia.
        </p>
      </Section>

      <Section id="prywatnosc" title="Twoja prywatność">
        <Bullets
          items={[
            "Łatwe do rozpoznania dane osobowe są automatycznie ukrywane, zanim treść zostanie przetworzona.",
            "Obrazy nie są zapisywane.",
            <>
              Sprawdzenia są przypisane do losowego numeru sesji w Twojej przeglądarce.
              Możesz je usunąć przyciskiem „Usuń moje dane z tej sesji” na{" "}
              <Link href="/" className="link">
                stronie głównej
              </Link>
              .
            </>,
            "Zapisy są usuwane automatycznie po określonym czasie. Aktualny okres widzisz niżej, w części „Aktualna konfiguracja”.",
            "Mimo to nie wklejaj haseł ani innych danych, których nie chcesz nikomu pokazywać.",
          ]}
        />
      </Section>

      <Section id="ai" title="Sztuczna inteligencja">
        <Bullets
          items={[
            "Prawdowid korzysta z modelu językowego, czyli sztucznej inteligencji.",
            "Model pomaga zrozumieć pytanie i porównać je z materiałami ze źródeł.",
            "Każde ustalenie ma link do źródła. Cytaty są sprawdzane automatycznie: muszą dosłownie występować w źródle.",
            "Opis oznaczony jako „Interpretacja systemu” pochodzi od modelu. Może zawierać błędy, dlatego zawsze warto zajrzeć do źródeł.",
          ]}
        />
      </Section>

      <Section id="konfiguracja" title="Aktualna konfiguracja">
        <p>Te dane pochodzą prosto z serwera.</p>
        <HealthBlock />
      </Section>
    </div>
  );
}
