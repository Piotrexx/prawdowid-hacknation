import { Search, Link as LinkIcon } from "lucide-react";
import { useState, type RefObject } from "react";
import { Button } from "@/components/ui/Button";
import { cx } from "@/lib/cx";
import { formatInteger, plural } from "@/lib/format";

const URL_LIMIT = 2000;

export function isValidUrl(text: string): boolean {
  try {
    const url = new URL(text.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

interface CheckFormProps {
  url: string;
  onUrlChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  waitSeconds: number;
  inputRef: RefObject<HTMLInputElement | null>;
}

export function CheckForm({
  url,
  onUrlChange,
  onSubmit,
  busy,
  error,
  waitSeconds,
  inputRef,
}: CheckFormProps) {
  const overLimit = url.length > URL_LIMIT;
  const excess = url.length - URL_LIMIT;

  return (
    <form
      noValidate
      aria-busy={busy}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <fieldset disabled={busy} className="min-w-0 space-y-5">
        <div className="space-y-3 rounded-xl border bg-surface p-4 sm:p-5">
          <label htmlFor="pole-url" className="block text-xl font-semibold">
            Wklej link do artykułu, który chcesz sprawdzić
          </label>
          <p id="pole-url-pomoc" className="text-muted">
            System pobierze treść artykułu, wyekstrahuje słowa kluczowe (model Bielik),
            sprawdzi bazę fact-checków Google i oceni, czy to fake news (DeepSeek).
          </p>
          <div className="relative">
            <LinkIcon aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 size-5 text-muted" />
            <input
              id="pole-url"
              ref={inputRef}
              type="url"
              value={url}
              placeholder="https://example.org/artykul-do-sprawdzenia"
              aria-describedby={cx(
                "pole-url-pomoc",
                url.length >= URL_LIMIT - 200 && "pole-url-licznik",
                error && "pole-url-blad",
              )}
              aria-invalid={error || overLimit ? true : undefined}
              onChange={(event) => onUrlChange(event.target.value)}
              className="block w-full rounded-lg border border-line-strong bg-surface pl-10 pr-3 py-3 text-lg leading-relaxed placeholder:text-muted"
            />
          </div>

          {url.length >= URL_LIMIT - 200 ? (
            <p id="pole-url-licznik" className={overLimit ? "font-medium text-bad-fg" : "text-muted"}>
              {overLimit
                ? `Za dużo o ${formatInteger(excess)} ${plural(excess, "znak", "znaki", "znaków")}.`
                : `Wpisano ${formatInteger(url.length)} z ${formatInteger(URL_LIMIT)} znaków.`}
            </p>
          ) : null}
          {overLimit ? (
            <p role="alert" className="font-medium text-bad-fg">
              Link jest za długi. Skróć go do {formatInteger(URL_LIMIT)} znaków.
            </p>
          ) : null}
          {error ? (
            <p id="pole-url-blad" role="alert" className="font-medium text-bad-fg">
              {error}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            type="submit"
            variant="primary"
            large
            disabled={waitSeconds > 0 || !url.trim() || overLimit}
            className="w-full sm:w-auto sm:min-w-48"
          >
            <Search aria-hidden="true" className="size-6" />
            Sprawdź
          </Button>
          {waitSeconds > 0 ? (
            <p className="text-muted">
              Możesz spróbować ponownie za {waitSeconds}{" "}
              {plural(waitSeconds, "sekundę", "sekundy", "sekund")}.
            </p>
          ) : null}
        </div>
      </fieldset>
    </form>
  );
}