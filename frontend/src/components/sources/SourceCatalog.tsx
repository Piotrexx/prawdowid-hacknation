"use client";

import { useMemo, useState } from "react";
import { cx } from "@/lib/cx";
import { plural } from "@/lib/format";
import {
  SOURCE_CATALOG,
  SOURCE_CATEGORY_LABELS,
  SOURCE_CATEGORY_ORDER,
  SOURCE_TIER_DESCRIPTIONS,
  SOURCE_TIER_LABELS,
  type SourceCategory,
  type SourceTier,
} from "@/lib/sourceCatalog";
import { SourceCard, TIER_STYLES } from "./SourceCard";

const TIERS: SourceTier[] = [1, 2, 3];

function sourceWord(count: number): string {
  return plural(count, "źródło", "źródła", "źródeł");
}

function FilterPill({
  active,
  count,
  children,
  onClick,
}: {
  active: boolean;
  count: number;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx(
        "inline-flex min-h-10 items-center gap-2 border-2 px-3.5 text-[0.75rem] font-extrabold tracking-[0.06em] uppercase transition-colors",
        active
          ? "border-accent bg-accent text-on-accent shadow-[3px_3px_0_0_var(--line-mid)]"
          : "border-line-mid bg-surface text-ink-soft hover:border-accent hover:text-accent",
      )}
    >
      {children}
      <span
        className={cx(
          "text-[0.6875rem] font-bold tabular-nums",
          active ? "text-on-accent" : "text-muted",
        )}
      >
        {count}
      </span>
    </button>
  );
}

export function SourceCatalog() {
  const [category, setCategory] = useState<SourceCategory | "all">("all");

  const categoryCounts = useMemo(() => {
    const counts = new Map<SourceCategory, number>();
    for (const source of SOURCE_CATALOG) {
      for (const item of source.categories) {
        counts.set(item, (counts.get(item) ?? 0) + 1);
      }
    }
    return counts;
  }, []);

  const tierCounts = useMemo(() => {
    const counts: Record<SourceTier, number> = { 1: 0, 2: 0, 3: 0 };
    for (const source of SOURCE_CATALOG) counts[source.tier] += 1;
    return counts;
  }, []);

  const visible =
    category === "all"
      ? SOURCE_CATALOG
      : SOURCE_CATALOG.filter((source) => source.categories.includes(category));

  return (
    <div className="space-y-12">
      <section aria-labelledby="poziomy-zrodel">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2
            id="poziomy-zrodel"
            className="text-2xl leading-none font-black tracking-[-0.01em] uppercase"
          >
            Poziomy źródeł
          </h2>
          <span className="border-2 border-line-mid bg-subtle px-3 py-1 text-[0.6875rem] font-extrabold tracking-[0.08em] uppercase text-ink-soft">
            {SOURCE_CATALOG.length} {sourceWord(SOURCE_CATALOG.length)} w katalogu
          </span>
        </div>

        <ul className="mt-4 grid gap-4 sm:grid-cols-3">
          {TIERS.map((tier) => (
            <li
              key={tier}
              className="relative overflow-hidden border-2 border-line-mid bg-surface p-5 pl-7 shadow-[4px_4px_0_0_var(--line-mid)]"
            >
              <span
                aria-hidden="true"
                className={cx("absolute inset-y-0 left-0 w-2", TIER_STYLES[tier].bar)}
              />
              <p className="text-[0.625rem] font-black tracking-[0.16em] text-muted uppercase">
                Poziom {tier}
              </p>
              <p className="mt-1 text-lg leading-tight font-black uppercase">
                {SOURCE_TIER_LABELS[tier]}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-ink-soft">
                {SOURCE_TIER_DESCRIPTIONS[tier]}
              </p>
              <p className="mt-3 text-[0.6875rem] font-extrabold tracking-[0.06em] text-accent uppercase">
                {tierCounts[tier]} {sourceWord(tierCounts[tier])}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="katalog-zrodel">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2
            id="katalog-zrodel"
            className="text-2xl leading-none font-black tracking-[-0.01em] uppercase"
          >
            Katalog źródeł
          </h2>
          <p
            role="status"
            className="text-[0.6875rem] font-extrabold tracking-[0.08em] text-muted uppercase"
          >
            Pokazuję {visible.length} z {SOURCE_CATALOG.length}{" "}
            {sourceWord(SOURCE_CATALOG.length)}
          </p>
        </div>

        <div
          role="group"
          aria-label="Filtruj źródła po kategorii"
          className="mt-4 flex flex-wrap gap-2"
        >
          <FilterPill
            active={category === "all"}
            count={SOURCE_CATALOG.length}
            onClick={() => setCategory("all")}
          >
            Wszystkie
          </FilterPill>
          {SOURCE_CATEGORY_ORDER.map((item) => (
            <FilterPill
              key={item}
              active={category === item}
              count={categoryCounts.get(item) ?? 0}
              onClick={() => setCategory(item)}
            >
              {SOURCE_CATEGORY_LABELS[item]}
            </FilterPill>
          ))}
        </div>

        {visible.length > 0 ? (
          <ul className="mt-7 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {visible.map((source) => (
              <SourceCard key={source.slug} source={source} />
            ))}
          </ul>
        ) : (
          <p className="mt-7 border-2 border-dashed border-line-mid bg-surface p-6 text-sm font-semibold text-muted">
            W tej kategorii nie ma jeszcze źródeł. Wybierz inną kategorię.
          </p>
        )}

        <p className="mt-8 border-t-2 border-line-mid pt-4 text-xs leading-relaxed text-muted">
          Podgląd na kafelku pochodzi z karty społecznościowej źródła, jeśli jest dostępny.
          Brak podglądu nie zmienia zasad kwalifikacji ani wagi źródła.
        </p>
      </section>
    </div>
  );
}
