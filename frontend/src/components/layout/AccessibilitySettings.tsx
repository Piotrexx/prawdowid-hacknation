"use client";

import { Accessibility, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import {
  DEFAULT_SETTINGS,
  readSettings,
  saveSettings,
  type A11ySettings,
  type TextSize,
} from "@/lib/a11ySettings";
import { cx } from "@/lib/cx";

const TEXT_SIZE_OPTIONS: Array<{ value: TextSize; label: string; sample: string }> = [
  { value: "normal", label: "Standardowy", sample: "text-base" },
  { value: "large", label: "Większy", sample: "text-lg" },
  { value: "larger", label: "Największy", sample: "text-xl" },
];

interface AccessibilitySettingsProps {
  /** Where the panel opens relative to the button. */
  placement?: "below" | "above";
}

export function AccessibilitySettings({ placement = "below" }: AccessibilitySettingsProps) {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<A11ySettings>(DEFAULT_SETTINGS);
  const panelId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    }
    function onPointer(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  function update(next: Partial<A11ySettings>) {
    const merged = { ...settings, ...next };
    setSettings(merged);
    saveSettings(merged);
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          // The pre-paint script already applied the saved settings; this syncs the controls.
          if (!open) setSettings(readSettings());
          setOpen(!open);
        }}
        className="inline-flex min-h-12 w-full items-center gap-2.5 rounded-[4px_4px_4px_4px] bg-accent px-4 collapsed:justify-center collapsed:px-0 text-[0.9375rem] font-semibold text-on-accent hover:bg-accent-hover"
      >
        <Accessibility aria-hidden="true" className="size-5 shrink-0" />
        <span className="collapsed:sr-only">Ustawienia dostępności</span>
      </button>

      {open ? (
        <div
          id={panelId}
          role="group"
          aria-label="Ustawienia dostępności"
          className={cx(
            "absolute z-40 w-[min(22rem,calc(100vw-2.5rem))] border border-line-mid bg-surface p-5 shadow-card",
            placement === "above" ? "bottom-full left-0 mb-2" : "right-0 mt-2",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="eyebrow">Ustawienia dostępności</p>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                buttonRef.current?.focus();
              }}
              className="-mt-2 -mr-2 inline-grid size-11 place-items-center rounded text-muted hover:bg-subtle hover:text-ink"
            >
              <X aria-hidden="true" className="size-5" />
              <span className="sr-only">Zamknij ustawienia</span>
            </button>
          </div>

          <fieldset className="mt-2">
            <legend className="font-bold">Rozmiar tekstu</legend>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {TEXT_SIZE_OPTIONS.map((option) => {
                const checked = settings.textSize === option.value;
                return (
                  <label
                    key={option.value}
                    className={cx(
                      "flex min-h-16 cursor-pointer flex-col items-center justify-center gap-0.5 border px-2 text-center text-sm has-focus-visible:outline-3 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus",
                      checked
                        ? "border-accent bg-info-bg font-bold text-info-fg"
                        : "border-line-mid hover:border-accent",
                    )}
                  >
                    <input
                      type="radio"
                      name="rozmiar-tekstu"
                      value={option.value}
                      checked={checked}
                      onChange={() => update({ textSize: option.value })}
                      className="sr-only"
                    />
                    <span aria-hidden="true" className={cx("leading-none font-bold", option.sample)}>
                      A
                    </span>
                    {option.label}
                  </label>
                );
              })}
            </div>
          </fieldset>

          <label className="mt-5 flex min-h-11 cursor-pointer items-center gap-3 font-bold">
            <input
              type="checkbox"
              checked={settings.highContrast}
              onChange={(event) => update({ highContrast: event.target.checked })}
              className="size-5 accent-accent"
            />
            Wysoki kontrast
          </label>

          <p className="mt-3 text-sm text-muted">
            Ustawienia zapisujemy tylko w tej przeglądarce.
          </p>
        </div>
      ) : null}
    </div>
  );
}
