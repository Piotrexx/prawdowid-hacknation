import { useEffect, useRef, useState } from "react";
import { formatFileSize } from "@/lib/format";

export const IMAGE_ACCEPT = "image/png,image/jpeg,image/webp";
const ALLOWED_TYPES = new Set(IMAGE_ACCEPT.split(","));
const ALLOWED_EXTENSION = /\.(png|jpe?g|webp)$/i;
const MAX_BYTES = 5 * 1024 * 1024;

export interface ImageAttachment {
  file: File;
  previewUrl: string;
}

function validateImage(file: File): string | null {
  // Some systems report an empty MIME type; fall back to the file extension then.
  const typeOk = file.type ? ALLOWED_TYPES.has(file.type) : ALLOWED_EXTENSION.test(file.name);
  if (!typeOk) {
    return "Tego pliku nie da się sprawdzić. Dodaj obraz w formacie PNG, JPEG albo WebP.";
  }
  if (file.size > MAX_BYTES) {
    return `Ten obraz jest za duży (${formatFileSize(file.size)}). Największy dozwolony rozmiar to 5 MB.`;
  }
  if (file.size === 0) return "Ten plik jest pusty. Wybierz inny obraz.";
  return null;
}

export function useImageAttachment() {
  const [attachment, setAttachment] = useState<ImageAttachment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  function release() {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }

  function attach(file: File) {
    const problem = validateImage(file);
    if (problem) {
      setError(problem);
      return;
    }
    release();
    const previewUrl = URL.createObjectURL(file);
    urlRef.current = previewUrl;
    setAttachment({ file, previewUrl });
    setError(null);
  }

  function clear() {
    release();
    setAttachment(null);
    setError(null);
  }

  useEffect(() => {
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  return { attachment, error, attach, clear };
}

/** Image file from a paste or drop, or null when the payload is not a single image. */
export function imageFromTransfer(data: DataTransfer | null): File | null {
  if (!data) return null;
  for (const file of Array.from(data.files)) {
    if (file.type.startsWith("image/") || ALLOWED_EXTENSION.test(file.name)) return file;
  }
  return null;
}
