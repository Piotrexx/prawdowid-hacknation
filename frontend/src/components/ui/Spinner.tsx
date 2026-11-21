import { LoaderCircle } from "lucide-react";
import { cx } from "@/lib/cx";

export function Spinner({ className }: { className?: string }) {
  return (
    <LoaderCircle
      aria-hidden="true"
      className={cx("shrink-0 animate-spin motion-reduce:animate-none", className)}
    />
  );
}
