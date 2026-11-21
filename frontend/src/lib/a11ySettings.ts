export type TextSize = "normal" | "large" | "larger";

export interface A11ySettings {
  textSize: TextSize;
  highContrast: boolean;
}

export const STORAGE_KEY = "prawdowid_a11y";

export const DEFAULT_SETTINGS: A11ySettings = { textSize: "normal", highContrast: false };

const TEXT_SIZES: TextSize[] = ["normal", "large", "larger"];

export function readSettings(): A11ySettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return DEFAULT_SETTINGS;
    const { textSize, highContrast } = parsed as Partial<A11ySettings>;
    return {
      textSize: TEXT_SIZES.includes(textSize as TextSize) ? (textSize as TextSize) : "normal",
      highContrast: highContrast === true,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function applySettings(settings: A11ySettings): void {
  const root = document.documentElement;
  if (settings.textSize === "normal") delete root.dataset.textSize;
  else root.dataset.textSize = settings.textSize;
  if (settings.highContrast) root.dataset.contrast = "high";
  else delete root.dataset.contrast;
}

export function saveSettings(settings: A11ySettings): void {
  applySettings(settings);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Settings still apply for this visit when storage is blocked.
  }
}

/** Runs before first paint so a saved text size or contrast does not flash. Keep it dependency-free. */
export const APPLY_SETTINGS_SCRIPT = `(function(){try{var s=JSON.parse(localStorage.getItem(${JSON.stringify(
  STORAGE_KEY,
)})||"{}");var r=document.documentElement;if(s.textSize==="large"||s.textSize==="larger")r.dataset.textSize=s.textSize;if(s.highContrast===true)r.dataset.contrast="high";}catch(e){}})();`;
