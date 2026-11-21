import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

export type Tone = "neutral" | "info" | "warn" | "bad" | "ok";

const TONES: Record<Tone, { box: string; icon: string }> = {
  neutral: { box: "border-line bg-subtle", icon: "text-muted" },
  info: { box: "border-info-line bg-info-bg", icon: "text-info-fg" },
  warn: { box: "border-warn-line bg-warn-bg", icon: "text-warn-fg" },
  bad: { box: "border-bad-line bg-bad-bg", icon: "text-bad-fg" },
  ok: { box: "border-ok-line bg-ok-bg", icon: "text-ok-fg" },
};

interface NoticeProps {
  tone?: Tone;
  icon: LucideIcon;
  title?: string;
  children?: ReactNode;
  role?: "alert" | "status";
  className?: string;
}

export function Notice({
  tone = "neutral",
  icon: Icon,
  title,
  children,
  role,
  className,
}: NoticeProps) {
  const styles = TONES[tone];
  return (
    <div
      role={role}
      className={cx("flex gap-3 rounded-lg border p-4 text-ink", styles.box, className)}
    >
      <Icon aria-hidden="true" className={cx("mt-0.5 size-5 shrink-0", styles.icon)} />
      <div className="min-w-0 flex-1 space-y-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children}
      </div>
    </div>
  );
}
