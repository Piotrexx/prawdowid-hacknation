import type { ComponentProps } from "react";
import { cx } from "@/lib/cx";

type Variant = "primary" | "secondary" | "quiet" | "danger";

// gov.pl buttons are flat and bold: a filled blue primary and a blue-outlined secondary.
const VARIANTS: Record<Variant, string> = {
  primary: "border-accent bg-accent text-on-accent hover:bg-accent-hover hover:border-accent-hover",
  secondary: "border-accent bg-surface text-accent hover:bg-subtle",
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
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-sm border-2 font-semibold transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-60",
        large ? "min-h-14 px-6 text-lg font-bold" : "px-4",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
