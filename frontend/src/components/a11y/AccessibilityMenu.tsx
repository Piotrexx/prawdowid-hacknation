"use client";

import { Accessibility, RotateCcw, X } from "lucide-react";
import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import {
  DEFAULT_DISPLAY,
  FONT_LABELS,
  FONT_SIZES,
  getDisplaySnapshot,
  getDisplayServerSnapshot,
  MOTION_LABELS,
  MOTIONS,
  setDisplay,
  subscribeDisplay,
  THEME_LABELS,
  THEMES,
  type Display,
} from "@/lib/theme";

interface ChoiceGroupProps<T extends string> {
  legend: string;
  name: string;
  options: readonly T[];
  labels: Record<T, string>;
  value: T;
  onChange: (value: T) => void;
}

function ChoiceGroup<T extends string>({
  legend,
  name,
  options,
  labels,
  value,
  onChange,
}: ChoiceGroupProps<T>) {
  return (
    <fieldset>
      <legend className="mb-1 font-semibold">{legend}</legend>
      <div className="flex flex-col">
        {options.map((option) => (
          <label
            key={option}
            className="flex min-h-11 cursor-pointer items-center gap-2 rounded-sm px-1 hover:bg-subtle"
          >
            <input
              type="radio"
              name={name}
              value={option}
              checked={value === option}
              onChange={() => onChange(option)}
              className="size-4 shrink-0 accent-[var(--accent)]"
            />
            {labels[option]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function AccessibilityMenu() {
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // localStorage is external state: the server renders defaults, the client the
  // stored settings, and React reconciles the two without a hydration mismatch.
  const display = useSyncExternalStore(
    subscribeDisplay,
    getDisplaySnapshot,
    getDisplayServerSnapshot,
  );

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    }

    function onPointerDown(event: PointerEvent) {
      if (wrapperRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  function update(patch: Partial<Display>) {
    setDisplay({ ...display, ...patch });
  }

  return (
    <div ref={wrapperRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-current px-3 font-semibold"
      >
        <Accessibility aria-hidden="true" className="size-5" />
        {/* The label collapses to the icon on narrow bars but stays in the a11y tree. */}
        <span className="hidden sm:inline">Dostępność</span>
        <span className="sr-only sm:hidden">Dostępność</span>
      </button>

      <div
        id={panelId}
        hidden={!open}
        className="absolute right-0 z-40 mt-1 w-72 max-w-[calc(100vw-2rem)] space-y-4 rounded-sm border border-line bg-surface p-4 text-ink shadow-lg"
      >
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-lg font-bold">Ustawienia wyświetlania</h2>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              buttonRef.current?.focus();
            }}
            className="inline-flex size-9 items-center justify-center rounded-sm border border-line"
          >
            <X aria-hidden="true" className="size-5" />
            <span className="sr-only">Zamknij ustawienia wyświetlania</span>
          </button>
        </div>

        <ChoiceGroup
          legend="Motyw"
          name="motyw"
          options={THEMES}
          labels={THEME_LABELS}
          value={display.theme}
          onChange={(theme) => update({ theme })}
        />
        <ChoiceGroup
          legend="Wielkość tekstu"
          name="tekst"
          options={FONT_SIZES}
          labels={FONT_LABELS}
          value={display.font}
          onChange={(font) => update({ font })}
        />
        <ChoiceGroup
          legend="Animacje"
          name="animacje"
          options={MOTIONS}
          labels={MOTION_LABELS}
          value={display.motion}
          onChange={(motion) => update({ motion })}
        />

        <button
          type="button"
          onClick={() => update(DEFAULT_DISPLAY)}
          className="inline-flex min-h-11 items-center gap-2 rounded-sm border-2 border-accent px-3 font-semibold text-accent hover:bg-subtle"
        >
          <RotateCcw aria-hidden="true" className="size-4" />
          Przywróć domyślne
        </button>

        <p className="text-sm text-muted">
          Ustawienia zapisują się w tej przeglądarce.
        </p>
      </div>
    </div>
  );
}
