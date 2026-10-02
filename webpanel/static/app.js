"use strict";

/* Heroku web panel — vanilla JS, no dependencies. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const STEP_ORDER = ["credentials", "phone", "code", "password"];

const ERROR_TEXT = {
  invalid_api_id: "API ID должен быть числом.",
  invalid_api_hash: "API HASH должен состоять из 32 hex-символов.",
  unknown_preset: "Неизвестный вариант ключей.",
  credentials_required: "Сначала укажите API-ключи.",
  invalid_phone: "Неверный номер. Укажите в формате +7 999 123-45-67.",
  phone_required: "Сначала укажите номер телефона.",
  recaptcha_required: "Telegram требует проверку reCAPTCHA.",
  recaptcha_token_required: "Пройдите проверку.",
  recaptcha_not_pending: "Проверка устарела. Запросите код заново.",
  recaptcha_failed: "Telegram отклонил проверку. Попробуйте войти по QR-коду.",
  invalid_code: "Неверный код. Проверьте и попробуйте снова.",
  qr_failed: "Не удалось начать вход по QR-коду. Попробуйте ещё раз.",
  qr_expired: "QR-код не удалось обновить. Начните вход заново.",
  qr_not_started: "QR-код не сгенерирован.",
  code_expired: "Код истёк. Запросите новый.",
  invalid_password: "Неверный облачный пароль.",
  send_code_failed: "Не удалось отправить код. Попробуйте позже.",
  sign_in_failed: "Не удалось войти. Попробуйте позже.",
};

const els = {
  steps: $("#steps"),
  panels: $$(".panel"),
  presets: $("#presets"),
  custom: $("#custom"),
  apiId: $("#api-id"),
  apiHash: $("#api-hash"),
  btnCredentials: $("#btn-credentials"),
  errCredentials: $("#err-credentials"),
  phone: $("#phone"),
  btnPhone: $("#btn-phone"),
  errPhone: $("#err-phone"),
  backCredentials: $("#back-credentials"),
  btnQr: $("#btn-qr"),
  methodHint: $("#method-hint"),
  errRecaptcha: $("#err-recaptcha"),
  btnRecaptchaKeys: $("#btn-recaptcha-keys"),
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
  toast: $("#toast"),
};

let presets = [];
let toastTimer = null;
let activeStep = "credentials";
let qrPollTimer = null;
let qrUrl = null;
let qrFailures = 0;
let qrImageTimer = 0;

/* ------------------------------------------------------------------ */
/* Requests                                                            */
/* ------------------------------------------------------------------ */

async function api(path, { method = "GET", body } = {}) {
  const options = { method, headers: {} };

  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(path, options);
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
  if (code && ERROR_TEXT[code]) return ERROR_TEXT[code];
  if (error.status === 429) return "Слишком много попыток. Подождите немного.";
  if (!navigator.onLine) return "Нет соединения с сервером.";
  return "Что-то пошло не так. Попробуйте ещё раз.";
}

async function countdown(button, seconds) {
  setLoading(button, false);
  const original = button.textContent;
  button.disabled = true;

  for (let left = seconds; left > 0; left--) {
    button.textContent = `Повторите через ${left} с`;
    await sleep(1000);
  }

  button.textContent = original;
  button.disabled = false;
}

/* ------------------------------------------------------------------ */
/* Step navigation                                                     */
/* ------------------------------------------------------------------ */

function go(step) {
  activeStep = step;

  els.panels.forEach((panel) => {
    panel.hidden = panel.dataset.panel !== step;
  });

  const active = els.panels.find((panel) => panel.dataset.panel === step);
  if (active) {
    active.style.animation = "none";
    void active.offsetWidth;
    active.style.animation = "";
  }

  updateSteps(step);
}

function updateSteps(step) {
  if (step === "done" || step === "qr" || step === "recaptcha") {
    els.steps.hidden = true;
    return;
  }

  els.steps.hidden = false;

  const current = STEP_ORDER.indexOf(step);
  $$(".step", els.steps).forEach((element) => {
    const index = STEP_ORDER.indexOf(element.dataset.step);
    if (index <= current) element.hidden = false;
    element.classList.toggle("is-active", index === current);
    element.classList.toggle("is-done", index < current);
  });
}

/* ------------------------------------------------------------------ */
/* Step 1 — API credentials                                            */
/* ------------------------------------------------------------------ */

function buildPresetRadio(preset, checked) {
  const label = document.createElement("label");
  label.className = "preset";

  const input = document.createElement("input");
  input.type = "radio";
  input.name = "preset";
  input.value = preset.id;
  input.checked = checked;

  input.addEventListener("change", () => {
    els.custom.hidden = input.value !== "custom";
    if (!els.custom.hidden) els.apiId.focus();
    clearError(els.errCredentials);
    updateMethodHint();
  });

  const body = document.createElement("span");
  body.className = "preset__body";

  const name = document.createElement("span");
  name.className = "preset__name";
  name.textContent = preset.name;

  const meta = document.createElement("span");
  meta.className = "preset__meta";
  meta.textContent = preset.api_id ? `api_id ${preset.api_id}` : preset.note || "";

  body.append(name, meta);
  label.append(input, body);
  return label;
}

async function loadPresets() {
  let data = { presets: [] };
  try {
    data = await api("/api/presets");
  } catch (_) {
    /* keep the custom option only */
  }

  presets = data.presets || [];
  els.presets.innerHTML = "";

  const custom = {
    id: "custom",
    name: "Свои ключи",
    api_id: null,
    note: "my.telegram.org",
  };

  [...presets, custom].forEach((preset, index) => {
    els.presets.append(buildPresetRadio(preset, index === 0));
  });
}

function isPresetApiId(apiId) {
  return Boolean(apiId) && presets.some((preset) => preset.api_id === apiId);
}

function updateMethodHint() {
  const selected = $('input[name="preset"]:checked', els.presets);
  if (!selected) {
    els.methodHint.textContent = "";
    return;
  }

  els.methodHint.textContent =
    selected.value === "custom"
      ? "Со своими ключами вход по номеру телефона или по QR-коду."
      : "С официальными ключами вход только по QR-коду.";
}

function prefillCredentials(state) {
  if (!state) {
    updateMethodHint();
    return;
  }

  if (state.api_id) {
    const match = presets.find((preset) => preset.api_id === state.api_id);
    if (match) {
      const radio = $(
        `input[name="preset"][value="${match.id}"]`,
        els.presets
      );
      if (radio) radio.checked = true;
      els.custom.hidden = true;
      updateMethodHint();
      return;
    }
    els.apiId.value = state.api_id;
  }

  const custom = $('input[name="preset"][value="custom"]', els.presets);
  if (custom) custom.checked = true;
  els.custom.hidden = false;
  updateMethodHint();
}

async function submitCredentials() {
  if (els.btnCredentials.disabled) return;
  clearError(els.errCredentials);

  const selected = $('input[name="preset"]:checked', els.presets);
  if (!selected) {
    showError(els.errCredentials, "Выберите способ подключения.");
    return;
  }

  const isCustom = selected.value === "custom";
  let body;
  if (isCustom) {
    const apiId = els.apiId.value.trim();
    const apiHash = els.apiHash.value.trim();

    if (!/^\d+$/.test(apiId)) {
      showError(els.errCredentials, ERROR_TEXT.invalid_api_id);
      return;
    }
    if (!/^[0-9a-fA-F]{32}$/.test(apiHash)) {
      showError(els.errCredentials, ERROR_TEXT.invalid_api_hash);
      return;
    }

    body = { api_id: Number(apiId), api_hash: apiHash };
  } else {
    body = { preset: selected.value };
  }

  setLoading(els.btnCredentials, true);
  try {
    await api("/api/credentials", { method: "POST", body });
    if (isCustom) {
      go("phone");
      els.phone.focus();
    } else {
      await startQrFlow(els.errCredentials);
    }
  } catch (error) {
    showError(els.errCredentials, errText(error));
  } finally {
    setLoading(els.btnCredentials, false);
  }
}

/* ------------------------------------------------------------------ */
/* Step 2 — phone                                                      */
/* ------------------------------------------------------------------ */

async function submitPhone() {
  if (els.btnPhone.disabled) return;
  clearError(els.errPhone);

  const phone = els.phone.value.trim();
  if (phone.replace(/\D/g, "").length < 5) {
    showError(els.errPhone, "Введите номер телефона.");
    return;
  }

  setLoading(els.btnPhone, true);
  try {
    const data = await api("/api/send_code", {
      method: "POST",
      body: { phone },
    });
    els.phoneEcho.textContent = data.phone || phone;
    resetOtp();
    go("code");
    els.otpInputs[0].focus();
  } catch (error) {
    if (error.data && error.data.error === "recaptcha_required") {
      showRecaptchaNotice();
    } else if (
      error.data &&
      error.data.error === "flood_wait" &&
      error.data.seconds
    ) {
      showError(
        els.errPhone,
        `Слишком много попыток. Повторите через ${error.data.seconds} с.`
      );
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
    showError(
      els.errQr,
      ERROR_TEXT[qr.error] || "Не удалось выполнить вход по QR-коду."
    );
    return;
  }

  if (qr.url && qr.url !== qrUrl) {
    qrUrl = qr.url;
    qrFailures = 0;
    qrImageTimer = Date.now();
    els.qrImage.src = `/api/qr/image?ts=${qrImageTimer}`;
  }

  els.qrStatus.textContent =
    typeof qr.expires_in === "number"
      ? `Код действителен ещё ${qr.expires_in} с`
      : "Ожидаем сканирование…";
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
      els.passwordHint.textContent = data.password_hint
        ? `Подсказка: ${data.password_hint}`
        : "Введите пароль двухфакторной аутентификации.";
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
  updateMethodHint();
}

/* ------------------------------------------------------------------ */
/* Step 3 — code                                                       */
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
    showError(els.errCode, "Введите 5-значный код.");
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
      els.passwordHint.textContent = error.data.hint
        ? `Подсказка: ${error.data.hint}`
        : "Введите пароль двухфакторной аутентификации.";
      els.password.value = "";
      go("password");
      els.password.focus();
      return;
    }

    if (code === "flood_wait" && error.data.seconds) {
      showError(
        els.errCode,
        `Слишком много попыток. Повторите через ${error.data.seconds} с.`
      );
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

  const original = els.resend.textContent;
  els.resend.disabled = true;
  els.resend.textContent = "Отправляем…";

  try {
    await api("/api/resend", { method: "POST" });
    resetOtp();
    toast("Код отправлен повторно");
    els.otpInputs[0].focus();
  } catch (error) {
    if (error.data && error.data.error === "recaptcha_required") {
      showRecaptchaNotice();
    } else if (
      error.data &&
      error.data.error === "flood_wait" &&
      error.data.seconds
    ) {
      showError(
        els.errCode,
        `Подождите ${error.data.seconds} с перед повторной отправкой.`
      );
    } else {
      showError(els.errCode, errText(error));
    }
  } finally {
    els.resend.textContent = original;
    els.resend.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/* Step 4 — 2FA password                                               */
/* ------------------------------------------------------------------ */

async function submitPassword() {
  if (els.btn2fa.disabled) return;
  clearError(els.err2fa);

  const password = els.password.value;
  if (!password) {
    showError(els.err2fa, "Введите пароль.");
    return;
  }

  setLoading(els.btn2fa, true);
  try {
    const data = await api("/api/2fa", { method: "POST", body: { password } });
    onSuccess(data.account);
  } catch (error) {
    if (error.data && error.data.error === "flood_wait" && error.data.seconds) {
      showError(
        els.err2fa,
        `Слишком много попыток. Повторите через ${error.data.seconds} с.`
      );
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
  go("done");

  if (account) {
    const name =
      [account.first_name, account.last_name].filter(Boolean).join(" ") ||
      "Аккаунт";
    const handle = account.username ? `@${account.username}` : `id ${account.id}`;

    els.account.innerHTML = "";
    const nameEl = document.createElement("span");
    nameEl.textContent = name;
    const idEl = document.createElement("span");
    idEl.className = "account__id";
    idEl.textContent = handle;
    els.account.append(nameEl, idEl);
    els.account.hidden = false;
  }

  watchForRestart();
}

async function watchForRestart() {
  await sleep(1500);

  for (let attempt = 0; attempt < 90; attempt++) {
    try {
      await fetch("/api/health", { cache: "no-store" });
    } catch (_) {
      els.doneText.textContent = "Юзербот запущен. Страницу можно закрыть.";
      return;
    }
    await sleep(1000);
  }

  els.doneText.textContent = "Юзербот запускается. Страницу можно закрыть.";
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */

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
  els.btnRecaptchaKeys.addEventListener("click", () => {
    clearError(els.errRecaptcha);
    go("credentials");
    updateMethodHint();
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

  els.phone.addEventListener("keydown", (event) => {
    if (event.key === "Enter") submitPhone();
  });
  els.password.addEventListener("keydown", (event) => {
    if (event.key === "Enter") submitPassword();
  });

  setupOtp();
}

async function boot() {
  bindEvents();
  await loadPresets();

  let state = {};
  try {
    state = await api("/api/state");
  } catch (_) {
    /* fall back to the credentials step */
  }

  prefillCredentials(state);

  if (state.step === "phone" && isPresetApiId(state.api_id)) {
    await startQrFlow(els.errCredentials);
  } else if (state.step === "phone") {
    go("phone");
    els.phone.focus();
  } else if (state.step === "qr") {
    go("qr");
    applyQrInfo(state.qr);
    startQrPolling();
  } else if (state.step === "recaptcha") {
    showRecaptchaNotice();
  } else if (state.step === "code") {
    els.phoneEcho.textContent = state.phone || "ваш номер";
    go("code");
    els.otpInputs[0].focus();
  } else if (state.step === "password") {
    els.passwordHint.textContent = state.password_hint
      ? `Подсказка: ${state.password_hint}`
      : "Введите пароль двухфакторной аутентификации.";
    go("password");
    els.password.focus();
  } else if (state.step === "done") {
    onSuccess(state.account);
  } else {
    go("credentials");
    els.apiId.focus();
  }
}

boot();
