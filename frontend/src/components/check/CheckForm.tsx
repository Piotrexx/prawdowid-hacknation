import { Search } from "lucide-react";
import { useState, type DragEvent, type RefObject } from "react";
import { Button } from "@/components/ui/Button";
import { cx } from "@/lib/cx";
import { formatInteger, plural } from "@/lib/format";
import { ImagePicker } from "./ImagePicker";
import { imageFromTransfer, type ImageAttachment } from "./useImageAttachment";

export const TEXT_LIMIT = 20_000;
const COUNTER_FROM = 18_000;

// Neutral prompts only: the examples must never suggest a specific claim.
const EXAMPLES = [
  {
    label: "Wiadomość z komunikatora",
    template: "Czy ta wiadomość z komunikatora jest prawdziwa?\n\n",
  },
  {
    label: "Wpis z mediów społecznościowych",
    template: "Czy ten wpis z mediów społecznościowych jest prawdziwy?\n\n",
  },
  {
    label: "Artykuł lub link",
    template: "Czy informacja z tego artykułu jest prawdziwa?\n\n",
  },
];

export function isExampleOnly(text: string): boolean {
  const trimmed = text.trim();
  return EXAMPLES.some((example) => example.template.trim() === trimmed);
}

interface CheckFormProps {
  text: string;
  onTextChange: (value: string) => void;
  attachment: ImageAttachment | null;
  imageError: string | null;
  onPickImage: (file: File) => void;
  onClearImage: () => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  waitSeconds: number;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}

export function CheckForm({
  text,
  onTextChange,
  attachment,
  imageError,
  onPickImage,
  onClearImage,
  onSubmit,
  busy,
  error,
  waitSeconds,
  textareaRef,
}: CheckFormProps) {
  const [dragActive, setDragActive] = useState(false);
  const overLimit = text.length > TEXT_LIMIT;
  const excess = text.length - TEXT_LIMIT;

  function applyExample(template: string) {
    const body = isExampleOnly(text)
      ? ""
      : EXAMPLES.reduce(
          (value, example) =>
            value.startsWith(example.template) ? value.slice(example.template.length) : value,
          text,
        );
    const next = `${template}${body}`;
    onTextChange(next);
    const field = textareaRef.current;
    if (!field) return;
    field.focus();
    requestAnimationFrame(() => field.setSelectionRange(next.length, next.length));
  }

  function hasFiles(event: DragEvent): boolean {
    return Array.from(event.dataTransfer.types).includes("Files");
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    if (!hasFiles(event)) return;
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files[0];
    if (file && !busy) onPickImage(file);
  }

  return (
    <form
      noValidate
      aria-busy={busy}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <fieldset disabled={busy} className="min-w-0 space-y-5">
        <div
          className={cx(
            "space-y-3 rounded-xl border bg-surface p-4 sm:p-5",
            dragActive ? "border-dashed border-focus outline-2 outline-focus" : "border-line",
          )}
          onDragOver={(event) => {
            if (!hasFiles(event)) return;
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              setDragActive(false);
            }
          }}
          onDrop={handleDrop}
        >
          <label htmlFor="pole-tresci" className="block text-xl font-semibold">
            Wklej wiadomość, link albo opisz, co chcesz sprawdzić
          </label>
          <p id="pole-tresci-pomoc" className="text-muted">
            Zanim sprawdzę treść, automatycznie ukrywam w niej łatwe do rozpoznania
            dane osobowe.
          </p>
          <textarea
            id="pole-tresci"
            ref={textareaRef}
            value={text}
            rows={7}
            aria-describedby={cx(
              "pole-tresci-pomoc",
              text.length >= COUNTER_FROM && "pole-tresci-licznik",
              error && "pole-tresci-blad",
            )}
            aria-invalid={error || overLimit ? true : undefined}
            onChange={(event) => onTextChange(event.target.value)}
            onPaste={(event) => {
              // Office apps put both text and a picture on the clipboard; text wins then.
              if (event.clipboardData.getData("text/plain")) return;
              const file = imageFromTransfer(event.clipboardData);
              if (!file) return;
              event.preventDefault();
              onPickImage(file);
            }}
            className="block w-full resize-y rounded-lg border border-line-strong bg-surface p-3 text-lg leading-relaxed placeholder:text-muted"
          />

          {text.length >= COUNTER_FROM ? (
            <p id="pole-tresci-licznik" className={overLimit ? "font-medium text-bad-fg" : "text-muted"}>
              {overLimit
                ? `Za dużo o ${formatInteger(excess)} ${plural(excess, "znak", "znaki", "znaków")}.`
                : `Wpisano ${formatInteger(text.length)} z ${formatInteger(TEXT_LIMIT)} znaków.`}
            </p>
          ) : null}
          {overLimit ? (
            <p role="alert" className="font-medium text-bad-fg">
              Tekst jest za długi. Skróć go do {formatInteger(TEXT_LIMIT)} znaków.
            </p>
          ) : null}
          {error ? (
            <p id="pole-tresci-blad" role="alert" className="font-medium text-bad-fg">
              {error}
            </p>
          ) : null}

          <div>
            <p id="przyklady" className="text-muted">
              Nie wiesz, jak zacząć? Wybierz, co chcesz sprawdzić, a potem wklej treść:
            </p>
            <ul aria-labelledby="przyklady" className="mt-2 flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <li key={example.label}>
                  <button
                    type="button"
                    onClick={() => applyExample(example.template)}
                    className="min-h-11 rounded-full border border-line-strong bg-subtle px-4 font-medium hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {example.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <ImagePicker
            attachment={attachment}
            error={imageError}
            hasText={text.trim().length > 0}
            onPick={onPickImage}
            onClear={onClearImage}
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            type="submit"
            variant="primary"
            large
            disabled={waitSeconds > 0}
            className="w-full sm:w-auto sm:min-w-48"
          >
            <Search aria-hidden="true" className="size-6" />
            Sprawdź
          </Button>
          {waitSeconds > 0 ? (
            <p className="text-muted">
              Możesz spróbować ponownie za {waitSeconds}{" "}
              {plural(waitSeconds, "sekundę", "sekundy", "sekund")}.
            </p>
          ) : null}
        </div>
      </fieldset>
    </form>
  );
}
