import { CheckCircle2, Cpu, KeyRound, Save, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Tag } from "@/components/ui/Tag";
import { getLlmProviders, getLlmSettings, saveLlmSettings } from "@/lib/api";
import { describeError } from "@/lib/errors";
import type { LlmProvider, LlmSettings } from "@/lib/types";
import { guarded, useAdminData, type AdminAccess } from "./useAdminData";

const FIELD_CLASS =
  "mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";
const PASSWORD_FIELD_CLASS =
  "block min-h-11 w-full rounded-lg border border-line-strong bg-surface py-2 pr-12 pl-3";

interface Bundle {
  providers: LlmProvider[];
  settings: LlmSettings;
}

export function LlmTab({ access }: { access: AdminAccess }) {
  const { state, reload } = useAdminData(access, "llm", (token, signal) =>
    Promise.all([getLlmProviders(token, signal), getLlmSettings(token, signal)]).then(
      ([providers, settings]) => ({ providers, settings }) satisfies Bundle,
    ),
  );

  if (state.status === "loading") return <LoadingBlock label="Wczytuję ustawienia modelu…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  return <LlmForm access={access} providers={state.data.providers} initial={state.data.settings} />;
}

function LlmForm({
  access,
  providers,
  initial,
}: {
  access: AdminAccess;
  providers: LlmProvider[];
  initial: LlmSettings;
}) {
  const [settings, setSettings] = useState(initial);
  const [providerKey, setProviderKey] = useState(settings.provider);
  const [model, setModel] = useState(settings.model);
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [apiKey, setApiKey] = useState("");
  const [priceIn, setPriceIn] = useState(
    settings.price_input == null ? "" : String(settings.price_input),
  );
  const [priceOut, setPriceOut] = useState(
    settings.price_output == null ? "" : String(settings.price_output),
  );
  const [jsonMode, setJsonMode] = useState(settings.json_mode);
  const [clearKey, setClearKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  // Musi być po deklaracji providerKey – wcześniej odwołanie kończyło się błędem.
  const selected = providers.find((provider) => provider.key === providerKey);

  function chooseProvider(key: string) {
    const provider = providers.find((candidate) => candidate.key === key);
    setProviderKey(key);
    setClearKey(false);
    setApiKey("");
    if (!provider) return;
    const modelOption = provider.models[0];
    setModel(modelOption?.id ?? "");
    setBaseUrl(provider.base_url);
    setPriceIn(modelOption?.price_input == null ? "" : String(modelOption.price_input));
    setPriceOut(modelOption?.price_output == null ? "" : String(modelOption.price_output));
  }

  function chooseModel(modelId: string) {
    setModel(modelId);
    const option = selected?.models.find((candidate) => candidate.id === modelId);
    if (option) {
      setPriceIn(option.price_input == null ? "" : String(option.price_input));
      setPriceOut(option.price_output == null ? "" : String(option.price_output));
    }
  }

  async function save() {
    setSaving(true);
    setFeedback(null);
    try {
      const saved = await guarded(
        access,
        saveLlmSettings(access.token, {
          provider: providerKey,
          model: model.trim(),
          base_url: baseUrl.trim() || undefined,
          api_key: apiKey.trim() || undefined,
          price_input: priceIn === "" ? null : Number(priceIn),
          price_output: priceOut === "" ? null : Number(priceOut),
          json_mode: jsonMode,
          clear_api_key: clearKey,
        }),
      );
      setSettings(saved);
      setProviderKey(saved.provider);
      setModel(saved.model);
      setBaseUrl(saved.base_url);
      setApiKey("");
      setClearKey(false);
      setPriceIn(saved.price_input == null ? "" : String(saved.price_input));
      setPriceOut(saved.price_output == null ? "" : String(saved.price_output));
      setFeedback({
        ok: saved.configured,
        text: saved.configured
          ? "Model zapisany i aktywny od następnej analizy."
          : "Zapisano, ale model nie jest aktywny – sprawdź klucz API i adres.",
      });
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zapisać. ${describeError(error)}` });
    } finally {
      setSaving(false);
    }
  }

  const keyHint = settings.api_key_hint ?? "••••";
  const keyPlaceholder =
    settings.api_key_source === "panel"
      ? `Zapisany klucz ${keyHint}. Wpisz nowy, aby go zastąpić.`
      : settings.api_key_source === "env"
        ? `Aktywny klucz z .env ${keyHint}. Wpisz własny, aby go nadpisać.`
        : "Wklej klucz API";

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Model językowy</h2>
            <p className="text-muted">
              Wybór działa od razu, bez restartu usługi. Klucze nie są pokazywane w panelu.
            </p>
          </div>
          <Tag tone={settings.configured ? "ok" : "warn"} icon={settings.configured ? CheckCircle2 : TriangleAlert}>
            {settings.configured ? "Model aktywny" : "Model nieaktywny"}
          </Tag>
        </div>

        {!settings.configured ? (
          <p className="mt-3 rounded-lg border border-warn-line bg-warn-bg px-3 py-2 text-warn-fg">
            Brak wymaganego klucza albo adres jest nieosiągalny. Analizy będą kończyć się
            błędem technicznym, dopóki model nie będzie skonfigurowany.
          </p>
        ) : null}

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {providers.map((provider) => {
            const selectedProvider = provider.key === providerKey;
            return (
              <button
                key={provider.key}
                type="button"
                onClick={() => chooseProvider(provider.key)}
                aria-pressed={selectedProvider}
                className={`flex min-h-20 items-center gap-3 rounded-xl border p-3 text-left transition-colors ${
                  selectedProvider
                    ? "border-accent bg-info-bg"
                    : "border-line bg-surface hover:bg-subtle"
                }`}
              >
                {provider.icon ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`/provider-icons/${provider.icon}`}
                    alt=""
                    aria-hidden="true"
                    className="size-9 shrink-0 object-contain"
                  />
                ) : (
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-subtle">
                    <Cpu aria-hidden="true" className="size-6" />
                  </span>
                )}
                <span className="min-w-0">
                  <span className="block font-semibold">{provider.name}</span>
                  <span className="block text-sm text-muted">
                    {provider.is_local ? "lokalnie, bez opłat za tokeny" : "API w chmurze"}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        {selected ? (
          <div className="mt-4 rounded-lg border border-line bg-subtle p-3">
            <p className="font-medium">{selected.name}</p>
            {selected.note ? <p className="text-sm text-muted">{selected.note}</p> : null}
            {selected.models.length > 0 ? (
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="text-left text-muted">
                    <th className="font-medium">Model</th>
                    <th className="font-medium">Wejście / 1M</th>
                    <th className="font-medium">Wyjście / 1M</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.models.map((option) => (
                    <tr key={option.id}>
                      <td className="py-0.5 font-mono text-xs">{option.id}</td>
                      <td>{option.price_input == null ? "wg modelu" : `$${option.price_input.toFixed(2)}`}</td>
                      <td>{option.price_output == null ? "wg modelu" : `$${option.price_output.toFixed(2)}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold">Parametry połączenia</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="block font-medium">
            Model
            <input
              value={model}
              onChange={(event) => chooseModel(event.target.value)}
              list="llm-modele"
              className={`${FIELD_CLASS} font-mono`}
            />
            <datalist id="llm-modele">
              {selected?.models.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </datalist>
          </label>
          <label className="block font-medium">
            Adres API (base URL)
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              className={`${FIELD_CLASS} font-mono`}
            />
          </label>
          <label className="block font-medium sm:col-span-2">
            Klucz API
            <PasswordInput
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={keyPlaceholder}
              containerClassName="mt-1"
              className={PASSWORD_FIELD_CLASS}
            />
            <span className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
              <KeyRound aria-hidden="true" className="size-4" />
              {settings.api_key_source === "env"
                ? `Domyślnie używany jest klucz z .env (${keyHint}).`
                : settings.api_key_source === "panel"
                  ? `Zapisany klucz: ${keyHint}.`
                  : "Brak klucza w panelu i w .env."}
            </span>
          </label>
          <label className="flex items-center gap-2 font-medium">
            <input
              type="checkbox"
              checked={clearKey}
              onChange={(event) => setClearKey(event.target.checked)}
              className="size-5"
            />
            Usuń zapisany klucz i wróć do .env
          </label>
          <label className="block font-medium">
            Tryb JSON
            <select
              value={jsonMode}
              onChange={(event) => setJsonMode(event.target.value as "json_object" | "json_schema")}
              className={FIELD_CLASS}
            >
              <option value="json_object">json_object (szersza zgodność)</option>
              <option value="json_schema">json_schema (strict, jeśli dostawca wspiera)</option>
            </select>
          </label>
          <label className="block font-medium">
            Cena wejścia / 1M tokenów (USD)
            <input
              type="number"
              min={0}
              step="0.01"
              value={priceIn}
              onChange={(event) => setPriceIn(event.target.value)}
              className={FIELD_CLASS}
            />
          </label>
          <label className="block font-medium">
            Cena wyjścia / 1M tokenów (USD)
            <input
              type="number"
              min={0}
              step="0.01"
              value={priceOut}
              onChange={(event) => setPriceOut(event.target.value)}
              className={FIELD_CLASS}
            />
          </label>
        </div>

        <p className="mt-2 text-sm text-muted">
          Ceny są orientacyjne i służą do szacowania kosztu w statystykach. Puste pole oznacza
          cenę z katalogu dla wybranego modelu. Model lokalny rozliczamy jako 0.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="primary"
            onClick={() => void save()}
            disabled={saving || !model.trim()}
          >
            <Save aria-hidden="true" className="size-5" />
            {saving ? "Zapisuję…" : "Zapisz model"}
          </Button>
          <p
            role="status"
            className={feedback?.ok === false ? "font-medium text-bad-fg" : "text-muted"}
          >
            {feedback?.text}
          </p>
        </div>
      </section>
    </div>
  );
}
