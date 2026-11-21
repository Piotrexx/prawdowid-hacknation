"use client";

import { ArrowUp, ImagePlus, X } from "lucide-react";
import { useLayoutEffect, useRef, type RefObject } from "react";
import { cx } from "@/lib/cx";
import { formatInteger, plural } from "@/lib/format";
import {
  IMAGE_ACCEPT,
  imageFromTransfer,
  type ImageAttachment,
} from "@/components/check/useImageAttachment";

export const TEXT_LIMIT = 20_000;
const COUNTER_FROM = 18_000;
const MAX_HEIGHT = 240;

interface ComposerProps {
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

export function Composer({
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
}: ComposerProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const overLimit = text.length > TEXT_LIMIT;
  const blocked = busy || waitSeconds > 0;

  // Grows with the text up to MAX_HEIGHT, then scrolls.
  useLayoutEffect(() => {
    const field = textareaRef.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, MAX_HEIGHT)}px`;
  }, [text, textareaRef]);

  const describedBy = cx(
    "czat-pomoc",
    text.length >= COUNTER_FROM && "czat-licznik",
    error && "czat-blad",
  );

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (!blocked) onSubmit();
      }}
      className="sticky bottom-0 bg-gradient-to-t from-surface from-70% to-transparent pt-6 pb-4"
    >
      <div
        className={cx(
          "border bg-surface shadow-card focus-within:border-accent",
          error || overLimit ? "border-bad-fg" : "border-line-strong",
        )}
      >
        {attachment ? (
          <div className="flex items-center gap-3 px-4 pt-3">
            {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
            <img
              src={attachment.previewUrl}
              alt=""
              className="size-14 shrink-0 border border-line object-cover"
            />
            <span className="min-w-0 flex-1 truncate text-sm">
              {attachment.file.name}
              <span className="block text-xs text-muted">
                {text.trim()
                  ? "Wyślę tylko obraz. Aby sprawdzić tekst, usuń obraz."
                  : "Sprawdzę tekst widoczny na obrazie."}
              </span>
            </span>
            <button
              type="button"
              onClick={() => {
                onClearImage();
                textareaRef.current?.focus();
              }}
              className="grid size-11 shrink-0 place-items-center text-muted hover:bg-subtle hover:text-ink"
            >
              <X aria-hidden="true" className="size-5" />
              <span className="sr-only">Usuń obraz</span>
            </button>
          </div>
        ) : null}

        <label htmlFor="pole-tresci" className="sr-only">
          Treść do sprawdzenia
        </label>
        <textarea
          id="pole-tresci"
          ref={textareaRef}
          value={text}
          rows={1}
          placeholder="Wklej wiadomość, wpis albo link do sprawdzenia…"
          aria-describedby={describedBy}
          aria-invalid={error || overLimit ? true : undefined}
          onChange={(event) => onTextChange(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter starts a new line; touch keyboards keep Enter for new lines.
            if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
            if (window.matchMedia("(pointer: coarse)").matches) return;
            event.preventDefault();
            if (!blocked) onSubmit();
          }}
          onPaste={(event) => {
            if (event.clipboardData.getData("text/plain")) return;
            const file = imageFromTransfer(event.clipboardData);
            if (!file) return;
            event.preventDefault();
            onPickImage(file);
          }}
          className="block max-h-60 min-h-14 w-full resize-none bg-transparent px-4 pt-4 pb-2 text-base leading-relaxed placeholder:text-muted focus:outline-none"
        />

        <div className="flex items-center gap-2 px-2 pb-2">
          <input
            ref={fileRef}
            type="file"
            accept={IMAGE_ACCEPT}
            tabIndex={-1}
            aria-hidden="true"
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onPickImage(file);
              event.target.value = "";
            }}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="inline-flex min-h-11 items-center gap-2 px-2.5 text-sm font-semibold text-link hover:bg-subtle"
          >
            <ImagePlus aria-hidden="true" className="size-5" />
            {attachment ? "Inny obraz" : "Zrzut ekranu"}
          </button>
          <span className="flex-1" />
          {text.length >= COUNTER_FROM ? (
            <span
              id="czat-licznik"
              className={cx("text-xs", overLimit ? "font-bold text-bad-fg" : "text-muted")}
            >
              {formatInteger(text.length)} / {formatInteger(TEXT_LIMIT)}
            </span>
          ) : null}
          <button
            type="submit"
            disabled={blocked}
            className="grid size-11 place-items-center bg-accent text-on-accent hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowUp aria-hidden="true" className="size-5.5" strokeWidth={2.5} />
            <span className="sr-only">Sprawdź</span>
          </button>
        </div>
      </div>

      {error || imageError ? (
        <p id="czat-blad" role="alert" className="mt-2 text-sm font-semibold text-bad-fg">
          {error || imageError}
        </p>
      ) : null}
      {waitSeconds > 0 ? (
        <p className="mt-2 text-sm text-muted">
          Możesz wysłać kolejne sprawdzenie za {waitSeconds}{" "}
          {plural(waitSeconds, "sekundę", "sekundy", "sekund")}.
        </p>
      ) : null}
      <p id="czat-pomoc" className="mt-2 text-center text-xs text-muted">
        Każda wiadomość to osobne sprawdzenie. Zawsze otwórz źródła – ocena należy do Ciebie.
        <span className="hidden sm:inline"> Enter wysyła, Shift+Enter dodaje nową linię.</span>
      </p>
    </form>
  );
}
