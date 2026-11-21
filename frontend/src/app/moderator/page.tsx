import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { Notice } from "@/components/ui/Notice";
import { Wrench } from "lucide-react";

export const metadata: Metadata = { title: "Panel moderatora" };

export default function ModeratorPage() {
  return (
    <PageShell
      wide
      title="Panel moderatora"
      lead="Panel moderatora dostępny jest wyłącznie przez API."
    >
      <Notice icon={Wrench} title="Dostęp do panelu">
        <p>Panel moderatora nie posiada interfejsu graficznego w tej wersji.</p>
        <p className="mt-2">
          Użyj endpointów API z nagłówkiem <code className="px-1.5 py-0.5 rounded bg-surface font-mono text-sm">X-Admin-Token</code>:
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-6 font-mono text-sm">
          <li><code>GET /api/v1/admin/metrics</code> – statystyki systemu</li>
          <li><code>GET /api/v1/admin/checks</code> – lista sprawdzeń</li>
          <li><code>GET /api/v1/admin/export?format=csv|json</code> – eksport danych</li>
        </ul>
        <p className="mt-3 text-muted">
          Token administratora ustawia się zmienną środowiskową <code className="px-1.5 py-0.5 rounded bg-surface font-mono text-sm">ADMIN_TOKEN</code> w backendzie.
        </p>
      </Notice>
    </PageShell>
  );
}