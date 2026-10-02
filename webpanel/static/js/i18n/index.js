import { ru } from "./ru.js";
import { en } from "./en.js";

export const I18N = { ru, en };
export const LANGS = Object.keys(I18N);

const STORAGE_KEY = "heroku.lang";

let current = "ru";

/** Pick the locale from the saved preference, then the system/browser. */
export function detectLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && LANGS.includes(saved)) return saved;
  } catch (_) {
    /* storage unavailable */
  }

  const candidates =
    navigator.languages && navigator.languages.length
      ? navigator.languages
      : [navigator.language || ""];

  for (const tag of candidates) {
    const base = String(tag).toLowerCase().split("-")[0];
    if (LANGS.includes(base)) return base;
  }

  return "en";
}

export function getLocale() {
  return current;
}

export function setLocale(next, { persist = true } = {}) {
  current = LANGS.includes(next) ? next : "ru";

  if (persist) {
    try {
      localStorage.setItem(STORAGE_KEY, current);
    } catch (_) {
      /* storage unavailable */
    }
  }

  return current;
}

/** Translate a dotted key, falling back to Russian, then the key itself. */
export function t(path, vars) {
  const pick = (dict) =>
    path.split(".").reduce((acc, key) => (acc == null ? acc : acc[key]), dict);

  let value = pick(I18N[current]);
  if (value === undefined) value = pick(I18N.ru);
  if (value === undefined) return path;

  if (typeof value === "function") return value(vars || {});
  if (vars) {
    for (const [key, val] of Object.entries(vars)) {
      value = value.replace(`{${key}}`, val);
    }
  }
  return value;
}
