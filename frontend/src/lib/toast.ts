export type ToastVariant = "error" | "warn" | "info";

interface ToastMessage {
  message: string;
  variant: ToastVariant;
}

type Listener = (msg: ToastMessage) => void;
const listeners = new Set<Listener>();

export function _registerToastListener(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function toast(message: string, variant: ToastVariant = "info"): void {
  listeners.forEach((fn) => fn({ message, variant }));
}
