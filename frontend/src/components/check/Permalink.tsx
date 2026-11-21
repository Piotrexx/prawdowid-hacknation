import { Check, Copy } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { checkPath } from "@/lib/links";

export function Permalink({ id }: { id: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "copied" | "selected">("idle");
  const path = checkPath(id);
  const url = typeof window === "undefined" ? path : `${window.location.origin}${path}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setStatus("copied");
    } catch {
      // Clipboard access can be blocked; selecting the text lets the user copy it by hand.
      inputRef.current?.focus();
      inputRef.current?.select();
      setStatus("selected");
    }
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <label htmlFor="link-do-wyniku" className="block font-semibold">
        Link do tego wyniku
      </label>
      <p className="text-muted">Możesz go zapisać albo wysłać innej osobie.</p>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <input
          id="link-do-wyniku"
          ref={inputRef}
          type="text"
          readOnly
          value={url}
          onFocus={(event) => event.target.select()}
          className="min-h-11 min-w-0 flex-1 rounded-lg border border-line-strong bg-subtle px-3"
        />
        <Button onClick={copy}>
          {status === "copied" ? (
            <Check aria-hidden="true" className="size-5" />
          ) : (
            <Copy aria-hidden="true" className="size-5" />
          )}
          Kopiuj link
        </Button>
      </div>
      <p role="status" className="mt-2 min-h-6 text-muted">
        {status === "copied" ? "Link skopiowany." : null}
        {status === "selected"
          ? "Link jest zaznaczony. Skopiuj go skrótem Ctrl+C albo z menu."
          : null}
      </p>
    </div>
  );
}
