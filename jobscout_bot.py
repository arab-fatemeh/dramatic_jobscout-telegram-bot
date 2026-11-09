# ============================================================
#  JobScout Italia Bot  (Jooble version)
#  Asks the user for country, city and field, then sends
#  matching job positions from Jooble.
# ============================================================

import os
import asyncio
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv
from telegram import (Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand,
                      InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters,
    ApplicationHandlerStop, PicklePersistence,
)

# ------------------------------------------------------------
# 1) SECRET KEYS
#    They are read from a file called .env (never upload it!).
#    Copy .env.example to .env and write your own keys there.
# ------------------------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
JOOBLE_KEY = os.environ["JOOBLE_KEY"]

# Your own Telegram chat ID: anonymous feedback is sent here.
# To find it: run the bot, send /myid to it, and put the number in .env
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0"))

# ------------------------------------------------------------
# 2) Countries the bot offers
# ------------------------------------------------------------
COUNTRIES = [
    "Italy", "Germany", "France", "Spain",
    "Netherlands", "Austria", "Switzerland", "United Kingdom",
]

# Example cities shown when the bot asks for the city
CITY_EXAMPLES = {
    "Italy": "Padova, Milano",
    "Germany": "Berlin, Munich",
    "France": "Paris, Lyon",
    "Spain": "Madrid, Barcelona",
    "Netherlands": "Amsterdam, Delft",
    "Austria": "Vienna, Graz",
    "Switzerland": "Zurich, Geneva",
    "United Kingdom": "London, Manchester",
}

# Indeed has a different website for each country
INDEED_SITES = {
    "Italy": "it.indeed.com",
    "Germany": "de.indeed.com",
    "France": "fr.indeed.com",
    "Spain": "es.indeed.com",
    "Netherlands": "nl.indeed.com",
    "Austria": "at.indeed.com",
    "Switzerland": "ch.indeed.com",
    "United Kingdom": "uk.indeed.com",
}

# What the user is looking for (first buttons)
JOBS = "💼 Jobs"
PHD = "🎓 PhD"
RESEARCH = "🔬 Research"
POSTDOC = "🧪 Postdoc"
SEARCH_TYPES = [JOBS, PHD, RESEARCH, POSTDOC]

# Word added to the user's field in the search, for each type
KEYWORD_ADD = {JOBS: "", PHD: "PhD", RESEARCH: "research", POSTDOC: "postdoc"}

# How each type is written in the bot's messages
TYPE_NAME = {JOBS: "jobs", PHD: "PhD positions", RESEARCH: "research positions",
             POSTDOC: "postdoc positions"}

# Funny sentence before searching, for each type
FUNNY_LINE = {
    JOBS: "Being unemployed is hard, being lazy is harder... "
          "that's why we both use this bot 😎\nSo let me search for my lazy friend...",
    PHD: "More years of studying? You're braver than me 😎\nLet me search...",
    RESEARCH: "A future scientist! 🧠 Let me search...",
    POSTDOC: "Dr. Someone is here! 🎩 Let me search...",
}

# For research types, the city is not so important
ANYWHERE = "🌍 Anywhere in the country"

# Button texts
NEW_SEARCH = "🔍 New search"
STOP = "🛑 Stop"
FEEDBACK = "💌 Feedback"

# Buttons shown after a search ends
MENU_KEYBOARD = ReplyKeyboardMarkup([[NEW_SEARCH, FEEDBACK]], resize_keyboard=True)

# The "steps" of the conversation
ASK_TYPE, ASK_COUNTRY, ASK_CITY, ASK_FIELD, ASK_FEEDBACK = range(5)


def keywords(field, kind):
    """'hydrology' + PhD -> 'PhD hydrology'"""
    return f"{KEYWORD_ADD.get(kind, '')} {field}".strip()


def place(city, country):
    """'Rovigo', 'Italy' -> 'Rovigo, Italy'   |   '', 'Italy' -> 'Italy'"""
    return f"{city}, {country}" if city else country


# ------------------------------------------------------------
# 3) Function that searches Jooble for jobs
# ------------------------------------------------------------
def search_jobs(country, city, field, kind=JOBS):
    url = f"https://jooble.org/api/{JOOBLE_KEY}"
    body = {
        "keywords": keywords(field, kind),   # e.g. "PhD hydrology"
        "location": place(city, country),    # e.g. "Rovigo, Italy"
        "page": "1",
    }
    response = requests.post(url, json=body, timeout=15)
    response.raise_for_status()   # stop if Jooble returns an error
    jobs = response.json().get("jobs", [])
    return jobs[:5]               # send only the first 5


# ------------------------------------------------------------
# Buttons that open the same search on LinkedIn and Indeed
# (only links: the bot does not read these websites)
# ------------------------------------------------------------
def more_links(country, city, field, kind=JOBS):
    words = quote_plus(keywords(field, kind))
    linkedin = ("https://www.linkedin.com/jobs/search/"
                f"?keywords={words}&location={quote_plus(place(city, country))}")
    indeed = (f"https://{INDEED_SITES.get(country, 'www.indeed.com')}/jobs"
              f"?q={words}&l={quote_plus(city or country)}")
    rows = [
        [InlineKeyboardButton("🔎 More on LinkedIn", url=linkedin)],
        [InlineKeyboardButton("🔎 More on Indeed", url=indeed)],
    ]
    # research websites for PhD, research and postdoc searches
    if kind != JOBS:
        euraxess = f"https://euraxess.ec.europa.eu/jobs/search?keywords={quote_plus(field)}"
        rows.append([InlineKeyboardButton("🇪🇺 More on EURAXESS", url=euraxess)])
    if kind == PHD:
        findaphd = f"https://www.findaphd.com/phds/?Keywords={quote_plus(field)}"
        rows.append([InlineKeyboardButton("🎓 More on FindAPhD", url=findaphd)])
    return InlineKeyboardMarkup(rows)


# ------------------------------------------------------------
# Statistics (only numbers and search words, no names or user IDs)
# ------------------------------------------------------------
def record_search(context, country, city, field, found, kind=JOBS):
    stats = context.bot_data.setdefault("stats", {})
    stats["searches"] = stats.get("searches", 0) + 1
    if found == 0:
        stats["empty"] = stats.get("empty", 0) + 1
    for key, value in (("types", kind), ("countries", country),
                       ("cities", city or "Anywhere"), ("fields", field)):
        if key != "types":
            value = value.strip().title()       # "rovigo " -> "Rovigo"
        table = stats.setdefault(key, {})
        table[value] = table.get(value, 0) + 1
    print(f"🔍 Search: {kind} | {field} in {place(city, country)} -> {found} results")


def top(table, n=5):
    """Turns {'Padova': 3, 'Milano': 5} into '  Milano: 5\n  Padova: 3'."""
    items = sorted(table.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return "\n".join(f"  {name}: {num}" for name, num in items) or "  (none yet)"


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats -> only YOU (the owner) can see the bot's numbers."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return  # secret command: everyone else gets no answer
    starts = [d.get("start_count", 0) for d in context.application.user_data.values()]
    users = sum(1 for s in starts if s > 0)
    comebacks = sum(1 for s in starts if s > 1)
    stats = context.bot_data.get("stats", {})
    feedback = len(context.bot_data.get("feedback_senders", {}))

    await update.message.reply_text(
        "📊 JobScout stats\n\n"
        f"👥 People who used the bot: {users}\n"
        f"🔁 People who came back again: {comebacks}\n"
        f"▶️ Total starts: {sum(starts)}\n"
        f"🔍 Searches: {stats.get('searches', 0)}"
        f" (with no results: {stats.get('empty', 0)})\n"
        f"💌 Feedback messages: {feedback}\n\n"
        f"📂 What people search:\n{top(stats.get('types', {}))}\n\n"
        f"🌍 Top countries:\n{top(stats.get('countries', {}))}\n\n"
        f"🏙 Top cities:\n{top(stats.get('cities', {}))}\n\n"
        f"🎓 Top fields:\n{top(stats.get('fields', {}))}\n\n"
        "(Searches are counted from this version on.)"
    )


# ------------------------------------------------------------
# 4) Conversation steps
# ------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 0: /start or 'New search' -> greet and ask what they look for."""
    # forget the previous search, but keep counting how many times they started
    for key in ("kind", "country", "city"):
        context.user_data.pop(key, None)
    count = context.user_data.get("start_count", 0) + 1
    context.user_data["start_count"] = count
    if count == 1:
        print("👤 New user joined!")   # shows in the black window

    if count == 1:
        greeting = "Hi! 👋 I'm JobScout. I'll help you find jobs, PhDs and research positions."
    else:
        # 2nd time: "again", 3rd: "again and again", 4th: "again and again and again"...
        agains = " and ".join(["again"] * min(count - 1, 300))  # 300 = safety limit
        greeting = f"Ohhhh, I knew you would come back {agains} 😏\nPeople can't move on from me."

    buttons = [[JOBS, PHD], [RESEARCH, POSTDOC], [STOP]]
    await update.message.reply_text(
        f"{greeting}\n\nWhat are you looking for?",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )
    return ASK_TYPE


async def got_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: save jobs / PhD / research / postdoc, ask the country."""
    kind = update.message.text
    if kind not in SEARCH_TYPES:
        await update.message.reply_text("Please choose one of the buttons 🙂")
        return ASK_TYPE

    context.user_data["kind"] = kind
    buttons = [COUNTRIES[i:i + 2] for i in range(0, len(COUNTRIES), 2)]  # 2 per row
    buttons.append([STOP])
    await update.message.reply_text(
        "Which country are you looking in?",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )
    return ASK_COUNTRY


async def got_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: save the country, ask the city."""
    country = update.message.text
    if country not in COUNTRIES:
        await update.message.reply_text("Please choose a country from the buttons 🙂")
        return ASK_COUNTRY

    context.user_data["country"] = country
    await update.message.reply_text(
        f"Great, {country}! Which city? (e.g. {CITY_EXAMPLES.get(country, 'your city')})",
        reply_markup=ReplyKeyboardMarkup([[ANYWHERE], [STOP]], resize_keyboard=True),
    )
    return ASK_CITY


async def got_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: save the city ('' = anywhere), ask the field/major."""
    city = update.message.text
    context.user_data["city"] = "" if city == ANYWHERE else city
    await update.message.reply_text(
        "What's your major or field? (e.g. civil engineering, data analyst, hydrology)",
        reply_markup=ReplyKeyboardMarkup([[STOP]], resize_keyboard=True),
    )
    return ASK_FIELD


async def got_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4: search Jooble and send the results."""
    field = update.message.text
    kind = context.user_data.get("kind", JOBS)
    country = context.user_data["country"]
    city = context.user_data["city"]
    links = more_links(country, city, field, kind)

    # funny sentence before searching
    await update.message.reply_text(FUNNY_LINE[kind])
    await update.message.reply_text(
        f"🔎 Searching {field} {TYPE_NAME[kind]} in {place(city, country)}..."
    )

    try:
        # run the search without freezing the bot
        jobs = await asyncio.to_thread(search_jobs, country, city, field, kind)
        record_search(context, country, city, field, len(jobs), kind)
    except Exception as error:
        print("Search error:", error)
        await update.message.reply_text(
            "Sorry, something went wrong with the search 😕\n"
            "You can still look on these websites 👇",
            reply_markup=links,
        )
        await update.message.reply_text("Or tap 🔍 New search to try again.",
                                        reply_markup=MENU_KEYBOARD)
        return ConversationHandler.END

    if not jobs:
        await update.message.reply_text(
            f"No {TYPE_NAME[kind]} found on Jooble 😕 Try a bigger city or a broader field.\n"
            "Or tap a button: your search is already done there 👇",
            reply_markup=links,
        )
        await update.message.reply_text("Tap 🔍 New search whenever you want.",
                                        reply_markup=MENU_KEYBOARD)
        return ConversationHandler.END

    for job in jobs:
        title = job.get("title") or "No title"
        company = job.get("company") or "Unknown company"
        location = job.get("location") or ""
        link = job.get("link") or ""
        await update.message.reply_text(
            f"💼 {title}\n🏢 {company}\n📍 {location}\n🔗 {link}"
        )

    # same search on LinkedIn and Indeed
    await update.message.reply_text(
        "Want more? 👀\n"
        "Telegram rules don't let me open these websites for you 🙈\n"
        "but tap a button and your search is already done there 👇",
        reply_markup=links,
    )

    # funny sentence after the results
    await update.message.reply_text(
        "YAAAAAAAY! 🎉 Time to stop being lazy.\n"
        "Apply FAST, and good luck, you rock! 🤘\n\n"
        "Jobs by Jooble: https://jooble.org",
        reply_markup=MENU_KEYBOARD,
    )
    return ConversationHandler.END


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User taps Stop or sends /stop -> end the conversation."""
    for key in ("kind", "country", "city"):
        context.user_data.pop(key, None)
    await update.message.reply_text(
        "Ohhhh, I'm not dramatic, but I will cry because you stopped me 😢\n"
        "I always knew you would cheat on me with another bot...\n\n"
        "Saying goodbye is hard 😭 Take care!",
        reply_markup=MENU_KEYBOARD,
    )
    return ConversationHandler.END


async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User taps Feedback or sends /feedback -> ask for their message."""
    if not OWNER_CHAT_ID:
        await update.message.reply_text("Feedback isn't set up yet, sorry! 🙈",
                                        reply_markup=MENU_KEYBOARD)
        return ConversationHandler.END
    await update.message.reply_text(
        "💌 Tell me anything: your opinion, ideas, complaints, love letters...\n"
        "It's anonymous: your name is NOT sent, only your words.\n\n"
        "Write your message now 👇",
        reply_markup=ReplyKeyboardMarkup([[STOP]], resize_keyboard=True),
    )
    return ASK_FEEDBACK


async def got_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the feedback text to the owner, without the sender's name."""
    sent = await context.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=f"💌 New anonymous feedback:\n\n{update.message.text}\n\n"
             "(Swipe/reply to this message to answer)",
    )
    # remember who sent it (only the bot knows, you never see it)
    context.bot_data.setdefault("feedback_senders", {})[sent.message_id] = update.effective_chat.id
    await update.message.reply_text(
        "Received! 🥹 Thank you, your words make me a better bot.",
        reply_markup=MENU_KEYBOARD,
    )
    return ConversationHandler.END


async def owner_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When YOU reply to a feedback message, the bot sends your answer back."""
    replied_id = update.message.reply_to_message.message_id
    user_chat = context.bot_data.get("feedback_senders", {}).get(replied_id)
    if user_chat is None:
        return  # not a reply to a feedback message -> ignore here

    await context.bot.send_message(
        chat_id=user_chat,
        text=f"💬 Reply from JobScout:\n\n{update.message.text}",
    )
    await update.message.reply_text("✅ Your reply was sent!")
    raise ApplicationHandlerStop  # don't treat it as a normal message


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tells you your chat ID (needed once, for OWNER_CHAT_ID)."""
    await update.message.reply_text(f"Your chat ID is: {update.effective_chat.id}")


async def set_menu(app: Application):
    """Adds the commands to Telegram's menu button (bottom-left)."""
    await app.bot.set_my_commands([
        BotCommand("start", "Start a new job search"),
        BotCommand("stop", "Stop the current search"),
        BotCommand("feedback", "Send anonymous feedback"),
    ])


# ------------------------------------------------------------
# 5) Start the bot
# ------------------------------------------------------------
def main():
    # saves memory (start counters, feedback senders) in a file,
    # so nothing is forgotten when the bot restarts
    memory = PicklePersistence(filepath="bot_memory.pickle")
    app = (Application.builder().token(TELEGRAM_TOKEN)
           .persistence(memory).post_init(set_menu).build())

    start_triggers = [
        CommandHandler("start", start),
        MessageHandler(filters.Regex(f"^{NEW_SEARCH}$"), start),
    ]
    stop_triggers = [
        CommandHandler("stop", stop),
        CommandHandler("cancel", stop),
        MessageHandler(filters.Regex(f"^{STOP}$"), stop),
    ]
    feedback_triggers = [
        CommandHandler("feedback", ask_feedback),
        MessageHandler(filters.Regex(f"^{FEEDBACK}$"), ask_feedback),
    ]
    normal_text = (filters.TEXT & ~filters.COMMAND
                   & ~filters.Regex(f"^({STOP}|{NEW_SEARCH}|{FEEDBACK})$"))

    conversation = ConversationHandler(
        entry_points=start_triggers + feedback_triggers + stop_triggers,  # stop works anytime
        states={
            ASK_TYPE: [MessageHandler(normal_text, got_type)],
            ASK_COUNTRY: [MessageHandler(normal_text, got_country)],
            ASK_CITY: [MessageHandler(normal_text, got_city)],
            ASK_FIELD: [MessageHandler(normal_text, got_field)],
            ASK_FEEDBACK: [MessageHandler(normal_text, got_feedback)],
        },
        # can stop, restart or give feedback anytime
        fallbacks=stop_triggers + start_triggers + feedback_triggers,
        allow_reentry=True,
    )
    # your replies to feedback are checked first (group -1)
    app.add_handler(
        MessageHandler(filters.Chat(OWNER_CHAT_ID) & filters.REPLY
                       & filters.TEXT & ~filters.COMMAND, owner_reply),
        group=-1,
    )
    app.add_handler(CommandHandler("myid", my_id))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(conversation)

    print("✅ JobScout bot is running... (press Ctrl+C to stop)")
    app.run_polling()


if __name__ == "__main__":
    main()
