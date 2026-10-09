import os
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🍎 اپل ایدی", "🔐 فیلتر شکن"],
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    await update.message.reply_text(
        "سلام خوش اومدی من آرین‌ام میتونم کمکت کنم :",
        reply_markup=reply_markup,
    )

# ---------- دکمه‌های کیبورد ----------
async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🍎 اپل ایدی":
        keyboard = [
            [
                InlineKeyboardButton("اپ استور", callback_data="apple_appstore"),
                InlineKeyboardButton("آیکلاد", callback_data="apple_icloud"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "اپل ایدی مد نظرت ؟",
            reply_markup=reply_markup,
        )

    elif text == "🔐 فیلتر شکن":
        keyboard = [
            [InlineKeyboardButton("ترکیه", callback_data="vpn_turkey")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "سرور مد نظرت انتخاب کن :",
            reply_markup=reply_markup,
        )

# ---------- دکمه‌های شیشه‌ای ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "apple_appstore":
        await query.edit_message_text("🍎 اپ استور\n\nبه‌زودی...")
    elif query.data == "apple_icloud":
        await query.edit_message_text("☁️ آیکلاد\n\nبه‌زودی...")
    elif query.data == "vpn_turkey":
        await query.edit_message_text("🇹🇷 سرور ترکیه\n\nبه‌زودی...")

# ---------- اجرا ----------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("ربات آنلاین شد...")
    app.run_polling()
