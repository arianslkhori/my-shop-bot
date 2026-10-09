import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍎 اپل ایدی", callback_data="apple_id")],
        [InlineKeyboardButton("💬 از من", callback_data="contact_me")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "سلامم من ارینم میخوایی چیکار کنیم ؟",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "apple_id":
        await query.edit_message_text("🍎 بخش اپل ایدی\n\nبه‌زودی...")
    elif query.data == "contact_me":
        await query.edit_message_text("💬 بخش ارتباط\n\nبه‌زودی...")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("ربات آنلاین شد...")
    app.run_polling()
