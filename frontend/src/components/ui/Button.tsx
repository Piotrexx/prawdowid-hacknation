import type { ComponentProps } from "react";
import { cx } from "@/lib/cx";

type Variant = "primary" | "secondary" | "quiet" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "border-transparent bg-accent text-on-accent hover:bg-accent-hover",
  secondary: "border-accent bg-surface text-accent hover:bg-info-bg",
  quiet:
    "border-transparent bg-transparent px-1 text-link underline underline-offset-4 hover:text-accent-hover",
  danger: "border-bad-line bg-surface text-bad-fg hover:bg-bad-bg",
};

interface ButtonProps extends ComponentProps<"button"> {
  variant?: Variant;
  large?: boolean;
}

export function Button({
  variant = "secondary",
  large = false,
  type = "button",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border font-semibold transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-60",
        large ? "min-h-13 px-7 text-[1.0625rem] font-bold" : "px-4",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
