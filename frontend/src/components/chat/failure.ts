import { Clock, FileWarning, WifiOff, Wrench, type LucideIcon } from "lucide-react";
import { ApiError } from "@/lib/api";
import { describeError } from "@/lib/errors";

export interface Failure {
  icon: LucideIcon;
  title: string;
  message: string;
  canRetry: boolean;
}

export function describeFailure(error: unknown): Failure {
  const kind = error instanceof ApiError ? error.kind : "http";
  const message = describeError(error);
  if (kind === "rate_limit") {
    return { icon: Clock, title: "Za dużo sprawdzeń naraz", message, canRetry: false };
  }
  if (kind === "validation") {
    return {
      icon: FileWarning,
      title: "Nie udało się przyjąć tej treści",
      message,
      canRetry: false,
    };
  }
  if (kind === "network" || kind === "timeout") {
    return { icon: WifiOff, title: "Problem z połączeniem", message, canRetry: true };
  }
  return { icon: Wrench, title: "Problem po stronie serwera", message, canRetry: true };
}
