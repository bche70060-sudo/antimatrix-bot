import logging
import re
import asyncio
import sqlite3
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- اطلاعات شما ---
API_ID = 25418755
API_HASH = "756fdbc00887c1faa3a15820a9555954"
BOT_TOKEN = "8858020201:AAElY77cbtAkywKmx02gqGrQgRgv29fyIGI"
ADMIN_ID = 6192708492
# ------------------

app = Client("digianti7bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- دیتابیس پیشرفته ---
DB_NAME = "antimatrix_pro.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        chat_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (chat_id, key))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS warns (
                        chat_id INTEGER, user_id INTEGER, count INTEGER, PRIMARY KEY (chat_id, user_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS gban (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_chats (chat_id INTEGER PRIMARY KEY, title TEXT)''')
    conn.commit()
    conn.close()

init_db()

def register_chat(chat_id, title="Group"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO active_chats (chat_id, title) VALUES (?, ?)", (chat_id, title))
        conn.commit()
        conn.close()
    except Exception: pass

def get_db_setting(chat_id, key, default="False"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE chat_id = ? AND key = ?", (chat_id, key))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_db_setting(chat_id, key, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (chat_id, key, value) VALUES (?, ?, ?)", (chat_id, key, value))
    conn.commit()
    conn.close()

def get_warns(chat_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM warns WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def add_warn(chat_id, user_id):
    current = get_warns(chat_id, user_id)
    new_warn = current + 1
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO warns (chat_id, user_id, count) VALUES (?, ?, ?)", (chat_id, user_id, new_warn))
    conn.commit()
    conn.close()
    return new_warn

def reset_warns(chat_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warns WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    conn.commit()
    conn.close()

def is_gbanned(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM gban WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

ADMINS_CACHE = {}

async def is_admin(client, chat_id, user_id):
    if user_id == ADMIN_ID: return True
    if chat_id in ADMINS_CACHE and user_id in ADMINS_CACHE[chat_id]: return ADMINS_CACHE[chat_id][user_id]
    try:
        member = await client.get_chat_member(chat_id, user_id)
        is_user_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        if chat_id not in ADMINS_CACHE: ADMINS_CACHE[chat_id] = {}
        ADMINS_CACHE[chat_id][user_id] = is_user_admin
        return is_user_admin
    except Exception: return False

# --- طراحی کیبوردهای شیشه‌ای حرفه‌ای ---

def get_settings_keyboard(chat_id):
    locks = ["link", "username", "sticker", "video", "photo", "document"]
    buttons = []
    for i in range(0, len(locks), 2):
        row = []
        for j in range(2):
            if i + j < len(locks):
                lock = locks[i + j]
                default_val = "True" if lock in ["link", "username"] else "False"
                status = get_db_setting(chat_id, lock, default_val)
                icon = "🔒" if status == "True" else "🔓"
                row.append(InlineKeyboardButton(f"{lock.capitalize()} {icon}", callback_data=f"toggle_{lock}_{chat_id}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton("❌ بستن پنل", callback_data="close_panel")])
    return InlineKeyboardMarkup(buttons)

def get_sudo_keyboard():
    buttons = [
        [InlineKeyboardButton("📊 آمار کامل ربات", callback_data="sudo_stats"),
         InlineKeyboardButton("📢 راهنمای همگانی", callback_data="sudo_help_bc")],
        [InlineKeyboardButton("❌ بستن پنل", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_private_start_keyboard():
    buttons = [
        [InlineKeyboardButton("➕ افزودن ربات به گروه", url=f"https://t.me/{app.me.username if app.me else 'Bot'}?startgroup=true")],
        [InlineKeyboardButton("⚙️ راهنمای مدیریت گروه", callback_data="pv_group_help"),
         InlineKeyboardButton("🛡 امکانات امنیتی", callback_data="pv_security")],
        [InlineKeyboardButton("💎 درباره ربات", callback_data="pv_about")],
        [InlineKeyboardButton("❌ بستن منو", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(buttons)

# --- مدیریت کلیک دکمه‌های شیشه‌ای (Callbacks) ---
@app.on_callback_query()
async def handle_callbacks(client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    if data == "close_panel":
        try:
            await callback_query.message.delete()
        except Exception: pass
        return

    if data == "pv_group_help":
        await callback_query.answer(
            "📚 راهنمای ادمین‌ها در گروه:\n\n1️⃣ ربات را ادمین کنید.\n2️⃣ دستور /settings را بفرستید.\n3️⃣ با کلیک روی دکمه‌ها، قفل‌ها را مدیریت کنید.",
            show_alert=True
        )
        return
    if data == "pv_security":
        await callback_query.answer(
            "🛡 سیستم ضد اسپم:\n\n- قفل لینک، آیدی، استیکر و رسانه\n- سیستم اخطار هوشمند (۳ اخطار = بن)\n- لیست سیاه جهانی (GBAN)",
            show_alert=True
        )
        return
    if data == "pv_about":
        await callback_query.answer(
            "💎 ربات نگهبان پیشرفته آنتی‌ماتریکس\nطراحی شده با پایتون و پایروگرام با بالاترین سرعت و پایداری.",
            show_alert=True
        )
        return

    if data.startswith("sudo_"):
        if user_id != ADMIN_ID:
            await callback_query.answer("❌ این بخش فقط مخصوص ادمین ارشد است!", show_alert=True)
            return
        
        if data == "sudo_stats":
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM active_chats")
            g_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM gban")
            gb_count = cursor.fetchone()[0]
            conn.close()
            await callback_query.answer(f"گروه‌های فعال: {g_count} | کاربران بن شده: {gb_count}", show_alert=True)
            return
            
        if data == "sudo_help_bc":
            await callback_query.message.reply_text(
                "💡 **راهنمای ارسال همگانی:**\n\nریپلای روی پیام و ارسال دستور:\n`/bc` (ارسال متن)\n`/fwd` (فوروارد)"
            )
            await callback_query.answer()
            return

    if data.startswith("toggle_"):
        if not await is_admin(client, chat_id, user_id):
            await callback_query.answer("❌ شما ادمین این گروه نیستید!", show_alert=True)
            return
        _, lock_type, c_id = data.split("_")
        default_val = "True" if lock_type in ["link", "username"] else "False"
        current_status = get_db_setting(int(c_id), lock_type, default_val)
        new_status = "False" if current_status == "True" else "True"
        set_db_setting(int(c_id), lock_type, new_status)
        
        await callback_query.message.edit_reply_markup(reply_markup=get_settings_keyboard(int(c_id)))
        await callback_query.answer(f"وضعیت قفل {lock_type} تغییر کرد.")

# --- دستورات پی‌وی ---
@app.on_message(filters.command("start") & filters.private)
async def private_start(client, message: Message):
    await message.reply_text(
        f"سلام {message.from_user.mention} عزیز! 👋\n\n"
        "من **ربات نگهبان و آنتی‌ماتریکس پیشرفته** هستم. 🛡\n"
        "می‌توانید از منوهای شیشه‌ای زیر برای دسترسی به بخش‌های مختلف استفاده کنید:",
        reply_markup=get_private_start_keyboard()
    )

# --- دستورات ادمین ارشد ---
@app.on_message(filters.command("sudo") & filters.user(ADMIN_ID))
async def sudo_panel(client, message: Message):
    await message.reply_text(
        "🛠 **پنل مدیریت ارشد (Sudo Control Center):**",
        reply_markup=get_sudo_keyboard()
    )

@app.on_message(filters.command("gban") & filters.user(ADMIN_ID))
async def global_ban(client, message):
    if not message.reply_to_message and len(message.command) < 2:
        await message.reply_text("❌ روی پیام کاربر ریپلای کنید یا آیدی عددی او را بدهید.")
        return
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else int(message.command[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO gban (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    await message.reply_text(f"🔴 کاربر `{user_id}` به لیست سیاه جهانی اضافه شد.")

@app.on_message(filters.command("ungban") & filters.user(ADMIN_ID))
async def global_unban(client, message):
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("❌ آیدی کاربر را وارد کنید.")
        return
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else int(message.command[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gban WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await message.reply_text(f"🟢 کاربر `{user_id}` از لیست سیاه جهانی خارج شد.")

@app.on_message(filters.command("bc") & filters.user(ADMIN_ID))
async def broadcast_message(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("❌ روی پیام مورد نظر برای ارسال همگانی ریپلای کنید.")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM active_chats")
    chats = cursor.fetchall()
    conn.close()

    sent = 0
    failed = 0
    status_msg = await message.reply_text("⏳ در حال ارسال همگانی...")

    for chat in chats:
        try:
            await message.reply_to_message.copy(chat[0])
            sent += 1
            await asyncio.sleep(0.1)
        except Exception:
            failed += 1

    await status_msg.edit_text(f"✅ ارسال به اتمام رسید.\n📤 موفق: `{sent}`\n❌ ناموفق: `{failed}`")

@app.on_message(filters.command("fwd") & filters.user(ADMIN_ID))
async def forward_broadcast(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("❌ روی پیام مورد نظر ریپلای کنید.")
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM active_chats")
    chats = cursor.fetchall()
    conn.close()

    sent = 0
    status_msg = await message.reply_text("⏳ در حال فوروارد همگانی...")

    for chat in chats:
        try:
            await message.reply_to_message.forward(chat[0])
            sent += 1
            await asyncio.sleep(0.1)
        except Exception: pass

    await status_msg.edit_text(f"✅ فوروارد همگانی به `{sent}` گروه انجام شد.")

# --- دستورات مدیریتی گروه ---
@app.on_message(filters.command("settings") & filters.group)
async def show_group_settings(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    register_chat(message.chat.id, message.chat.title)
    await message.reply_text("⚙️ **پنل شیشه‌ای تنظیمات قفل‌ها:**", reply_markup=get_settings_keyboard(message.chat.id))

@app.on_message(filters.command("mute") & filters.group)
async def mute_user(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return
    await client.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=False))
    await message.reply_text(f"🔇 کاربر {message.reply_to_message.from_user.mention} بیصدا شد.")

@app.on_message(filters.command("unmute") & filters.group)
async def unmute_user(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return
    await client.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
    await message.reply_text(f"🔊 کاربر {message.reply_to_message.from_user.mention} از سکوت خارج شد.")

@app.on_message(filters.command("purge") & filters.group)
async def purge_messages(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return
    message_ids = []
    for i in range(message.reply_to_message.id, message.id + 1):
        message_ids.append(i)
        if len(message_ids) >= 100: break
    try:
        await client.delete_messages(message.chat.id, message_ids)
        sent = await message.reply_text("🗑 پاک‌سازی با موفقیت انجام شد.")
        await asyncio.sleep(3)
        await sent.delete()
    except Exception as e:
        await message.reply_text(f"❌ خطا: {e}")

@app.on_message(filters.command("pin") & filters.group)
async def pin_message(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return
    try:
        await message.reply_to_message.pin()
        await message.reply_text("📌 پیام سنجاق شد.")
    except Exception as e:
        await message.reply_text(f"❌ خطا: {e}")

# --- مانیتورینگ و آنتی اسپم هوشمند ---
@app.on_message(filters.new_chat_members)
async def welcome_new_member(client, message: Message):
    register_chat(message.chat.id, message.chat.title)
    for member in message.new_chat_members:
        if member.id == client.me.id:
            await message.reply_text("سلام! از اینکه من را ادمین کردید متشکرم. 🚀\nبرای تنظیمات دستور `/settings` را ارسال کنید.")
            return
        await message.reply_text(f"سلام {member.mention} عزیز! 👋\nبه گروه خوش آمدید.")

@app.on_message(filters.group & ~filters.service)
async def core_monitor(client, message: Message):
    if not message.from_user: return
    chat_id = message.chat.id
    user_id = message.from_user.id

    register_chat(chat_id, message.chat.title)

    if is_gbanned(user_id):
        try:
            await message.delete()
            await client.ban_chat_member(chat_id, user_id)
            return
        except Exception: pass

    if await is_admin(client, chat_id, user_id): return

    delete_msg = False
    reason = ""

    if get_db_setting(chat_id, "link", "True") == "True":
        text = message.text or message.caption or ""
        if re.search(r'(https?://[^\s]+|t\.me/[^\s]+|telegram\.me/[^\s]+)', text, re.IGNORECASE):
            delete_msg = True
            reason = "ارسال لینک ممنوع است! ⛔"

    if not delete_msg and get_db_setting(chat_id, "username", "True") == "True":
        text = message.text or message.caption or ""
        if "@" in text:
            delete_msg = True
            reason = "ارسال آیدی ممنوع است! ⛔"

    if not delete_msg and get_db_setting(chat_id, "sticker", "False") == "True" and message.sticker:
        delete_msg = True
        reason = "ارسال استیکر ممنوع است! ⛔"

    if not delete_msg and get_db_setting(chat_id, "video", "False") == "True" and message.video:
        delete_msg = True
        reason = "ارسال ویدیو ممنوع است! ⛔"

    if not delete_msg and get_db_setting(chat_id, "photo", "False") == "True" and message.photo:
        delete_msg = True
        reason = "ارسال تصویر ممنوع است! ⛔"

    if not delete_msg and get_db_setting(chat_id, "document", "False") == "True" and message.document:
        delete_msg = True
        reason = "ارسال فایل ممنوع است! ⛔"

    if delete_msg:
        try:
            await message.delete()
            warn_count = add_warn(chat_id, user_id)

            if warn_count >= 3:
                await client.ban_chat_member(chat_id, user_id)
                await client.send_message(chat_id, f"⚠️ کاربر {message.from_user.mention} به دلیل دریافت ۳ اخطار اخراج شد.")
                reset_warns(chat_id, user_id)
            else:
                warn_msg = await client.send_message(chat_id, f"⚠️ کاربر {message.from_user.mention}، {reason}\nاخطار: {warn_count} از 3")
                await asyncio.sleep(5)
                await warn_msg.delete()
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logging.error(f"Error: {e}")

@app.on_chat_member_updated()
async def clear_cache(client, update):
    if update.chat.id in ADMINS_CACHE:
        ADMINS_CACHE.pop(update.chat.id, None)

if __name__ == "__main__":
    logging.info("🚀 ربات با بالاترین کارایی و پنل‌های شیشه‌ای دوگانه روشن شد!")
    app.run()
