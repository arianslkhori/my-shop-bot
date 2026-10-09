import os
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
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
    "support_id": "@ArianSupport",
    "card_number": "6037-9911-2233-4455",
    "card_owner": "آرین",
    "start_text": "سلام خوش اومدی 👋\n\nاز منوی زیر انتخاب کن :",
    "channel_lock": "off",
}


# ---------- وب‌سرور برای Render ----------
web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Bot is alive!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


# ---------- دیتابیس ----------
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
                banned BOOLEAN DEFAULT FALSE,
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
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                category TEXT,
                name TEXT,
                price BIGINT,
                description TEXT DEFAULT '',
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                product_name TEXT,
                price BIGINT,
                status TEXT DEFAULT 'paid',
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS force_join (
                id SERIAL PRIMARY KEY,
                channel TEXT UNIQUE
            )
        """)
        for key, value in DEFAULT_SETTINGS.items():
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                (key, str(value)),
            )
        # محصولات پیش‌فرض
        cur.execute("SELECT COUNT(*) FROM products")
        if cur.fetchone()[0] == 0:
            defaults = [
                ("v2ray", "یک ماهه - ۱۰۰ گیگ", 100000),
                ("v2ray", "دو ماهه - ۲۰۰ گیگ", 180000),
                ("apple", "اپ استور", 50000),
                ("apple", "آیکلاد", 80000),
                ("ssh", "SSH یک ماهه", 50000),
            ]
            for cat, name, price in defaults:
                cur.execute(
                    "INSERT INTO products (category, name, price) VALUES (%s, %s, %s)",
                    (cat, name, price),
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
            "INSERT INTO settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = %s",
            (key, str(value), str(value)),
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
            "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s) "
            "ON CONFLICT (user_id) DO NOTHING",
            (user_id, username, first_name),
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
            (amount, user_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ⬇️ تکه ۲ اینجا
# ---------- چک جوین اجباری ----------
async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("channel_lock") != "on":
        return True
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT channel FROM force_join")
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    if not rows:
        return True
    for r in rows:
        try:
            member = await context.bot.get_chat_member(
                chat_id=r[0], user_id=update.effective_user.id
            )
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""

    add_user(user_id, username, first_name)

    user = get_user(user_id)
    if user and user.get("banned"):
        await update.message.reply_text("🚫 شما از ربات بن شده‌اید.")
        return

    if not await check_join(update, context):
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT channel FROM force_join")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        buttons = []
        for r in rows:
            ch = r[0].replace("@", "")
            buttons.append([InlineKeyboardButton(f"📢 عضویت در @{ch}", url=f"https://t.me/{ch}")])
        buttons.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join_btn")])
        await update.message.reply_text(
            "برای استفاده از ربات، اول تو کانال‌های زیر عضو شو :",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    start_text = get_setting("start_text")
    keyboard = [
        ["🛒 خرید محصولات", "💼 حساب کاربری"],
        ["💰 افزایش موجودی", "📞 پشتیبانی"],
    ]
    if user_id == ADMIN_ID:
        keyboard.append(["⚙️ پنل ادمین"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(start_text, reply_markup=reply_markup)


# ---------- هندلر کیبورد ----------
async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if context.user_data.get("awaiting"):
        return

    if text == "🛒 خرید محصولات":
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT DISTINCT category FROM products WHERE active = TRUE")
            cats = [r[0] for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()
        if not cats:
            await update.message.reply_text("❌ فعلاً محصولی موجود نیست.")
            return
        cat_names = {
            "v2ray": "🌐 v2ray",
            "apple": "🍎 اپل ایدی",
            "ssh": "💻 SSH",
        }
        keyboard = []
        for c in cats:
            keyboard.append([InlineKeyboardButton(cat_names.get(c, c), callback_data=f"cat_{c}")])
        await update.message.reply_text(
            "🛒 **دسته‌بندی محصولات**\n\nیه دسته رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif text == "💼 حساب کاربری":
        user = get_user(user_id)
        if user:
            balance = user["balance"]
            first_name = user["first_name"] or "کاربر"
        else:
            balance = 0
            first_name = "کاربر"

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = %s", (user_id,))
            orders_count = cur.fetchone()[0]
        finally:
            cur.close()
            conn.close()

        msg = (
            f"💼 **حساب کاربری**\n\n"
            f"👤 نام: {first_name}\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"💰 موجودی: **{balance:,}** تومان\n"
            f"📦 تعداد خرید: {orders_count}"
        )
        keyboard = [
            [InlineKeyboardButton("📋 تاریخچه خرید", callback_data="my_orders")],
        ]
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif text == "💰 افزایش موجودی":
        keyboard = [
            [
                InlineKeyboardButton("۵۰,۰۰۰ تومان", callback_data="amt_50000"),
                InlineKeyboardButton("۱۰۰,۰۰۰ تومان", callback_data="amt_100000"),
            ],
            [
                InlineKeyboardButton("۲۰۰,۰۰۰ تومان", callback_data="amt_200000"),
                InlineKeyboardButton("۵۰۰,۰۰۰ تومان", callback_data="amt_500000"),
            ],
            [InlineKeyboardButton("۱,۰۰۰,۰۰۰ تومان", callback_data="amt_1000000")],
            [
                InlineKeyboardButton("✏️ مبلغ دلخواه", callback_data="amt_custom"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
            ],
        ]
        await update.message.reply_text(
            "💰 **افزایش موجودی**\n\nمبلغ مورد نظرت رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif text == "📞 پشتیبانی":
        support = get_setting("support_id")
        await update.message.reply_text(
            f"📞 **پشتیبانی**\n\n"
            f"برای ارتباط با پشتیبانی به آیدی زیر پیام بده :\n\n"
            f"{support}",
            parse_mode="Markdown",
        )

    elif text == "⚙️ پنل ادمین" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 آمار کامل", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users_menu")],
            [InlineKeyboardButton("📦 مدیریت محصولات", callback_data="admin_products_menu")],
            [InlineKeyboardButton("💳 پرداخت‌های در انتظار", callback_data="admin_pending")],
            [InlineKeyboardButton("📋 آخرین سفارشات", callback_data="admin_orders")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔗 جوین اجباری", callback_data="admin_forcejoin_menu")],
            [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings_menu")],
        ]
        await update.message.reply_text(
            "⚙️ **پنل ادمین**\n\nیه گزینه رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


# ⬇️ تکه ۳ اینجا
# ---------- هندلر دکمه‌های شیشه‌ای ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    # --- بازگشت ---
    if data == "back_main":
        context.user_data["awaiting"] = None
        context.user_data["pending_amount"] = None
        keyboard = [
            ["🛒 خرید محصولات", "💼 حساب کاربری"],
            ["💰 افزایش موجودی", "📞 پشتیبانی"],
        ]
        if user_id == ADMIN_ID:
            keyboard.append(["⚙️ پنل ادمین"])
        await query.message.reply_text(
            "منوی اصلی:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    elif data == "check_join_btn":
        if await check_join(update, context):
            await query.edit_message_text("✅ عضویت تایید شد. حالا /start بزن.")
        else:
            await query.answer("❌ هنوز عضو نشدی!", show_alert=True)

    # --- دسته‌بندی محصولات ---
    elif data.startswith("cat_"):
        cat = data.replace("cat_", "")
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, price FROM products WHERE category = %s AND active = TRUE",
                (cat,),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        if not rows:
            await query.edit_message_text("❌ محصولی تو این دسته نیست.")
            return
        keyboard = []
        for r in rows:
            keyboard.append([
                InlineKeyboardButton(f"{r[1]} - {r[2]:,} تومان", callback_data=f"buy_{r[0]}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])
        await query.edit_message_text(
            f"📦 محصولات **{cat}**:\n\nیکی رو انتخاب کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # --- خرید محصول ---
    elif data.startswith("buy_"):
        prod_id = int(data.split("_")[1])
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT name, price FROM products WHERE id = %s AND active = TRUE", (prod_id,))
            row = cur.fetchone()
        finally:
            cur.close()
            conn.close()
        if not row:
            await query.edit_message_text("❌ محصول پیدا نشد.")
            return
        name, price = row
        await handle_purchase(query, user_id, name, price)

    # --- تاریخچه خرید ---
    elif data == "my_orders":
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT product_name, price, created_at FROM orders WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
                (user_id,),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        if not rows:
            await query.edit_message_text("📋 هنوز خریدی نداری.")
            return
        text = "📋 **آخرین ۱۰ خرید شما:**\n\n"
        for r in rows:
            text += f"📦 {r[0]} - {r[1]:,} تومان\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    # --- مبالغ افزایش موجودی ---
    elif data == "amt_custom":
        context.user_data["awaiting"] = "amount"
        await query.edit_message_text(
            "✏️ مبلغ مورد نظرت رو به تومان بفرست (فقط عدد).\nمثلاً: `50000`",
            parse_mode="Markdown",
        )

    elif data.startswith("amt_"):
        amount = int(data.split("_")[1])
        context.user_data["pending_amount"] = amount
        await show_card(query, amount)

    elif data == "send_receipt":
        context.user_data["awaiting"] = "receipt"
        await query.edit_message_text("📸 لطفاً عکس رسید رو بفرست :")

    # --- پنل ادمین: آمار ---
    elif data == "admin_stats" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
            total_balance = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
            approved_pays = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
            pending_pays = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM orders")
            orders_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(price), 0) FROM orders")
            total_sales = cur.fetchone()[0]
        finally:
            cur.close()
            conn.close()
        await query.edit_message_text(
            f"📊 **آمار کامل ربات**\n\n"
            f"👥 کاربران: {users_count}\n"
            f"💰 مجموع موجودی: {total_balance:,} تومان\n"
            f"📦 سفارشات: {orders_count}\n"
            f"💵 مجموع فروش: {total_sales:,} تومان\n"
            f"✅ پرداخت‌های تایید شده: {approved_pays}\n"
            f"⏳ پرداخت‌های در انتظار: {pending_pays}",
            parse_mode="Markdown",
        )

    # --- پنل ادمین: منوی کاربران ---
    elif data == "admin_users_menu" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📋 لیست کاربران", callback_data="admin_users")],
            [InlineKeyboardButton("🔍 جستجو با آیدی", callback_data="admin_find_user")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")],
        ]
        await query.edit_message_text(
            "👥 **مدیریت کاربران**",
            reply_markup=InlineKeyboardMarkup(keyboard),
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

    elif data == "admin_find_user" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "find_user"
        await query.edit_message_text("🆔 آیدی عددی کاربر رو بفرست :")

    # --- پنل ادمین: منوی محصولات ---
    elif data == "admin_products_menu" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📋 لیست محصولات", callback_data="admin_products")],
            [InlineKeyboardButton("➕ افزودن محصول", callback_data="admin_add_product")],
            [InlineKeyboardButton("🗑 حذف محصول", callback_data="admin_del_product")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")],
        ]
        await query.edit_message_text(
            "📦 **مدیریت محصولات**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "admin_products" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, category, name, price, active FROM products ORDER BY id")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        text = "📦 **لیست محصولات:**\n\n"
        for r in rows:
            status = "✅" if r[4] else "❌"
            text += f"{status} `{r[0]}` | {r[1]} | {r[2]} | {r[3]:,}\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "admin_add_product" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "add_product"
        await query.edit_message_text(
            "➕ **افزودن محصول**\n\n"
            "این فرمت رو بفرست:\n"
            "`دسته | اسم | قیمت`\n\n"
            "مثال:\n"
            "`v2ray | سه ماهه ۳۰۰ گیگ | 250000`"
        )

    elif data == "admin_del_product" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "del_product"
        await query.edit_message_text(
            "🗑 **حذف محصول**\n\n"
            "آیدی محصول رو بفرست (از لیست محصولات):"
        )

    # --- پنل ادمین: پرداخت‌های در انتظار ---
    elif data == "admin_pending" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, user_id, amount FROM payments WHERE status = 'pending' ORDER BY created_at DESC LIMIT 20")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        if not rows:
            await query.edit_message_text("✅ هیچ پرداخت در انتظاری نیست.")
            return
        text = "⏳ **پرداخت‌های در انتظار:**\n\n"
        for r in rows:
            text += f"🆔 `{r[0]}` | کاربر `{r[1]}` | {r[2]:,} تومان\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    # --- پنل ادمین: سفارشات ---
    elif data == "admin_orders" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id, product_name, price FROM orders ORDER BY created_at DESC LIMIT 20")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        text = "📋 **آخرین ۲۰ سفارش:**\n\n"
        for r in rows:
            text += f"🆔 `{r[0]}` | {r[1]} | {r[2]:,}\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    # --- پنل ادمین: پیام همگانی ---
    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "broadcast"
        await query.edit_message_text("📢 پیام همگانی رو بفرست :")

    # --- پنل ادمین: جوین اجباری ---
    elif data == "admin_forcejoin_menu" and user_id == ADMIN_ID:
        status = get_setting("channel_lock")
        keyboard = [
            [InlineKeyboardButton(f"{'🟢 روشن' if status == 'on' else '🔴 خاموش'}", callback_data="admin_toggle_lock")],
            [InlineKeyboardButton("➕ افزودن کانال", callback_data="admin_add_channel")],
            [InlineKeyboardButton("🗑 حذف همه کانال‌ها", callback_data="admin_clear_channels")],
            [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="admin_list_channels")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")],
        ]
        await query.edit_message_text(
            f"🔗 **جوین اجباری** (وضعیت: {status})\n\n"
            "کانال‌های عضو اجباری رو مدیریت کن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "admin_toggle_lock" and user_id == ADMIN_ID:
        current = get_setting("channel_lock")
        new = "off" if current == "on" else "on"
        set_setting("channel_lock", new)
        await query.edit_message_text(f"✅ وضعیت جوین اجباری: **{new}**", parse_mode="Markdown")

    elif data == "admin_add_channel" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "add_channel"
        await query.edit_message_text("📢 آیدی کانال رو با @ بفرست (مثلاً `@mychannel`):")

    elif data == "admin_clear_channels" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM force_join")
            conn.commit()
        finally:
            cur.close()
            conn.close()
        await query.edit_message_text("✅ همه کانال‌ها پاک شدن.")

    elif data == "admin_list_channels" and user_id == ADMIN_ID:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT channel FROM force_join")
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        if not rows:
            await query.edit_message_text("📋 هیچ کانالی تنظیم نشده.")
            return
        text = "📋 **کانال‌های جوین اجباری:**\n\n"
        for r in rows:
            text += f"📢 {r[0]}\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    # --- پنل ادمین: تنظیمات ---
    elif data == "admin_settings_menu" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("💰 تغییر شماره کارت", callback_data="admin_card")],
            [InlineKeyboardButton("📞 تغییر آیدی پشتیبانی", callback_data="admin_support")],
            [InlineKeyboardButton("✏️ تغییر متن استارت", callback_data="admin_start_text")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")],
        ]
        await query.edit_message_text(
            "⚙️ **تنظیمات**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "admin_card" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "card_number"
        await query.edit_message_text("💰 شماره کارت جدید رو بفرست :")

    elif data == "admin_support" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "support_id"
        await query.edit_message_text("📞 آیدی پشتیبانی جدید رو بفرست :")

    elif data == "admin_start_text" and user_id == ADMIN_ID:
        context.user_data["awaiting"] = "start_text"
        await query.edit_message_text("✏️ متن استارت جدید رو بفرست :")

    elif data == "admin_back" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 آمار کامل", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users_menu")],
            [InlineKeyboardButton("📦 مدیریت محصولات", callback_data="admin_products_menu")],
            [InlineKeyboardButton("💳 پرداخت‌های در انتظار", callback_data="admin_pending")],
            [InlineKeyboardButton("📋 آخرین سفارشات", callback_data="admin_orders")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔗 جوین اجباری", callback_data="admin_forcejoin_menu")],
            [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings_menu")],
        ]
        await query.edit_message_text(
            "⚙️ **پنل ادمین**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # --- تایید و رد پرداخت ---
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
                    text=f"✅ پرداخت شما تایید شد.\n💰 {row[1]:,} تومان به موجودی اضافه شد.",
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
                    text="❌ متاسفانه رسید شما تایید نشد.",
                )
                await query.edit_message_caption(caption=f"❌ پرداخت #{pay_id} رد شد.")
        finally:
            cur.close()
            conn.close()


async def show_card(query, amount):
    card = get_setting("card_number")
    owner = get_setting("card_owner")
    keyboard = [
        [InlineKeyboardButton("💳 ارسال رسید", callback_data="send_receipt")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ]
    await query.edit_message_text(
        f"💳 **افزایش موجودی**\n\n"
        f"💰 مبلغ: **{amount:,}** تومان\n\n"
        f"مبلغ رو به کارت زیر واریز کن :\n\n"
        f"💳 شماره کارت:\n`{card}`\n\n"
        f"👤 به نام: {owner}\n\n"
        f"بعد از واریز، دکمه **ارسال رسید** رو بزن :",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_purchase(query, user_id, plan, price):
    user = get_user(user_id)
    balance = user["balance"] if user else 0
    if balance < price:
        await query.edit_message_text(
            f"❌ **موجودی کافی نیست**\n\n"
            f"💰 موجودی: {balance:,} تومان\n"
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
            "INSERT INTO orders (user_id, product_name, price, status) VALUES (%s, %s, %s, 'paid')",
            (user_id, plan, price),
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


# ⬇️ تکه ۴ اینجا
# ---------- هندلر پیام‌ها ----------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting = context.user_data.get("awaiting")

    if not awaiting:
        return

    # --- مبلغ دلخواه ---
    if awaiting == "amount":
        if not update.message.text:
            return
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text(
                "❌ فقط عدد بفرست. مثلاً: `50000`", parse_mode="Markdown"
            )
            return
        amount = int(text)
        if amount < 1000:
            await update.message.reply_text("❌ حداقل ۱,۰۰۰ تومان.")
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
            f"به کارت زیر واریز کن :\n\n"
            f"💳 `{card}`\n"
            f"👤 {owner}\n\n"
            f"بعد دکمه **ارسال رسید** رو بزن :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    # --- عکس رسید ---
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
                (user_id, amount),
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
                f"💰 مبلغ: **{amount:,}** تومان"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        await update.message.reply_text("✅ رسید ارسال شد. منتظر تایید باش. 🙏")
        return

    # --- پیام‌های ادمین ---
    if user_id == ADMIN_ID:
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
        elif awaiting == "add_channel":
            conn = get_db()
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO force_join (channel) VALUES (%s) ON CONFLICT (channel) DO NOTHING",
                    (text,),
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()
            await update.message.reply_text(f"✅ کانال {text} اضافه شد.")
        elif awaiting == "add_product":
            try:
                parts = [p.strip() for p in text.split("|")]
                if len(parts) != 3:
                    raise ValueError
                cat, name, price = parts[0], parts[1], int(parts[2])
                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO products (category, name, price) VALUES (%s, %s, %s)",
                        (cat, name, price),
                    )
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
                await update.message.reply_text(f"✅ محصول «{name}» اضافه شد.")
            except Exception:
                await update.message.reply_text(
                    "❌ فرمت اشتباه. مثال:\n`v2ray | سه ماهه | 250000`",
                    parse_mode="Markdown",
                )
        elif awaiting == "del_product":
            try:
                pid = int(text.strip())
                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE products SET active = FALSE WHERE id = %s", (pid,))
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
                await update.message.reply_text(f"✅ محصول #{pid} حذف شد.")
            except Exception:
                await update.message.reply_text("❌ آیدی نامعتبر.")
        elif awaiting == "find_user":
            try:
                uid = int(text.strip())
                user = get_user(uid)
                if not user:
                    await update.message.reply_text("❌ کاربر پیدا نشد.")
                else:
                    keyboard = [
                        [
                            InlineKeyboardButton("➕ ۱۰۰,۰۰۰", callback_data=f"addbal_{uid}_100000"),
                            InlineKeyboardButton("➖ ۱۰۰,۰۰۰", callback_data=f"subbal_{uid}_100000"),
                        ]
                    ]
                    await update.message.reply_text(
                        f"👤 **کاربر**\n\n"
                        f"🆔 `{uid}`\n"
                        f"نام: {user['first_name']}\n"
                        f"💰 موجودی: {user['balance']:,} تومان",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown",
                    )
            except Exception:
                await update.message.reply_text("❌ آیدی نامعتبر.")

        context.user_data["awaiting"] = None
        return
        # ---------- هندلرهای اضافی ادمین ----------
async def admin_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        return

    data = query.data

    if data.startswith("addbal_"):
        parts = data.split("_")
        target = int(parts[1])
        amount = int(parts[2])
        update_balance(target, amount)
        await context.bot.send_message(
            chat_id=target,
            text=f"✅ {amount:,} تومان به موجودی شما اضافه شد.",
        )
        await query.edit_message_text(f"✅ {amount:,} تومان به کاربر {target} اضافه شد.")

    elif data.startswith("subbal_"):
        parts = data.split("_")
        target = int(parts[1])
        amount = int(parts[2])
        update_balance(target, -amount)
        await context.bot.send_message(
            chat_id=target,
            text=f"➖ {amount:,} تومان از موجودی شما کم شد.",
        )
        await query.edit_message_text(f"➖ {amount:,} تومان از کاربر {target} کم شد.")


# ---------- تایید/رد پرداخت با کپشن ----------
async def photo_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # اگه ادمین روی یه عکس رسید ریپلای کنه و مبلغ بنویسه، اون مبلغ رو ثبت می‌کنه
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        return
    if not update.message.reply_to_message.caption:
        return
    if "رسید جدید" not in update.message.reply_to_message.caption:
        return

    text = update.message.text.strip()
    if not text.isdigit():
        return

    amount = int(text)
    # استخراج pay_id از کپشن
    caption = update.message.reply_to_message.caption
    try:
        # دنبال "پرداخت #" نمی‌گردیم، از دیتابیس آخرین pending رو می‌گیریم
        # اینجا فقط تایید دستی مبلغ
        pass
    except Exception:
        pass


# ---------- اجرا ----------
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_balance_handler, pattern="^(addbal_|subbal_)"))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))
    app.add_handler(MessageHandler(filters.PHOTO, message_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("ربات آنلاین شد...")
    app.run_polling()
        

