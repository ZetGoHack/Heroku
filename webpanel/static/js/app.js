/* Heroku web panel - vanilla JS, no dependencies. */

import { detectLang, getLocale, setLocale, t } from "./i18n/index.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const ACCESS_TOKEN = new URLSearchParams(location.search).get("token") || "";

/** Append the panel access token to an internal URL. */
function withToken(path) {
  if (!ACCESS_TOKEN) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}token=${encodeURIComponent(ACCESS_TOKEN)}`;
}

/* ------------------------------------------------------------------ */
/* Element references & UI state                                       */
/* ------------------------------------------------------------------ */

const els = {
  panels: $$(".panel"),
  apiId: $("#api-id"),
  apiHash: $("#api-hash"),
  btnCredentials: $("#btn-credentials"),
  errCredentials: $("#err-credentials"),
  phone: $("#phone"),
  btnPhone: $("#btn-phone"),
  errPhone: $("#err-phone"),
  backCredentials: $("#back-credentials"),
  btnQr: $("#btn-qr"),
  errRecaptcha: $("#err-recaptcha"),
  btnRecaptchaQr: $("#btn-recaptcha-qr"),
  backPhoneRecaptcha: $("#back-phone-recaptcha"),
  qrImage: $("#qr-image"),
  qrStatus: $("#qr-status"),
  errQr: $("#err-qr"),
  backPhoneQr: $("#back-phone-qr"),
  phoneEcho: $("#phone-echo"),
  otp: $("#otp"),
  otpInputs: $$(".otp__input"),
  btnCode: $("#btn-code"),
  errCode: $("#err-code"),
  resend: $("#resend"),
  backPhone: $("#back-phone"),
  password: $("#password"),
  passwordHint: $("#password-hint"),
  btn2fa: $("#btn-2fa"),
  err2fa: $("#err-2fa"),
  doneText: $("#done-text"),
  account: $("#account"),
  hosted: $("#hosted"),
  toast: $("#toast"),
  langButtons: $$(".lang__btn"),
};

const ui = {
  phone: null,
  passwordHint: null,
  qrExpires: null,
  donePhase: "saved",
  account: null,
  platform: null,
};

let toastTimer = null;
let qrPollTimer = null;
let qrUrl = null;
let qrFailures = 0;
let qrImageTimer = 0;

/* ------------------------------------------------------------------ */
/* i18n rendering                                                      */
/* ------------------------------------------------------------------ */

function applyI18n() {
  document.title = t("docTitle");
  document.documentElement.lang = getLocale();

  $$("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });

  $$("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });

  $$("[data-i18n-aria-label]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel, { index: el.dataset.index }));
  });

  $$("[data-i18n-alt]").forEach((el) => {
    el.setAttribute("alt", t(el.dataset.i18nAlt));
  });
}

function renderAccount() {
  const account = ui.account;
  if (!account || !els.account) return;

  const name =
    [account.first_name, account.last_name].filter(Boolean).join(" ") ||
    t("accountFallback");
  const handle = account.username ? `@${account.username}` : `id ${account.id}`;

  els.account.innerHTML = "";

  if (account.avatar) {
    const avatar = document.createElement("img");
    avatar.className = "account__avatar";
    avatar.src = account.avatar;
    avatar.alt = "";
    els.account.append(avatar);
  } else {
    const fallback = document.createElement("span");
    fallback.className = "account__avatar account__avatar--fallback";
    fallback.textContent = (name[0] || "?").toUpperCase();
    els.account.append(fallback);
  }

  const meta = document.createElement("span");
  meta.className = "account__meta";

  const nameEl = document.createElement("span");
  nameEl.className = "account__name";
  nameEl.textContent = name;

  const idEl = document.createElement("span");
  idEl.className = "account__id";
  idEl.textContent = handle;

  meta.append(nameEl, idEl);
  els.account.append(meta);
  els.account.classList.toggle("account--avatar", Boolean(account.avatar));
  els.account.hidden = false;
}

/**
 * Display-only phone formatting, matching the hint examples
 * (+7 999 123-45-67 / +1 555 123-4567). Other numbers are left untouched.
 */
function formatPhone(value) {
  const raw = String(value || "").trim();
  const digits = raw.replace(/\D/g, "");
  if (digits.length < 7) return raw;

  if (digits.length === 11 && (digits[0] === "7" || digits[0] === "8")) {
    const area = digits.slice(1, 4);
    const mid = digits.slice(4, 7);
    const tail = digits.slice(7, 9);
    return `+7 ${area} ${mid}-${tail}-${digits.slice(9)}`;
  }

  if (digits.length === 11 && digits[0] === "1") {
    const area = digits.slice(1, 4);
    const mid = digits.slice(4, 7);
    return `+1 ${area} ${mid}-${digits.slice(7)}`;
  }

  // Unknown length/country: leave the number untouched rather than guess.
  return raw;
}

function renderDynamic() {
  if (els.qrStatus) {
    els.qrStatus.textContent =
      typeof ui.qrExpires === "number"
        ? t("qrValid", { seconds: ui.qrExpires })
        : t("qrWaiting");
  }

  if (els.phoneEcho) {
    els.phoneEcho.textContent = ui.phone ? formatPhone(ui.phone) : t("yourPhone");
  }

  if (els.passwordHint) {
    els.passwordHint.textContent = ui.passwordHint
      ? t("passwordHintWith", { hint: ui.passwordHint })
      : t("passwordHintText");
  }

  if (els.doneText) {
    els.doneText.textContent =
      ui.donePhase === "running"
        ? t("doneRunning")
        : ui.donePhase === "starting"
        ? t("doneStarting")
        : t("doneSaved");
  }

  if (els.hosted) {
    // ``data-platform`` is injected server-side so the footer is correct on the
    // very first paint; ``ui.platform`` from /api/state keeps it authoritative.
    const platform = ui.platform || els.hosted.dataset.platform;
    if (platform) {
      els.hosted.textContent = t("hosted", { platform });
    }
  }

  renderAccount();
}

function updateLangButtons() {
  const current = getLocale();
  els.langButtons.forEach((btn) => {
    const active = btn.dataset.lang === current;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function setLang(next, { persist = true } = {}) {
  setLocale(next, { persist });
  applyI18n();
  updateLangButtons();
  renderDynamic();
}

/* ------------------------------------------------------------------ */
/* Requests                                                            */
/* ------------------------------------------------------------------ */

async function api(path, { method = "GET", body } = {}) {
  const options = { method, headers: {} };

  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(withToken(path), options);
  let data = null;

  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }

  if (!response.ok) {
    const error = new Error((data && data.error) || `http_${response.status}`);
    error.status = response.status;
    error.data = data || {};
    throw error;
  }

  return data || {};
}

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */

function setLoading(button, loading) {
  button.classList.toggle("is-loading", loading);
  button.disabled = loading;
}

function showError(element, message) {
  element.textContent = message;
  element.hidden = false;
}

function clearError(element) {
  element.textContent = "";
  element.hidden = true;
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove("is-visible"), 2600);
}

function errText(error) {
  const code = error.data && error.data.error;
  if (code) {
    const text = t(`errors.${code}`);
    if (text !== `errors.${code}`) return text;
  }
  if (error.status === 429) return t("tooMany");
  if (!navigator.onLine) return t("offline");
  return t("genericError");
}

async function countdown(button, seconds) {
  setLoading(button, false);
  const original = button.dataset.i18n
    ? t(button.dataset.i18n)
    : button.textContent;
  button.disabled = true;

  for (let left = seconds; left > 0; left--) {
    button.textContent = t("countdown", { seconds: left });
    await sleep(1000);
  }

  button.textContent = button.dataset.i18n ? t(button.dataset.i18n) : original;
  button.disabled = false;
}

/* ------------------------------------------------------------------ */
/* Step navigation                                                     */
/* ------------------------------------------------------------------ */

function go(step) {
  els.panels.forEach((panel) => {
    panel.hidden = panel.dataset.panel !== step;
  });

  const active = els.panels.find((panel) => panel.dataset.panel === step);
  if (active) {
    active.style.animation = "none";
    void active.offsetWidth;
    active.style.animation = "";
  }
}

/* ------------------------------------------------------------------ */
/* API credentials                                                     */
/* ------------------------------------------------------------------ */

async function submitCredentials() {
  if (els.btnCredentials.disabled) return;
  clearError(els.errCredentials);

  const apiId = els.apiId.value.trim();
  const apiHash = els.apiHash.value.trim();

  if (!/^\d+$/.test(apiId)) {
    showError(els.errCredentials, t("errors.invalid_api_id"));
    return;
  }
  if (!/^[0-9a-fA-F]{32}$/.test(apiHash)) {
    showError(els.errCredentials, t("errors.invalid_api_hash"));
    return;
  }

  setLoading(els.btnCredentials, true);
  try {
    await api("/api/credentials", {
      method: "POST",
      body: { api_id: Number(apiId), api_hash: apiHash },
    });
    go("phone");
    els.phone.focus();
  } catch (error) {
    showError(els.errCredentials, errText(error));
  } finally {
    setLoading(els.btnCredentials, false);
  }
}

/* ------------------------------------------------------------------ */
/* Step 2 - phone                                                      */
/* ------------------------------------------------------------------ */

async function submitPhone() {
  if (els.btnPhone.disabled) return;
  clearError(els.errPhone);

  const phone = els.phone.value.trim();
  if (phone.replace(/\D/g, "").length < 5) {
    showError(els.errPhone, t("enterPhone"));
    return;
  }

  setLoading(els.btnPhone, true);
  try {
    const data = await api("/api/send_code", {
      method: "POST",
      body: { phone },
    });
    ui.phone = data.phone || phone;
    renderDynamic();
    resetOtp();
    go("code");
    els.otpInputs[0].focus();
  } catch (error) {
    if (error.data && error.data.error === "recaptcha_required") {
      showRecaptchaNotice();
    } else if (error.data && error.data.error === "flood_wait" && error.data.seconds) {
      showError(els.errPhone, t("floodWait", { seconds: error.data.seconds }));
    } else {
      showError(els.errPhone, errText(error));
    }
  } finally {
    setLoading(els.btnPhone, false);
  }
}

/* ------------------------------------------------------------------ */
/* reCAPTCHA                                                           */
/* ------------------------------------------------------------------ */

function showRecaptchaNotice() {
  clearError(els.errRecaptcha);
  go("recaptcha");
}

/* ------------------------------------------------------------------ */
/* QR login (no auth.sendCode, no reCAPTCHA)                           */
/* ------------------------------------------------------------------ */

function stopQrPolling() {
  if (qrPollTimer) {
    clearInterval(qrPollTimer);
    qrPollTimer = null;
  }
}

function applyQrInfo(qr) {
  if (!qr) return;

  if (qr.error) {
    const text = t(`errors.${qr.error}`);
    showError(els.errQr, text !== `errors.${qr.error}` ? text : t("errors.qr_failed"));
    return;
  }

  if (qr.url && qr.url !== qrUrl) {
    qrUrl = qr.url;
    qrFailures = 0;
    qrImageTimer = Date.now();
    els.qrImage.src = withToken(`/api/qr/image?ts=${qrImageTimer}`);
  }

  ui.qrExpires = typeof qr.expires_in === "number" ? qr.expires_in : null;
  renderDynamic();
}

async function startQrFlow(errorEl = els.errCredentials) {
  clearError(els.errQr);
  clearError(els.errRecaptcha);

  try {
    const data = await api("/api/qr/start", { method: "POST" });
    qrUrl = null;
    qrFailures = 0;
    go("qr");
    applyQrInfo(data.qr);
    startQrPolling();
  } catch (error) {
    if (error.data && error.data.error === "recaptcha_required") {
      showRecaptchaNotice();
    } else {
      showError(errorEl, errText(error));
    }
  }
}

function startQrPolling() {
  stopQrPolling();
  qrPollTimer = setInterval(pollQr, 1000);
}

async function pollQr() {
  try {
    const data = await api("/api/qr/status");
    qrFailures = 0;

    if (data.step === "password") {
      stopQrPolling();
      ui.passwordHint = data.password_hint || null;
      renderDynamic();
      go("password");
      els.password.focus();
      return;
    }

    if (data.step === "done") {
      stopQrPolling();
      onSuccess(data.account);
      return;
    }

    if (data.step !== "qr") {
      stopQrPolling();
      return;
    }

    applyQrInfo(data.qr);
  } catch (_) {
    // Once the login succeeds, the panel server is replaced by the userbot.
    qrFailures += 1;
    if (qrFailures >= 3) {
      stopQrPolling();
      onSuccess(null);
    }
  }
}

async function backFromQr() {
  stopQrPolling();
  qrUrl = null;
  try {
    await api("/api/qr/cancel", { method: "POST" });
  } catch (_) {
    /* ignore */
  }
  clearError(els.errQr);
  go("credentials");
}

/* ------------------------------------------------------------------ */
/* Step 3 - code                                                       */
/* ------------------------------------------------------------------ */

function otpValue() {
  return els.otpInputs.map((input) => input.value).join("");
}

function resetOtp() {
  els.otpInputs.forEach((input) => {
    input.value = "";
    input.disabled = false;
  });
  els.otp.classList.remove("is-error");
  clearError(els.errCode);
}

function setupOtp() {
  els.otpInputs.forEach((input, index) => {
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "").slice(-1);
      els.otp.classList.remove("is-error");

      if (input.value && index < els.otpInputs.length - 1) {
        els.otpInputs[index + 1].focus();
      }
      if (otpValue().length === 5) submitCode();
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !input.value && index > 0) {
        event.preventDefault();
        const previous = els.otpInputs[index - 1];
        previous.value = "";
        previous.focus();
      } else if (event.key === "ArrowLeft" && index > 0) {
        event.preventDefault();
        els.otpInputs[index - 1].focus();
      } else if (event.key === "ArrowRight" && index < els.otpInputs.length - 1) {
        event.preventDefault();
        els.otpInputs[index + 1].focus();
      } else if (event.key === "Enter") {
        event.preventDefault();
        submitCode();
      }
    });

    input.addEventListener("paste", (event) => {
      const digits = (event.clipboardData.getData("text") || "")
        .replace(/\D/g, "")
        .slice(0, 5);
      if (!digits) return;

      event.preventDefault();
      els.otpInputs.forEach((element, i) => {
        element.value = digits[i] || "";
      });
      els.otpInputs[Math.min(digits.length, els.otpInputs.length - 1)].focus();
      if (digits.length === 5) submitCode();
    });

    input.addEventListener("focus", () => input.select());
  });
}

async function submitCode() {
  if (els.btnCode.disabled) return;

  const code = otpValue();
  if (code.length !== 5) {
    showError(els.errCode, t("enterCode"));
    return;
  }

  clearError(els.errCode);
  setLoading(els.btnCode, true);
  els.otpInputs.forEach((input) => (input.disabled = true));

  try {
    const data = await api("/api/sign_in", { method: "POST", body: { code } });
    onSuccess(data.account);
  } catch (error) {
    const code = error.data && error.data.error;

    if (code === "2fa_required") {
      ui.passwordHint = error.data.hint || null;
      renderDynamic();
      els.password.value = "";
      go("password");
      els.password.focus();
      return;
    }

    if (code === "flood_wait" && error.data.seconds) {
      showError(els.errCode, t("floodWait", { seconds: error.data.seconds }));
      await countdown(els.btnCode, Number(error.data.seconds));
      return;
    }

    els.otpInputs.forEach((input) => (input.value = ""));
    els.otp.classList.remove("is-error");
    void els.otp.offsetWidth;
    els.otp.classList.add("is-error");
    showError(els.errCode, errText(error));
    if (!error.data || error.data.error !== "code_expired") {
      els.otpInputs[0].focus();
    }
  } finally {
    els.otpInputs.forEach((input) => (input.disabled = false));
    setLoading(els.btnCode, false);
  }
}

async function resendCode() {
  if (els.resend.disabled) return;
  clearError(els.errCode);

  const original = els.resend.dataset.i18n
    ? t(els.resend.dataset.i18n)
    : els.resend.textContent;
  els.resend.disabled = true;
  els.resend.textContent = t("sending");

  try {
    await api("/api/resend", { method: "POST" });
    resetOtp();
    toast(t("codeResent"));
    els.otpInputs[0].focus();
  } catch (error) {
    if (error.data && error.data.error === "recaptcha_required") {
      showRecaptchaNotice();
    } else if (error.data && error.data.error === "flood_wait" && error.data.seconds) {
      showError(els.errCode, t("floodResend", { seconds: error.data.seconds }));
    } else {
      showError(els.errCode, errText(error));
    }
  } finally {
    els.resend.textContent = els.resend.dataset.i18n
      ? t(els.resend.dataset.i18n)
      : original;
    els.resend.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/* Step 4 - 2FA password                                               */
/* ------------------------------------------------------------------ */

async function submitPassword() {
  if (els.btn2fa.disabled) return;
  clearError(els.err2fa);

  const password = els.password.value;
  if (!password) {
    showError(els.err2fa, t("enterPassword"));
    return;
  }

  setLoading(els.btn2fa, true);
  try {
    const data = await api("/api/2fa", { method: "POST", body: { password } });
    onSuccess(data.account);
  } catch (error) {
    if (error.data && error.data.error === "flood_wait" && error.data.seconds) {
      showError(els.err2fa, t("floodWait", { seconds: error.data.seconds }));
      await countdown(els.btn2fa, Number(error.data.seconds));
      return;
    }
    showError(els.err2fa, errText(error));
    els.password.select();
  } finally {
    setLoading(els.btn2fa, false);
  }
}

/* ------------------------------------------------------------------ */
/* Success                                                             */
/* ------------------------------------------------------------------ */

function onSuccess(account) {
  if (account) ui.account = account;
  ui.donePhase = "saved";
  go("done");
  renderDynamic();
  watchForRestart();
}

async function watchForRestart() {
  await sleep(1500);

  for (let attempt = 0; attempt < 90; attempt++) {
    try {
      await fetch(withToken("/api/health"), { cache: "no-store" });
    } catch (_) {
      ui.donePhase = "running";
      renderDynamic();
      return;
    }
    await sleep(1000);
  }

  ui.donePhase = "starting";
  renderDynamic();
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */

function onEnter(input, handler) {
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handler();
    }
  });
}

function bindEvents() {
  els.btnCredentials.addEventListener("click", submitCredentials);
  els.btnPhone.addEventListener("click", submitPhone);
  els.btnCode.addEventListener("click", submitCode);
  els.btn2fa.addEventListener("click", submitPassword);
  els.resend.addEventListener("click", resendCode);

  els.backCredentials.addEventListener("click", () => {
    clearError(els.errPhone);
    go("credentials");
  });
  els.backPhone.addEventListener("click", () => {
    clearError(els.errCode);
    go("phone");
  });
  els.btnRecaptchaQr.addEventListener("click", async () => {
    if (els.btnRecaptchaQr.disabled) return;
    clearError(els.errRecaptcha);
    setLoading(els.btnRecaptchaQr, true);
    try {
      await startQrFlow(els.errRecaptcha);
    } finally {
      setLoading(els.btnRecaptchaQr, false);
    }
  });
  els.backPhoneRecaptcha.addEventListener("click", () => {
    clearError(els.errRecaptcha);
    go("credentials");
  });
  els.btnQr.addEventListener("click", async () => {
    if (els.btnQr.disabled) return;
    clearError(els.errPhone);
    setLoading(els.btnQr, true);
    try {
      await startQrFlow(els.errPhone);
    } finally {
      setLoading(els.btnQr, false);
    }
  });
  els.backPhoneQr.addEventListener("click", backFromQr);

  // Enter confirms input on every text field (PC keyboards).
  onEnter(els.apiId, submitCredentials);
  onEnter(els.apiHash, submitCredentials);
  onEnter(els.phone, submitPhone);
  onEnter(els.password, submitPassword);

  els.langButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.lang !== getLocale()) setLang(btn.dataset.lang);
    });
  });

  setupOtp();
}

async function syncState({ focus = true } = {}) {
  let state = {};
  try {
    state = await api("/api/state");
  } catch (_) {
    return false;
  }

  if (state.platform) ui.platform = state.platform;
  ui.account = state.account || null;
  // Render shared/static bits (e.g. the "Hosted on …" footer) before the
  // step-specific branches, some of which never call renderDynamic().
  renderDynamic();

  if (state.step === "phone") {
    go("phone");
    if (focus) els.phone.focus();
  } else if (state.step === "qr") {
    ui.qrExpires =
      state.qr && typeof state.qr.expires_in === "number" ? state.qr.expires_in : null;
    renderDynamic();
    go("qr");
    applyQrInfo(state.qr);
    startQrPolling();
  } else if (state.step === "recaptcha") {
    showRecaptchaNotice();
  } else if (state.step === "code") {
    ui.phone = state.phone || null;
    renderDynamic();
    go("code");
    if (focus) els.otpInputs[0].focus();
  } else if (state.step === "password") {
    ui.passwordHint = state.password_hint || null;
    renderDynamic();
    go("password");
    if (focus) els.password.focus();
  } else if (state.step === "done") {
    ui.donePhase = "saved";
    go("done");
    renderDynamic();
    watchForRestart();
  } else {
    go("credentials");
    if (focus) els.apiId.focus();
  }

  return true;
}

async function boot() {
  bindEvents();

  setLang(detectLang(), { persist: false });

  const ok = await syncState({ focus: true });
  if (!ok) {
    go("credentials");
  }
}

boot();
