# JobScout – a Telegram bot for jobs, PhDs and research positions

JobScout is a Telegram bot that helps people find **jobs, PhD, research and postdoc positions** in Europe. It asks a few simple questions with buttons, searches the [Jooble](https://jooble.org) job API and sends the best matches, together with ready-made search links for LinkedIn, Indeed, EURAXESS and FindAPhD.

I built it because I was searching for PhD and research positions myself and wanted a faster, friendlier way to do it.

## Features

- Step-by-step search with buttons: **type** (jobs / PhD / research / postdoc) → **country** → **city** (or anywhere) → **field**
- Top 5 results from the Jooble API, with title, company, location and link
- One-tap buttons that open the same search on LinkedIn, Indeed, EURAXESS (research) and FindAPhD (PhD)
- **Anonymous feedback**: users can send a message to the owner without their name, and the owner can reply through the bot
- **Statistics for the owner** (`/stats`): number of users, returning users, searches and the most searched countries, cities and fields (no names or personal data)
- Memory that survives restarts (`PicklePersistence`)
- A bit of humour along the way ╰(*°▽°*)╯

## Commands

| Command | What it does |
|---|---|
| `/start` | Start a new search |
| `/stop` | Stop the current search |
| `/feedback` | Send anonymous feedback |
| `/myid` | Show your chat ID (to set the owner) |
| `/stats` | Bot statistics (owner only) |

## How to run it

1. Install Python 3.10+ and the requirements:
   ```
   pip install -r requirements.txt
   ```
2. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and get its token. Get a free API key from [Jooble](https://jooble.org/api/about).
3. Copy `.env.example` to `.env` and write your keys there. Send `/myid` to the bot once and put the number in `OWNER_CHAT_ID`.
4. Run:
   ```
   python jobscout_bot.py
   ```

## Built with

Python · [python-telegram-bot](https://python-telegram-bot.org) · Jooble REST API · requests

## Author

Fatemeh Arab Sadeghabadi – job results by [Jooble](https://jooble.org)
