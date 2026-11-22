"use client";

import { ArrowUpRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cx } from "@/lib/cx";
import {
  SOURCE_CATEGORY_LABELS,
  SOURCE_TIER_LABELS,
  sourceImagePath,
  type CatalogSource,
  type SourceTier,
} from "@/lib/sourceCatalog";

export const TIER_STYLES: Record<
  SourceTier,
  { bar: string; pill: string; dot: string }
> = {
  1: {
    bar: "bg-accent",
    pill: "border-accent bg-info-bg text-info-fg",
    dot: "bg-accent",
  },
  2: {
    bar: "bg-ok-line",
    pill: "border-ok-line bg-ok-bg text-ok-fg",
    dot: "bg-ok-line",
  },
  3: {
    bar: "bg-warn-line",
    pill: "border-warn-line bg-warn-bg text-warn-fg",
    dot: "bg-warn-line",
  },
};

function Artwork({ source }: { source: CatalogSource }) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const imageRef = useRef<HTMLImageElement>(null);

  // A cached image can finish before hydration attaches onLoad, so sync once on mount.
  useEffect(() => {
    const image = imageRef.current;
    if (!image || !image.complete) return;
    if (image.naturalWidth > 0) setLoaded(true);
    else setFailed(true);
  }, []);

  return (
    <div className="relative aspect-[16/9] overflow-hidden border-b-2 border-line-mid bg-info-bg">
      <div aria-hidden="true" className="absolute inset-0 grid place-items-center">
        <span className="text-[3.25rem] leading-none font-black tracking-[-0.06em] text-accent opacity-30">
          {source.mark}
        </span>
      </div>
      <span
        aria-hidden="true"
        className="absolute inset-0 text-line-mid"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
          backgroundSize: "14px 14px",
          opacity: 0.35,
        }}
      />
      {!failed ? (
        // eslint-disable-next-line @next/next/no-img-element -- fetched through our own preview endpoint
        <img
          ref={imageRef}
          src={sourceImagePath(source.slug)}
          alt=""
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
          className={cx(
            "absolute inset-0 size-full object-cover transition-opacity duration-500",
            loaded ? "opacity-100" : "opacity-0",
          )}
        />
      ) : null}
      <span
        className={cx(
          "absolute top-3 left-3 inline-flex items-center gap-1.5 border-2 px-2.5 py-1 text-[0.6875rem] font-extrabold tracking-[0.08em] uppercase shadow-[3px_3px_0_0_var(--line-mid)]",
          TIER_STYLES[source.tier].pill,
        )}
      >
        <span aria-hidden="true" className={cx("size-2", TIER_STYLES[source.tier].dot)} />
        {SOURCE_TIER_LABELS[source.tier]}
      </span>
    </div>
  );
}

export function SourceCard({ source }: { source: CatalogSource }) {
  return (
    <li className="flex">
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className={cx(
          "group flex w-full flex-col border-2 border-line-mid bg-surface text-ink",
          "shadow-[6px_6px_0_0_var(--line-mid)] transition-[border-color,box-shadow] duration-150",
          "hover:border-accent hover:shadow-[8px_8px_0_0_var(--accent)]",
        )}
      >
        <span aria-hidden="true" className={cx("block h-1.5", TIER_STYLES[source.tier].bar)} />
        <Artwork source={source} />

        <div className="flex flex-1 flex-col p-5">
          <p className="text-[0.6875rem] font-bold tracking-[0.08em] text-muted uppercase">
            {source.fullName}
          </p>
          <h3 className="mt-1.5 text-2xl leading-none font-black tracking-[-0.02em] uppercase">
            {source.name}
          </h3>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">{source.description}</p>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {source.categories.map((category) => (
              <span
                key={category}
                className="border-2 border-line-mid bg-subtle px-2 py-0.5 text-[0.625rem] font-extrabold tracking-[0.08em] uppercase text-ink-soft"
              >
                {SOURCE_CATEGORY_LABELS[category]}
              </span>
            ))}
          </div>

          <span className="mt-auto flex items-center justify-between gap-3 pt-6 text-[0.8125rem] font-extrabold tracking-[0.08em] uppercase text-accent">
            Otwórz źródło
            <ArrowUpRight
              aria-hidden="true"
              className="size-5 shrink-0 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            />
          </span>
        </div>
      </a>
    </li>
  );
}
