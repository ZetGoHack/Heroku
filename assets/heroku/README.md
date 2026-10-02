# Heroku artwork

Optional custom pictures used by the userbot. The code resolves them through
`heroku.utils.assets`, which looks in `assets/heroku/<name>` first and then in
the legacy `assets/<name>` location. **If a file is missing the media step is
simply skipped** – the text/action is still performed, nothing crashes.

Expected files and where they are used:

| File                   | Used for                                              |
|------------------------|-------------------------------------------------------|
| `heroku.png`           | content channel avatar (falls back to `assets/heroku.png`) |
| `heroku-ava.png`       | inline bot profile photo                              |
| `heroku_started.png`   | startup badge posted to the logs chat                 |
| `declined_jr.png`      | "declined join request" inline message                |
| `join_request.png`     | "join request" prompt sent by the bot                 |
| `updated.png`          | update notification                                   |
| `unit_alpha.png`       | autoupdate / backup setup prompts                     |
| `presets_cmd.png`      | `/presets` menu                                        |
| `heroku_cmd.png`       | heroku module info / help media                       |
| `heroku_installation.png` | installation guide                                  |
| `start_cmd.png`        | bot `/start` and `/profile` replies                   |
| `joined_jr.png`        | "joined channel" inline message                       |

Recommended: square PNG, at least 160×160 (Telegram rejects smaller avatars).
`heroku-ava.png` currently ships as a copy of the project logo.
