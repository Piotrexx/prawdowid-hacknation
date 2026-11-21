import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import pl from "./locales/pl.json";

export const defaultNS = "translation";
export const resources = { pl: { translation: pl } } as const;

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    lng: "pl",
    fallbackLng: "pl",
    defaultNS,
    resources,
    interpolation: { escapeValue: false },
  });
}

export default i18n;
