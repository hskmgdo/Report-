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
from datetime import datetime
import yt_dlp
import instaloader
from pathlib import Path

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
    
    def get_platform_stats(self, user_id):
        self.cursor.execute(
            "SELECT platform, COUNT(*) FROM downloads WHERE user_id = ? GROUP BY platform",
            (user_id,)
        )
        return self.cursor.fetchall()

db = Database()

# ==================== کلاس دانلودر پیشرفته ====================
class AdvancedDownloader:
    
    @staticmethod
    def detect_platform(url):
        """تشخیص پلتفرم از روی لینک"""
        if re.search(r'(youtube\.com|youtu\.be)', url):
            return 'youtube'
        elif re.search(r'(instagram\.com|instagr\.am)', url):
            return 'instagram'
        elif re.search(r'(tiktok\.com|vm\.tiktok)', url):
            return 'tiktok'
        elif re.search(r'(twitter\.com|x\.com)', url):
            return 'twitter'
        elif re.search(r'(soundcloud\.com)', url):
            return 'soundcloud'
        elif re.search(r'(spotify\.com)', url):
            return 'spotify'
        elif re.search(r'(aparat\.com)', url):
            return 'aparat'
        elif re.search(r'(telegram\.org|t\.me)', url):
            return 'telegram'
        else:
            return 'unknown'
    
    @staticmethod
    def download_with_ytdlp(url, user_id, audio_only=False, quality='best'):
        """دانلود با yt-dlp (پشتیبانی از یوتیوب، اینستاگرام، تیک‌تاک و...)"""
        temp_dir = f"temp_{user_id}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            if audio_only:
                # دانلود فقط صدا
                ydl_opts = {
                    'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }],
                    'extract_flat': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            else:
                # دانلود ویدیو
                ydl_opts = {
                    'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                    'extract_flat': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    # پیدا کردن فایل دانلود شده
                    files = os.listdir(temp_dir)
                    for file in files:
                        file_path = os.path.join(temp_dir, file)
                        if os.path.isfile(file_path):
                            # تشخیص نوع فایل
                            if file.endswith(('.mp3', '.m4a', '.aac', '.wav')):
                                return [('audio', file_path)], info.get('title', 'فایل'), info.get('uploader', '')
                            elif file.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                                return [('video', file_path)], info.get('title', 'فایل'), info.get('uploader', '')
                            elif file.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                return [('photo', file_path)], info.get('title', 'فایل'), info.get('uploader', '')
            
            # پاک کردن پوشه
            def cleanup():
                time.sleep(5)
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            threading.Thread(target=cleanup, daemon=True).start()
            
            return None, None, "فایلی پیدا نشد"
            
        except Exception as e:
            # پاک کردن پوشه
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            return None, None, str(e)[:200]
    
    @staticmethod
    def download_instagram(url, user_id):
        """دانلود از اینستاگرام با instaloader"""
        temp_dir = f"temp_{user_id}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
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
            loader.dirname_pattern = temp_dir
            
            post = instaloader.Post.from_url(loader.context, url)
            loader.download_post(post, target=f"{temp_dir}/{post.owner_username}")
            
            files = os.listdir(temp_dir)
            media_files = []
            for file in files:
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    if file.endswith(('.mp4', '.mov', '.avi')):
                        media_files.append(('video', file_path))
                    elif file.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        media_files.append(('photo', file_path))
            
            def cleanup():
                time.sleep(5)
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            threading.Thread(target=cleanup, daemon=True).start()
            
            if media_files:
                return media_files, post.owner_username, post.caption
            return None, None, "فایلی پیدا نشد"
            
        except Exception as e:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            return None, None, str(e)[:200]

# ==================== کیبوردهای رنگی ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📥 دانلود یوتیوب", callback_data="youtube"),
        InlineKeyboardButton("🎵 دانلود آهنگ", callback_data="music"),
        InlineKeyboardButton("📸 دانلود اینستاگرام", callback_data="instagram"),
        InlineKeyboardButton("🎬 دانلود کلیپ", callback_data="clip"),
        InlineKeyboardButton("🔗 لینک مستقیم", callback_data="direct"),
        InlineKeyboardButton("📊 آمار من", callback_data="stats"),
        InlineKeyboardButton("🆘 راهنما", callback_data="help"),
        InlineKeyboardButton("📢 کانال ما", url="https://t.me/rezagrootz")
    )
    return keyboard

def quality_menu(platform):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📱 کیفیت بالا (1080p)", callback_data=f"quality_high_{platform}"),
        InlineKeyboardButton("📱 کیفیت متوسط (720p)", callback_data=f"quality_med_{platform}"),
        InlineKeyboardButton("📱 کیفیت پایین (480p)", callback_data=f"quality_low_{platform}"),
        InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data=f"quality_audio_{platform}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return keyboard

# ==================== دستور /start ====================
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    text = """
🌟 <b>ربات دانلودر فوق‌پیشرفته REZA GROOTZ</b> 🌟

⚡️ <b>قابلیت‌های بی‌نظیر:</b>
✅ دانلود از یوتیوب (ویدیو و آهنگ)
✅ دانلود از اینستاگرام (پست، ریل، استوری)
✅ دانلود از تیک‌تاک
✅ دانلود از توییتر/X
✅ دانلود از آپارات
✅ دانلود کلیپ و ویدیو کوتاه
✅ تبدیل ویدیو به آهنگ (MP3)
✅ کیفیت‌های مختلف (1080p, 720p, 480p)
✅ سرعت فوق‌العاده بالا

📌 <b>چطور استفاده کنم؟</b>
🔹 گزینه مورد نظر را انتخاب کنید
🔹 لینک را بفرستید
🔹 فایل دانلود شده را دریافت کنید

💡 <b>پشتیبانی از:</b> یوتیوب • اینستاگرام • تیک‌تاک • توییتر • آپارات • و...
"""
    bot.reply_to(message, text, reply_markup=main_menu())

# ==================== دریافت لینک ====================
@bot.message_handler(func=lambda message: True)
def handle_link(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # تشخیص پلتفرم
    platform = AdvancedDownloader.detect_platform(text)
    
    if platform == 'unknown':
        if text.lower() in ['دانلود', 'download', 'لینک', 'link']:
            bot.reply_to(message, "📥 لطفاً لینک مورد نظر را ارسال کنید.\n\nمثال:\n• یوتیوب: https://youtube.com/watch?v=...\n• اینستاگرام: https://instagram.com/p/...")
        else:
            bot.reply_to(message, "❌ لینک معتبری یافت نشد!\nلطفاً لینک را به درستی ارسال کنید.", reply_markup=main_menu())
        return
    
    # پردازش لینک
    processing_msg = bot.reply_to(message, f"⏳ در حال پردازش لینک از {platform}...")
    
    try:
        if platform == 'youtube':
            # دانلود از یوتیوب
            media_files, title, uploader = AdvancedDownloader.download_with_ytdlp(text, user_id, audio_only=False)
        elif platform == 'instagram':
            media_files, title, uploader = AdvancedDownloader.download_instagram(text, user_id)
        else:
            # سایر پلتفرم‌ها با yt-dlp
            media_files, title, uploader = AdvancedDownloader.download_with_ytdlp(text, user_id, audio_only=False)
        
        if not media_files:
            bot.edit_message_text(
                f"❌ خطا در دانلود!\n\n🔹 <b>پلتفرم:</b> {platform}\n🔹 <b>خطا:</b> {uploader}\n\n💡 ممکن است:\n• لینک اشتباه باشد\n• محتوا خصوصی باشد\n• محدودیت منطقه‌ای وجود داشته باشد",
                message.chat.id,
                processing_msg.message_id,
                reply_markup=back_button()
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
                            caption=f"🎬 <b>{title[:50]}</b>\n👤 {uploader}\n📥 @rezagrootz",
                            reply_markup=back_button()
                        )
                elif media_type == 'audio':
                    with open(file_path, 'rb') as f:
                        bot.send_audio(
                            message.chat.id,
                            f,
                            caption=f"🎵 <b>{title[:50]}</b>\n👤 {uploader}\n📥 @rezagrootz",
                            reply_markup=back_button()
                        )
                elif media_type == 'photo':
                    with open(file_path, 'rb') as f:
                        bot.send_photo(
                            message.chat.id,
                            f,
                            caption=f"📸 <b>{title[:50]}</b>\n📥 @rezagrootz",
                            reply_markup=back_button()
                        )
                
                db.add_download(user_id, text, media_type, platform)
                
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ خطا در ارسال: {str(e)[:100]}")
        
        # پاک کردن پوشه
        temp_dir = os.path.dirname(file_path) if media_files else None
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ خطا: {str(e)[:200]}",
            message.chat.id,
            processing_msg.message_id
        )

# ==================== کال‌بک‌ها ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "back_main":
        text = "🌟 <b>منوی اصلی ربات دانلودر</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data == "youtube":
        text = """
🎬 <b>دانلود از یوتیوب</b>

📌 لینک ویدیو یا لیست پخش را بفرستید.

📌 <b>کیفیت مورد نظر را انتخاب کنید:</b>
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=quality_menu('youtube'))
        bot.answer_callback_query(call.id)
        return
    
    if data == "music":
        bot.edit_message_text(
            "🎵 <b>دانلود آهنگ</b>\n\nلینک آهنگ یا ویدیو را بفرستید تا به MP3 تبدیل کنم.\n\n📌 از یوتیوب، ساندکلاود و... پشتیبانی میکنم.",
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
            "🎬 <b>دانلود کلیپ و ویدیو کوتاه</b>\n\nلینک کلیپ از هر پلتفرمی (یوتیوب Shorts، اینستاگرام Reel، تیک‌تاک و...) را بفرستید.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "direct":
        bot.edit_message_text(
            "🔗 <b>دانلود با لینک مستقیم</b>\n\nلینک مستقیم فایل را بفرستید تا دانلود کنم.\n\n📌 پشتیبانی از: mp4, mp3, jpg, png, pdf, zip و...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    if data == "stats":
        total = db.get_stats(user_id)
        platform_stats = db.get_platform_stats(user_id)
        
        text = f"""
📊 <b>آمار دانلودهای شما</b>
━━━━━━━━━━━━━━━━━━━━━━
📥 تعداد کل: {total}

<b>📈 تفکیک پلتفرم‌ها:</b>
"""
        if platform_stats:
            for platform, count in platform_stats:
                emoji = {'youtube': '🎬', 'instagram': '📸', 'tiktok': '🎵', 'twitter': '🐦', 'soundcloud': '🎧'}.get(platform, '🔗')
                text += f"{emoji} {platform}: {count}\n"
        else:
            text += "📭 هنوز دانلودی نداری!"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if data == "help":
        text = """
🆘 <b>راهنمای کامل ربات</b>
━━━━━━━━━━━━━━━━━━━━━━

🎬 <b>دانلود یوتیوب:</b>
• ویدیو با کیفیت 1080p/720p/480p
• دانلود لیست پخش
• دانلود زیرنویس

🎵 <b>دانلود آهنگ:</b>
• تبدیل ویدیو به MP3
• کیفیت 320kbps
• پشتیبانی از ساندکلاود

📸 <b>اینستاگرام:</b>
• پست، ریل، استوری
• دانلود عکس و ویدیو
• کیفیت اصلی

🎬 <b>کلیپ:</b>
• یوتیوب Shorts
• اینستاگرام Reel
• تیک‌تاک
• ویدیوهای کوتاه

🔗 <b>لینک مستقیم:</b>
• هر فایل با لینک مستقیم

━━━━━━━━━━━━━━━━━━━━━━
📢 <b>کانال ما:</b> @rezagrootz
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # ===== کیفیت =====
    if data.startswith('quality_'):
        parts = data.split('_')
        quality = parts[1]
        platform = parts[2]
        
        if quality == 'audio':
            # دانلود فقط صدا
            bot.edit_message_text(
                f"🎵 <b>دانلود آهنگ از {platform}</b>\n\nلینک ویدیو یا آهنگ را بفرستید تا به MP3 تبدیل کنم.\n\nکیفیت: 320kbps",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=back_button()
            )
        else:
            quality_map = {'high': '1080p', 'med': '720p', 'low': '480p'}
            bot.edit_message_text(
                f"🎬 <b>دانلود از {platform}</b>\n\nلینک ویدیو را بفرستید.\n\nکیفیت: {quality_map.get(quality, 'بهترین')}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=back_button()
            )
        bot.answer_callback_query(call.id)
        return

# ==================== اجرا ====================
if __name__ == "__main__":
    print("=" * 70)
    print("🌟 ربات دانلودر فوق‌پیشرفته REZA GROOTZ")
    print("=" * 70)
    print("💎 قابلیت‌ها:")
    print("  ✅ دانلود از یوتیوب (ویدیو + آهنگ)")
    print("  ✅ دانلود از اینستاگرام")
    print("  ✅ دانلود از تیک‌تاک")
    print("  ✅ دانلود از توییتر/X")
    print("  ✅ دانلود از آپارات")
    print("  ✅ دانلود کلیپ و ویدیو کوتاه")
    print("  ✅ تبدیل ویدیو به MP3")
    print("  ✅ کیفیت‌های مختلف (1080p, 720p, 480p)")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)
