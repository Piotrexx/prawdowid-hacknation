import { Compass, MessageCircleQuestion, Wrench, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { CheckResponse, CheckStatus } from "@/lib/types";

type NonVerdictStatus = Exclude<CheckStatus, "completed">;

const PANELS: Record<NonVerdictStatus, { icon: LucideIcon; fallback: string }> = {
  needs_clarification: {
    icon: MessageCircleQuestion,
    fallback: "Nie wiem jeszcze, co dokładnie mam sprawdzić. Opisz to trochę szerzej.",
  },
  out_of_scope: {
    icon: Compass,
    fallback: "Na to pytanie nie potrafię odpowiedzieć na podstawie moich źródeł.",
  },
  error: {
    icon: Wrench,
    fallback: "Coś poszło nie tak po stronie systemu. Spróbuj ponownie za chwilę.",
  },
};

export const STATUS_TITLES: Record<CheckStatus, string> = {
  completed: "Wynik sprawdzenia",
  needs_clarification: "Potrzebuję więcej szczegółów",
  out_of_scope: "To pytanie jest poza zakresem",
  error: "Nie udało się wykonać sprawdzenia",
};

interface StatusPanelProps {
  result: CheckResponse;
  actions?: ReactNode;
}

/** States that are not verdicts. Deliberately styled unlike a claim card. */
export function StatusPanel({ result, actions }: StatusPanelProps) {
  if (result.status === "completed") return null;
  const panel = PANELS[result.status] ?? PANELS.error;
  const Icon = panel.icon;

  return (
    <div className="flex gap-4 rounded-xl border-2 border-dashed border-line-strong bg-surface p-5">
      <Icon aria-hidden="true" className="mt-1 size-7 shrink-0 text-muted" />
      <div className="min-w-0 space-y-3">
        <p className="text-lg leading-relaxed whitespace-pre-line">
          {result.status_message || panel.fallback}
        </p>
        {result.status === "error" ? (
          <p className="text-muted">Ta treść nie została oceniona.</p>
        ) : null}
        {result.status === "out_of_scope" ? (
          <p className="text-muted">
            To nie jest ocena prawdziwości. Odpowiadam tylko na podstawie opisanego
            zbioru źródeł.
          </p>
        ) : null}
        {actions}
        {result.status === "error" && result.error_code ? (
          <p className="text-sm text-muted">Kod błędu: {result.error_code}</p>
        ) : null}
      </div>
    </div>
  );
}
