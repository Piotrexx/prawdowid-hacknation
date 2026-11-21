import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { SmsSimulator } from "@/components/sms/SmsSimulator";

export const metadata: Metadata = { title: "Symulator SMS" };

export default function SmsPage() {
  return (
    <PageShell
      title="Symulator SMS"
      lead="Zobacz, jak wygląda sprawdzanie informacji przez wiadomość tekstową."
    >
      <SmsSimulator />
    </PageShell>
  );
}
