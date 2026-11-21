"use client";

import { useCallback, useState } from "react";

export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp,image/gif";
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB

export interface ImageAttachment {
  file: File;
  previewUrl: string;
}

function validateImage(file: File): string | null {
  if (!file.type.startsWith("image/")) return "Plik musi być zdjęciem (JPEG, PNG, WebP lub GIF).";
  if (file.size > MAX_BYTES) return "Zdjęcie jest za duże (maksymalnie 10 MB).";
  return null;
}

export function imageFromTransfer(transfer: DataTransfer): File | null {
  for (const item of Array.from(transfer.items)) {
    if (item.kind === "file" && item.type.startsWith("image/")) {
      return item.getAsFile();
    }
  }
  return null;
}

export function useImageAttachment() {
  const [attachment, setAttachment] = useState<ImageAttachment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const attach = useCallback((file: File) => {
    const validationError = validateImage(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    if (attachment) URL.revokeObjectURL(attachment.previewUrl);
    setAttachment({ file, previewUrl: URL.createObjectURL(file) });
  }, [attachment]);

  const clear = useCallback(() => {
    if (attachment) URL.revokeObjectURL(attachment.previewUrl);
    setAttachment(null);
    setError(null);
  }, [attachment]);

  return { attachment, error, attach, clear };
}
