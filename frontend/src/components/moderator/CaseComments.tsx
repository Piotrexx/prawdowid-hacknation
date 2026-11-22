import { MessageSquare, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { addCaseComment, deleteComment, getCaseComments } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { formatShortDateTime } from "@/lib/format";
import type { Comment } from "@/lib/types";
import { guarded, useAdminData, type AdminAccess } from "./useAdminData";

const COMMENT_LIMIT = 4000;

export function CaseComments({
  caseId,
  access,
  onChanged,
}: {
  caseId: number;
  access: AdminAccess;
  onChanged?: (delta: number) => void;
}) {
  const { state, reload, mutate } = useAdminData(access, `case-comments:${caseId}`, (token, signal) =>
    getCaseComments(token, caseId, signal),
  );
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function submit() {
    const text = body.trim();
    if (!text) return;
    setSending(true);
    setFeedback(null);
    try {
      const created = await guarded(access, addCaseComment(access.token, caseId, text));
      mutate((comments) => [...comments, created]);
      setBody("");
      setFeedback("Dodano opinię.");
      onChanged?.(1);
    } catch (error) {
      setFeedback(`Nie udało się dodać opinii. ${describeError(error)}`);
    } finally {
      setSending(false);
    }
  }

  async function remove(comment: Comment) {
    setFeedback(null);
    try {
      await guarded(access, deleteComment(access.token, comment.id));
      mutate((comments) => comments.filter((current) => current.id !== comment.id));
      setFeedback("Usunięto opinię.");
      onChanged?.(-1);
    } catch (error) {
      setFeedback(`Nie udało się usunąć opinii. ${describeError(error)}`);
    }
  }

  const canDelete = (comment: Comment) =>
    access.isSuperuser || (access.moderatorId != null && comment.moderator_id === access.moderatorId);

  return (
    <section className="mt-4 border-t border-line pt-3">
      <h4 className="flex items-center gap-2 font-semibold">
        <MessageSquare aria-hidden="true" className="size-5" />
        Opinie moderatorów
        {state.status === "ready" ? (
          <span className="text-sm font-normal text-muted">({state.data.length})</span>
        ) : null}
      </h4>

      {state.status === "loading" ? <LoadingBlock label="Wczytuję opinie…" /> : null}
      {state.status === "error" ? <ErrorBlock error={state.error} onRetry={reload} /> : null}
      {state.status === "ready" ? (
        state.data.length === 0 ? (
          <p className="mt-2 text-muted">Nikt jeszcze nie dodał opinii do tej sprawy.</p>
        ) : (
          <ul className="mt-2 space-y-3">
            {state.data.map((comment) => (
              <li key={comment.id} className="rounded-lg border border-line bg-subtle p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">
                    {comment.author_name || comment.author_email}
                    <span className="ml-2 text-sm font-normal text-muted">
                      {comment.author_email}
                    </span>
                  </p>
                  <div className="flex items-center gap-2">
                    <time
                      dateTime={comment.created_at}
                      className="text-sm text-muted"
                    >
                      {formatShortDateTime(comment.created_at) ?? comment.created_at}
                    </time>
                    {canDelete(comment) ? (
                      <Button
                        variant="quiet"
                        onClick={() => void remove(comment)}
                        aria-label={`Usuń opinię ${comment.author_name || comment.author_email}`}
                        className="text-bad-fg"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                        Usuń
                      </Button>
                    ) : null}
                  </div>
                </div>
                <p className="mt-1 whitespace-pre-wrap">{comment.body}</p>
              </li>
            ))}
          </ul>
        )
      ) : null}

      <form
        className="mt-3 space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="block font-medium">
          Dodaj opinię do sprawy
          <textarea
            value={body}
            rows={3}
            maxLength={COMMENT_LIMIT}
            onChange={(event) => setBody(event.target.value)}
            placeholder="Co ustaliłeś(-aś)? Dołącz godzinę albo źródło, jeśli pomaga."
            className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-3 py-2"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" disabled={sending || !body.trim()}>
            <Send aria-hidden="true" className="size-5" />
            {sending ? "Dodaję…" : "Dodaj opinię"}
          </Button>
          <p role="status" className="text-muted">
            {feedback}
          </p>
        </div>
      </form>
    </section>
  );
}
