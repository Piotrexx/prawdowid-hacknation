import { Minus, Plus, Equal, type LucideIcon } from "lucide-react";
import { Disclosure } from "@/components/ui/Disclosure";
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

export function StrengthMeter({ strength }: { strength: Strength }) {
  const filled = STEPS[strength.level] ?? 0;
  const label = STRENGTH_LABELS[strength.level] ?? strength.level;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="font-semibold">Siła podstawy: {label}</p>
        <span aria-hidden="true" className="flex gap-1">
          {[1, 2, 3].map((step) => (
            <span
              key={step}
              className={cx(
                "h-3 w-9 rounded-full border border-line-strong",
                step <= filled ? "bg-ink" : "bg-transparent",
              )}
            />
          ))}
        </span>
      </div>
      <p className="mt-1 text-muted">
        Pokazuje, jak solidne są materiały, na których opiera się ocena.
      </p>

      {strength.factors.length > 0 ? (
        <Disclosure summary="Skąd ta ocena siły?">
          <ul className="space-y-2">
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
                    <span className="font-medium">{factor.label}:</span> {factor.value}{" "}
                    <span className="text-muted">({effect.label})</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </Disclosure>
      ) : null}
    </div>
  );
}
