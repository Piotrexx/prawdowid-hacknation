import { Bell, BellRing, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { StatTile } from "@/components/ui/StatTile";
import {
  changePassword,
  deletePushSubscription,
  getProfile,
  getPushPublicKey,
  savePushSubscription,
  updateProfile,
} from "@/lib/api";
import { describeError } from "@/lib/errors";
import { formatShortDateTime } from "@/lib/format";
import type { Profile } from "@/lib/types";
import { guarded, useAdminData, type AdminAccess } from "./useAdminData";

const FIELD_CLASS =
  "mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";
const PASSWORD_FIELD_CLASS =
  "block min-h-11 w-full rounded-lg border border-line-strong bg-surface py-2 pr-12 pl-3";
const ACTION_LABELS: Record<string, string> = {
  status_change: "Zmiana statusu",
  edit: "Edycja twierdzenia",
  comment: "Opinia",
  comment_deleted: "Usunięcie opinii",
  account: "Konto",
  llm_change: "Zmiana modelu",
  note: "Notatka",
};

export function AccountTab({ access }: { access: AdminAccess }) {
  const { state, reload, mutate } = useAdminData(access, "profile", (token, signal) =>
    getProfile(token, signal),
  );

  if (state.status === "loading") return <LoadingBlock label="Wczytuję konto…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  return (
    <AccountContent
      access={access}
      profile={state.data}
      onProfile={(profile) => mutate(() => profile)}
      reload={reload}
    />
  );
}

function AccountContent({
  access,
  profile,
  onProfile,
  reload,
}: {
  access: AdminAccess;
  profile: Profile;
  onProfile: (profile: Profile) => void;
  reload: () => void;
}) {
  const moderator = profile.moderator;
  const technical = moderator.id === 0;

  const [displayName, setDisplayName] = useState(moderator.display_name);
  const [notifyPush, setNotifyPush] = useState(moderator.notify_push);
  const [webhook, setWebhook] = useState(moderator.discord_webhook_url ?? "");
  const [threshold, setThreshold] = useState(moderator.comment_notify_threshold);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordFeedback, setPasswordFeedback] = useState<string | null>(null);

  const [pushBusy, setPushBusy] = useState(false);
  const [pushFeedback, setPushFeedback] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await guarded(
        access,
        updateProfile(access.token, {
          display_name: displayName,
          notify_discord: Boolean(webhook.trim()),
          notify_push: notifyPush,
          discord_webhook_url: webhook,
          comment_notify_threshold: threshold,
        }),
      );
      onProfile(updated);
      setFeedback({ ok: true, text: "Zapisano ustawienia konta." });
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zapisać. ${describeError(error)}` });
    } finally {
      setSaving(false);
    }
  }

  async function submitPassword() {
    if (newPassword !== repeatPassword) {
      setPasswordFeedback("Nowe hasła nie są takie same.");
      return;
    }
    setPasswordBusy(true);
    setPasswordFeedback(null);
    try {
      await guarded(
        access,
        changePassword(access.token, currentPassword, newPassword),
      );
      setPasswordFeedback("Hasło zmienione. Zaloguj się ponownie.");
      access.onUnauthorized();
    } catch (error) {
      setPasswordFeedback(`Nie udało się zmienić hasła. ${describeError(error)}`);
    } finally {
      setPasswordBusy(false);
    }
  }

  async function enablePush() {
    setPushBusy(true);
    setPushFeedback(null);
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        setPushFeedback("Ta przeglądarka nie obsługuje powiadomień push.");
        return;
      }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setPushFeedback("Brak zgody na powiadomienia w przeglądarce.");
        return;
      }
      const { public_key, configured } = await getPushPublicKey(access.token);
      if (!configured || !public_key) {
        setPushFeedback("Serwer nie ma jeszcze kluczy do powiadomień push.");
        return;
      }
      const registration = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;
      const subscription =
        (await registration.pushManager.getSubscription()) ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: base64UrlToBytes(public_key) as BufferSource,
        }));
      await savePushSubscription(access.token, subscription.toJSON());
      const updated = await guarded(access, updateProfile(access.token, { notify_push: true }));
      onProfile(updated);
      setNotifyPush(true);
      setPushFeedback("Powiadomienia push włączone w tej przeglądarce.");
    } catch (error) {
      setPushFeedback(`Nie udało się włączyć push. ${describeError(error)}`);
    } finally {
      setPushBusy(false);
    }
  }

  async function disablePush() {
    setPushBusy(true);
    setPushFeedback(null);
    try {
      const registration = await navigator.serviceWorker.getRegistration("/sw.js");
      const subscription = await registration?.pushManager.getSubscription();
      if (subscription) {
        await deletePushSubscription(access.token, subscription.endpoint);
        await subscription.unsubscribe();
      }
      const updated = await guarded(access, updateProfile(access.token, { notify_push: false }));
      onProfile(updated);
      setNotifyPush(false);
      setPushFeedback("Powiadomienia push wyłączone.");
    } catch (error) {
      setPushFeedback(`Nie udało się wyłączyć push. ${describeError(error)}`);
    } finally {
      setPushBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold">Konto</h2>
        <dl className="mt-3 grid gap-x-6 gap-y-1 sm:grid-cols-2">
          {[
            ["E-mail", moderator.email],
            ["Nazwa", moderator.display_name || "brak"],
            ["Utworzono", formatShortDateTime(moderator.created_at) ?? "brak daty"],
            ["Ostatnie logowanie", formatShortDateTime(moderator.last_login_at) ?? "brak"],
            ["Utworzone przez", moderator.created_by ?? "system"],
            ["Wymagana zmiana hasła", moderator.must_change_password ? "tak" : "nie"],
          ].map(([label, value]) => (
            <div key={label} className="flex gap-2">
              <dt className="text-muted">{label}:</dt>
              <dd className="font-medium">{value}</dd>
            </div>
          ))}
        </dl>
        {technical ? (
          <p className="mt-3 rounded-lg border border-line bg-subtle px-3 py-2 text-muted">
            To jest token techniczny. Załóż konto moderatora, aby korzystać z powiadomień,
            opinii i historii zmian.
          </p>
        ) : null}
      </section>

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Opinie" value={String(profile.stats.comments)} />
        <StatTile label="Zmiany statusu" value={String(profile.stats.status_changes)} />
        <StatTile label="Edycje twierdzeń" value={String(profile.stats.edits)} />
        <StatTile label="Twierdzenia w historii" value={String(profile.stats.cases_touched)} />
      </dl>

      {!technical ? (
        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="text-lg font-semibold">Powiadomienia</h2>
          <p className="mt-1 text-muted">
            Powiadomienia wysyłamy, gdy twierdzenie albo artykuł osiągnie wskazaną liczbę opinii.
          </p>
          <div className="mt-4 space-y-4">
            <label className="block font-medium">
              Adres webhooka Discorda
              <PasswordInput
                value={webhook}
                onChange={(event) => setWebhook(event.target.value)}
                placeholder="https://discord.com/api/webhooks/…"
                containerClassName="mt-1"
                className={PASSWORD_FIELD_CLASS}
              />
              <span className="mt-1 block text-sm font-normal text-muted">
                Powiadomienia na Discorda wysyłamy, gdy adres jest wpisany.
              </span>
            </label>

            <div className="rounded-lg border border-line bg-subtle p-3">
              <p className="flex items-center gap-2 font-semibold">
                <BellRing aria-hidden="true" className="size-5" />
                Powiadomienia w przeglądarce (Web Push)
              </p>
              <p className="mt-1 text-sm text-muted">
                {profile.push_available
                  ? "Działają, dopóki ta przeglądarka ma zapisaną subskrypcję."
                  : "Serwer nie ma jeszcze kluczy VAPID."}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  onClick={() => void enablePush()}
                  disabled={pushBusy || !profile.push_available}
                >
                  <Bell aria-hidden="true" className="size-5" />
                  {notifyPush ? "Odśwież subskrypcję" : "Włącz w tej przeglądarce"}
                </Button>
                {notifyPush ? (
                  <Button
                    type="button"
                    variant="danger"
                    onClick={() => void disablePush()}
                    disabled={pushBusy}
                  >
                    <Trash2 aria-hidden="true" className="size-5" />
                    Wyłącz
                  </Button>
                ) : null}
              </div>
              <p role="status" className="mt-1 text-sm">
                {pushFeedback}
              </p>
            </div>

            <label className="block max-w-xs font-medium">
              Próg powiadomienia (liczba opinii)
              <input
                type="number"
                min={1}
                max={20}
                value={threshold}
                onChange={(event) => setThreshold(Number(event.target.value))}
                className={FIELD_CLASS}
              />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button type="button" variant="primary" onClick={() => void save()} disabled={saving}>
              <Save aria-hidden="true" className="size-5" />
              {saving ? "Zapisuję…" : "Zapisz ustawienia"}
            </Button>
            <p
              role="status"
              className={feedback?.ok === false ? "font-medium text-bad-fg" : "text-muted"}
            >
              {feedback?.text}
            </p>
          </div>
        </section>
      ) : null}

      {!technical ? (
        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="text-lg font-semibold">Nazwa i hasło</h2>
          <label className="mt-3 block max-w-md font-medium">
            Nazwa wyświetlana
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className={FIELD_CLASS}
            />
          </label>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Button type="button" onClick={() => void save()} disabled={saving}>
              <Save aria-hidden="true" className="size-5" />
              {saving ? "Zapisuję…" : "Zapisz nazwę"}
            </Button>
            <p
              role="status"
              className={feedback?.ok === false ? "font-medium text-bad-fg" : "text-muted"}
            >
              {feedback?.text}
            </p>
          </div>
          <div className="mt-4 grid max-w-2xl gap-3 sm:grid-cols-3">
            <div className="block font-medium">
              <label htmlFor="haslo-obecne">Obecne hasło</label>
              <PasswordInput
                id="haslo-obecne"
                containerClassName="mt-1"
                className={PASSWORD_FIELD_CLASS}
                autoComplete="current-password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </div>
            <div className="block font-medium">
              <label htmlFor="haslo-nowe">Nowe hasło</label>
              <PasswordInput
                id="haslo-nowe"
                containerClassName="mt-1"
                className={PASSWORD_FIELD_CLASS}
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
            </div>
            <div className="block font-medium">
              <label htmlFor="haslo-powtorz">Powtórz nowe hasło</label>
              <PasswordInput
                id="haslo-powtorz"
                containerClassName="mt-1"
                className={PASSWORD_FIELD_CLASS}
                autoComplete="new-password"
                value={repeatPassword}
                onChange={(event) => setRepeatPassword(event.target.value)}
              />
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button
              type="button"
              onClick={() => void submitPassword()}
              disabled={passwordBusy || !currentPassword || !newPassword}
            >
              Zmień hasło
            </Button>
            <p role="status" className="text-red-500">
              {passwordFeedback}
            </p>
          </div>
        </section>
      ) : null}

      {/* Opinie moderatorów są na razie wyłączone (front i backend).
      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <MessageSquare aria-hidden="true" className="size-5" />
          Moje opinie
        </h2>
        {profile.comments.length === 0 ? (
          <p className="mt-2 text-muted">Nie dodałeś(-aś) jeszcze żadnej opinii.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {profile.comments.map((comment) => (
              <li key={comment.id} className="rounded-lg border border-line bg-subtle p-3">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="font-semibold">
                    {comment.case_id != null
                      ? `Twierdzenie nr ${comment.case_id}`
                      : comment.article_title ?? `Artykuł nr ${comment.article_id}`}
                  </span>
                  <time dateTime={comment.created_at} className="text-muted">
                    {formatShortDateTime(comment.created_at) ?? comment.created_at}
                  </time>
                </div>
                {comment.case_claim_preview ? (
                  <p className="mt-1 text-sm text-muted">{comment.case_claim_preview}</p>
                ) : null}
                <p className="mt-1 whitespace-pre-wrap">{comment.body}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
      */}

      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold">Historia zmian twierdzeń</h2>
        <p className="text-muted">
          Tutaj widzisz twierdzenia, którym zmieniłeś(-aś) status albo treść.
        </p>
        {profile.actions.length === 0 ? (
          <p className="mt-2 text-muted">Brak zapisanych zmian.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {profile.actions.map((action) => (
              <li key={action.id} className="py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold">
                    {ACTION_LABELS[action.action] ?? action.action}
                    {action.case_id != null ? ` · twierdzenie nr ${action.case_id}` : ""}
                  </span>
                  <time dateTime={action.created_at} className="text-sm text-muted">
                    {formatShortDateTime(action.created_at) ?? action.created_at}
                  </time>
                </div>
                {action.case_claim_preview ? (
                  <p className="text-sm text-muted">{action.case_claim_preview}</p>
                ) : null}
                {action.field ? (
                  <p className="text-sm">
                    <span className="text-muted">{action.field}:</span>{" "}
                    <span className="line-through">{action.value_before}</span>
                    {" → "}
                    <span className="font-medium">{action.value_after}</span>
                  </p>
                ) : action.detail ? (
                  <p className="text-sm text-muted">{action.detail}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-sm text-muted">
        <button type="button" className="link" onClick={reload}>
          Odśwież dane konta
        </button>
      </p>
    </div>
  );
}

function base64UrlToBytes(value: string): Uint8Array {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
  return bytes;
}
