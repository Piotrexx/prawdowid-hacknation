export type TextSize = "normal" | "large" | "larger";

export interface A11ySettings {
  textSize: TextSize;
  highContrast: boolean;
  /** Wyłącza animacje w interfejsie. Niezależne od systemowego prefers-reduced-motion,
   *  które i tak jest respektowane – to ustawienie pozwala je włączyć samodzielnie. */
  reduceMotion: boolean;
}

export const STORAGE_KEY = "prawdowid_a11y";

export const DEFAULT_SETTINGS: A11ySettings = {
  textSize: "normal",
  highContrast: false,
  reduceMotion: false,
};

const TEXT_SIZES: TextSize[] = ["normal", "large", "larger"];

export function readSettings(): A11ySettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return DEFAULT_SETTINGS;
    const { textSize, highContrast, reduceMotion } = parsed as Partial<A11ySettings>;
    return {
      textSize: TEXT_SIZES.includes(textSize as TextSize) ? (textSize as TextSize) : "normal",
      highContrast: highContrast === true,
      reduceMotion: reduceMotion === true,
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
  if (settings.reduceMotion) root.dataset.motion = "reduced";
  else delete root.dataset.motion;
}

export function saveSettings(settings: A11ySettings): void {
  applySettings(settings);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Settings still apply for this visit when storage is blocked.
  }
}

/** Runs before first paint so a saved text size, contrast or motion choice does not flash.
 *  Keep it dependency-free. */
export const APPLY_SETTINGS_SCRIPT = `(function(){try{var s=JSON.parse(localStorage.getItem(${JSON.stringify(
  STORAGE_KEY,
)})||"{}");var r=document.documentElement;if(s.textSize==="large"||s.textSize==="larger")r.dataset.textSize=s.textSize;if(s.highContrast===true)r.dataset.contrast="high";if(s.reduceMotion===true)r.dataset.motion="reduced";}catch(e){}})();`;
