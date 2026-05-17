# TG VC Direct Stream Bot

Pyrogram + PyTgCalls music bot for Telegram group calls. It supports:

- `/play song name` for audio
- `/vplay song name` for video
- `/skip`
- `/end`
- `/pause`
- `/resume`

The bot resolves YouTube with `yt-dlp` using `download=False` and passes a direct stream URL to PyTgCalls. It does not intentionally download songs or save temp media files.

## Render Deploy

1. Push this folder to a public GitHub repository.
2. In Render, choose **New Web Service**.
3. Select **Public Git Repository** and paste your GitHub repo URL.
4. Render will use the `Dockerfile`.
5. Add these environment variables:

| Key | Value |
| --- | --- |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API hash |
| `BOT_TOKEN` | Bot token from @BotFather |
| `STRING_SESSION` | Pyrogram user session string |
| `OWNER_ID` | Your Telegram numeric user ID |

## Important

- Add both the bot and assistant user account to the Telegram group.
- Start a group voice chat before using `/play`.
- `STRING_SESSION` is a password-level secret. Never publish it in GitHub.
- Render free services can sleep, so the bot may disconnect after inactivity.

## Local Run

```bash
pip install -r requirements.txt
python -m app.bot
```

Use `.env.example` only as a guide. Set real values as environment variables.
