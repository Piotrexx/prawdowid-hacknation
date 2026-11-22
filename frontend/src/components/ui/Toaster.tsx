"use client";

import { AlertCircle, AlertTriangle, Info, X } from "lucide-react";
import { useEffect, useState } from "react";
import { cx } from "@/lib/cx";
import { _registerToastListener, type ToastVariant } from "@/lib/toast";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

let _next = 0;
const AUTO_DISMISS_MS = 5000;

const STYLES: Record<ToastVariant, { container: string; icon: string; Icon: typeof AlertCircle }> = {
  error: {
    container: "border-bad-line bg-bad-bg text-ink",
    icon: "text-bad-fg",
    Icon: AlertCircle,
  },
  warn: {
    container: "border-warn-line bg-warn-bg text-ink",
    icon: "text-warn-fg",
    Icon: AlertTriangle,
  },
  info: {
    container: "border-info-line bg-info-bg text-ink",
    icon: "text-info-fg",
    Icon: Info,
  },
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    return _registerToastListener(({ message, variant }) => {
      const id = ++_next;
      setItems((prev) => [...prev, { id, message, variant }]);
      setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), AUTO_DISMISS_MS);
    });
  }, []);

  if (items.length === 0) return null;

  return (
    <div
      aria-live="assertive"
      className="pointer-events-none fixed inset-0 z-50 flex flex-col items-end justify-start gap-2 p-4 sm:p-6"
    >
      {items.map((item) => {
        const { container, icon, Icon } = STYLES[item.variant];
        return (
          <div
            key={item.id}
            className={cx(
              "pointer-events-auto flex max-w-sm items-start gap-3 rounded-lg border px-4 py-3 shadow-card",
              container,
            )}
          >
            <Icon aria-hidden="true" className={cx("mt-0.5 size-5 shrink-0", icon)} />
            <p className="flex-1 text-sm font-medium leading-snug">{item.message}</p>
            <button
              type="button"
              onClick={() => setItems((prev) => prev.filter((t) => t.id !== item.id))}
              className="ml-1 grid size-6 shrink-0 place-items-center rounded text-muted hover:text-ink"
            >
              <X aria-hidden="true" className="size-4" />
              <span className="sr-only">Zamknij</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
