import telebot
from telebot.types import Message
import sqlite3
import re
import time
import hashlib
from datetime import datetime

# ==================== تنظیمات ====================
BOT_TOKEN = "8423981755:AAFaEYzOefEaxDiuyvKKyyTJzlhDXWSqyRw"
ADMIN_IDS = [8916314219]  # لیست آیدی عددی ادمین‌ها
DESTINATION_CHAT_ID = "@your_group"  # آیدی گروه مقصد (می‌تواند عددی یا @username باشد)
CHECK_INTERVAL = 1  # ثانیه بین هر بار بررسی پیام‌های جدید

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('scanner_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        # جدول کانال‌های منبع
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                title TEXT,
                username TEXT,
                added_by INTEGER,
                added_at INTEGER,
                active INTEGER DEFAULT 1
            )
        ''')
        
        # جدول کانفیگ‌های شناسایی شده (برای جلوگیری از تکرار)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_hash TEXT UNIQUE,
                config_text TEXT,
                source_chat_id INTEGER,
                source_message_id INTEGER,
                forwarded_at INTEGER,
                first_seen INTEGER
            )
        ''')
        
        # جدول تنظیمات (برای ذخیره گروه مقصد و ...)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()
        
        # درج تنظیمات پیش‌فرض در صورت نبود
        self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('destination', ?)", (DESTINATION_CHAT_ID,))
        self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active', '1')")
        self.conn.commit()
    
    def add_channel(self, chat_id, title, username, added_by):
        now = int(time.time())
        try:
            self.cursor.execute(
                "INSERT INTO channels (chat_id, title, username, added_by, added_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, title, username, added_by, now)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_channel(self, chat_id):
        self.cursor.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
        self.conn.commit()
    
    def get_channels(self, active_only=True):
        if active_only:
            self.cursor.execute("SELECT chat_id, title, username FROM channels WHERE active = 1")
        else:
            self.cursor.execute("SELECT chat_id, title, username FROM channels")
        return self.cursor.fetchall()
    
    def get_destination(self):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'destination'")
        row = self.cursor.fetchone()
        return row[0] if row else None
    
    def set_destination(self, chat_id):
        self.cursor.execute("UPDATE settings SET value = ? WHERE key = 'destination'", (chat_id,))
        self.conn.commit()
    
    def is_active(self):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'active'")
        row = self.cursor.fetchone()
        return row and row[0] == '1'
    
    def set_active(self, status):
        self.cursor.execute("UPDATE settings SET value = ? WHERE key = 'active'", ('1' if status else '0'))
        self.conn.commit()
    
    def add_config(self, config_text, source_chat_id, source_message_id):
        config_hash = hashlib.md5(config_text.encode()).hexdigest()
        now = int(time.time())
        try:
            self.cursor.execute(
                "INSERT INTO configs (config_hash, config_text, source_chat_id, source_message_id, first_seen) VALUES (?, ?, ?, ?, ?)",
                (config_hash, config_text, source_chat_id, source_message_id, now)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def close(self):
        self.conn.close()

db = Database()

# ==================== توابع کمکی ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def extract_configs(text):
    """استخراج تمام کانفیگ‌های موجود در متن با regex"""
    patterns = [
        r'vless://[^\s]+',
        r'vmess://[^\s]+',
        r'trojan://[^\s]+',
        r'ss://[^\s]+',
        r'ssr://[^\s]+'
    ]
    configs = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        configs.extend(matches)
    return configs

def send_to_destination(config_text, source_chat_title, source_message_link):
    """ارسال کانفیگ به گروه مقصد با ذکر منبع"""
    dest = db.get_destination()
    if not dest:
        return False
    try:
        text = f"""
🔹 <b>کانفیگ جدید شناسایی شد</b>
📌 منبع: {source_chat_title}
🔗 <a href="{source_message_link}">مشاهده پیام اصلی</a>

<code>{config_text}</code>
"""
        bot.send_message(dest, text, parse_mode='HTML', disable_web_page_preview=True)
        return True
    except Exception as e:
        print(f"خطا در ارسال به مقصد: {e}")
        return False

def get_chat_info(chat_id):
    """دریافت اطلاعات کانال از طریق بات"""
    try:
        chat = bot.get_chat(chat_id)
        return chat.title, chat.username
    except:
        return None, None

# ==================== دستورات ادمین ====================
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    bot.reply_to(message, """
🤖 <b>ربات اسکنر کانفیگ</b>

این ربات به طور خودکار کانال‌های مشخص‌شده را بررسی کرده و کانفیگ‌های VPN را استخراج و به گروه مقصد ارسال می‌کند.

🔹 <b>دستورات ادمین:</b>
/addchannel @username  - اضافه کردن کانال (با شناسه)
/removechannel @username - حذف کانال
/listchannels - لیست کانال‌های فعال
/setdestination @group - تنظیم گروه مقصد
/status - وضعیت ربات (فعال/غیرفعال)
/toggle - فعال/غیرفعال کردن ربات
/help - این پیام

⚠️ توجه: بات باید در کانال‌های مورد نظر عضو باشد تا بتواند پیام‌ها را بخواند.
""")

@bot.message_handler(commands=['addchannel'])
def add_channel_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً شناسه کانال را وارد کنید.\nمثال: /addchannel @my_channel")
        return
    
    username = args[1]
    # حذف @ اگر وجود داشته باشد
    if username.startswith('@'):
        username = username[1:]
    
    try:
        # تلاش برای دریافت اطلاعات کانال با username
        chat = bot.get_chat(f"@{username}")
        chat_id = chat.id
        title = chat.title
        if db.add_channel(chat_id, title, username, message.from_user.id):
            bot.reply_to(message, f"✅ کانال <b>{title}</b> با موفقیت اضافه شد.")
        else:
            bot.reply_to(message, "❌ این کانال قبلاً اضافه شده است.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا در افزودن کانال: {e}\nاطمینان حاصل کنید که بات در کانال عضو است.")

@bot.message_handler(commands=['removechannel'])
def remove_channel_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً شناسه کانال را وارد کنید.\nمثال: /removechannel @my_channel")
        return
    
    username = args[1]
    if username.startswith('@'):
        username = username[1:]
    
    try:
        chat = bot.get_chat(f"@{username}")
        chat_id = chat.id
        db.remove_channel(chat_id)
        bot.reply_to(message, f"✅ کانال {username} با موفقیت حذف شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@bot.message_handler(commands=['listchannels'])
def list_channels_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید.")
        return
    
    channels = db.get_channels()
    if not channels:
        bot.reply_to(message, "📭 هیچ کانالی اضافه نشده است.")
        return
    
    text = "📋 <b>کانال‌های فعال:</b>\n"
    for chat_id, title, username in channels:
        text += f"• {title} (@{username}) - ID: {chat_id}\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['setdestination'])
def set_destination_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً شناسه گروه مقصد را وارد کنید.\nمثال: /setdestination @my_group")
        return
    
    dest = args[1]
    db.set_destination(dest)
    bot.reply_to(message, f"✅ گروه مقصد به {dest} تنظیم شد.")

@bot.message_handler(commands=['status'])
def status_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید.")
        return
    
    active = db.is_active()
    dest = db.get_destination()
    channels = db.get_channels()
    text = f"""
📊 <b>وضعیت ربات</b>
🔹 فعال: {'✅' if active else '❌'}
🔹 گروه مقصد: {dest or 'تنظیم نشده'}
🔹 تعداد کانال‌های منبع: {len(channels)}
"""
    bot.reply_to(message, text)

@bot.message_handler(commands=['toggle'])
def toggle_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید.")
        return
    
    current = db.is_active()
    new_status = not current
    db.set_active(new_status)
    bot.reply_to(message, f"✅ ربات {'فعال' if new_status else 'غیرفعال'} شد.")

@bot.message_handler(commands=['help'])
def help_command(message: Message):
    start_command(message)  # همان پیام start

# ==================== پردازش پیام‌های جدید ====================
def process_new_messages():
    """
    این تابع به صورت مداوم پیام‌های جدید را از همه چت‌هایی که بات عضو است دریافت می‌کند.
    اگر پیام از یک کانال منبع باشد، اسکن می‌شود.
    """
    if not db.is_active():
        return
    
    # دریافت آخرین آفست از دیتابیس یا حافظه (برای سادگی از متغیر global استفاده می‌کنیم)
    # اما بهتر است در دیتابیس ذخیره شود.
    # در اینجا از یک متغیر سراسری استفاده می‌کنیم.
    global last_update_id
    if last_update_id is None:
        # ابتدا آخرین آپدیت را دریافت می‌کنیم تا از قدیمی‌ها صرف نظر کنیم
        updates = bot.get_updates(limit=1, offset=-1)
        if updates:
            last_update_id = updates[-1].update_id + 1
        else:
            last_update_id = 0
    
    try:
        updates = bot.get_updates(offset=last_update_id, timeout=10)
    except Exception as e:
        print(f"خطا در دریافت آپدیت‌ها: {e}")
        return
    
    for update in updates:
        last_update_id = update.update_id + 1
        if not update.channel_post:  # فقط پیام‌های کانال را پردازش می‌کنیم
            continue
        
        message = update.channel_post
        chat_id = message.chat.id
        # بررسی اینکه آیا این کانال در لیست ما هست؟
        channels = db.get_channels()
        channel_ids = [c[0] for c in channels]
        if chat_id not in channel_ids:
            continue
        
        # اگر پیام دارای متن نباشد، رد می‌شود
        if not message.text:
            continue
        
        # استخراج کانفیگ‌ها
        configs = extract_configs(message.text)
        if not configs:
            continue
        
        # دریافت اطلاعات کانال برای ذکر منبع
        chat_info = bot.get_chat(chat_id)
        chat_title = chat_info.title
        chat_username = chat_info.username or f"chat{chat_id}"
        
        # ساخت لینک به پیام
        message_link = f"https://t.me/{chat_username}/{message.message_id}" if chat_username else None
        
        for cfg in configs:
            # بررسی تکراری نبودن
            if db.add_config(cfg, chat_id, message.message_id):
                # ارسال به مقصد
                if send_to_destination(cfg, chat_title, message_link or "بدون لینک"):
                    print(f"کانفیگ جدید ارسال شد: {cfg[:30]}...")
                else:
                    print("خطا در ارسال کانفیگ به مقصد")
            else:
                # تکراری است
                pass

# ==================== حلقه اصلی ====================
last_update_id = None

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 ربات اسکنر کانفیگ VPN")
    print("=" * 60)
    print("✅ ربات راه‌اندازی شد.")
    print("👑 ادمین‌ها:", ADMIN_IDS)
    print("📌 برای مدیریت از دستورات استفاده کنید.")
    print("=" * 60)
    
    # یک ترد جداگانه برای پردازش پیام‌ها
    import threading
    
    def scanner_loop():
        while True:
            try:
                process_new_messages()
            except Exception as e:
                print(f"خطا در اسکنر: {e}")
            time.sleep(CHECK_INTERVAL)
    
    # اجرای اسکنر در پس‌زمینه
    scanner_thread = threading.Thread(target=scanner_loop, daemon=True)
    scanner_thread.start()
    
    # اجرای پولینگ برای دستورات
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"خطا در پولینگ: {e}")
            time.sleep(5)
