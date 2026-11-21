import type { ComponentProps } from "react";
import { cx } from "@/lib/cx";

type Variant = "primary" | "secondary" | "quiet" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "border-transparent bg-accent text-on-accent hover:bg-accent-hover",
  secondary: "border-line-strong bg-surface text-ink hover:bg-subtle",
  quiet: "border-transparent bg-transparent text-link underline underline-offset-4 hover:bg-subtle",
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
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-60",
        large ? "min-h-14 px-6 text-lg font-semibold" : "px-4",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
