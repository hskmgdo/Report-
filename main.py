import telebot
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import time
import json
from datetime import datetime

# ==================== تنظیمات ====================
BOT_TOKEN = "8423981755:AAFaEYzOefEaxDiuyvKKyyTJzlhDXWSqyRw"
ADMIN_IDS = [123456789]  # آیدی عددی ادمین‌ها (خودتان)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('/tmp/whites_panel.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                link TEXT UNIQUE,
                added_by INTEGER,
                added_at INTEGER,
                category TEXT DEFAULT 'general'
            )
        ''')
        self.conn.commit()
    
    def add_config(self, name, link, added_by, category='general'):
        try:
            self.cursor.execute(
                "INSERT INTO configs (name, link, added_by, added_at, category) VALUES (?, ?, ?, ?, ?)",
                (name, link, added_by, int(time.time()), category)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_all_configs(self, category=None):
        if category:
            self.cursor.execute("SELECT id, name, link, category FROM configs WHERE category = ?", (category,))
        else:
            self.cursor.execute("SELECT id, name, link, category FROM configs")
        return self.cursor.fetchall()
    
    def get_config(self, config_id):
        self.cursor.execute("SELECT id, name, link, category FROM configs WHERE id = ?", (config_id,))
        return self.cursor.fetchone()
    
    def delete_config(self, config_id):
        self.cursor.execute("DELETE FROM configs WHERE id = ?", (config_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_categories(self):
        self.cursor.execute("SELECT DISTINCT category FROM configs")
        return [row[0] for row in self.cursor.fetchall()]
    
    def close(self):
        self.conn.close()

db = Database()

# ==================== منوی اصلی (رنگی فارسی) ====================
def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    if user_id in ADMIN_IDS:
        btn_add = KeyboardButton("➕ افزودن کانفیگ", style="success")      # سبز
        btn_list = KeyboardButton("📋 لیست کانفیگ‌ها", style="primary")    # آبی
        btn_delete = KeyboardButton("❌ حذف کانفیگ", style="danger")       # قرمز
        btn_get = KeyboardButton("📤 دریافت کانفیگ", style="primary")      # آبی
        btn_cat = KeyboardButton("📂 دسته‌بندی", style="primary")          # آبی
        btn_help = KeyboardButton("❓ راهنما", style="primary")            # آبی
        markup.add(btn_add, btn_list, btn_delete, btn_get, btn_cat, btn_help)
    else:
        btn_list = KeyboardButton("📋 لیست کانفیگ‌ها", style="primary")
        btn_get = KeyboardButton("📤 دریافت کانفیگ", style="primary")
        btn_help = KeyboardButton("❓ راهنما", style="primary")
        markup.add(btn_list, btn_get, btn_help)
    
    return markup

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ==================== پیام خوش‌آمدگویی ====================
@bot.message_handler(commands=['start', 'help'])
def start_command(message: Message):
    user_id = message.from_user.id
    markup = get_main_menu(user_id)
    
    text = f"""
🌐 <b>پنل وایت‌دی‌ان‌اس (Whites DNS)</b>

سلام {message.from_user.first_name} 👋
به پنل مدیریت کانفیگ‌های <b>StormDNS</b> خوش آمدید.

🔹 <b>امکانات:</b>
• مدیریت کانفیگ‌های وایت‌دی‌ان‌اس
• دسته‌بندی پیشرفته
• دریافت لینک با یک کلیک
• رابط کاربری لوکس و رنگی

🔸 <b>راهنما:</b>
از دکمه‌های زیر برای مدیریت استفاده کنید.

⚡ <i>پنل شما آماده است!</i>
"""
    bot.reply_to(message, text, reply_markup=markup)

# ==================== دکمه‌های اصلی ====================
@bot.message_handler(func=lambda m: m.text == "➕ افزودن کانفیگ")
def add_config_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = """
➕ <b>افزودن کانفیگ جدید</b>

لطفاً اطلاعات را به صورت زیر وارد کنید:

<code>/addconfig نام_کانفیگ | لینک_stormdns | دسته‌بندی(اختیاری)</code>

📌 <b>مثال:</b>
<code>/addconfig ریزا | stormdns://... | ایران</code>

💡 <i>دسته‌بندی اختیاری است و اگر وارد نشود، در دسته 'general' قرار می‌گیرد.</i>
"""
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

@bot.message_handler(commands=['addconfig'])
def add_config_command(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ لطفاً اطلاعات را کامل وارد کنید.\nمثال: /addconfig ریزا | stormdns://... | ایران", reply_markup=get_main_menu(message.from_user.id))
        return
    
    parts = args[1].split('|')
    if len(parts) < 2:
        bot.reply_to(message, "❌ فرمت ورودی صحیح نیست.\nاز '|' برای جدا کردن نام و لینک استفاده کنید.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    name = parts[0].strip()
    link = parts[1].strip()
    category = parts[2].strip() if len(parts) > 2 else 'general'
    
    if not link.startswith('stormdns://'):
        bot.reply_to(message, "❌ لینک باید با <code>stormdns://</code> شروع شود.", parse_mode='HTML', reply_markup=get_main_menu(message.from_user.id))
        return
    
    if db.add_config(name, link, message.from_user.id, category):
        bot.reply_to(message, f"✅ کانفیگ <b>{name}</b> با موفقیت افزوده شد.\nدسته: {category}", reply_markup=get_main_menu(message.from_user.id))
    else:
        bot.reply_to(message, "❌ این لینک قبلاً در سیستم ثبت شده است.", reply_markup=get_main_menu(message.from_user.id))

# ==================== لیست کانفیگ‌ها ====================
@bot.message_handler(func=lambda m: m.text == "📋 لیست کانفیگ‌ها")
def list_configs(message: Message):
    configs = db.get_all_configs()
    if not configs:
        bot.reply_to(message, "📭 هیچ کانفیگی در سیستم وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = "📋 <b>لیست کانفیگ‌های وایت‌دی‌ان‌اس</b>\n\n"
    for cid, name, link, category in configs:
        text += f"🔹 <b>{name}</b>\n"
        text += f"   📂 {category}\n"
        text += f"   🆔 {cid}\n"
        text += f"   🔗 <code>{link[:40]}...</code>\n\n"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== دریافت کانفیگ ====================
@bot.message_handler(func=lambda m: m.text == "📤 دریافت کانفیگ")
def get_config_menu(message: Message):
    markup = InlineKeyboardMarkup(row_width=1)
    configs = db.get_all_configs()
    
    if not configs:
        bot.reply_to(message, "📭 هیچ کانفیگی موجود نیست.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    for cid, name, link, category in configs:
        btn = InlineKeyboardButton(f"📌 {name} ({category})", callback_data=f"get_{cid}")
        markup.add(btn)
    
    bot.reply_to(message, "🔽 یکی از کانفیگ‌های زیر را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('get_'))
def send_config(call):
    config_id = int(call.data.split('_')[1])
    config = db.get_config(config_id)
    if not config:
        bot.answer_callback_query(call.id, "❌ کانفیگ پیدا نشد!")
        return
    
    cid, name, link, category = config
    text = f"""
🌐 <b>کانفیگ وایت‌دی‌ان‌اس</b>

📌 نام: {name}
📂 دسته: {category}
🆔 شناسه: {cid}

🔗 <b>لینک:</b>
<code>{link}</code>

💡 <i>برای استفاده، لینک را کپی کنید.</i>
"""
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')
    bot.answer_callback_query(call.id, "✅ کانفیگ ارسال شد!")

# ==================== حذف کانفیگ ====================
@bot.message_handler(func=lambda m: m.text == "❌ حذف کانفیگ")
def delete_config_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    configs = db.get_all_configs()
    
    if not configs:
        bot.reply_to(message, "📭 هیچ کانفیگی برای حذف وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    for cid, name, link, category in configs:
        btn = InlineKeyboardButton(f"❌ {name}", callback_data=f"del_{cid}")
        markup.add(btn)
    
    bot.reply_to(message, "⚠️ کانفیگ مورد نظر را برای حذف انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_config(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
        return
    
    config_id = int(call.data.split('_')[1])
    if db.delete_config(config_id):
        bot.answer_callback_query(call.id, "✅ کانفیگ با موفقیت حذف شد!")
        bot.edit_message_text("✅ کانفیگ حذف شد.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ خطا در حذف!")

# ==================== دسته‌بندی ====================
@bot.message_handler(func=lambda m: m.text == "📂 دسته‌بندی")
def category_menu(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها دسترسی دارند.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    categories = db.get_categories()
    if not categories:
        bot.reply_to(message, "📭 هیچ دسته‌بندی وجود ندارد.", reply_markup=get_main_menu(message.from_user.id))
        return
    
    text = "📂 <b>دسته‌بندی کانفیگ‌ها</b>\n\n"
    for cat in categories:
        count = db.cursor.execute("SELECT COUNT(*) FROM configs WHERE category = ?", (cat,)).fetchone()[0]
        text += f"• {cat} ({count} کانفیگ)\n"
    
    bot.reply_to(message, text, reply_markup=get_main_menu(message.from_user.id))

# ==================== راهنما ====================
@bot.message_handler(func=lambda m: m.text == "❓ راهنما")
def help_menu(message: Message):
    start_command(message)

# ==================== مدیریت خطا ====================
@bot.message_handler(func=lambda m: True)
def fallback(message: Message):
    bot.reply_to(message, "❓ دستور ناشناخته. از دکمه‌های منو استفاده کنید.", reply_markup=get_main_menu(message.from_user.id))

# ==================== راه‌اندازی ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🌐 پنل وایت‌دی‌ان‌اس (Whites DNS Panel)")
    print("=" * 60)
    print("✅ ربات راه‌اندازی شد.")
    print("👑 ادمین‌ها:", ADMIN_IDS)
    print("📌 برای شروع از /start استفاده کنید.")
    print("=" * 60)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"خطا در پولینگ: {e}")
            time.sleep(5)
