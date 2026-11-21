import { RotateCcw, WifiOff } from "lucide-react";
import { describeError } from "@/lib/errors";
import { Button } from "./Button";
import { Notice } from "./Notice";
import { Spinner } from "./Spinner";

export function LoadingBlock({ label = "Wczytuję dane…" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-3 py-6 text-lg text-muted">
      <Spinner className="size-6" />
      {label}
    </p>
  );
}

interface ErrorBlockProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export function ErrorBlock({
  error,
  onRetry,
  title = "Nie udało się wczytać danych",
}: ErrorBlockProps) {
  return (
    <div className="space-y-3">
      <Notice icon={WifiOff} title={title} role="alert">
        <p>{describeError(error)}</p>
      </Notice>
      {onRetry ? (
        <Button onClick={onRetry}>
          <RotateCcw aria-hidden="true" className="size-5" />
          Spróbuj ponownie
        </Button>
      ) : null}
    </div>
  );
}
