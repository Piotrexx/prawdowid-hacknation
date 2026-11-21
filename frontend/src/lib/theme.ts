/** User-facing display settings, stored per browser and applied to <html>. */

export const THEMES = ["auto", "light", "dark", "contrast"] as const;
export const FONT_SIZES = ["normal", "large", "xlarge"] as const;
export const MOTIONS = ["auto", "reduced"] as const;

export type Theme = (typeof THEMES)[number];
export type FontSize = (typeof FONT_SIZES)[number];
export type Motion = (typeof MOTIONS)[number];

export interface Display {
  theme: Theme;
  font: FontSize;
  motion: Motion;
}

export const DEFAULT_DISPLAY: Display = { theme: "light", font: "normal", motion: "auto" };

export const STORAGE_KEY = "prawdowid:display";

export const THEME_LABELS: Record<Theme, string> = {
  auto: "Systemowy",
  light: "Jasny",
  dark: "Ciemny",
  contrast: "Wysoki kontrast",
};

export const FONT_LABELS: Record<FontSize, string> = {
  normal: "Standardowa",
  large: "Większa",
  xlarge: "Największa",
};

export const MOTION_LABELS: Record<Motion, string> = {
  auto: "Systemowy",
  reduced: "Ogranicz animacje",
};

function isOneOf<T extends string>(values: readonly T[], value: unknown): value is T {
  return typeof value === "string" && (values as readonly string[]).includes(value);
}

/** Never throws: private mode and blocked site data both surface as a read failure. */
export function readDisplay(): Display {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_DISPLAY;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return DEFAULT_DISPLAY;
    const { theme, font, motion } = parsed as Record<string, unknown>;
    return {
      theme: isOneOf(THEMES, theme) ? theme : DEFAULT_DISPLAY.theme,
      font: isOneOf(FONT_SIZES, font) ? font : DEFAULT_DISPLAY.font,
      motion: isOneOf(MOTIONS, motion) ? motion : DEFAULT_DISPLAY.motion,
    };
  } catch {
    return DEFAULT_DISPLAY;
  }
}

export function saveDisplay(display: Display): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(display));
  } catch {
    // A rejected write only costs persistence; the setting still applies to this page.
  }
}

/** Resolves "auto" against the OS setting, because the stylesheet only knows concrete themes. */
export function applyDisplay(display: Display): void {
  const root = document.documentElement;
  const prefersDark =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  root.dataset.theme =
    display.theme === "auto" ? (prefersDark ? "dark" : "light") : display.theme;
  root.dataset.font = display.font;
  root.dataset.motion = display.motion;
}

/* A tiny store so components can read the settings through useSyncExternalStore:
   localStorage is external state, and the snapshot has to stay referentially stable. */

let cached: Display | null = null;
const listeners = new Set<() => void>();

export function subscribeDisplay(onChange: () => void): () => void {
  listeners.add(onChange);

  // "auto" has to keep tracking the OS while the page is open.
  const query =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)")
      : null;
  const reapply = () => applyDisplay(getDisplaySnapshot());
  query?.addEventListener("change", reapply);

  return () => {
    listeners.delete(onChange);
    query?.removeEventListener("change", reapply);
  };
}

export function getDisplaySnapshot(): Display {
  cached ??= readDisplay();
  return cached;
}

/** The server cannot know the preference, so it renders the defaults. */
export function getDisplayServerSnapshot(): Display {
  return DEFAULT_DISPLAY;
}

export function setDisplay(next: Display): void {
  cached = next;
  applyDisplay(next);
  saveDisplay(next);
  for (const listener of listeners) listener();
}

/** Inlined in <head> so the stored theme is painted on the first frame, not after hydration. */
export const DISPLAY_BOOT_SCRIPT = `(function(){try{var fallback=${JSON.stringify(
  DEFAULT_DISPLAY,
)};var d=JSON.parse(localStorage.getItem(${JSON.stringify(
  STORAGE_KEY,
)})||"{}")||{};var t=d.theme||fallback.theme;var e=document.documentElement;e.dataset.theme=t==="auto"?(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):t;e.dataset.font=d.font||fallback.font;e.dataset.motion=d.motion||fallback.motion;}catch(_){}})();`;
