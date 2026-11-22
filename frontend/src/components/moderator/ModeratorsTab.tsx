import { KeyRound, Plus, UserCog, UserX, UserCheck } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Tag } from "@/components/ui/Tag";
import { createModerator, listModerators, resetModeratorPassword, updateModerator } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { formatShortDateTime } from "@/lib/format";
import type { Moderator } from "@/lib/types";
import { guarded, useAdminData, type AdminAccess } from "./useAdminData";

const FIELD_CLASS =
  "mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";
const PASSWORD_FIELD_CLASS =
  "block min-h-11 w-full rounded-lg border border-line-strong bg-surface py-2 pr-12 pl-3";

export function ModeratorsTab({ access }: { access: AdminAccess }) {
  const { state, reload, mutate } = useAdminData(access, "moderators", (token, signal) =>
    listModerators(token, signal),
  );

  if (state.status === "loading") return <LoadingBlock label="Wczytuję konta…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  return (
    <ModeratorList
      access={access}
      moderators={state.data}
      onChanged={reload}
      onUpdated={(updated) =>
        mutate((moderators) =>
          moderators.map((current) => (current.id === updated.id ? updated : current)),
        )
      }
    />
  );
}

function ModeratorList({
  access,
  moderators,
  onChanged,
  onUpdated,
}: {
  access: AdminAccess;
  moderators: Moderator[];
  onChanged: () => void;
  onUpdated: (moderator: Moderator) => void;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const [generated, setGenerated] = useState<string | null>(null);

  async function create() {
    setBusy(true);
    setFeedback(null);
    setGenerated(null);
    try {
      const created = await guarded(
        access,
        createModerator(access.token, {
          email: email.trim(),
          display_name: displayName.trim(),
          role: "moderator",
          password: password.trim() || undefined,
        }),
      );
      setFeedback({ ok: true, text: `Utworzono konto ${created.moderator.email}.` });
      setGenerated(created.generated_password);
      setEmail("");
      setDisplayName("");
      setPassword("");
      onChanged();
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się utworzyć konta. ${describeError(error)}` });
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(moderator: Moderator) {
    setFeedback(null);
    try {
      const updated = await guarded(
        access,
        updateModerator(access.token, moderator.id, { is_active: !moderator.is_active }),
      );
      onUpdated(updated);
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zmienić konta. ${describeError(error)}` });
    }
  }

  async function resetPassword(moderator: Moderator) {
    setFeedback(null);
    setGenerated(null);
    try {
      const result = await guarded(access, resetModeratorPassword(access.token, moderator.id));
      setFeedback({
        ok: true,
        text: `Zresetowano hasło ${result.moderator.email}. Wszystkie sesje tej osoby zostały wylogowane.`,
      });
      setGenerated(result.generated_password);
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zresetować hasła. ${describeError(error)}` });
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Plus aria-hidden="true" className="size-5" />
          Nowe konto moderatora
        </h2>
        <p className="text-muted">
          Konta tworzone tutaj mają zawsze uprawnienia moderatora. Puste pole hasła oznacza, że
          serwer wygeneruje hasło startowe i pokaże je jednorazowo.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="block font-medium">
            E-mail
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={FIELD_CLASS}
            />
          </label>
          <label className="block font-medium">
            Nazwa wyświetlana
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className={FIELD_CLASS}
            />
          </label>
          <div className="block font-medium">
            <label htmlFor="haslo-nowego-konta">Hasło (opcjonalne)</label>
            <PasswordInput
              id="haslo-nowego-konta"
              containerClassName="mt-1"
              className={PASSWORD_FIELD_CLASS}
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="min. 10 znaków, 3 grupy znaków"
            />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="primary"
            onClick={() => void create()}
            disabled={busy || !email.trim()}
          >
            <UserCog aria-hidden="true" className="size-5" />
            {busy ? "Tworzę…" : "Utwórz konto"}
          </Button>
          <p
            role="status"
            className={feedback?.ok === false ? "font-medium text-bad-fg" : "text-muted"}
          >
            {feedback?.text}
          </p>
        </div>
        {generated ? (
          <p className="mt-3 rounded-lg border border-warn-line bg-warn-bg px-3 py-2">
            <span className="font-semibold">Hasło startowe: </span>
            <code className="font-mono">{generated}</code>
            <span className="block text-sm">
              Zapisz je teraz. Po zamknięciu komunikatu nie będzie można go ponownie zobaczyć.
            </span>
          </p>
        ) : null}
      </section>

      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold">Konta ({moderators.length})</h2>
        <ul className="mt-3 divide-y divide-line">
          {moderators.map((moderator) => {
            const self = access.moderatorId === moderator.id;
            return (
              <li key={moderator.id} className="py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      {moderator.display_name || moderator.email}
                      <Tag tone={moderator.is_active ? "ok" : "bad"}>
                        {moderator.is_active ? "aktywne" : "wyłączone"}
                      </Tag>
                      {self ? <span className="text-sm text-muted">(to Ty)</span> : null}
                    </p>
                    <p className="text-sm text-muted">{moderator.email}</p>
                    <p className="text-sm text-muted">
                      Ostatnie logowanie:{" "}
                      {formatShortDateTime(moderator.last_login_at) ?? "brak"}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      onClick={() => void toggleActive(moderator)}
                      disabled={self}
                    >
                      {moderator.is_active ? (
                        <UserX aria-hidden="true" className="size-5" />
                      ) : (
                        <UserCheck aria-hidden="true" className="size-5" />
                      )}
                      {moderator.is_active ? "Wyłącz" : "Włącz"}
                    </Button>
                    <Button type="button" onClick={() => void resetPassword(moderator)}>
                      <KeyRound aria-hidden="true" className="size-5" />
                      Reset hasła
                    </Button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
