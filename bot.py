import os
import json
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

ADMIN_ID = 7730300274
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "start_text": "سلام خوش اومدی من آرین‌ام میتونم کمکت کنم :",
    "profile_bio": "بیو پیش‌فرض",
    "force_join": [],
    "users": [],
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"خطا در ذخیره: {e}")


async def is_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    channels = settings.get("force_join", [])
    if not channels:
        return True
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(
                chat_id=ch, user_id=update.effective_user.id
            )
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    user_id = update.effective_user.id

    if user_id not in settings["users"]:
        settings["users"].append(user_id)
        save_settings(settings)

    if not await is_joined(update, context):
        channels = settings.get("force_join", [])
        buttons = []
        for ch in channels:
            buttons.append([
                InlineKeyboardButton(
                    f"عضویت در {ch}",
                    url=f"https://t.me/{ch.replace('@', '')}"
                )
            ])
        buttons.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
        await update.message.reply_text(
            "برای استفاده از ربات، اول تو کانال‌های زیر عضو شو :",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    keyboard = [
        ["🍎 اپل ایدی", "🔐 فیلتر شکن"],
    ]
    if user_id == ADMIN_ID:
        keyboard.append(["⚙️ پنل ادمین"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        settings["start_text"],
        reply_markup=reply_markup,
    )


# ---------- هندلر کیبورد (اصلاح‌شده) ----------
async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()  # حذف فاصله اضافی
    user_id = update.effective_user.id

    # چک با "in" به جای "==" تا مقاوم‌تر بشه
    if "اپل ایدی" in text:
        keyboard = [
            [
                InlineKeyboardButton("اپ استور", callback_data="apple_appstore"),
                InlineKeyboardButton("آیکلاد", callback_data="apple_icloud"),
            ],
        ]
        await update.message.reply_text(
            "اپل ایدی مد نظرت ؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif "فیلتر شکن" in text:
        keyboard = [[InlineKeyboardButton("ترکیه", callback_data="vpn_turkey")]]
        await update.message.reply_text(
            "سرور مد نظرت انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif "پنل ادمین" in text and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 آمار", callback_data="admin_stats")],
            [InlineKeyboardButton("✏️ ویرایش متن استارت", callback_data="admin_edit_start")],
            [InlineKeyboardButton("📝 ویرایش بیو", callback_data="admin_edit_bio")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔗 جوین اجباری", callback_data="admin_force_join")],
        ]
        await update.message.reply_text(
            "⚙️ پنل ادمین",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting = context.user_data.get("awaiting")

    if user_id != ADMIN_ID or not awaiting:
        return

    settings = load_settings()
    text = update.message.text

    if awaiting == "start_text":
        settings["start_text"] = text
        save_settings(settings)
        await update.message.reply_text("✅ متن استارت ذخیره شد.")
    elif awaiting == "profile_bio":
        settings["profile_bio"] = text
        save_settings(settings)
        await update.message.reply_text("✅ بیو ذخیره شد.")
    elif awaiting == "broadcast":
        count = 0
        for uid in settings["users"]:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                count += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ پیام به {count} کاربر ارسال شد.")
    elif awaiting == "force_join":
        if text.lower() == "clear":
            settings["force_join"] = []
            save_settings(settings)
            await update.message.reply_text("✅ همه کانال‌ها پاک شدن.")
        else:
            if text not in settings["force_join"]:
                settings["force_join"].append(text)
                save_settings(settings)
            await update.message.reply_text(f"✅ کانال {text} اضافه شد.")

    context.user_data["awaiting"] = None


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "apple_appstore":
        await query.edit_message_text("🍎 اپ استور\n\nبه‌زودی...")
    elif data == "apple_icloud":
        await query.edit_message_text("☁️ آیکلاد\n\nبه‌زودی...")
    elif data == "vpn_turkey":
        await query.edit_message_text("🇹🇷 سرور ترکیه\n\nبه‌زودی...")
    elif data == "check_join":
        if await is_joined(update, context):
            await query.edit_message_text("✅ عضویت تایید شد. حالا /start بزن.")
        else:
            await query.answer("هنوز عضو نشدی!", show_alert=True)
    elif data == "admin_stats" and user_id == ADMIN_ID:
        settings = load_settings()
        await query.edit_message_text(
            f"📊 آمار ربات\n\n"
            f"👥 تعداد کاربران: {len(settings['users'])}\n"
            f"🔗 کانال‌های جوین اجباری: {len(settings['force_join'])}"
        )
    elif data == "admin_edit_start" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "start_text"
        await query.edit_message_text("متن جدید استارت رو بفرست:")
    elif data == "admin_edit_bio" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "profile_bio"
        await query.edit_message_text("بیو جدید رو بفرست:")
    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "broadcast"
        await query.edit_message_text("پیام همگانی رو بفرست:")
    elif data == "admin_force_join" and user_id == ADMIN_ID:
        settings = load_settings()
        ch_list = "\n".join(settings["force_join"]) or "هیچ کانالی تنظیم نشده"
        await query.edit_message_text(
            f"🔗 کانال‌های جوین اجباری:\n\n{ch_list}\n\n"
            f"برای اضافه کردن، آیدی کانال رو با @ بفرست (مثلاً @mychannel)\n"
            f"برای پاک کردن همه، بنویس: clear"
        )
        context.user_data["awaiting"] = "force_join"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    print("ربات آنلاین شد...")
    app.run_polling()
