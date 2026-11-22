import { Download } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { downloadExport } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { guarded, type AdminAccess } from "./useAdminData";

type ExportFormat = "csv" | "json" | "stix";

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ExportButtons({ access }: { access: AdminAccess }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function download(format: ExportFormat) {
    setBusy(format);
    setMessage(null);
    try {
      const { blob, filename } = await guarded(access, downloadExport(access.token, format));
      const day = new Date().toISOString().slice(0, 10);
      const extension = format === "stix" ? "json" : format;
      saveBlob(blob, filename ?? `prawdowid-eksport-${day}.${extension}`);
      setMessage(`Pobrano plik ${format === "stix" ? "STIX" : format.toUpperCase()}.`);
    } catch (error) {
      setMessage(`Nie udało się pobrać pliku. ${describeError(error)}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {(["csv", "json", "stix"] as const).map((format) => (
          <Button key={format} onClick={() => void download(format)} disabled={busy !== null}>
            <Download aria-hidden="true" className="size-5" />
            {busy === format ? "Pobieram…" : `Eksport ${format === "stix" ? "STIX" : format.toUpperCase()}`}
          </Button>
        ))}
      </div>
      <p role="status" className="mt-1 min-h-6 text-muted">
        {message}
      </p>
    </div>
  );
}
