import { ImagePlus, Trash2 } from "lucide-react";
import Image from "next/image";
import { useRef } from "react";
import { Button } from "@/components/ui/Button";
import { formatFileSize } from "@/lib/format";
import { IMAGE_ACCEPT, type ImageAttachment } from "./useImageAttachment";

interface ImagePickerProps {
  attachment: ImageAttachment | null;
  error: string | null;
  hasText: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
}

export function ImagePicker({ attachment, error, hasText, onPick, onClear }: ImagePickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const pickButtonRef = useRef<HTMLButtonElement>(null);

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept={IMAGE_ACCEPT}
        hidden
        tabIndex={-1}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onPick(file);
          // Reset so choosing the same file again still fires a change event.
          event.target.value = "";
        }}
      />

      {attachment ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line-strong bg-surface p-3">
          <Image
            src={attachment.previewUrl}
            alt="Podgląd dodanego obrazu"
            width={56}
            height={56}
            unoptimized
            className="size-14 shrink-0 rounded-md border border-line object-cover"
          />
          <p className="min-w-0 flex-1">
            <span className="block truncate font-medium">{attachment.file.name}</span>
            <span className="text-muted">{formatFileSize(attachment.file.size)}</span>
          </p>
          <Button
            onClick={() => {
              onClear();
              pickButtonRef.current?.focus();
            }}
          >
            <Trash2 aria-hidden="true" className="size-5" />
            Usuń<span className="sr-only"> obraz</span>
          </Button>
        </div>
      ) : null}

      <Button ref={pickButtonRef} onClick={() => inputRef.current?.click()}>
        <ImagePlus aria-hidden="true" className="size-5" />
        {attachment ? "Wybierz inne zdjęcie" : "Dodaj zdjęcie"}
      </Button>

      {attachment ? (
        <p className="text-muted">
          {hasText
            ? "Wyślę tylko obraz. Aby sprawdzić wpisany tekst, usuń obraz."
            : "Sprawdzę tekst widoczny na tym obrazie."}{" "}
          Obraz nie jest zapisywany.
        </p>
      ) : (
        <p className="text-muted">
          PNG, JPEG lub WebP, do 5 MB. Możesz też przeciągnąć obraz na to pole albo
          wkleić go ze schowka.
        </p>
      )}

      {error ? (
        <p role="alert" className="font-medium text-bad-fg">
          {error}
        </p>
      ) : null}
    </div>
  );
}
