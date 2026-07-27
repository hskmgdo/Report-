import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import instaloader
import os
import re
import time
import requests
import shutil
from datetime import datetime
import threading
import sqlite3

# ==================== تنظیمات ====================
BOT_TOKEN = "8423981755:AAFaEYzOefEaxDiuyvKKyyTJzlhDXWSqyRw"
ADMIN_IDS = [8916314219]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('instagram_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                type TEXT,
                time INTEGER
            )
        ''')
        self.conn.commit()
    
    def add_download(self, user_id, url, media_type):
        self.cursor.execute(
            "INSERT INTO downloads (user_id, url, type, time) VALUES (?, ?, ?, ?)",
            (user_id, url, media_type, int(time.time()))
        )
        self.conn.commit()
    
    def get_stats(self, user_id):
        self.cursor.execute("SELECT COUNT(*) FROM downloads WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()[0]

db = Database()

# ==================== کلاس دانلودر اینستاگرام ====================
class InstagramDownloader:
    def __init__(self):
        self.loader = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            compress_json=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
            max_connection_attempts=3
        )
        # تنظیمات برای جلوگیری از بن شدن
        self.loader.sleep = True
        self.loader.quiet = True
        
    def download_post(self, url, user_id):
        """دانلود پست اینستاگرام با لینک"""
        try:
            # ایجاد پوشه موقت
            temp_dir = f"temp_{user_id}_{int(time.time())}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # تغییر مسیر ذخیره
            self.loader.dirname_pattern = temp_dir
            
            # دانلود پست
            post = instaloader.Post.from_url(self.loader.context, url)
            self.loader.download_post(post, target=f"{temp_dir}/{post.owner_username}")
            
            # پیدا کردن فایل‌های دانلود شده
            files = os.listdir(temp_dir)
            media_files = []
            
            for file in files:
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    # تشخیص نوع فایل
                    if file.endswith(('.mp4', '.mov')):
                        media_files.append(('video', file_path))
                    elif file.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        media_files.append(('photo', file_path))
            
            # پاک کردن پوشه بعد از دانلود (با تاخیر)
            def cleanup():
                time.sleep(5)
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            
            threading.Thread(target=cleanup, daemon=True).start()
            
            return media_files, post.owner_username, post.caption
            
        except Exception as e:
            return None, None, str(e)
    
    def download_reel(self, url, user_id):
        """دانلود ریل اینستاگرام"""
        return self.download_post(url, user_id)
    
    def download_story(self, url, user_id):
        """دانلود استوری اینستاگرام (نیاز به لاگین)"""
        # استوری نیاز به لاگین دارد، این روش پشتیبانی نمیشه
        return None, None, "استوری نیاز به لاگین دارد! لطفاً از پست یا ریل استفاده کنید."

# ==================== کیبوردها ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📥 دانلود ویدیو", callback_data="download_video"),
        InlineKeyboardButton("📸 دانلود عکس", callback_data="download_photo"),
        InlineKeyboardButton("📊 آمار دانلودها", callback_data="stats"),
        InlineKeyboardButton("🆘 راهنما", callback_data="help"),
        InlineKeyboardButton("📢 کانال ما", url="https://t.me/rezagrootz")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return keyboard

# ==================== توابع کمکی ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def extract_instagram_url(text):
    """استخراج لینک اینستاگرام از متن"""
    pattern = r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[a-zA-Z0-9_-]+/?)'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

def validate_url(url):
    """بررسی اینکه لینک اینستاگرام معتبر است"""
    if not url:
        return False
    patterns = [
        r'instagram\.com/p/',
        r'instagram\.com/reel/',
        r'instagram\.com/tv/',
        r'instagram\.com/stories/'
    ]
    for pattern in patterns:
        if re.search(pattern, url):
            return True
    return False

# ==================== دستور /start ====================
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    text = """
📥 <b>ربات دانلود اینستاگرام REZA GROOTZ</b> 📥

⚡️ <b>قابلیت‌ها:</b>
✅ دانلود ویدیو و ریل
✅ دانلود عکس
✅ دانلود پست‌های چندرسانه‌ای
✅ پشتیبانی از لینک‌های مستقیم
✅ سرعت بالا
✅ کاملاً رایگان

📌 <b>چطور استفاده کنم؟</b>
🔹 لینک پست/ریل/عکس را کپی کنید
🔹 در ربات بچسبانید و ارسال کنید
🔹 فایل دانلود شده را دریافت کنید

مثال: <code>https://www.instagram.com/p/ABC123/</code>
"""
    bot.reply_to(message, text, reply_markup=main_menu())

# ==================== دریافت لینک ====================
@bot.message_handler(func=lambda message: True)
def handle_instagram_link(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # استخراج لینک اینستاگرام
    url = extract_instagram_url(text)
    
    if not url:
        # بررسی اینکه آیا کاربر درخواست دانلود داده
        if text.lower() in ['دانلود', 'download', 'لینک']:
            bot.reply_to(message, "📥 لطفاً لینک اینستاگرام را ارسال کنید:\nمثال: https://www.instagram.com/p/ABC123/")
        else:
            bot.reply_to(message, "❌ لینک اینستاگرام معتبری یافت نشد!\nلطفاً لینک را به درستی ارسال کنید.")
        return
    
    # ارسال پیام در حال پردازش
    processing_msg = bot.reply_to(message, "⏳ در حال پردازش و دانلود... لطفاً صبر کنید...")
    
    try:
        # دانلود
        downloader = InstagramDownloader()
        media_files, username, caption = downloader.download_post(url, user_id)
        
        if not media_files:
            error_msg = f"❌ خطا در دانلود!\nمشکل: {caption}"
            bot.edit_message_text(error_msg, message.chat.id, processing_msg.message_id)
            return
        
        # ارسال فایل‌ها
        sent_count = 0
        for media_type, file_path in media_files:
            try:
                if media_type == 'video':
                    with open(file_path, 'rb') as f:
                        bot.send_video(
                            message.chat.id,
                            f,
                            caption=f"🎬 {username}\n📥 دانلود شده در: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n💡 @rezagrootz",
                            reply_markup=back_button()
                        )
                elif media_type == 'photo':
                    with open(file_path, 'rb') as f:
                        bot.send_photo(
                            message.chat.id,
                            f,
                            caption=f"📸 {username}\n📥 دانلود شده در: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n💡 @rezagrootz",
                            reply_markup=back_button()
                        )
                sent_count += 1
                # ذخیره در دیتابیس
                db.add_download(user_id, url, media_type)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ خطا در ارسال فایل: {str(e)[:100]}")
        
        # حذف پیام پردازش
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if sent_count == 0:
            bot.send_message(message.chat.id, "❌ هیچ فایلی برای ارسال یافت نشد!", reply_markup=back_button())
        else:
            bot.send_message(
                message.chat.id,
                f"✅ {sent_count} فایل با موفقیت دانلود و ارسال شد!",
                reply_markup=back_button()
            )
            
    except Exception as e:
        bot.edit_message_text(
            f"❌ خطا در دانلود!\n{str(e)[:200]}",
            message.chat.id,
            processing_msg.message_id
        )

# ==================== کال‌بک‌ها ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "back_main":
        text = """
📥 <b>ربات دانلود اینستاگرام REZA GROOTZ</b> 📥

⚡️ <b>قابلیت‌ها:</b>
✅ دانلود ویدیو و ریل
✅ دانلود عکس
✅ دانلود پست‌های چندرسانه‌ای
✅ پشتیبانی از لینک‌های مستقیم
✅ سرعت بالا
✅ کاملاً رایگان

📌 <b>چطور استفاده کنم؟</b>
🔹 لینک پست/ریل/عکس را کپی کنید
🔹 در ربات بچسبانید و ارسال کنید
🔹 فایل دانلود شده را دریافت کنید
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data == "download_video":
        bot.edit_message_text(
            "🎬 لطفاً لینک ویدیو یا ریل اینستاگرام را ارسال کنید:\nمثال: https://www.instagram.com/reel/ABC123/",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "download_photo":
        bot.edit_message_text(
            "📸 لطفاً لینک عکس اینستاگرام را ارسال کنید:\nمثال: https://www.instagram.com/p/ABC123/",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "stats":
        total = db.get_stats(user_id)
        text = f"""
📊 <b>آمار دانلودهای شما</b>
━━━━━━━━━━━━━━━━━━━━━━
📥 تعداد دانلودها: {total}
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if data == "help":
        text = """
🆘 <b>راهنمای ربات</b>
━━━━━━━━━━━━━━━━━━━━━━
📌 <b>چطور دانلود کنم؟</b>
1. لینک پست/ریل/عکس را کپی کنید
2. در ربات بچسبانید و ارسال کنید
3. فایل دانلود شده را دریافت کنید

🔹 <b>لینک‌های پشتیبانی شده:</b>
• پست: instagram.com/p/...
• ریل: instagram.com/reel/...
• ویدیو: instagram.com/tv/...

⚠️ <b>نکات مهم:</b>
• پست‌های خصوصی قابل دانلود نیستند
• استوری نیاز به لاگین دارد
• حجم فایل‌ها محدود نیست

📢 <b>کانال ما:</b> @rezagrootz
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return

# ==================== اجرا ====================
if __name__ == "__main__":
    print("=" * 70)
    print("📥 ربات دانلود اینستاگرام REZA GROOTZ")
    print("=" * 70)
    print("💎 قابلیت‌ها:")
    print("  ✅ دانلود ویدیو/ریل")
    print("  ✅ دانلود عکس")
    print("  ✅ دانلود پست‌های چندرسانه‌ای")
    print("  ✅ پشتیبانی از لینک‌های مستقیم")
    print("  ✅ سرعت بالا")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)
