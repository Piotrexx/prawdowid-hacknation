import Link from "next/link";
import type { ReactNode } from "react";
import { VerdictBadge } from "@/components/result/VerdictBadge";
import type { VerdictLabel } from "@/lib/types";
import { HealthBlock } from "./HealthBlock";

const VERDICTS: Array<{ verdict: VerdictLabel; meaning: string }> = [
  { verdict: "fake_news", meaning: "Artykuł zawiera fałszywe informacje (dezinformacja). Fact-checki obalają te twierdzenia." },
  { verdict: "prawdziwe", meaning: "Główne twierdzenia artykułu są wspierane przez wiarygodne źródła i fact-checki." },
  { verdict: "niepewne", meaning: "Brak wystarczających dowodów ani w jedną, ani w drugą stronę. Twierdzenia są trudne do zweryfikowania." },
  { verdict: "satyna", meaning: "Artykuł jest satyrą/paryzą (np. ASZdziennik), nie ma być traktowany poważnie." },
  { verdict: "opinia", meaning: "Artykuł wyraża opinię lub komentarz autora, a nie stwierdza fakty." },
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
            "Pobiera treść artykułu z podanego linku (trafilatura).",
            "Wyciąga słowa kluczowe z tytułu i treści (model Bielik 4.5B Instruct, prompt po polsku).",
            "Wyszukuje powiązane sprawdzenia faktów w Google Fact Check Tools API (top 5 wyników).",
            "Ocenia, czy artykuł to fake news, na podstawie treści, słów kluczowych i znalezionych fact-checków (DeepSeek).",
            "Mówi wprost, czego nie udało się ustalić (brak fact-checków, sprzeczne źródła).",
          ]}
        />
      </Section>

      <Section id="czego-nie-robi" title="Czego Prawdowid nie robi">
        <Bullets
          items={[
            "Nie jest sędzią prawdy. Pokazuje analizę opartą na modelach AI i fact-checkach. Ostateczna ocena należy do Ciebie.",
            "Nie przeszukuje całego internetu na żywo – korzysta z Google Fact Check Tools API (baza istniejących sprawdzeń).",
            "Nie zgaduje. Gdy dowodów jest za mało, zwraca werdykt „niepewne”.",
            "Nie ocenia autentyczności zdjęć ani filmów – tylko tekst artykułu.",
            "Nie zastępuje urzędu, prawnika ani lekarza.",
          ]}
        />
      </Section>

      <Section id="oceny" title="Pięć możliwych werdyktów">
        <p>Każdy sprawdzony artykuł dostaje jedną z pięciu ocen:</p>
        <dl className="space-y-4">
          {VERDICTS.map(({ verdict, meaning }) => (
            <div key={verdict}>
              <dt>
                <VerdictBadge verdict={verdict} confidence={0.8} justification={meaning} />
              </dt>
              <dd className="mt-1 text-muted">{meaning}</dd>
            </div>
          ))}
        </dl>
        <p>
          Czasem zamiast werdyktu zobaczysz prośbę o poprawny link, informację, że pytanie jest poza zakresem,
          albo komunikat o problemie technicznym. To nie są werdykty merytoryczne.
        </p>
      </Section>

      <Section id="prywatnosc" title="Twoja prywatność">
        <Bullets
          items={[
            "Sprawdzane jest tylko to, co podasz w linku. Treść artykułu nie jest przechowywana trwale (tylko fragment do 1500 znaków).",
            "Łatwe do rozpoznania dane osobowe są automatycznie ukrywane przed wysłaniem do modeli.",
            "Sprawdzenia są przypisane do losowego numeru sesji w Twojej przeglądarce. Możesz je usunąć przyciskiem „Usuń moje dane z tej sesji” na stronie głównej.",
            "Zapisy są usuwane automatycznie po określonym czasie (domyślnie 30 dni).",
            "Mimo to nie wklejaj haseł ani innych danych, których nie chcesz nikomu pokazywać.",
          ]}
        />
      </Section>

      <Section id="ai" title="Sztuczna inteligencja">
        <Bullets
          items={[
            "Prawdowid korzysta z dwóch modeli językowych: Bielik 4.5B Instruct (lokalnie przez Ollama/vLLM) do słów kluczowych, oraz DeepSeek (API) do ostatecznego werdyktu.",
            "Modele pomagają zrozumieć treść i porównać ją z znalezionymi fact-checkami.",
            "Każdy znaleziony fact-check ma link do oryginału (np. Demagog, AFP, Reuters Fact Check).",
            "Werdykt i uzasadnienie pochodzą od modelu DeepSeek. Mogą zawierać błędy, dlatego zawsze warto zajrzeć do źródeł fact-checków.",
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