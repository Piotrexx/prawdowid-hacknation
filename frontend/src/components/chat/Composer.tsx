"use client";

import { ArrowUp, CornerDownRight, FileAudio, ImagePlus, X } from "lucide-react";
import { useLayoutEffect, useRef, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";
import { formatInteger, plural } from "@/lib/format";
import { Spinner } from "@/components/ui/Spinner";
import {
  IMAGE_ACCEPT,
  imageFromTransfer,
  type ImageAttachment,
} from "@/components/check/useImageAttachment";

export const TEXT_LIMIT = 20_000;
export const MIN_TEXT_LENGTH = 20;
const COUNTER_FROM = 18_000;
const MAX_HEIGHT = 240;
const AUDIO_ACCEPT = "audio/*,audio/mp3,audio/mpeg,audio/wav,audio/webm,audio/ogg,audio/m4a,audio/aac";

interface ComposerProps {
  text: string;
  onTextChange: (value: string) => void;
  attachment: ImageAttachment | null;
  imageError: string | null;
  onPickImage: (file: File) => void;
  onClearImage: () => void;
  /** Wysyła plik audio do sprawdzenia po stronie serwera. */
  onAudio: (file: File) => void;
  onSubmit: () => void;
  busy: boolean;
  /** 0–100 podczas uploadu pliku, null poza nim. */
  uploadProgress: number | null;
  error: string | null;
  waitSeconds: number;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  /** The next text message answers a clarifying question instead of starting a new check. */
  replying?: boolean;
  onCancelReply?: () => void;
}

export function Composer({
  text,
  onTextChange,
  attachment,
  imageError,
  onPickImage,
  onClearImage,
  onAudio,
  onSubmit,
  busy,
  uploadProgress,
  error,
  waitSeconds,
  textareaRef,
  replying = false,
  onCancelReply,
}: ComposerProps) {
  const { t } = useTranslation();
  const imageFileRef = useRef<HTMLInputElement>(null);
  const audioFileRef = useRef<HTMLInputElement>(null);

  const overLimit = text.length > TEXT_LIMIT;
  const blocked = busy || waitSeconds > 0;

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

  function handleSubmitAttempt() {
    if (!blocked) onSubmit();
  }

  return (
    <>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          handleSubmitAttempt();
        }}
        className="sticky bottom-0 bg-gradient-to-t from-surface from-70% to-transparent pt-6 pb-4"
      >
        <div
          className={cx(
            "border bg-surface shadow-card focus-within:border-accent",
            error || overLimit ? "border-bad-fg" : "border-line-strong",
          )}
        >
          {replying && !attachment ? (
            <div className="flex items-center gap-2 border-b border-line bg-subtle py-1 pr-1 pl-4 text-sm">
              <CornerDownRight aria-hidden="true" className="size-4 shrink-0 text-accent" />
              <span className="min-w-0 flex-1 font-semibold">{t("composer.replyingTo")}</span>
              <button
                type="button"
                onClick={() => {
                  onCancelReply?.();
                  textareaRef.current?.focus();
                }}
                className="inline-flex min-h-11 shrink-0 items-center px-2.5 font-semibold text-link hover:bg-surface"
              >
                {t("composer.replyCancel")}
              </button>
            </div>
          ) : null}

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
                    ? t("composer.imageWillSend")
                    : t("composer.imageWillCheck")}
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
                <span className="sr-only">{t("composer.removeImage")}</span>
              </button>
            </div>
          ) : null}

          <label htmlFor="pole-tresci" className="sr-only">
            {t("composer.contentLabel")}
          </label>
          <textarea
            id="pole-tresci"
            ref={textareaRef}
            value={text}
            rows={1}
            placeholder={
              replying && !attachment ? t("composer.replyPlaceholder") : t("composer.placeholder")
            }
            aria-describedby={describedBy}
            aria-invalid={error || overLimit ? true : undefined}
            onChange={(event) => onTextChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
              if (window.matchMedia("(pointer: coarse)").matches) return;
              event.preventDefault();
              handleSubmitAttempt();
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
            {/* Hidden image file input */}
            <input
              ref={imageFileRef}
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
            {/* Hidden audio file input */}
            <input
              ref={audioFileRef}
              type="file"
              accept={AUDIO_ACCEPT}
              tabIndex={-1}
              aria-hidden="true"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onAudio(file);
                event.target.value = "";
              }}
            />

            <button
              type="button"
              onClick={() => imageFileRef.current?.click()}
              disabled={blocked}
              className={cx(
                "inline-flex min-h-11 items-center gap-2 px-2.5 text-sm font-semibold hover:bg-subtle",
                blocked ? "cursor-not-allowed text-muted" : "text-link",
              )}
            >
              <ImagePlus aria-hidden="true" className="size-5" />
              {attachment ? t("composer.otherImage") : t("composer.screenshot")}
            </button>

            <button
              type="button"
              onClick={() => audioFileRef.current?.click()}
              disabled={blocked}
              className={cx(
                "inline-flex min-h-11 items-center gap-2 px-2.5 text-sm font-semibold hover:bg-subtle",
                blocked ? "cursor-not-allowed text-muted" : "text-link",
              )}
            >
              <FileAudio aria-hidden="true" className="size-5" />
              {t("composer.audio")}
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
              className="grid size-11 place-items-center bg-accent text-on-accent hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? (
                <Spinner className="size-5" />
              ) : (
                <ArrowUp aria-hidden="true" className="size-5.5" strokeWidth={2.5} />
              )}
              <span className="sr-only">{busy ? t("composer.sending") : t("composer.submit")}</span>
            </button>
          </div>
        </div>

        {uploadProgress !== null ? (
          <div className="mt-2 space-y-1">
            <div className="flex justify-between text-xs text-muted">
              <span>{t("composer.uploading")}</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-subtle">
              <div
                className="h-full rounded-full bg-accent transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        ) : null}
        {error || imageError ? (
          <p id="czat-blad" role="alert" className="mt-2 text-sm font-semibold text-bad-fg">
            {error || imageError}
          </p>
        ) : null}
        {waitSeconds > 0 ? (
          <p className="mt-2 text-sm text-muted">
            {t("composer.waitSeconds", {
              seconds: waitSeconds,
              unit: plural(waitSeconds, "sekundę", "sekundy", "sekund"),
            })}
          </p>
        ) : null}
        <p id="czat-pomoc" className="mt-2 text-center text-xs text-muted">
          {replying && !attachment ? t("composer.replyHelp") : t("composer.help")}
          <span className="hidden sm:inline">{t("composer.helpDesktop")}</span>
        </p>
      </form>
    </>
  );
}
