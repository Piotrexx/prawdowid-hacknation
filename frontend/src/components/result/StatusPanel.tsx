import { Compass, MessageCircleQuestion, TriangleAlert, Wrench, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
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
  completed: "Wynik analizy",
  needs_clarification: "Potrzebuję więcej szczegółów",
  out_of_scope: "To pytanie jest poza zakresem",
  error: "Błąd systemu – to nie jest wynik analizy",
};

interface StatusPanelProps {
  result: CheckResponse;
  actions?: ReactNode;
}

/** States that are not verdicts. Deliberately styled unlike a claim card.
 * A system error gets its own high-alert look (solid bad-toned border, "Błąd systemu"
 * eyebrow) so it can never be mistaken for a verdict such as "brak wystarczających
 * dowodów" – requirements treat technical failures, API limits and missing keys as
 * something that must never be presented as a substantive result. */
export function StatusPanel({ result, actions }: StatusPanelProps) {
  if (result.status === "completed") return null;
  const panel = PANELS[result.status] ?? PANELS.error;
  const Icon = panel.icon;
  const isError = result.status === "error";

  return (
    <div
      role={isError ? "alert" : undefined}
      className={
        isError
          ? "border-2 border-bad-line bg-bad-bg p-5"
          : "flex gap-4 border-2 border-dashed border-line-strong bg-surface p-5"
      }
    >
      {isError ? (
        <div className="flex items-center gap-2 pb-3">
          <TriangleAlert aria-hidden="true" className="size-5 shrink-0 text-bad-fg" />
          <p className="eyebrow text-bad-fg">Błąd systemu</p>
        </div>
      ) : null}
      <div className={isError ? "flex gap-4" : "contents"}>
        <Icon
          aria-hidden="true"
          className={cx("mt-1 size-7 shrink-0", isError ? "text-bad-fg" : "text-muted")}
        />
        <div className="min-w-0 space-y-3">
          <p className="text-lg leading-relaxed whitespace-pre-line">
            {result.status_message || panel.fallback}
          </p>
          {isError ? (
            <p className="font-semibold text-bad-fg">
              To nie jest wynik analizy: żadna teza nie została oceniona.
            </p>
          ) : null}
          {result.status === "out_of_scope" ? (
            <p className="text-muted">
              To nie jest ocena prawdziwości. Odpowiadam tylko na podstawie opisanego
              zbioru źródeł.
            </p>
          ) : null}
          {actions}
          {isError && result.error_code ? (
            <p className="text-sm text-muted">Kod błędu: {result.error_code}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
