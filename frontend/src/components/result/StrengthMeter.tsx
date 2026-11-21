"use client";

import { Equal, Minus, Plus, type LucideIcon } from "lucide-react";
import { useId, useState } from "react";
import { cx } from "@/lib/cx";
import { STRENGTH_LABELS } from "@/lib/labels";
import type { Strength, StrengthEffect, StrengthLevel } from "@/lib/types";

const STEPS: Record<StrengthLevel, number> = {
  brak: 0,
  slaba: 1,
  umiarkowana: 2,
  mocna: 3,
};

const EFFECTS: Record<StrengthEffect, { icon: LucideIcon; label: string }> = {
  plus: { icon: Plus, label: "wzmacnia" },
  minus: { icon: Minus, label: "osłabia" },
  neutral: { icon: Equal, label: "bez wpływu" },
};

export function StrengthMeter({ strength, id }: { strength: Strength; id?: string }) {
  const [open, setOpen] = useState(false);
  const factorsId = useId();
  const filled = STEPS[strength.level] ?? 0;
  const label = STRENGTH_LABELS[strength.level] ?? strength.level;
  const hasFactors = strength.factors.length > 0;

  return (
    <section id={id} className="scroll-mt-6 border border-line bg-surface px-5 py-4.5">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <p className="font-bold">Siła podstawy: {label}</p>
        <span aria-hidden="true" className="flex gap-1.5">
          {[1, 2, 3].map((step) => (
            <span
              key={step}
              className={cx(
                "h-2.5 w-10 rounded-full",
                step <= filled ? "bg-accent" : "border border-line-strong bg-transparent",
              )}
            />
          ))}
        </span>
        {hasFactors ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={factorsId}
            onClick={() => setOpen((value) => !value)}
            className="link ml-auto inline-flex min-h-11 items-center text-sm font-semibold"
          >
            {open ? "Ukryj uzasadnienie" : "Skąd ta ocena?"}
          </button>
        ) : null}
      </div>
      <p className="mt-1 text-sm text-muted">
        Pokazuje, jak solidne są materiały, na których opiera się ocena.
      </p>

      {hasFactors ? (
        <ul id={factorsId} hidden={!open} className="mt-3 space-y-2 border-t border-line pt-3">
          {strength.factors.map((factor) => {
            const effect = EFFECTS[factor.effect] ?? EFFECTS.neutral;
            const Icon = effect.icon;
            return (
              <li key={factor.code} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border border-line-strong"
                >
                  <Icon className="size-4" />
                </span>
                <span>
                  <span className="font-semibold">{factor.label}:</span> {factor.value}{" "}
                  <span className="text-muted">({effect.label})</span>
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
