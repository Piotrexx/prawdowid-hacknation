import Link from "next/link";
import { Copy, Check, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { cx } from "@/lib/cx";

const HOME_LINK_CLASS =
  "inline-flex min-h-11 items-center rounded-lg bg-accent px-4 font-medium text-on-accent hover:bg-accent-hover";

interface PermalinkProps {
  id: string;
}

export function Permalink({ id }: PermalinkProps) {
  const [copied, setCopied] = useState(false);
  const url = typeof window !== "undefined" ? `${window.location.origin}/sprawdzenie/${id}` : "";

  async function handleCopy() {
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
      <p className="font-semibold">Chcesz zapisać lub podzielić się tym wynikiem?</p>
      <div className="flex flex-wrap gap-3">
        <Link href={`/sprawdzenie/${id}`} className={HOME_LINK_CLASS}>
          <ExternalLink className="size-5 mr-2" />
          Otwórz stronę z wynikiem
        </Link>
        <Button variant="secondary" onClick={handleCopy} disabled={copied}>
          {copied ? (
            <>
              <Check className="size-5 mr-2" />
              Skopiowano!
            </>
          ) : (
            <>
              <Copy className="size-5 mr-2" />
              Skopiuj link
            </>
          )}
        </Button>
      </div>
    </div>
  );
}