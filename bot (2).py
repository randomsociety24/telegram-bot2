import os, logging, base64, asyncio, httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# AQ. key এর জন্য সঠিক endpoint
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GEMINI_API_KEY}"

histories: dict[int, list] = {}

async def call_gemini(contents: list) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json={"contents": contents}
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    histories[update.effective_user.id] = []
    await update.message.reply_text(
        "👋 স্বাগতম! আমি Gemini AI Bot 🤖\n\n"
        "✅ যা করতে পারবে:\n"
        "• যেকোনো প্রশ্ন করো (বাংলা/ইংরেজি)\n"
        "• ছবি পাঠাও → আমি বিশ্লেষণ করব\n"
        "• /clear → নতুন কথোপকথন শুরু করো\n\n"
        "⚡ Powered by Google Gemini"
    )

async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    histories[update.effective_user.id] = []
    await update.message.reply_text("🗑️ পরিষ্কার! নতুন করে শুরু করো।")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    if uid not in histories:
        histories[uid] = []

    histories[uid].append({"role": "user", "parts": [{"text": text}]})
    thinking = await update.message.reply_text("⏳ ভাবছি...")

    try:
        reply = await call_gemini(histories[uid])
        histories[uid].append({"role": "model", "parts": [{"text": reply}]})
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i:i+4000])
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ সমস্যা হয়েছে, আবার চেষ্টা করো।")
    finally:
        await thinking.delete()

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    caption = update.message.caption or "এই ছবিটি বিশ্লেষণ করো বাংলায়।"
    thinking = await update.message.reply_text("🔍 ছবি দেখছি...")

    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        b64 = base64.standard_b64encode(photo_bytes).decode()

        contents = [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            {"text": caption}
        ]}]

        reply = await call_gemini(contents)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Photo error: {e}")
        await update.message.reply_text("❌ ছবি প্রসেস করতে সমস্যা হয়েছে।")
    finally:
        await thinking.delete()

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    logger.info("✅ Bot চালু হয়েছে!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
