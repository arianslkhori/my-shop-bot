import os
import logging
import asyncpg
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

# ✅ آیدی عددی ادمین (خودت)
ADMIN_ID = 7730300274

# ---------- تنظیمات پیش‌فرض ----------
DEFAULT_SETTINGS = {
    "brand_name": "ArianShop",
    "support_id": "@ArianSupport",
    "card_number": "6037-9911-2233-4455",
    "card_owner": "آرین",
    "start_text": "سلام خوش اومدی به ArianShop 👋\n\nاز منوی زیر انتخاب کن :",
}


# ---------- اتصال به دیتابیس ----------
async def get_db():
    return await asyncpg.connect(DATABASE_URL)


async def init_db():
    conn = await get_db()
    try:
        # جدول کاربران
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # جدول تنظیمات
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # جدول سفارش‌ها
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                product TEXT,
                price BIGINT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # جدول پرداخت‌ها
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount BIGINT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # درج تنظیمات پیش‌فرض
        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                key, str(value)
            )
    finally:
        await conn.close()


async def get_setting(key):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row["value"] if row else DEFAULT_SETTINGS.get(key, "")
    finally:
        await conn.close()


async def set_setting(key, value):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
            key, str(value)
        )
    finally:
        await conn.close()


async def get_user(user_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return row
    finally:
        await conn.close()


async def add_user(user_id, username, first_name):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING",
            user_id, username, first_name
        )
    finally:
        await conn.close()


async def update_balance(user_id, amount):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            amount, user_id
        )
    finally:
        await conn.close()


# ⬇️ تکه بعدی رو دقیقاً اینجا پیست کن (بدون خط خالی اضافی)
# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""

    await add_user(user_id, username, first_name)

    brand = await get_setting("brand_name")
    start_text = await get_setting("start_text")

    keyboard = [
        ["🌐 خرید v2ray", "💻 خرید SSH"],
        ["🌍 خرید WireGuard", "♾️ افزایش موجودی"],
        ["💼 حساب کاربری", "📞 پشتیبانی"],
    ]
    if user_id == ADMIN_ID:
        keyboard.append(["⚙️ پنل ادمین"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(start_text, reply_markup=reply_markup)


# ---------- هندلر کیبورد ----------
async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # --- v2ray ---
    if "خرید v2ray" in text:
        keyboard = [
            [InlineKeyboardButton("یک ماهه - ۱۰۰ گیگ - ۱۰۰,۰۰۰ تومان", callback_data="buy_v2ray_1")],
            [InlineKeyboardButton("دو ماهه - ۲۰۰ گیگ - ۱۸۰,۰۰۰ تومان", callback_data="buy_v2ray_2")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.message.reply_text(
            "🌐 پلن‌های v2ray:\n\nیکی رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --- SSH ---
    elif "خرید SSH" in text:
        keyboard = [
            [InlineKeyboardButton("یک ماهه - ۵۰,۰۰۰ تومان", callback_data="buy_ssh_1")],
            [InlineKeyboardButton("دو ماهه - ۹۰,۰۰۰ تومان", callback_data="buy_ssh_2")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.message.reply_text(
            "💻 پلن‌های SSH:\n\nیکی رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --- WireGuard ---
    elif "خرید WireGuard" in text:
        keyboard = [
            [InlineKeyboardButton("یک ماهه - ۸۰,۰۰۰ تومان", callback_data="buy_wg_1")],
            [InlineKeyboardButton("دو ماهه - ۱۴۰,۰۰۰ تومان", callback_data="buy_wg_2")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.message.reply_text(
            "🌍 پلن‌های WireGuard:\n\nیکی رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --- افزایش موجودی ---
    elif "افزایش موجودی" in text:
        card = await get_setting("card_number")
        owner = await get_setting("card_owner")
        keyboard = [
            [InlineKeyboardButton("💳 ارسال رسید", callback_data="send_receipt")],
        ]
        await update.message.reply_text(
            f"💳 افزایش موجودی\n\n"
            f"مبلغ مورد نظر رو به کارت زیر واریز کن :\n\n"
            f"شماره کارت: `{card}`\n"
            f"به نام: {owner}\n\n"
            f"بعد از واریز، رسید رو بفرست :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # --- حساب کاربری ---
    elif "حساب کاربری" in text:
        user = await get_user(user_id)
        balance = user["balance"] if user else 0
        await update.message.reply_text(
            f"💼 حساب کاربری\n\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"💰 موجودی: {balance:,} تومان",
            parse_mode="Markdown",
        )

    # --- پشتیبانی ---
    elif "پشتیبانی" in text:
        support = await get_setting("support_id")
        await update.message.reply_text(
            f"📞 پشتیبانی\n\n"
            f"برای ارتباط با پشتیبانی به آیدی زیر پیام بده :\n\n"
            f"{support}"
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


# ⬇️ تکه بعدی رو دقیقاً اینجا پیست کن
# ---------- هندلر دکمه‌های شیشه‌ای ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    # --- بازگشت به منوی اصلی ---
    if data == "back_main":
        keyboard = [
            ["🌐 خرید v2ray", "💻 خرید SSH"],
            ["🌍 خرید WireGuard", "♾️ افزایش موجودی"],
            ["💼 حساب کاربری", "📞 پشتیبانی"],
        ]
        if user_id == ADMIN_ID:
            keyboard.append(["⚙️ پنل ادمین"])
        await query.message.reply_text(
            "منوی اصلی:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    # --- خرید v2ray ---
    elif data.startswith("buy_v2ray"):
        price = 100000 if data == "buy_v2ray_1" else 180000
        plan = "v2ray یک ماهه" if data == "buy_v2ray_1" else "v2ray دو ماهه"
        await handle_purchase(query, context, user_id, plan, price)

    # --- خرید SSH ---
    elif data.startswith("buy_ssh"):
        price = 50000 if data == "buy_ssh_1" else 90000
        plan = "SSH یک ماهه" if data == "buy_ssh_1" else "SSH دو ماهه"
        await handle_purchase(query, context, user_id, plan, price)

    # --- خرید WireGuard ---
    elif data.startswith("buy_wg"):
        price = 80000 if data == "buy_wg_1" else 140000
        plan = "WireGuard یک ماهه" if data == "buy_wg_1" else "WireGuard دو ماهه"
        await handle_purchase(query, context, user_id, plan, price)

    # --- ارسال رسید ---
    elif data == "send_receipt":
        context.user_data["awaiting"] = "receipt"
        await query.edit_message_text(
            "📸 لطفاً عکس رسید رو بفرست :"
        )

    # --- پنل ادمین: آمار ---
    elif data == "admin_stats" and user_id == ADMIN_ID:
        conn = await get_db()
        try:
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_balance = await conn.fetchval("SELECT COALESCE(SUM(balance), 0) FROM users")
            payments_count = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
        finally:
            await conn.close()
        await query.edit_message_text(
            f"📊 آمار ربات\n\n"
            f"👥 تعداد کاربران: {users_count}\n"
            f"💰 مجموع موجودی‌ها: {total_balance:,} تومان\n"
            f"✅ پرداخت‌های تایید شده: {payments_count}"
        )

    # --- پنل ادمین: کاربران ---
    elif data == "admin_users" and user_id == ADMIN_ID:
        conn = await get_db()
        try:
            rows = await conn.fetch("SELECT user_id, first_name, balance FROM users ORDER BY created_at DESC LIMIT 20")
        finally:
            await conn.close()
        text = "👥 آخرین ۲۰ کاربر:\n\n"
        for r in rows:
            text += f"🆔 `{r['user_id']}` - {r['first_name']} - {r['balance']:,} تومان\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    # --- پنل ادمین: تنظیم شماره کارت ---
    elif data == "admin_card" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "card_number"
        await query.edit_message_text("شماره کارت جدید رو بفرست :")

    # --- پنل ادمین: تنظیم پشتیبانی ---
    elif data == "admin_support" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "support_id"
        await query.edit_message_text("آیدی پشتیبانی جدید رو بفرست :")

    # --- پنل ادمین: ویرایش متن استارت ---
    elif data == "admin_start_text" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "start_text"
        await query.edit_message_text("متن استارت جدید رو بفرست :")

    # --- پنل ادمین: پیام همگانی ---
    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "broadcast"
        await query.edit_message_text("پیام همگانی رو بفرست :")

    # --- تایید پرداخت توسط ادمین ---
    elif data.startswith("approve_pay_") and user_id == ADMIN_ID:
        pay_id = int(data.split("_")[2])
        conn = await get_db()
        try:
            row = await conn.fetchrow("SELECT * FROM payments WHERE id = $1", pay_id)
            if row and row["status"] == "pending":
                await conn.execute("UPDATE payments SET status = 'approved' WHERE id = $1", pay_id)
                await update_balance(row["user_id"], row["amount"])
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text=f"✅ پرداخت شما تایید شد.\n💰 {row['amount']:,} تومان به موجودی اضافه شد."
                )
                await query.edit_message_caption(
                    caption=f"✅ پرداخت #{pay_id} تایید شد."
                )
        finally:
            await conn.close()

    # --- رد پرداخت توسط ادمین ---
    elif data.startswith("reject_pay_") and user_id == ADMIN_ID:
        pay_id = int(data.split("_")[2])
        conn = await get_db()
        try:
            row = await conn.fetchrow("SELECT * FROM payments WHERE id = $1", pay_id)
            if row and row["status"] == "pending":
                await conn.execute("UPDATE payments SET status = 'rejected' WHERE id = $1", pay_id)
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text="❌ متاسفانه رسید شما تایید نشد."
                )
                await query.edit_message_caption(caption=f"❌ پرداخت #{pay_id} رد شد.")
        finally:
            await conn.close()


# ---------- خرید محصول ----------
async def handle_purchase(query, context, user_id, plan, price):
    user = await get_user(user_id)
    balance = user["balance"] if user else 0

    if balance < price:
        await query.edit_message_text(
            f"❌ موجودی کافی نیست.\n\n"
            f"💰 موجودی شما: {balance:,} تومان\n"
            f"💵 قیمت: {price:,} تومان\n\n"
            f"اول موجودی رو افزایش بده."
        )
        return

    await update_balance(user_id, -price)
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO orders (user_id, product, price, status) VALUES ($1, $2, $3, 'paid')",
            user_id, plan, price
        )
    finally:
        await conn.close()

    support = await get_setting("support_id")
    await query.edit_message_text(
        f"✅ خرید موفق!\n\n"
        f"📦 محصول: {plan}\n"
        f"💰 مبلغ: {price:,} تومان\n\n"
        f"برای دریافت، به پشتیبانی پیام بده:\n{support}"
    )


# ⬇️ تکه بعدی رو دقیقاً اینجا پیست کن
# ---------- هندلر رسید و پیام‌های ادمین ----------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting = context.user_data.get("awaiting")

    # --- دریافت رسید از کاربر ---
    if awaiting == "receipt" and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data["awaiting"] = None

        # ثبت پرداخت
        conn = await get_db()
        try:
            pay_id = await conn.fetchval(
                "INSERT INTO payments (user_id, amount, status) VALUES ($1, $2, 'pending') RETURNING id",
                user_id, 0
            )
        finally:
            await conn.close()

        # ارسال به ادمین با دکمه تایید/رد
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید", callback_data=f"approve_pay_{pay_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_pay_{pay_id}"),
            ]
        ]
        user = await get_user(user_id)
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=(
                f"📸 رسید جدید\n\n"
                f"🆔 کاربر: `{user_id}`\n"
                f"👤 نام: {user['first_name'] if user else 'ناشناس'}\n\n"
                f"برای تایید، مبلغ رو به صورت متن ریپلای کن یا دکمه رو بزن."
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        await update.message.reply_text("✅ رسیدت برای ادمین ارسال شد. منتظر تایید باش.")
        return

    # --- پیام‌های ادمین (تنظیمات) ---
    if user_id == ADMIN_ID and awaiting:
        text = update.message.text

        if awaiting == "card_number":
            await set_setting("card_number", text)
            await update.message.reply_text("✅ شماره کارت ذخیره شد.")
        elif awaiting == "support_id":
            await set_setting("support_id", text)
            await update.message.reply_text("✅ آیدی پشتیبانی ذخیره شد.")
        elif awaiting == "start_text":
            await set_setting("start_text", text)
            await update.message.reply_text("✅ متن استارت ذخیره شد.")
        elif awaiting == "broadcast":
            conn = await get_db()
            try:
                rows = await conn.fetch("SELECT user_id FROM users")
            finally:
                await conn.close()
            count = 0
            for r in rows:
                try:
                    await context.bot.send_message(chat_id=r["user_id"], text=text)
                    count += 1
                except Exception:
                    pass
            await update.message.reply_text(f"✅ پیام به {count} کاربر ارسال شد.")

        context.user_data["awaiting"] = None
        return


# ---------- اجرا ----------
if __name__ == "__main__":
    import asyncio

    asyncio.get_event_loop().run_until_complete(init_db())

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))
    app.add_handler(MessageHandler(filters.PHOTO, message_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("ربات آنلاین شد...")
    app.run_polling()
    # ============================================
# پایان کد
# ============================================
