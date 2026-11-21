import { KeyRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { getMetrics } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { isUnauthorized } from "./useAdminData";

interface TokenPromptProps {
  notice: string | null;
  /** True after a logout or a rejected token, when focus was lost with the closed panel. */
  takeFocus: boolean;
  onAccepted: (token: string) => void;
}

export function TokenPrompt({ notice, takeFocus, onAccepted }: TokenPromptProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (takeFocus) inputRef.current?.focus();
  }, [takeFocus]);

  async function submit() {
    const candidate = token.trim();
    if (!candidate) {
      setError("Wpisz token moderatora.");
      return;
    }
    setChecking(true);
    setError(null);
    try {
      await getMetrics(candidate);
      onAccepted(candidate);
    } catch (failure) {
      setError(
        isUnauthorized(failure)
          ? "Nieprawidłowy token. Sprawdź go i spróbuj ponownie."
          : describeError(failure),
      );
    } finally {
      setChecking(false);
    }
  }

  const message = error ?? notice;

  return (
    <form
      noValidate
      className="max-w-md space-y-4 rounded-xl border border-line bg-surface p-5"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div>
        <label htmlFor="token-moderatora" className="block text-lg font-semibold">
          Token moderatora{" "}
          <span aria-hidden="true" className="required-mark">
            *
          </span>
          <span className="sr-only"> (pole wymagane)</span>
        </label>
        <p id="token-pomoc" className="text-muted">
          Token jest pamiętany tylko do zamknięcia tej karty przeglądarki.
        </p>
        <input
          id="token-moderatora"
          ref={inputRef}
          type="password"
          autoComplete="off"
          aria-required="true"
          value={token}
          aria-describedby={message ? "token-pomoc token-blad" : "token-pomoc"}
          aria-invalid={error ? true : undefined}
          onChange={(event) => setToken(event.target.value)}
          className="mt-2 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3"
        />
      </div>
      {message ? (
        <p id="token-blad" role="alert" className="font-medium text-bad-fg">
          {message}
        </p>
      ) : null}
      <Button type="submit" variant="primary" disabled={checking}>
        <KeyRound aria-hidden="true" className="size-5" />
        {checking ? "Sprawdzam…" : "Otwórz panel"}
      </Button>
    </form>
  );
}
