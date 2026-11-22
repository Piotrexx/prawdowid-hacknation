"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface BackButtonProps {
  label?: string;
}

/** Pokazuje się tylko wtedy, gdy przeglądarka ma dokąd wrócić. */
export function BackButton({ label = "Wróć" }: BackButtonProps) {
  const router = useRouter();
  const [canGoBack, setCanGoBack] = useState(false);

  useEffect(() => {
    // Historia jest dostępna dopiero po hydratacji.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- odczyt window.history
    setCanGoBack(window.history.length > 1);
  }, []);

  if (!canGoBack) return null;

  return (
    <button
      type="button"
      onClick={() => router.back()}
      className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-link hover:text-accent-hover"
    >
      <ArrowLeft aria-hidden="true" className="size-4" />
      {label}
    </button>
  );
}
