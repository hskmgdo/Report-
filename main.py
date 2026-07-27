import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import os
import re
import time
import requests
import shutil
import threading
import sqlite3
import json
import subprocess
from datetime import datetime
from pathlib import Path
import yt_dlp

# ==================== تنظیمات ====================
BOT_TOKEN = "8423981755:AAFaEYzOefEaxDiuyvKKyyTJzlhDXWSqyRw"
ADMIN_IDS = [8916314219]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('downloader_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                type TEXT,
                platform TEXT,
                time INTEGER
            )
        ''')
        self.conn.commit()
    
    def add_download(self, user_id, url, media_type, platform):
        self.cursor.execute(
            "INSERT INTO downloads (user_id, url, type, platform, time) VALUES (?, ?, ?, ?, ?)",
            (user_id, url, media_type, platform, int(time.time()))
        )
        self.conn.commit()
    
    def get_stats(self, user_id):
        self.cursor.execute("SELECT COUNT(*) FROM downloads WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()[0]

db = Database()

# ==================== کیبوردها ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎬 دانلود یوتیوب", callback_data="youtube"),
        InlineKeyboardButton("🎵 دانلود آهنگ", callback_data="music"),
        InlineKeyboardButton("📸 اینستاگرام", callback_data="instagram"),
        InlineKeyboardButton("🎬 دانلود کلیپ", callback_data="clip"),
        InlineKeyboardButton("📊 آمار من", callback_data="stats"),
        InlineKeyboardButton("🆘 راهنما", callback_data="help")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return keyboard

# ==================== کلاس دانلودر ====================
class Downloader:
    
    @staticmethod
    def download_media(url, user_id, audio_only=False):
        """دانلود از هر پلتفرمی با yt-dlp"""
        
        # ایجاد پوشه موقت
        temp_dir = f"temp_{user_id}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # تنظیمات yt-dlp
            if audio_only:
                ydl_opts = {
                    'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'socket_timeout': 30,
                    'retries': 10,
                    'fragment_retries': 10,
                    'ignoreerrors': True
                }
            else:
                ydl_opts = {
                    'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'best[ext=mp4]/best',
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'socket_timeout': 30,
                    'retries': 10,
                    'fragment_retries': 10,
                    'ignoreerrors': True
                }
            
            # دانلود
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    return None, None, "خطا: اطلاعات ویدیو دریافت نشد"
                
                # پیدا کردن فایل دانلود شده
                files = os.listdir(temp_dir)
                if not files:
                    return None, None, "خطا: فایلی دانلود نشد"
                
                # پیدا کردن فایل اصلی
                media_file = None
                for file in files:
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path) and os.path.getsize(file_path) > 1024:  # بزرگتر از 1KB
                        media_file = file_path
                        break
                
                if not media_file:
                    return None, None, "خطا: فایل معتبری پیدا نشد"
                
                # تشخیص نوع فایل
                if media_file.endswith(('.mp3', '.m4a', '.aac', '.wav')):
                    media_type = 'audio'
                elif media_file.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    media_type = 'video'
                else:
                    media_type = 'other'
                
                # گرفتن عنوان
                title = info.get('title', 'فایل')
                uploader = info.get('uploader', 'ناشناس')
                
                # پاک کردن پوشه بعد از دانلود
                def cleanup():
                    time.sleep(10)
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except:
                        pass
                threading.Thread(target=cleanup, daemon=True).start()
                
                return [(media_type, media_file)], title, uploader
                
        except Exception as e:
            # پاک کردن پوشه در صورت خطا
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            return None, None, str(e)[:200]
    
    @staticmethod
    def detect_platform(url):
        """تشخیص پلتفرم"""
        patterns = {
            'youtube': r'(youtube\.com|youtu\.be)',
            'instagram': r'(instagram\.com|instagr\.am)',
            'tiktok': r'(tiktok\.com|vm\.tiktok)',
            'twitter': r'(twitter\.com|x\.com)',
            'soundcloud': r'(soundcloud\.com)',
            'aparat': r'(aparat\.com)',
            'telegram': r'(t\.me|telegram\.org)'
        }
        
        for platform, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform
        return 'unknown'

# ==================== دستور /start ====================
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    text = """
🌟 <b>ربات دانلودر فوق‌پیشرفته</b> 🌟

⚡️ <b>قابلیت‌ها:</b>
✅ دانلود از یوتیوب
✅ دانلود آهنگ (تبدیل به MP3)
✅ دانلود از اینستاگرام
✅ دانلود کلیپ و ریل
✅ پشتیبانی از تیک‌تاک، توییتر، آپارات و...

📌 <b>چطور استفاده کنم؟</b>
🔹 گزینه مورد نظر را انتخاب کنید
🔹 لینک را بفرستید
🔹 فایل را دریافت کنید

💡 <b>فقط کافیه لینک رو بفرستی!</b>
"""
    bot.reply_to(message, text, reply_markup=main_menu())

# ==================== دریافت لینک ====================
@bot.message_handler(func=lambda message: True)
def handle_links(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # اگر دستورات خاص باشه
    if text.startswith('/'):
        return
    
    # تشخیص پلتفرم
    platform = Downloader.detect_platform(text)
    
    if platform == 'unknown':
        if len(text) > 10 and ('http' in text or 'www' in text):
            # تلاش برای دانلود با لینک مستقیم
            processing_msg = bot.reply_to(message, "⏳ در حال دانلود لینک مستقیم...")
            try:
                response = requests.get(text, stream=True, timeout=30)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '')
                    filename = f"temp_{user_id}_{int(time.time())}.mp4"
                    
                    if 'video' in content_type:
                        filename = filename.replace('.mp4', '.mp4')
                    elif 'image' in content_type:
                        filename = filename.replace('.mp4', '.jpg')
                    elif 'audio' in content_type:
                        filename = filename.replace('.mp4', '.mp3')
                    else:
                        filename = filename.replace('.mp4', '.bin')
                    
                    with open(filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # ارسال فایل
                    with open(filename, 'rb') as f:
                        if filename.endswith('.mp4'):
                            bot.send_video(message.chat.id, f, caption="📥 لینک مستقیم @rezagrootz")
                        elif filename.endswith(('.jpg', '.png')):
                            bot.send_photo(message.chat.id, f, caption="📥 لینک مستقیم @rezagrootz")
                        elif filename.endswith('.mp3'):
                            bot.send_audio(message.chat.id, f, caption="📥 لینک مستقیم @rezagrootz")
                        else:
                            bot.send_document(message.chat.id, f, caption="📥 لینک مستقیم @rezagrootz")
                    
                    os.remove(filename)
                    bot.delete_message(message.chat.id, processing_msg.message_id)
                    return
                else:
                    bot.edit_message_text("❌ لینک معتبر نیست!", message.chat.id, processing_msg.message_id)
                    return
            except Exception as e:
                bot.edit_message_text(f"❌ خطا: {str(e)[:100]}", message.chat.id, processing_msg.message_id)
                return
        else:
            bot.reply_to(message, "❌ لینک معتبری یافت نشد!\nلطفاً یک لینک معتبر بفرستید.", reply_markup=main_menu())
        return
    
    # پردازش لینک
    processing_msg = bot.reply_to(message, f"⏳ در حال دانلود از {platform}...")
    
    # دانلود
    media_files, title, uploader = Downloader.download_media(text, user_id, audio_only=False)
    
    if not media_files:
        bot.edit_message_text(
            f"❌ خطا در دانلود!\n\n🔹 پلتفرم: {platform}\n🔹 خطا: {uploader}\n\n💡 نکات:\n• لینک رو چک کن\n• از VPN استفاده کن\n• دوباره تلاش کن",
            message.chat.id,
            processing_msg.message_id,
            reply_markup=back_button()
        )
        return
    
    # حذف پیام پردازش
    bot.delete_message(message.chat.id, processing_msg.message_id)
    
    # ارسال فایل‌ها
    for media_type, file_path in media_files:
        try:
            # بررسی حجم فایل
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # تبدیل به مگابایت
            if file_size > 50:  # اگر بزرگتر از 50 مگابایت بود
                bot.send_message(
                    message.chat.id,
                    f"⚠️ حجم فایل {file_size:.1f} مگابایت است. ممکن است ارسال آن طول بکشد..."
                )
            
            with open(file_path, 'rb') as f:
                if media_type == 'video':
                    bot.send_video(
                        message.chat.id,
                        f,
                        caption=f"🎬 <b>{title[:50]}</b>\n👤 {uploader}\n📥 @rezagrootz",
                        reply_markup=back_button()
                    )
                elif media_type == 'audio':
                    bot.send_audio(
                        message.chat.id,
                        f,
                        caption=f"🎵 <b>{title[:50]}</b>\n👤 {uploader}\n📥 @rezagrootz",
                        reply_markup=back_button()
                    )
                else:
                    bot.send_document(
                        message.chat.id,
                        f,
                        caption=f"📄 <b>{title[:50]}</b>\n📥 @rezagrootz",
                        reply_markup=back_button()
                    )
            
            db.add_download(user_id, text, media_type, platform)
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ارسال: {str(e)[:100]}")
    
    # پاک کردن فایل موقت
    try:
        os.remove(file_path)
    except:
        pass
    
    # پاک کردن پوشه
    temp_dir = os.path.dirname(file_path)
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except:
        pass

# ==================== کال‌بک‌ها ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    
    if data == "back_main":
        text = "🌟 <b>منوی اصلی</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data == "youtube":
        bot.edit_message_text(
            "🎬 <b>دانلود از یوتیوب</b>\n\nلینک ویدیو یا لیست پخش را بفرستید.\n\n📌 کیفیت خودکار انتخاب میشه.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "music":
        bot.edit_message_text(
            "🎵 <b>دانلود آهنگ</b>\n\nلینک ویدیو یا آهنگ را بفرستید تا به MP3 تبدیل کنم.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "instagram":
        bot.edit_message_text(
            "📸 <b>دانلود از اینستاگرام</b>\n\nلینک پست، ریل یا استوری را بفرستید.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "clip":
        bot.edit_message_text(
            "🎬 <b>دانلود کلیپ</b>\n\nلینک کلیپ (Shorts/Reel/TikTok) را بفرستید.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "stats":
        total = db.get_stats(call.from_user.id)
        text = f"""
📊 <b>آمار شما</b>
━━━━━━━━━━━━━━━━━━━━━━
📥 تعداد دانلودها: {total}
📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if data == "help":
        text = """
🆘 <b>راهنما</b>
━━━━━━━━━━━━━━━━━━━━━━

🎬 <b>یوتیوب:</b> لینک ویدیو رو بفرست
🎵 <b>آهنگ:</b> لینک ویدیو رو بفرست، MP3 میشه
📸 <b>اینستاگرام:</b> لینک پست/ریل رو بفرست
🎬 <b>کلیپ:</b> لینک Shorts/Reel رو بفرست

🔹 <b>پشتیبانی از:</b>
یوتیوب • اینستاگرام • تیک‌تاک • توییتر • آپارات • ساندکلاود

⚠️ <b>نکات:</b>
• لینک رو کامل بفرست
• اگر تحریم هستی از VPN استفاده کن
• حجم فایل‌ها محدود نیست

📢 @rezagrootz
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return

# ==================== اجرا ====================
if __name__ == "__main__":
    print("=" * 70)
    print("🌟 ربات دانلودر فوق‌پیشرفته")
    print("=" * 70)
    print("💎 قابلیت‌ها:")
    print("  ✅ دانلود از یوتیوب")
    print("  ✅ دانلود آهنگ (MP3)")
    print("  ✅ دانلود از اینستاگرام")
    print("  ✅ دانلود کلیپ")
    print("  ✅ پشتیبانی از تیک‌تاک، توییتر، آپارات")
    print("  ✅ لینک مستقیم")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            time.sleep(5)
