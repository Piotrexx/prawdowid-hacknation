import { KeyRound, LogIn } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { getProfile, loginModerator } from "@/lib/api";
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
  // "token" mode (token techniczny) temporarily hidden — only account login shown
  const [mode] = useState<"account" | "token">("account");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (takeFocus) inputRef.current?.focus();
  }, [takeFocus]);

  async function submit() {
    setChecking(true);
    setError(null);
    try {
      if (mode === "account") {
        const candidateEmail = email.trim();
        if (!candidateEmail || !password) {
          setError("Podaj e-mail i hasło.");
          return;
        }
        const session = await loginModerator(candidateEmail, password);
        onAccepted(session.token);
      } else {
        const candidate = token.trim();
        if (!candidate) {
          setError("Wpisz token moderatora.");
          return;
        }
        await getProfile(candidate);
        onAccepted(candidate);
      }
    } catch (failure) {
      if (mode === "account") {
        setError(
          isUnauthorized(failure)
            ? "Niepoprawny e-mail albo hasło."
            : describeError(failure),
        );
      } else {
        setError(
          isUnauthorized(failure)
            ? "Nieprawidłowy token. Sprawdź go i spróbuj ponownie."
            : describeError(failure),
        );
      }
    } finally {
      setChecking(false);
    }
  }

  const message = error ?? notice;
  const fieldClass =
    "mt-2 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";
  const passwordFieldClass =
    "block min-h-11 w-full rounded-lg border border-line-strong bg-surface py-2 pr-12 pl-3";

  return (
    <form
      noValidate
      className="max-w-md space-y-4 rounded-xl border border-line bg-surface p-5"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {/* Token techniczny tab temporarily hidden
      <div className="flex gap-2" role="tablist" aria-label="Sposób logowania">
        {(
          [
            ["account", "Konto moderatora"],
            ["token", "Token techniczny"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={mode === key}
            onClick={() => {
              setMode(key);
              setError(null);
            }}
            className={`min-h-11 rounded-lg border px-3 text-sm font-semibold ${
              mode === key
                ? "border-accent bg-surface text-ink"
                : "border-transparent text-muted hover:bg-subtle hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      */}

      {mode === "account" ? (
        <>
          <div>
            <label htmlFor="moderator-email" className="block text-lg font-semibold">
              E-mail{" "}
              <span aria-hidden="true" className="required-mark">
                *
              </span>
              <span className="sr-only"> (pole wymagane)</span>
            </label>
            <input
              id="moderator-email"
              ref={inputRef}
              type="email"
              autoComplete="username"
              aria-required="true"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={fieldClass}
            />
          </div>
          <div>
            <label htmlFor="moderator-password" className="block text-lg font-semibold">
              Hasło{" "}
              <span aria-hidden="true" className="required-mark">
                *
              </span>
              <span className="sr-only"> (pole wymagane)</span>
            </label>
            <PasswordInput
              id="moderator-password"
              containerClassName="mt-2"
              className={passwordFieldClass}
              autoComplete="current-password"
              aria-required="true"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
        </>
      ) : (
        <div>
          <label htmlFor="token-moderatora" className="block text-lg font-semibold">
            Token moderatora{" "}
            <span aria-hidden="true" className="required-mark">
              *
            </span>
            <span className="sr-only"> (pole wymagane)</span>
          </label>
          <p id="token-pomoc" className="text-muted">
            Token techniczny z konfiguracji `ADMIN_TOKEN`. Konto moderatora jest
            wygodniejsze, ale token nadal działa.
          </p>
          <PasswordInput
            id="token-moderatora"
            ref={inputRef}
            containerClassName="mt-2"
            className={passwordFieldClass}
            autoComplete="off"
            aria-required="true"
            aria-describedby={message ? "token-pomoc token-blad" : "token-pomoc"}
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
        </div>
      )}

      {message ? (
        <p id="token-blad" role="alert" className="font-medium text-bad-fg">
          {message}
        </p>
      ) : null}
      <Button type="submit" variant="primary" disabled={checking}>
        {mode === "account" ? (
          <LogIn aria-hidden="true" className="size-5" />
        ) : (
          <KeyRound aria-hidden="true" className="size-5" />
        )}
        {checking ? "Sprawdzam…" : mode === "account" ? "Zaloguj się" : "Otwórz panel"}
      </Button>
    </form>
  );
}
