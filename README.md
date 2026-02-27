# Audius Song of the Day Bot

A Discord bot built with [py-cord](https://pycord.dev/) that automatically selects and announces a daily **Song of the Day** from the [Audius](https://audius.co/) music platform. It posts rich embeds with artwork, artist info, genre, and play stats to configured guild channels and optionally DMs subscribers.

## Features

- **Daily Track Discovery** — Fetches a track from the Audius API every day and announces it with a rich embed (artwork, artist, genre, play/repost/favorite counts).
- **Persistent History** — All selected tracks are stored in a local SQLite database so users can browse past picks.
- **Per-Guild Configuration** — Server owners (or users with the **SOTD Bot Admin** role) can set a dedicated announcement channel and an optional mention role.
- **DM Subscriptions** — Users who install the bot to their account can subscribe to receive the SOTD directly in their DMs.
- **Global Error Handler** — Friendly error messages with unique error codes for easy troubleshooting.

## Commands

### Song of the Day

| Command | Description |
|---|---|
| `/sotd current` | Display the current Song of the Day with full track details. |
| `/sotd history` | Show the last 10 Song of the Day entries. |

### Guild Setup (Server Owner / SOTD Bot Admin)

| Command | Description |
|---|---|
| `/sotd set-channel <channel>` | Set the channel where the SOTD is posted for this server. |
| `/sotd set-role [role]` | Set an optional role to mention with each SOTD post (omit to clear). |

### DM Subscriptions (User-Installed)

| Command | Description |
|---|---|
| `/sotd subscribe` | Receive the daily Song of the Day in your DMs. |
| `/sotd unsubscribe` | Stop receiving the daily Song of the Day in your DMs. |

### Owner-Only

| Command | Description |
|---|---|
| `/config get <key>` | Get the value of a bot config key. |
| `/config set <key> <value>` | Set a bot config key. |
| `/config delete <key>` | Delete a bot config key. |
| `/check-latency` | Check the bot's latency. |

## Tech Stack

- **Python 3.14**
- **[py-cord](https://pycord.dev/)** — Discord API wrapper
- **SQLite** via [aiosqlite](https://github.com/omnilib/aiosqlite) — async local database
- **[aiohttp](https://docs.aiohttp.org/)** — HTTP client for Audius API calls
- **[Audius API](https://docs.audius.co/api/)** — music data source


## Links

- [Invite the Bot](https://discord.com/oauth2/authorize?client_id=1473099313080176774)
- [GitHub Repository](https://github.com/tobezdev/Audius-Song-of-the-Day)
- [Website](https://audius-sotd.tobezdev.com/) <!-- update with actual site URL when deployed -->
