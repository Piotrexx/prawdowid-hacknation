import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cx } from "@/lib/cx";

/** Tall, full-width tiles stacked in the right column ("Na skróty", "Działania"). */
const TILE =
  "flex min-h-16 w-full items-center justify-between gap-3 border px-6 text-left text-[0.9375rem] font-semibold tracking-[0.01em] uppercase transition-colors";

function tileTone(highlight: boolean): string {
  return highlight
    ? "border-line-mid bg-info-bg text-info-fg hover:border-accent"
    : "border-line-mid bg-surface text-ink hover:border-accent hover:text-accent";
}

interface TileContentProps {
  icon: LucideIcon;
  highlight: boolean;
  children: ReactNode;
}

function TileContent({ icon: Icon, highlight, children }: TileContentProps) {
  return (
    <>
      <span>{children}</span>
      <Icon
        aria-hidden="true"
        className={cx("size-5.5 shrink-0", highlight ? "text-current" : "text-accent")}
      />
    </>
  );
}

interface SideLinkProps {
  href: string;
  icon: LucideIcon;
  highlight?: boolean;
  children: ReactNode;
}

export function SideLink({ href, icon, highlight = false, children }: SideLinkProps) {
  const className = cx(TILE, tileTone(highlight));
  const content = (
    <TileContent icon={icon} highlight={highlight}>
      {children}
    </TileContent>
  );
  // In-page anchors stay plain links so the browser moves focus to the target.
  return href.startsWith("#") ? (
    <a href={href} className={className}>
      {content}
    </a>
  ) : (
    <Link href={href} className={className}>
      {content}
    </Link>
  );
}

interface SideButtonProps extends Omit<ComponentProps<"button">, "children"> {
  icon: LucideIcon;
  highlight?: boolean;
  children: ReactNode;
}

export function SideButton({
  icon,
  highlight = false,
  children,
  className,
  ...props
}: SideButtonProps) {
  return (
    <button type="button" className={cx(TILE, tileTone(highlight), className)} {...props}>
      <TileContent icon={icon} highlight={highlight}>
        {children}
      </TileContent>
    </button>
  );
}

/** Bordered card with a title, a status badge and optional detail lines below. */
export function SideCard({
  title,
  badge,
  children,
}: {
  title: ReactNode;
  badge?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-start gap-x-3 gap-y-2.5 border border-line-mid p-5">
      <div className="min-w-0">{title}</div>
      {badge ? <div className="justify-self-end">{badge}</div> : <span />}
      {children ? <div className="col-span-2 min-w-0">{children}</div> : null}
    </div>
  );
}
