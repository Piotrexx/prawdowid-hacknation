import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

type TagTone = "neutral" | "warn" | "bad" | "ok" | "info";

const TONES: Record<TagTone, string> = {
  neutral: "border-line bg-subtle text-ink",
  warn: "border-warn-line bg-warn-bg text-warn-fg",
  bad: "border-bad-line bg-bad-bg text-bad-fg",
  ok: "border-ok-line bg-ok-bg text-ok-fg",
  info: "border-info-line bg-info-bg text-info-fg",
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
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-sm font-medium",
        TONES[tone],
      )}
    >
      {Icon ? <Icon aria-hidden="true" className="size-4 shrink-0" /> : null}
      {children}
    </span>
  );
}
