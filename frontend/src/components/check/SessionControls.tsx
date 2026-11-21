import { Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { deleteSession } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { plural } from "@/lib/format";
import { clearSessionId, peekSessionId } from "@/lib/session";

type Step = "idle" | "confirm" | "deleting";

export function SessionControls({ onDeleted }: { onDeleted: () => void }) {
  const [step, setStep] = useState<Step>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  function close() {
    setStep("idle");
    triggerRef.current?.focus();
  }

  async function remove() {
    const sessionId = peekSessionId();
    if (!sessionId) {
      setMessage("W tej sesji nie ma zapisanych danych. Nie ma czego usuwać.");
      close();
      return;
    }
    setStep("deleting");
    try {
      const { deleted } = await deleteSession(sessionId);
      clearSessionId();
      onDeleted();
      setMessage(
        deleted > 0
          ? `Usunięto ${deleted} ${plural(deleted, "zapis", "zapisy", "zapisów")} z tej sesji.`
          : "W tej sesji nie było zapisanych danych.",
      );
    } catch (error) {
      setMessage(`Nie udało się usunąć danych. ${describeError(error)}`);
    } finally {
      close();
    }
  }

  return (
    <section aria-labelledby="twoje-dane" className="border-t border-line pt-6">
      <h2 id="twoje-dane" className="text-xl font-semibold">
        Twoje dane
      </h2>
      <p className="mt-1 text-muted">
        Sprawdzenia są zapisywane pod losowym numerem sesji. Ten numer jest
        przechowywany tylko w tej przeglądarce. Możesz usunąć swoje sprawdzenia w
        każdej chwili.
      </p>

      <Button
        ref={triggerRef}
        className="mt-3"
        aria-expanded={step !== "idle"}
        onClick={() => {
          setMessage(null);
          setStep((current) => (current === "idle" ? "confirm" : "idle"));
        }}
      >
        <Trash2 aria-hidden="true" className="size-5" />
        Usuń moje dane z tej sesji
      </Button>

      {step !== "idle" ? (
        <div className="mt-3 rounded-lg border border-line-strong bg-surface p-4">
          <p className="font-medium">
            Usunąć wszystkie sprawdzenia z tej sesji? Linki do nich przestaną działać.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="danger" onClick={remove} disabled={step === "deleting"}>
              {step === "deleting" ? "Usuwam…" : "Tak, usuń"}
            </Button>
            <Button onClick={close} disabled={step === "deleting"}>
              Anuluj
            </Button>
          </div>
        </div>
      ) : null}

      <p role="status" className="mt-2 min-h-6">
        {message}
      </p>
    </section>
  );
}
