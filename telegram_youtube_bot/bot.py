import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from config import Config
from logging_config import setup_logging
from downloader import download_url
from cookie_utils import (
    cookies_available, last_modified, fetch_cookies_from_drive
)
from musicbrainzngs import search_recordings, set_useragent
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

setup_logging()
logger = logging.getLogger(__name__)

ADMIN_IDS = Config.ADMIN_IDS

# --- Conversation states ---
SEARCH, CHOOSE, MANUAL = range(3)

set_useragent("KMVPBot", "1.0", "https://vectorhost.net")

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in ADMIN_IDS:
            return await func(update, context)
        else:
            await update.message.reply_text("❌ Not authorized.")
    return wrapper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Welcome to KMVP Downloader Bot!\nSend a YouTube link to start.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/help - Show this help message\n"
        "/status - Show bot status\n"
        "/update_cookies - Update cookies.txt from Google Drive (admin)\n"
        "/set_log_level LEVEL - Change log level (admin)\n"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = f"KMVP Downloader Bot\nLog Level: {Config.LOG_LEVEL}\nCookies.txt: {'✅' if cookies_available() else '❌'}"
    if cookies_available():
        txt += f"\nLast updated: {last_modified()}"
    await update.message.reply_text(txt)

@admin_only
async def update_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok = fetch_cookies_from_drive()
    if ok:
        await update.message.reply_text("✅ Updated cookies.txt from Google Drive.")
    else:
        await update.message.reply_text("❌ Failed to update cookies.txt from Google Drive.")

@admin_only
async def set_log_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        level = context.args[0].upper()
        logging.getLogger().setLevel(getattr(logging, level, logging.INFO))
        await update.message.reply_text(f"Log level set to {level}")
    else:
        await update.message.reply_text("Usage: /set_log_level DEBUG|INFO|WARNING|ERROR")

async def start_download_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data['url'] = url
    # Extract title guess from URL with yt-dlp (metadata-only)
    ydl_opts = {'quiet': True, 'skip_download': True}
    from yt_dlp import YoutubeDL
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            guess_title = info.get("title", "")
        except Exception:
            guess_title = ""
    if not guess_title:
        guess_title = url  # fallback

    await update.message.reply_text(f"🔎 Searching MusicBrainz for: '{guess_title}'")
    results = musicbrainz_search(guess_title)
    return await present_metadata_options(update, context, results, guess_title, 1)

def musicbrainz_search(query, limit=5, offset=0):
    try:
        results = search_recordings(query, limit=limit, offset=offset)
        return results['recording-list']
    except Exception as e:
        logger.error(f"MusicBrainz search error: {e}")
        return []

async def present_metadata_options(update, context, results, original_query, page):
    if not results:
        keyboard = [
            [InlineKeyboardButton("Direct Search", callback_data='direct')],
            [InlineKeyboardButton("Manual Entry", callback_data='manual')],
        ]
        await update.message.reply_text(
            "No matches found. Choose another option:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['mb_offset'] = page
        context.user_data['mb_query'] = original_query
        return CHOOSE

    keyboard = []
    text = "🎶 *Select a matching track or choose another option:*\n\n"
    for idx, rec in enumerate(results, start=1):
        artist = rec['artist-credit'][0]['artist']['name'] if rec.get('artist-credit') else 'Unknown'
        title = rec.get('title', 'Unknown')
        album = rec['release-list'][0]['title'] if rec.get('release-list') else "Unknown"
        text += f"{idx}. {title} — {artist} [{album}]\n"
        keyboard.append([InlineKeyboardButton(f"{idx}", callback_data=f"choose_{idx-1}")])
    # Extra actions
    keyboard.append([InlineKeyboardButton("Try Again", callback_data='again')])
    keyboard.append([InlineKeyboardButton("Direct Search", callback_data='direct')])
    keyboard.append([InlineKeyboardButton("Manual Entry", callback_data='manual')])
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )
    context.user_data['mb_results'] = results
    context.user_data['mb_query'] = original_query
    context.user_data['mb_offset'] = page
    return CHOOSE

async def handle_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    results = context.user_data.get('mb_results', [])
    page = context.user_data.get('mb_offset', 1)
    original_query = context.user_data.get('mb_query', "")

    if user_choice.startswith("choose_"):
        idx = int(user_choice.replace("choose_", ""))
        chosen = results[idx]
        # Collect metadata
        artist = chosen['artist-credit'][0]['artist']['name'] if chosen.get('artist-credit') else 'Unknown'
        title = chosen.get('title', 'Unknown')
        album = chosen['release-list'][0]['title'] if chosen.get('release-list') else "YTD Tracks"
        metadata = {"title": title, "artist": artist, "album": album}
        context.user_data['metadata'] = metadata
        await query.edit_message_text(f"🎵 Using: {title} — {artist} [{album}]")
        return await finish_download(update, context)
    elif user_choice == "again":
        # fetch next page of results (offset by 5 each time)
        page = page + 1
        results = musicbrainz_search(original_query, limit=5, offset=(page-1)*5)
        return await present_metadata_options(update, context, results, original_query, page)
    elif user_choice == "direct":
        await query.edit_message_text("🔎 Please enter your search as `Title;Artist` or keywords.", parse_mode='Markdown')
        return SEARCH
    elif user_choice == "manual":
        await query.edit_message_text("✏️ Please enter the metadata as `Title;Artist`. The album will be set to 'YTD Tracks'.", parse_mode='Markdown')
        return MANUAL
    else:
        await query.edit_message_text("Invalid option.")
        return ConversationHandler.END

async def handle_direct_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    # Prefer Title;Artist but allow freeform
    if ";" in query:
        title, artist = [part.strip() for part in query.split(";", 1)]
        results = musicbrainz_search(f"{title} {artist}")
    else:
        results = musicbrainz_search(query)
    return await present_metadata_options(update, context, results, query, 1)

async def handle_manual_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if ";" in query:
        title, artist = [part.strip() for part in query.split(";", 1)]
    else:
        await update.message.reply_text("Invalid format. Use: Title;Artist")
        return MANUAL
    album = "YTD Tracks"
    metadata = {"title": title, "artist": artist, "album": album}
    context.user_data['metadata'] = metadata
    await update.message.reply_text(f"🎵 Manual metadata set: {title} — {artist} [{album}]")
    return await finish_download(update, context)

def safe_output_path(basename, directory="/input"):
    name, ext = os.path.splitext(basename)
    i = 1
    candidate = os.path.join(directory, basename)
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{name}-({i}){ext}")
        i += 1
    return candidate

async def finish_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.user_data['url']
    metadata = context.user_data['metadata']
    await update.message.reply_text(f"⬇️ Downloading and tagging: {metadata['title']} — {metadata['artist']}")

    # Download to temp, then tag, then move to /input/
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="ytmp3_")
    try:
        tmpfile = os.path.join(tmpdir, "track.mp3")
        # Use yt-dlp to download to temp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': tmpfile,
            'quiet': False,
            'no_warnings': False,
            'logger': logger,
            'overwrites': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'cookiefile': Config.COOKIES_FILE if Config.COOKIES_FILE else None,
        }
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])
        # Apply tags
        audio = MP3(tmpfile, ID3=EasyID3)
        audio['title'] = metadata['title']
        audio['artist'] = metadata['artist']
        audio['album'] = metadata['album']
        audio.save()
        # Move to /input/
        dest_basename = f"{metadata['artist']} - {metadata['title']}.mp3"
        dest_path = safe_output_path(dest_basename, "/input")
        shutil.move(tmpfile, dest_path)
        await update.message.reply_text("✅ Download and tagging complete. File sent to pipeline.")
    except Exception as e:
        logger.error(f"Download/tag error: {e}")
        await update.message.reply_text("❌ Download or tagging failed. Check logs.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return ConversationHandler.END

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import platform, datetime
    text = (
        f"🛠 *Admin Info*\n"
        f"Uptime: {datetime.datetime.now()}\n"
        f"Host: {platform.node()}\n"
        f"Python: {platform.python_version()}\n"
        f"Log Level: {Config.LOG_LEVEL}\n"
        f"Cookies.txt: {'✅' if cookies_available() else '❌'}"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏹ Operation cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'https?://(www\.)?youtube\.com/.*'), start_download_conversation)],
        states={
            CHOOSE: [CallbackQueryHandler(handle_choose)],
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direct_search)],
            MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_entry)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, ctx: update.message.reply_text("Cancelled."))]
    )
    app.add_handler(conv_handler)
    # Admin commands
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("update_cookies", update_cookies))
    app.add_handler(CommandHandler("set_log_level", set_log_level))
    app.run_polling()

if __name__ == "__main__":
    main()
