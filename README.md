<div align="center">
  <img src="https://github.com/hikariatama/assets/raw/master/1326-command-window-line-flat.webp" height="80">
  <h1>Heroku Userbot</h1>
  <p>Advanced Telegram userbot with enhanced security and modern features</p>
  
  <p>
    <a href="https://www.codacy.com/gh/coddrago/Heroku/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=coddrago/Heroku&amp;utm_campaign=Badge_Grade">
      <img src="https://app.codacy.com/project/badge/Grade/97e3ea868f9344a5aa6e4d874f83db14" alt="Codacy Grade">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/languages/code-size/coddrago/Heroku" alt="Code Size">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/issues-raw/coddrago/Heroku" alt="Open Issues">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/license/coddrago/Heroku" alt="License">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/commit-activity/m/coddrago/Heroku" alt="Commit Activity">
    </a>
    <br>
    <a href="#">
      <img src="https://img.shields.io/github/forks/coddrago/Heroku?style=flat" alt="Forks">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/stars/coddrago/Heroku" alt="Stars">
    </a>
    <a href="https://github.com/psf/black">
      <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style: Black">
    </a>
  </p>
</div>

---

## ⚠️ Security Notice

> **Important Security Advisory**  
> While Heroku implements extended security measures, installing modules from untrusted developers may still cause damage to your server/account.
> 
> **Recommendations:**
> - ✅ Download modules exclusively from official repositories or trusted developers
> - ❌ Do NOT install modules if unsure about their safety
> - ⚠️ Exercise caution with unknown commands (`.terminal`, `.eval`, `.ecpp`, etc.)

---

## 🚀 Installation

### Manual Installation (VPS/VDS Server)

```bash
apt update && apt install git python3 -y && \
git clone https://github.com/coddrago/Heroku && \
cd Heroku && \
pip install -r requirements.txt && \
python3 -m heroku
```

> **Note for VPS/VDS Users:**  
> Add `--proxy-pass` to enable SSH tunneling  
> Add `--no-web` for console-only setup  
> Add `--root` for root users (to avoid entering force_insecure)

### Additional Features

<details>
  <summary><b>🔒 Automatic Database Backuper</b></summary>
  <img src="https://user-images.githubusercontent.com/36935426/202905566-964d2904-f3ce-4a14-8f05-0e7840e1b306.png" width="400">
</details>

<details>
  <summary><b>👋 Welcome Installation Screens</b></summary>
  <img src="https://user-images.githubusercontent.com/36935426/202905720-6319993b-697c-4b09-a194-209c110c79fd.png" width="300">
  <img src="https://user-images.githubusercontent.com/36935426/202905746-2a511129-0208-4581-bb27-7539bd7b53c9.png" width="300">
</details>

---

## ✨ Key Features & Improvements

| Feature | Description |
|---------|-------------|
| 🆕 **Latest Telegram Layer** | Support for forums and newest Telegram features |
| 🔒 **Enhanced Security** | Native entity caching and targeted security rules |
| 🎨 **UI/UX Improvements** | Modern interface and user experience |
| 📦 **Core Modules** | Improved and new core functionality |
| ⏱ **Rapid Bug Fixes** | Faster resolution than FTG/GeekTG |
| 🔄 **Backward Compatibility** | Works with FTG, GeekTG and Hikka modules |
| ▶️ **Inline Elements** | Forms, galleries and lists support |

---

## 📋 Requirements

- **Python 3.9-3.13**
- **API Credentials** from [Telegram Apps](https://my.telegram.org/apps)

---

## 📚 Documentation

| Type | Link |
|------|------|
| **User Documentation** | [heroku-ub.xyz](https://heroku-ub.xyz/) |
| **Developer Docs** | [dev.heroku-ub.xyz](https://dev.heroku-ub.xyz/) |

---

## 💬 Support

[![Telegram Support](https://img.shields.io/badge/Telegram-Support_Group-2594cb?logo=telegram)](https://t.me/heroku_talks)

---

## ⚠️ Usage Disclaimer

> This project is provided as-is. The developer takes **NO responsibility** for:
> - Account bans or restrictions
> - Message deletions by Telegram
> - Security issues from scam modules
> - Session leaks from malicious modules
>
> **Security Recommendations:**
> - Enable `.api_fw_protection`
> - Avoid installing many modules at once
> - Review [Telegram's Terms](https://core.telegram.org/api/terms)

---

## 🙏 Acknowledgements

- [**Hikari**](https://gitlab.com/hikariatama) for Hikka (project foundation)
- [**Lonami**](https://t.me/lonami) for Telethon (Heroku-TL backbone)
