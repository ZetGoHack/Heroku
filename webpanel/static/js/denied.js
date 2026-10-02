/* Access-denied page - reuses the shared i18n locales. */

import { detectLang, getLocale, setLocale, t } from "./i18n/index.js";

function applyI18n() {
  document.title = t("deniedTitle");
  document.documentElement.lang = getLocale();

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel));
  });
}

const langButtons = Array.from(document.querySelectorAll(".lang__btn"));

function updateLangButtons() {
  const current = getLocale();
  langButtons.forEach((btn) => {
    const active = btn.dataset.lang === current;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function setLang(next) {
  setLocale(next);
  applyI18n();
  updateLangButtons();
}

setLocale(detectLang(), { persist: false });
applyI18n();
updateLangButtons();

langButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.lang !== getLocale()) setLang(btn.dataset.lang);
  });
});

document.getElementById("token-form").addEventListener("submit", (event) => {
  event.preventDefault();

  const token = document.getElementById("token-input").value.trim();
  if (!token) return;

  const url = new URL(location.href);
  url.searchParams.set("token", token);
  location.replace(url.toString());
});
