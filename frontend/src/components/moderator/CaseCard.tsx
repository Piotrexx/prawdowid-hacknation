import { ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { updateCase } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { formatShortDateTime } from "@/lib/format";
import { CASE_STATUSES, CASE_STATUS_LABELS, channelLabel } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import type { CaseOut, CaseStatus } from "@/lib/types";
import { guarded, type AdminAccess } from "./useAdminData";

const NOTE_LIMIT = 2000;
const FIELD_CLASS =
  "mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";

interface CaseCardProps {
  item: CaseOut;
  access: AdminAccess;
  onUpdated: (updated: CaseOut) => void;
}

export function CaseCard({ item, access, onUpdated }: CaseCardProps) {
  const id = useId();
  const [status, setStatus] = useState<CaseStatus>(item.status);
  const [note, setNote] = useState(item.note);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  const changed = status !== item.status || note !== item.note;

  async function save() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await guarded(access, updateCase(access.token, item.id, { status, note }));
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
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold">Sprawa nr {item.id}</h3>
        <Tag>{CASE_STATUS_LABELS[item.status] ?? item.status}</Tag>
        {item.risk === "high" ? (
          <Tag tone="warn" icon={ShieldAlert}>
            Wysokie ryzyko
          </Tag>
        ) : null}
      </div>

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
          <p className="text-muted">Powiązane sprawdzenia:</p>
          <ul className="flex flex-wrap gap-x-4">
            {item.check_ids.map((checkId, index) => (
              <li key={checkId}>
                <Link href={checkPath(checkId)} className="link inline-flex min-h-11 items-center">
                  Sprawdzenie {index + 1}
                  <span className="sr-only"> w sprawie nr {item.id}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <form
        className="mt-3 grid gap-3 border-t border-line pt-3 sm:grid-cols-[12rem_1fr]"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor={`${id}-status`} className="block font-medium">
          Stan sprawy
          <select
            id={`${id}-status`}
            value={status}
            onChange={(event) => setStatus(event.target.value as CaseStatus)}
            className={FIELD_CLASS}
          >
            {CASE_STATUSES.map((value) => (
              <option key={value} value={value}>
                {CASE_STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
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
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <Button type="submit" variant="primary" disabled={saving || !changed}>
            {saving ? "Zapisuję…" : "Zapisz zmiany"}
          </Button>
          <p role="status" className={feedback?.ok === false ? "font-medium text-bad-fg" : undefined}>
            {feedback?.text}
          </p>
        </div>
      </form>
    </li>
  );
}
