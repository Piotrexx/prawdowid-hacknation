import { ChevronDown, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { updateCase } from "@/lib/api";
import { cx } from "@/lib/cx";
import { describeError } from "@/lib/errors";
import { formatShortDateTime } from "@/lib/format";
import { CASE_STATUSES, CASE_STATUS_LABELS, channelLabel } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import type { CaseOut, CaseStatus, Risk } from "@/lib/types";
import { guarded, type AdminAccess } from "./useAdminData";

const NOTE_LIMIT = 2000;
const CLAIM_LIMIT = 20000;
const FIELD_CLASS =
  "mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";

const STATUS_TAG_TONES: Record<CaseStatus, "ok" | "warn" | "info"> = {
  open: "ok",
  in_review: "warn",
  resolved: "info",
};

const STATUS_DOT_HEX: Record<CaseStatus, string> = {
  open: "#22c55e",
  in_review: "#f97316",
  resolved: "#0052a5",
};

interface CaseCardProps {
  item: CaseOut;
  access: AdminAccess;
  onUpdated: (updated: CaseOut) => void;
}

export function CaseCard({ item, access, onUpdated }: CaseCardProps) {
  const id = useId();
  const [status, setStatus] = useState<CaseStatus>(item.status);
  const [note, setNote] = useState(item.note);
  const [claimText, setClaimText] = useState(item.claim_text);
  const [risk, setRisk] = useState<Risk>(item.risk);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const [open, setOpen] = useState(true);

  const changed =
    status !== item.status ||
    note !== item.note ||
    claimText !== item.claim_text ||
    risk !== item.risk;

  async function save() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await guarded(
        access,
        updateCase(access.token, item.id, {
          status,
          note,
          claim_text: claimText,
          risk,
        }),
      );
      onUpdated(updated);
      setFeedback({ ok: true, text: "Zapisano zmiany." });
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zapisać. ${describeError(error)}` });
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-semibold">Twierdzenie nr {item.id}</h3>
          <Tag tone={STATUS_TAG_TONES[item.status] ?? "neutral"}>
            {CASE_STATUS_LABELS[item.status] ?? item.status}
          </Tag>
          {item.risk === "high" ? (
            <Tag tone="warn" icon={ShieldAlert}>
              Wysokie ryzyko
            </Tag>
          ) : null}
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`${id}-twierdzenie`}
          onClick={() => setOpen((current) => !current)}
          className="grid size-11 shrink-0 place-items-center rounded text-muted transition-colors hover:bg-subtle hover:text-ink"
        >
          <ChevronDown
            aria-hidden="true"
            className={cx("size-5 transition-transform", open && "rotate-180")}
          />
          <span className="sr-only">
            {open ? "Zwiń twierdzenie" : "Rozwiń twierdzenie"} nr {item.id}
          </span>
        </button>
      </div>

      <div id={`${id}-twierdzenie`} hidden={!open}>
        <p className="mt-2 text-lg">{item.claim_text}</p>

      <dl className="mt-3 grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {[
          ["Liczba zgłoszeń", String(item.occurrences)],
          ["Kanały", item.channels.map(channelLabel).join(", ") || "brak danych"],
          ["Utworzono", formatShortDateTime(item.created_at) ?? "brak daty"],
          ["Ostatnia zmiana", formatShortDateTime(item.updated_at) ?? "brak daty"],
          ["Powiadomienie", formatShortDateTime(item.notified_at) ?? "nie wysłano"],
        ].map(([label, value]) => (
          <div key={label} className="flex gap-2">
            <dt className="text-muted">{label}:</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>

      {item.check_ids.length > 0 ? (
        <div className="mt-3">
          <p className="text-muted">Powiązane analizy:</p>
          <ul className="flex flex-wrap gap-x-4">
            {item.check_ids.map((checkId, index) => (
              <li key={checkId}>
                <Link href={checkPath(checkId)} className="link inline-flex min-h-11 items-center">
                  Analiza {index + 1}
                  <span className="sr-only"> w twierdzeniu nr {item.id}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <form
        className="mt-3 space-y-3 border-t border-line pt-3"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor={`${id}-claim`} className="block font-medium">
          Treść twierdzenia
          <span className="ml-2 text-sm font-normal text-muted">
            każde pole możesz poprawić
          </span>
          <textarea
            id={`${id}-claim`}
            value={claimText}
            rows={3}
            maxLength={CLAIM_LIMIT}
            onChange={(event) => setClaimText(event.target.value)}
            className={`${FIELD_CLASS} py-2`}
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label htmlFor={`${id}-status`} className="block font-medium">
            Stan twierdzenia
            <div className="relative mt-1">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 left-3 size-2.5 -translate-y-1/2 rounded-full"
                style={{ backgroundColor: STATUS_DOT_HEX[status] }}
              />
              <select
                id={`${id}-status`}
                value={status}
                onChange={(event) => setStatus(event.target.value as CaseStatus)}
                className="block min-h-11 w-full rounded-lg border border-line-strong bg-surface py-0 pl-8 pr-3"
              >
                {CASE_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {CASE_STATUS_LABELS[value]}
                  </option>
                ))}
              </select>
            </div>
          </label>
          <label htmlFor={`${id}-risk`} className="block font-medium">
            Waga twierdzenia
            <select
              id={`${id}-risk`}
              value={risk}
              onChange={(event) => setRisk(event.target.value as Risk)}
              className="mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3"
            >
              <option value="standard">Standardowa</option>
              <option value="high">Wysokie ryzyko</option>
            </select>
          </label>
        </div>

        <label htmlFor={`${id}-note`} className="block font-medium">
          Notatka moderatora
          <textarea
            id={`${id}-note`}
            value={note}
            rows={2}
            maxLength={NOTE_LIMIT}
            onChange={(event) => setNote(event.target.value)}
            className={`${FIELD_CLASS} py-2`}
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" disabled={saving || !changed}>
            {saving ? "Zapisuję…" : "Zapisz zmiany"}
          </Button>
          <p role="status" className={feedback?.ok === false ? "font-medium text-bad-fg" : undefined}>
            {feedback?.text}
          </p>
        </div>
      </form>

      {/* Opinie moderatorów są na razie wyłączone (front i backend). */}
      </div>
    </li>
  );
}
