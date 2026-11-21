import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

type TagTone = "neutral" | "warn" | "bad" | "ok" | "info";

const TONES: Record<TagTone, string> = {
  neutral: "bg-calm-bg text-calm-fg",
  warn: "bg-warn-bg text-warn-fg",
  bad: "bg-bad-bg text-bad-fg",
  ok: "bg-ok-bg text-ok-fg",
  info: "bg-info-bg text-info-fg",
};

interface TagProps {
  tone?: TagTone;
  icon?: LucideIcon;
  children: ReactNode;
}

export function Tag({ tone = "neutral", icon: Icon, children }: TagProps) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 border border-transparent px-2.5 py-1 text-xs font-bold tracking-[0.02em] uppercase",
        TONES[tone],
      )}
    >
      {Icon ? <Icon aria-hidden="true" className="size-4 shrink-0" /> : null}
      {children}
    </span>
  );
}
