import { CheckFlow } from "@/components/check/CheckFlow";
import { PageShell } from "@/components/layout/PageShell";

export default function HomePage() {
  return (
    <PageShell
      title="Sprawdź informację w źródłach"
      lead="Wklej wiadomość, link albo zrzut ekranu. Zobaczysz, co mówią o tym źródła i czego nie udało się ustalić. Ocena należy do Ciebie."
    >
      <CheckFlow />
    </PageShell>
  );
}
