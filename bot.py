import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
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
DATABASE_URL = os.environ.get("DATABASE_URL")

ADMIN_ID = 7730300274

DEFAULT_SETTINGS = {
    "brand_name": "ArianShop",
    "support_id": "@ArianSupport",
    "card_number": "6037-9911-2233-4455",
    "card_owner": "آرین",
    "start_text": "سلام خوش اومدی به ArianShop 👋\n\nاز منوی زیر انتخاب کن :",
}


def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                product TEXT,
                price BIGINT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount BIGINT DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for key, value in DEFAULT_SETTINGS.items():
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                (key, str(value))
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_setting(key):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else DEFAULT_SETTINGS.get(key, "")
    finally:
        cur.close()
        conn.close()


def set_setting(key, value):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s",
            (key, str(value), str(value))
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_user(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def add_user(user_id, username, first_name):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, username, first_name)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def update_balance(user_id, amount):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET balance = balance + %s WHERE user_id = %s",
            (amount, user_id)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
        # ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""

    add_user(user_id, username, first_name)
    start_text = get_setting("start_text")

    keyboard = [
        ["🍎 اپل ایدی", "🌐 خرید v2ray"],
        ["♾️ افزایش موجودی", "💼 حساب کاربری"],
        ["📞 پشتیبانی"],
    ]
    if user_id == ADMIN_ID:
        keyboard.append(["⚙️ پنل ادمین"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(start_text, reply_markup=reply_markup)


# ---------- هندلر کیبورد ----------
async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # --- اپل ایدی ---
    if "اپل ایدی" in text:
        keyboard = [
            [
                InlineKeyboardButton("🍎 اپ استور", callback_data="apple_appstore"),
                InlineKeyboardButton("☁️ آیکلاد", callback_data="apple_icloud"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.message.reply_text(
            "🍎 اپل ایدی مد نظرت کدومه ؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --- خرید v2ray ---
    elif "خرید v2ray" in text:
        keyboard = [
            [InlineKeyboardButton("یک ماهه - ۱۰۰ گیگ - ۱۰۰,۰۰۰ تومان", callback_data="buy_v2ray_1")],
            [InlineKeyboardButton("دو ماهه - ۲۰۰ گیگ - ۱۸۰,۰۰۰ تومان", callback_data="buy_v2ray_2")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.message.reply_text(
            "🌐 پلن‌های v2ray:\n\nیکی رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --- افزایش موجودی ---
    elif "افزایش موجودی" in text:
        context.user_data["awaiting"] = "amount"
        await update.message.reply_text(
            "💰 چقدر می‌خوای افزایش بدی؟\n\n"
            "مبلغ رو به تومان بفرست (فقط عدد).\n"
            "مثلاً: `50000`",
            parse_mode="Markdown",
        )

    # --- حساب کاربری ---
    elif "حساب کاربری" in text:
        user = get_user(user_id)
        if user:
            balance = user["balance"]
            first_name = user["first_name"] or "کاربر"
            username = user["username"]
            username_text = f"@{username}" if username else "ندارد"
        else:
            balance = 0
            first_name = "کاربر"
            username_text = "ندارد"

        text = (
            f"╭───────────────────╮\n"
            f"   💼  **حساب کاربری شما**\n"
            f"╰───────────────────╯\n\n"
            f"👤 **نام:** {first_name}\n"
            f"🔗 **یوزرنیم:** {username_text}\n"
            f"🆔 **آیدی عددی:** `{user_id}`\n\n"
            f"╭───────────────────╮\n"
            f"   💰  **موجودی شما**\n"
            f"╰───────────────────╯\n\n"
            f"**{balance:,}** تومان\n\n"
            f"✨ برای افزایش موجودی از منوی اصلی استفاده کن."
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    # --- پشتیبانی ---
    elif "پشتیبانی" in text:
        support = get_setting("support_id")
        await update.message.reply_text(
            f"📞 **پشتیبانی**\n\n"
            f"برای ارتباط با پشتیبانی به آیدی زیر پیام بده :\n\n"
            f"{support}",
            parse_mode="Markdown",
        )

    # --- پنل ادمین ---
    elif "پنل ادمین" in text and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 آمار", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 کاربران", callback_data="admin_users")],
            [InlineKeyboardButton("💰 تنظیم شماره کارت", callback_data="admin_card")],
            [InlineKeyboardButton("📞 تنظیم پشتیبانی", callback_data="admin_support")],
            [InlineKeyboardButton("✏️ ویرایش متن استارت", callback_data="admin_start_text")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
        ]
        await update.message.reply_text(
            "⚙️ پنل ادمین",
            reply_markup=InlineKeyboardMarkup(keyboard),
            )
   # ---------- هندلر دکمه‌های شیشه‌ای ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "back_main":
        keyboard = [
            ["🍎 اپل ایدی", "🌐 خرید v2ray"],
            ["♾️ افزایش موجودی", "💼 حساب کاربری"],
            ["📞 پشتیبانی"],
        ]
        if user_id == ADMIN_ID:
            keyboard.append(["⚙️ پنل ادمین"])
        await query.message.reply_text(
            "منوی اصلی:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    elif data == "apple_appstore":
        await query.edit_message_text(
            "🍎 **اپ استور**\n\n"
            "به‌زودی محصولات این بخش اضافه میشه...",
            parse_mode="Markdown",
        )

    elif data == "apple_icloud":
        await query.edit_message_text(
            "☁️ **آیکلاد**\n\n"
            "به‌زودی محصولات این بخش اضافه میشه...",
            parse_mode="Markdown",
        )

    elif data.startswith("buy_v2ray"):
        price = 100000 if data == "buy_v2ray_1" else 180000
        plan = "v2ray یک ماهه" if data == "buy_v2ray_1" else "v2ray دو ماهه"
        await handle_purchase(query, user_id, plan, price)

    elif data == "send_receipt":
        context.user_data["awaiting"] = "receipt"
        await query.edit_message_text("📸 لطفاً عکس رسید رو بفرست :")

    elif data == "admin_stats" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
            total_balance = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
            payments_count = cur.fetchone()[0]
        finally:
            cur.close()
            conn.close()
        await query.edit_message_text(
            f"📊 **آمار ربات**\n\n"
            f"👥 تعداد کاربران: {users_count}\n"
            f"💰 مجموع موجودی‌ها: {total_balance:,} تومان\n"
            f"✅ پرداخت‌های تایید شده: {payments_count}",
            parse_mode="Markdown",
        )

    elif data == "admin_users" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id, first_name, balance FROM users ORDER BY created_at DESC LIMIT 20")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        text = "👥 **آخرین ۲۰ کاربر:**\n\n"
        for r in rows:
            text += f"🆔 `{r[0]}` - {r[1]} - {r[2]:,} تومان\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "admin_card" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "card_number"
        await query.edit_message_text("شماره کارت جدید رو بفرست :")

    elif data == "admin_support" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "support_id"
        await query.edit_message_text("آیدی پشتیبانی جدید رو بفرست :")

    elif data == "admin_start_text" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "start_text"
        await query.edit_message_text("متن استارت جدید رو بفرست :")

    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "broadcast"
        await query.edit_message_text("پیام همگانی رو بفرست :")

    elif data.startswith("approve_pay_") and user_id == ADMIN_ID:
        pay_id = int(data.split("_")[2])
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id, amount, status FROM payments WHERE id = %s", (pay_id,))
            row = cur.fetchone()
            if row and row[2] == "pending":
                cur.execute("UPDATE payments SET status = 'approved' WHERE id = %s", (pay_id,))
                conn.commit()
                update_balance(row[0], row[1])
                await context.bot.send_message(
                    chat_id=row[0],
                    text=f"✅ پرداخت شما تایید شد.\n💰 {row[1]:,} تومان به موجودی اضافه شد."
                )
                await query.edit_message_caption(
                    caption=f"✅ پرداخت #{pay_id} تایید شد.\n💰 مبلغ: {row[1]:,} تومان"
                )
        finally:
            cur.close()
            conn.close()

    elif data.startswith("reject_pay_") and user_id == ADMIN_ID:
        pay_id = int(data.split("_")[2])
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id, status FROM payments WHERE id = %s", (pay_id,))
            row = cur.fetchone()
            if row and row[1] == "pending":
                cur.execute("UPDATE payments SET status = 'rejected' WHERE id = %s", (pay_id,))
                conn.commit()
                await context.bot.send_message(
                    chat_id=row[0],
                    text="❌ متاسفانه رسید شما تایید نشد."
                )
                await query.edit_message_caption(caption=f"❌ پرداخت #{pay_id} رد شد.")
        finally:
            cur.close()
            conn.close()


async def handle_purchase(query, user_id, plan, price):
    user = get_user(user_id)
    balance = user["balance"] if user else 0

    if balance < price:
        await query.edit_message_text(
            f"❌ **موجودی کافی نیست**\n\n"
            f"💰 موجودی شما: {balance:,} تومان\n"
            f"💵 قیمت: {price:,} تومان\n\n"
            f"اول موجودی رو افزایش بده.",
            parse_mode="Markdown",
        )
        return

    update_balance(user_id, -price)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO orders (user_id, product, price, status) VALUES (%s, %s, %s, 'paid')",
            (user_id, plan, price)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    support = get_setting("support_id")
    await query.edit_message_text(
        f"✅ **خرید موفق!**\n\n"
        f"📦 محصول: {plan}\n"
        f"💰 مبلغ: {price:,} تومان\n\n"
        f"برای دریافت، به پشتیبانی پیام بده:\n{support}",
        parse_mode="Markdown",
            )
# ---------- هندلر پیام‌ها (رسید، مبلغ، ادمین) ----------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting = context.user_data.get("awaiting")

    # --- دریافت مبلغ برای افزایش موجودی ---
    if awaiting == "amount":
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text("❌ لطفاً فقط عدد بفرست. مثلاً: `50000`", parse_mode="Markdown")
            return

        amount = int(text)
        if amount < 1000:
            await update.message.reply_text("❌ حداقل مبلغ ۱,۰۰۰ تومان است.")
            return

        context.user_data["awaiting"] = None
        context.user_data["pending_amount"] = amount

        card = get_setting("card_number")
        owner = get_setting("card_owner")

        keyboard = [
            [InlineKeyboardButton("💳 ارسال رسید", callback_data="send_receipt")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.message.reply_text(
            f"💳 **افزایش موجودی**\n\n"
            f"💰 مبلغ: **{amount:,}** تومان\n\n"
            f"مبلغ رو به کارت زیر واریز کن :\n\n"
            f"💳 شماره کارت:\n`{card}`\n\n"
            f"👤 به نام: {owner}\n\n"
            f"بعد از واریز، دکمه **ارسال رسید** رو بزن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    # --- دریافت عکس رسید ---
    if awaiting == "receipt" and update.message.photo:
        photo = update.message.photo[-1]
        amount = context.user_data.get("pending_amount", 0)
        context.user_data["awaiting"] = None
        context.user_data["pending_amount"] = None

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO payments (user_id, amount, status) VALUES (%s, %s, 'pending') RETURNING id",
                (user_id, amount)
            )
            pay_id = cur.fetchone()[0]
            conn.commit()
        finally:
            cur.close()
            conn.close()

        keyboard = [
            [
                InlineKeyboardButton("✅ تایید", callback_data=f"approve_pay_{pay_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_pay_{pay_id}"),
            ]
        ]
        user = get_user(user_id)
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=(
                f"📸 **رسید جدید**\n\n"
                f"🆔 کاربر: `{user_id}`\n"
                f"👤 نام: {user['first_name'] if user else 'ناشناس'}\n"
                f"💰 مبلغ درخواستی: **{amount:,}** تومان\n\n"
                f"برای تایید یا رد، دکمه رو بزن."
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            "✅ رسیدت برای ادمین ارسال شد.\nمنتظر تایید باش. 🙏"
        )
        return

    # --- پیام‌های ادمین ---
    if user_id == ADMIN_ID and awaiting:
        text = update.message.text

        if awaiting == "card_number":
            set_setting("card_number", text)
            await update.message.reply_text("✅ شماره کارت ذخیره شد.")
        elif awaiting == "support_id":
            set_setting("support_id", text)
            await update.message.reply_text("✅ آیدی پشتیبانی ذخیره شد.")
        elif awaiting == "start_text":
            set_setting("start_text", text)
            await update.message.reply_text("✅ متن استارت ذخیره شد.")
        elif awaiting == "broadcast":
            conn = get_db()
            cur = conn.cursor()
            try:
                cur.execute("SELECT user_id FROM users")
                rows = cur.fetchall()
            finally:
                cur.close()
                conn.close()
            count = 0
            for r in rows:
                try:
                    await context.bot.send_message(chat_id=r[0], text=text)
                    count += 1
                except Exception:
                    pass
            await update.message.reply_text(f"✅ پیام به {count} کاربر ارسال شد.")

        context.user_data["awaiting"] = None
        return
        # ---------- اجرا ----------
if __name__ == "__main__":
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))
    app.add_handler(MessageHandler(filters.PHOTO, message_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("ربات آنلاین شد...")
    app.run_polling()
        
