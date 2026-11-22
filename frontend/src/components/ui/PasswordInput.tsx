"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState, type ComponentProps } from "react";
import { cx } from "@/lib/cx";

interface PasswordInputProps extends Omit<ComponentProps<"input">, "type"> {
  /** Classes for the wrapper that keeps the eye button aligned with the field. */
  containerClassName?: string;
}

/** Pole hasła z przyciskiem oka do przełączania widoczności. */
export function PasswordInput({
  className,
  containerClassName,
  ...props
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const label = visible ? "Ukryj hasło" : "Pokaż hasło";

  return (
    <div className={cx("relative", containerClassName)}>
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={cx(className, "pr-12")}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        aria-label={label}
        aria-pressed={visible}
        title={label}
        className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted transition-colors hover:text-ink"
      >
        {visible ? (
          <EyeOff aria-hidden="true" className="size-5" />
        ) : (
          <Eye aria-hidden="true" className="size-5" />
        )}
      </button>
    </div>
  );
}
