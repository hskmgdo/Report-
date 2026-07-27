import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import time
from datetime import datetime
import sqlite3

# ==================== تنظیمات ====================
BOT_TOKEN = "8423981755:AAFaEYzOefEaxDiuyvKKyyTJzlhDXWSqyRw"
ADMIN_IDS = [8916314219]  # آیدی عددی خودت

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس (برای ذخیره تاریخچه جستجو) ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('user_search.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                searched_user_id INTEGER,
                searched_username TEXT,
                time INTEGER
            )
        ''')
        self.conn.commit()
    
    def add_search(self, admin_id, user_id, username):
        self.cursor.execute(
            "INSERT INTO search_history (admin_id, searched_user_id, searched_username, time) VALUES (?, ?, ?, ?)",
            (admin_id, user_id, username, int(time.time()))
        )
        self.conn.commit()
    
    def get_history(self, admin_id, limit=10):
        self.cursor.execute(
            "SELECT searched_user_id, searched_username, time FROM search_history WHERE admin_id = ? ORDER BY id DESC LIMIT ?",
            (admin_id, limit)
        )
        return self.cursor.fetchall()

db = Database()

# ==================== کیبوردها ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="search_user"),
        InlineKeyboardButton("📋 تاریخچه جستجو", callback_data="search_history"),
        InlineKeyboardButton("👤 اطلاعات خودم", callback_data="my_info"),
        InlineKeyboardButton("🆘 راهنما", callback_data="help")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return keyboard

# ==================== توابع کمکی ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def format_user_info(user, chat_id=None):
    """فرمت‌سازی اطلاعات کاربر به صورت زیبا"""
    info = f"""
👤 <b>اطلاعات کاربر</b>
━━━━━━━━━━━━━━━━━━━━━━
📛 <b>نام:</b> {user.first_name or 'نامشخص'}
👥 <b>نام خانوادگی:</b> {user.last_name or 'نامشخص'}
🆔 <b>آیدی عددی:</b> <code>{user.id}</code>
🔖 <b>یوزرنیم:</b> {('@' + user.username) if user.username else 'ندارد'}
📱 <b>شماره تماس:</b> {'دارد' if hasattr(user, 'phone') else 'نامشخص'}
🤖 <b>ربات:</b> {'✅' if user.is_bot else '❌'}
🔐 <b>پریمیوم:</b> {'✅' if user.is_premium else '❌'}
"""
    
    # اگر chat_id داشته باشیم، اطلاعات گروه رو هم می‌گیریم
    if chat_id:
        try:
            member = bot.get_chat_member(chat_id, user.id)
            info += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            info += f"📊 <b>وضعیت در گروه:</b>\n"
            info += f"👑 <b>نقش:</b> {member.status}\n"
            
            if member.status in ['administrator', 'creator']:
                info += f"🔹 <b>مدیریت پیام‌ها:</b> {'✅' if member.can_delete_messages else '❌'}\n"
                info += f"🔹 <b>بن کردن:</b> {'✅' if member.can_restrict_members else '❌'}\n"
                info += f"🔹 <b>پین کردن:</b> {'✅' if member.can_pin_messages else '❌'}\n"
        except:
            pass
    
    info += f"\n━━━━━━━━━━━━━━━━━━━━━━"
    return info

def get_user_by_identifier(identifier):
    """دریافت کاربر با آیدی یا یوزرنیم"""
    try:
        # اگر عدد بود، به عنوان آیدی در نظر بگیر
        if identifier.isdigit():
            user_id = int(identifier)
            try:
                user = bot.get_chat_member(user_id, user_id).user
                return user
            except:
                return None
        
        # اگر با @ شروع شد یا یوزرنیم بود
        if identifier.startswith('@'):
            username = identifier
        else:
            username = f"@{identifier}"
        
        try:
            # برای پیدا کردن کاربر با یوزرنیم از get_chat استفاده می‌کنیم
            chat = bot.get_chat(username)
            return chat
        except:
            return None
    except:
        return None

# ==================== دستور /start ====================
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ شما دسترسی به این ربات ندارید!")
        return
    
    text = """
🔍 <b>ربات جستجوی اطلاعات تلگرام</b> 🔍

⚡️ <b>قابلیت‌ها:</b>
✅ دریافت اطلاعات کامل کاربر
✅ نمایش نام، یوزرنیم، آیدی
✅ وضعیت در گروه (اگر عضو باشد)
✅ تاریخچه جستجو
✅ دریافت عکس پروفایل

📌 <b>برای جستجو:</b>
• آیدی عددی کاربر را وارد کنید
• یا یوزرنیم را با @ وارد کنید

👑 <b>فقط برای ادمین‌ها قابل استفاده است!</b>
"""
    bot.reply_to(message, text, reply_markup=main_menu())

# ==================== دریافت پیام‌های حاوی آیدی ====================
@bot.message_handler(func=lambda message: True)
def handle_search_message(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ شما دسترسی ندارید!")
        return
    
    text = message.text.strip()
    
    # اگر عدد یا یوزرنیم بود
    if text.isdigit() or text.startswith('@'):
        # جستجوی کاربر
        user = get_user_by_identifier(text)
        
        if user:
            # ذخیره در تاریخچه
            db.add_search(user_id, user.id, user.username)
            
            # نمایش اطلاعات
            info = format_user_info(user)
            
            # دکمه‌های بیشتر
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🖼️ عکس پروفایل", callback_data=f"photo_{user.id}"),
                InlineKeyboardButton("📋 کپی آیدی", callback_data=f"copy_{user.id}"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
            )
            
            bot.reply_to(message, info, reply_markup=keyboard)
        else:
            bot.reply_to(message, f"❌ کاربر با شناسه <code>{text}</code> یافت نشد!", parse_mode='HTML')
    else:
        bot.reply_to(message, "❌ لطفاً یک آیدی عددی یا یوزرنیم معتبر وارد کنید!")

# ==================== کال‌بک‌ها ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
        return
    
    # ===== بازگشت =====
    if data == "back_main":
        text = """
🔍 <b>ربات جستجوی اطلاعات تلگرام</b> 🔍

⚡️ <b>قابلیت‌ها:</b>
✅ دریافت اطلاعات کامل کاربر
✅ نمایش نام، یوزرنیم، آیدی
✅ وضعیت در گروه (اگر عضو باشد)
✅ تاریخچه جستجو
✅ دریافت عکس پروفایل

📌 <b>برای جستجو:</b>
• آیدی عددی کاربر را وارد کنید
• یا یوزرنیم را با @ وارد کنید

👑 <b>فقط برای ادمین‌ها قابل استفاده است!</b>
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    # ===== جستجوی کاربر =====
    if data == "search_user":
        bot.edit_message_text(
            "🔍 لطفاً آیدی عددی یا یوزرنیم کاربر را وارد کنید:\nمثال: <code>8916314219</code> یا <code>@rezagrootz</code>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button(),
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
        return
    
    # ===== تاریخچه جستجو =====
    if data == "search_history":
        history = db.get_history(user_id)
        
        if not history:
            text = "📭 شما هنوز جستجویی انجام نداده‌اید!"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
            bot.answer_callback_query(call.id)
            return
        
        text = "📋 <b>تاریخچه جستجو</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, (uid, username, timestamp) in enumerate(history, 1):
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
            username_str = f"@{username}" if username else "بدون یوزرنیم"
            text += f"{i}. <code>{uid}</code> - {username_str} ({time_str})\n"
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🗑️ پاک کردن تاریخچه", callback_data="clear_history"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)
        return
    
    # ===== پاک کردن تاریخچه =====
    if data == "clear_history":
        db.cursor.execute("DELETE FROM search_history WHERE admin_id = ?", (user_id,))
        db.conn.commit()
        bot.answer_callback_query(call.id, "✅ تاریخچه پاک شد!")
        bot.edit_message_text(
            "🗑️ تاریخچه جستجوی شما پاک شد.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        return
    
    # ===== اطلاعات خودم =====
    if data == "my_info":
        user = bot.get_chat_member(call.message.chat.id, user_id).user
        info = format_user_info(user)
        bot.edit_message_text(info, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # ===== عکس پروفایل =====
    if data.startswith("photo_"):
        target_id = int(data.split("_")[1])
        try:
            photos = bot.get_user_profile_photos(target_id, limit=1)
            if photos.total_count > 0:
                photo = photos.photos[0][-1]
                bot.send_photo(
                    call.message.chat.id,
                    photo.file_id,
                    caption=f"🖼️ عکس پروفایل کاربر <code>{target_id}</code>",
                    parse_mode='HTML'
                )
                bot.answer_callback_query(call.id)
            else:
                bot.answer_callback_query(call.id, "❌ این کاربر عکس پروفایل ندارد!")
        except:
            bot.answer_callback_query(call.id, "❌ خطا در دریافت عکس!")
        return
    
    # ===== کپی آیدی =====
    if data.startswith("copy_"):
        target_id = data.split("_")[1]
        bot.send_message(
            call.message.chat.id,
            f"📋 آیدی کاربر: <code>{target_id}</code>",
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id, "✅ آیدی کپی شد!")
        return
    
    # ===== راهنما =====
    if data == "help":
        text = """
🆘 <b>راهنمای ربات</b>
━━━━━━━━━━━━━━━━━━━━━━
🔹 <b>چگونه جستجو کنیم؟</b>
• آیدی عددی کاربر را وارد کنید
• یا یوزرنیم را با @ وارد کنید
• مثال: 8916314219 یا @rezagrootz

🔹 <b>چه اطلاعاتی نمایش داده میشه؟</b>
• نام و نام خانوادگی
• یوزرنیم
• آیدی عددی
• وضعیت پریمیوم
• وضعیت در گروه (اگر عضو باشد)
• نقش در گروه (ادمین/عادی)

🔹 <b>امکانات اضافه:</b>
• مشاهده عکس پروفایل
• کپی آیدی کاربر
• تاریخچه جستجو

👑 <b>فقط ادمین‌ها!</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return

# ==================== اجرا ====================
if __name__ == "__main__":
    print("=" * 70)
    print("🔍 ربات جستجوی اطلاعات تلگرام")
    print("=" * 70)
    print(f"👑 ادمین‌ها: {ADMIN_IDS}")
    print("💎 قابلیت‌ها:")
    print("  ✅ جستجو با آیدی عددی")
    print("  ✅ جستجو با یوزرنیم")
    print("  ✅ نمایش اطلاعات کامل کاربر")
    print("  ✅ نمایش وضعیت در گروه")
    print("  ✅ دریافت عکس پروفایل")
    print("  ✅ تاریخچه جستجو")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)
