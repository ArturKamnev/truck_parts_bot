import { translations as ru } from "./ru";
import { translations as en } from "./en";
import { translations as ky } from "./ky";

const locales: Record<string, Record<string, string>> = {
  ru,
  en,
  ky,
};

export const t = (key: string, locale: string | null | undefined): string => {
  const locStr = typeof locale === "string" ? locale : "ru";
  const lang = locStr.toLowerCase().slice(0, 2);
  const activeLocale = locales[lang] ? lang : "ru";
  
  const dict = locales[activeLocale];
  const value = (dict as Record<string, string>)[key];
  
  if (value !== undefined) {
    return value;
  }
  
  if (import.meta.env.DEV) {
    console.warn(`[i18n] Missing translation key "${key}" for locale "${lang}". Falling back to RU.`);
  }
  
  return (ru as Record<string, string>)[key] || key;
};
export default t;
