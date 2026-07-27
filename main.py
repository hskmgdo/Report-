import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import os
import re
import time
import requests
import shutil
from datetime import datetime
import threading
import sqlite3
import instaloader
import yt_dlp
from bs4 import BeautifulSoup

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

# ==================== کیبوردها ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📥 دانلود ویدیو", callback_data="download_video"),
        InlineKeyboardButton("📸 دانلود عکس", callback_data="download_photo"),
        InlineKeyboardButton("📊 آمار دانلودها", callback_data="stats"),
        InlineKeyboardButton("🆘 راهنما", callback_data="help")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return keyboard

# ==================== روش‌های دانلود ====================
class InstagramDownloader:
    
    # ---- ابزار کمکی برای پیدا کردن فایل‌ها به صورت بازگشتی ----
    @staticmethod
    def find_media_files(directory):
        media_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file)[1].lower()
                    if ext in ('.mp4', '.mov', '.avi', '.mkv'):
                        media_files.append(('video', file_path))
                    elif ext in ('.mp3', '.m4a', '.aac'):
                        media_files.append(('audio', file_path))
                    elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                        media_files.append(('photo', file_path))
        return media_files

    # ===== روش 1: yt-dlp (اولویت برای ویدیو + استخراج صدا) =====
    @staticmethod
    def method_ytdlp(url, temp_dir):
        try:
            ydl_opts = {
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'format': 'best[ext=mp4]/best',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'keepvideo': True,  # نگه‌داشتن فایل ویدیو پس از استخراج صدا
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    # پیدا کردن فایل‌های دانلود شده
                    base_filename = ydl.prepare_filename(info)
                    # حذف پسوند برای پیدا کردن فایل‌های مرتبط
                    base_no_ext = os.path.splitext(base_filename)[0]
                    
                    # اسکن پوشه برای یافتن همه فایل‌های رسانه‌ای
                    media_files = InstagramDownloader.find_media_files(temp_dir)
                    if media_files:
                        username = info.get('uploader', 'instagram')
                        caption = info.get('description', '')
                        return media_files, username, caption
            return None, None, "yt-dlp: فایلی پیدا نشد"
        except Exception as e:
            return None, None, f"yt-dlp: {str(e)[:100]}"

    # ===== روش 2: instaloader (برای عکس و ویدیو بدون صدا) =====
    @staticmethod
    def method_instaloader(url, temp_dir):
        try:
            loader = instaloader.Instaloader(
                download_pictures=True,
                download_videos=True,
                download_video_thumbnails=False,
                compress_json=False,
                save_metadata=False,
                post_metadata_txt_pattern="",
                max_connection_attempts=3
            )
            loader.quiet = True
            loader.sleep = True
            loader.dirname_pattern = temp_dir  # پوشه اصلی
            
            post = instaloader.Post.from_url(loader.context, url)
            loader.download_post(post, target=temp_dir)  # دانلود مستقیم در temp_dir
            
            # اسکن بازگشتی پوشه برای یافتن فایل‌ها
            media_files = InstagramDownloader.find_media_files(temp_dir)
            if media_files:
                return media_files, post.owner_username, post.caption
            return None, None, "instaloader: فایلی پیدا نشد"
        except Exception as e:
            return None, None, f"instaloader: {str(e)[:100]}"

    # ===== روش 3: API (snapinsta) =====
    @staticmethod
    def method_api(url, temp_dir):
        try:
            response = requests.post(
                'https://snapinsta.app/api/ajaxSearch',
                data={'q': url},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    # برای ویدیو
                    video_url = data['data'][0].get('url')
                    if video_url:
                        response = requests.get(video_url, stream=True, timeout=30)
                        if response.status_code == 200:
                            filename = f"{temp_dir}/video_{int(time.time())}.mp4"
                            with open(filename, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=1024*1024):
                                    if chunk:
                                        f.write(chunk)
                            media_files = [('video', filename)]
                            return media_files, 'instagram', 'دانلود شده با snapinsta'
                    # برای عکس
                    image_url = data['data'][0].get('url')
                    if image_url:
                        response = requests.get(image_url, stream=True, timeout=30)
                        if response.status_code == 200:
                            filename = f"{temp_dir}/photo_{int(time.time())}.jpg"
                            with open(filename, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=1024*1024):
                                    if chunk:
                                        f.write(chunk)
                            media_files = [('photo', filename)]
                            return media_files, 'instagram', 'دانلود شده با snapinsta'
            return None, None, "API: خطا در دریافت لینک"
        except Exception as e:
            return None, None, f"API: {str(e)[:100]}"

    # ===== متد اصلی =====
    @staticmethod
    def download(url, user_id):
        temp_dir = f"temp_{user_id}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        results = []
        # ترتیب: yt-dlp اول (برای ویدیو+صدا)، سپس instaloader، سپس API
        methods = [
            ('yt-dlp', InstagramDownloader.method_ytdlp),
            ('instaloader', InstagramDownloader.method_instaloader),
            ('API', InstagramDownloader.method_api)
        ]
        
        for method_name, method_func in methods:
            try:
                media_files, username, caption = method_func(url, temp_dir)
                if media_files:
                    results = media_files
                    break
            except:
                continue
        
        # پاک کردن پوشه بعد از دانلود
        def cleanup():
            time.sleep(5)
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        threading.Thread(target=cleanup, daemon=True).start()
        
        if results:
            return results, username or 'instagram', caption or 'بدون توضیحات'
        return None, None, "همه روش‌ها ناموفق بودن!"

# ==================== دستور /start ====================
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    text = """
📥 <b>ربات دانلود اینستاگرام REZA GROOTZ</b> 📥

⚡️ <b>قابلیت‌ها:</b>
✅ دانلود عکس و ویدیو
✅ استخراج صدا از ویدیو (MP3)
✅ ۳ روش دانلود پشتیبان
✅ سرعت بالا و کاملاً رایگان

📌 <b>چطور استفاده کنم؟</b>
🔹 لینک را کپی کنید و در ربات بفرستید
🔹 فایل‌های دانلود شده را دریافت کنید

مثال: <code>https://www.instagram.com/p/ABC123/</code>
"""
    bot.reply_to(message, text, reply_markup=main_menu())

# ==================== دریافت لینک ====================
@bot.message_handler(func=lambda message: True)
def handle_instagram_link(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # استخراج لینک
    pattern = r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[a-zA-Z0-9_-]+/?)'
    match = re.search(pattern, text)
    
    if not match:
        if text.lower() in ['دانلود', 'download']:
            bot.reply_to(message, "📥 لطفاً لینک اینستاگرام را ارسال کنید.")
        else:
            bot.reply_to(message, "❌ لینک اینستاگرام معتبری یافت نشد!")
        return
    
    url = match.group(1)
    processing_msg = bot.reply_to(message, "⏳ در حال دانلود... لطفاً صبر کنید...")
    
    try:
        media_files, username, caption = InstagramDownloader.download(url, user_id)
        
        if not media_files:
            bot.edit_message_text(
                f"❌ خطا در دانلود!\nهمه روش‌ها ناموفق بودن.\n\n💡 نکات:\n• مطمئن شوید لینک درست است\n• پست خصوصی نباشد\n• از VPN استفاده کنید\n\n📢 @rezagrootz",
                message.chat.id,
                processing_msg.message_id
            )
            return
        
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        # ارسال فایل‌ها
        for media_type, file_path in media_files:
            try:
                if media_type == 'video':
                    with open(file_path, 'rb') as f:
                        bot.send_video(
                            message.chat.id,
                            f,
                            caption=f"🎬 {username}\n📥 @rezagrootz",
                            reply_markup=back_button()
                        )
                elif media_type == 'photo':
                    with open(file_path, 'rb') as f:
                        bot.send_photo(
                            message.chat.id,
                            f,
                            caption=f"📸 {username}\n📥 @rezagrootz",
                            reply_markup=back_button()
                        )
                elif media_type == 'audio':
                    with open(file_path, 'rb') as f:
                        bot.send_audio(
                            message.chat.id,
                            f,
                            caption=f"🎵 {username}\n📥 @rezagrootz",
                            reply_markup=back_button()
                        )
                db.add_download(user_id, url, media_type)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ خطا در ارسال فایل: {str(e)[:100]}")
        
        bot.send_message(
            message.chat.id,
            f"✅ دانلود با موفقیت انجام شد!",
            reply_markup=back_button()
        )
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ خطا: {str(e)[:200]}",
            message.chat.id,
            processing_msg.message_id
        )

# ==================== کال‌بک‌ها ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    
    if data == "back_main":
        text = "📥 <b>ربات دانلود اینستاگرام</b>\nلینک را بفرستید تا دانلود کنم."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data == "download_video":
        bot.edit_message_text(
            "🎬 لینک ویدیو یا ریل را بفرستید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "download_photo":
        bot.edit_message_text(
            "📸 لینک عکس را بفرستید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "stats":
        total = db.get_stats(call.from_user.id)
        bot.edit_message_text(
            f"📊 تعداد دانلودها: {total}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "help":
        text = """
🆘 <b>راهنما</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ لینک را کپی کنید و بفرستید
✅ ربات با ۳ روش دانلود میکنه
✅ اگر یکی خطا داد، روش بعدی رو امتحان میکنه

🔹 <b>لینک‌های پشتیبانی:</b>
• instagram.com/p/... (عکس یا ویدیو)
• instagram.com/reel/... (ریل)
• instagram.com/tv/... (ویدیو)

🎵 <b>ویژگی جدید:</b>
برای ویدیو و ریل، صدای آن نیز به صورت MP3 دانلود می‌شود.

⚠️ <b>نکات:</b>
• پست‌های خصوصی قابل دانلود نیستند
• اگر تحریم هستید، از VPN استفاده کنید
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return

# ==================== اجرا ====================
if __name__ == "__main__":
    print("=" * 70)
    print("📥 ربات دانلود اینستاگرام (۳ روش + استخراج صدا)")
    print("=" * 70)
    print("💎 روش‌های دانلود:")
    print("  1️⃣ yt-dlp (اولویت برای ویدیو + صدا)")
    print("  2️⃣ instaloader (عکس و ویدیو)")
    print("  3️⃣ API (snapinsta)")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            time.sleep(5)
