import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
import sqlite3
import json
import random
import string
import time
import hashlib
import base64
from datetime import datetime, timedelta
import threading
import re

# ==================== تنظیمات ====================
BOT_TOKEN = "8810741889:AAF9h94CG7dmkvJRd3SHNH1npwezAi2wQ1A"
ADMIN_IDS = [8916314219]
CHANNEL_ID = "@rezagrootz"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== دیتابیس پیشرفته ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('panel_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
        
    def _create_tables(self):
        # جدول کاربران
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                balance INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                join_date INTEGER,
                last_seen INTEGER,
                is_admin INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                language TEXT DEFAULT 'fa',
                referral_code TEXT,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0
            )
        ''')
        
        # جدول کانفیگ‌ها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                type TEXT,
                config TEXT,
                server_ip TEXT,
                server_port INTEGER,
                created_at INTEGER,
                expires_at INTEGER,
                is_active INTEGER DEFAULT 1,
                traffic_limit INTEGER DEFAULT 0,
                traffic_used INTEGER DEFAULT 0,
                note TEXT
            )
        ''')
        
        # جدول سرورها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                ip TEXT,
                port INTEGER,
                location TEXT,
                country_code TEXT,
                max_users INTEGER DEFAULT 50,
                current_users INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at INTEGER
            )
        ''')
        
        # جدول پلن‌ها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price INTEGER,
                duration INTEGER,
                traffic_limit INTEGER,
                speed_limit INTEGER,
                description TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # جدول سفارشات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_id INTEGER,
                config_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                payment_method TEXT,
                created_at INTEGER,
                paid_at INTEGER,
                expires_at INTEGER
            )
        ''')
        
        # جدول تراکنش‌ها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at INTEGER
            )
        ''')
        
        # جدول تیکت‌ها
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                message TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'normal',
                created_at INTEGER,
                assigned_to INTEGER
            )
        ''')
        
        # جدول پاسخ‌های خودکار
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT,
                response TEXT,
                type TEXT DEFAULT 'text',
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # جدول کش
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                expires_at INTEGER
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        now = int(time.time())
        self.cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, last_seen) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, now, now)
        )
        self.conn.commit()
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def update_user(self, user_id, **kwargs):
        for key, value in kwargs.items():
            self.cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()
    
    def add_config(self, user_id, name, config_type, config, server_ip, server_port, expires_at, traffic_limit=0):
        now = int(time.time())
        self.cursor.execute(
            "INSERT INTO configs (user_id, name, type, config, server_ip, server_port, created_at, expires_at, traffic_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, config_type, config, server_ip, server_port, now, expires_at, traffic_limit)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user_configs(self, user_id):
        self.cursor.execute("SELECT * FROM configs WHERE user_id = ? AND is_active = 1 ORDER BY id DESC", (user_id,))
        return self.cursor.fetchall()
    
    def get_config(self, config_id):
        self.cursor.execute("SELECT * FROM configs WHERE id = ?", (config_id,))
        return self.cursor.fetchone()
    
    def deactivate_config(self, config_id):
        self.cursor.execute("UPDATE configs SET is_active = 0 WHERE id = ?", (config_id,))
        self.conn.commit()
    
    def add_server(self, name, ip, port, location, country_code):
        now = int(time.time())
        self.cursor.execute(
            "INSERT INTO servers (name, ip, port, location, country_code, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, ip, port, location, country_code, now)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_servers(self):
        self.cursor.execute("SELECT * FROM servers WHERE is_active = 1")
        return self.cursor.fetchall()
    
    def add_plan(self, name, price, duration, traffic_limit, speed_limit, description):
        self.cursor.execute(
            "INSERT INTO plans (name, price, duration, traffic_limit, speed_limit, description) VALUES (?, ?, ?, ?, ?, ?)",
            (name, price, duration, traffic_limit, speed_limit, description)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_plans(self):
        self.cursor.execute("SELECT * FROM plans WHERE is_active = 1")
        return self.cursor.fetchall()
    
    def add_order(self, user_id, plan_id, amount):
        now = int(time.time())
        self.cursor.execute(
            "INSERT INTO orders (user_id, plan_id, amount, created_at) VALUES (?, ?, ?, ?)",
            (user_id, plan_id, amount, now)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_order_status(self, order_id, status):
        self.cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        self.conn.commit()
    
    def add_transaction(self, user_id, amount, trans_type, description):
        now = int(time.time())
        self.cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, trans_type, description, now)
        )
        self.conn.commit()
    
    def add_ticket(self, user_id, subject, message):
        now = int(time.time())
        self.cursor.execute(
            "INSERT INTO tickets (user_id, subject, message, created_at) VALUES (?, ?, ?, ?)",
            (user_id, subject, message, now)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_tickets(self, user_id):
        self.cursor.execute("SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC", (user_id,))
        return self.cursor.fetchall()
    
    def get_all_tickets(self):
        self.cursor.execute("SELECT * FROM tickets WHERE status = 'open' ORDER BY id DESC")
        return self.cursor.fetchall()
    
    def close_ticket(self, ticket_id):
        self.cursor.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
        self.conn.commit()
    
    def add_auto_reply(self, trigger, response):
        self.cursor.execute(
            "INSERT INTO auto_replies (trigger, response) VALUES (?, ?)",
            (trigger, response)
        )
        self.conn.commit()
    
    def get_auto_reply(self, trigger):
        self.cursor.execute("SELECT response FROM auto_replies WHERE trigger = ? AND is_active = 1", (trigger,))
        return self.cursor.fetchone()
    
    def set_cache(self, key, value, expires_in=3600):
        expires_at = int(time.time()) + expires_in
        self.cursor.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), expires_at)
        )
        self.conn.commit()
    
    def get_cache(self, key):
        self.cursor.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        if row and row[1] > int(time.time()):
            return json.loads(row[0])
        return None
    
    def close(self):
        self.conn.close()

db = Database()

# ==================== کلاس تولید کانفیگ ====================
class ConfigGenerator:
    @staticmethod
    def generate_uuid():
        return ''.join(random.choices(string.hexdigits.lower(), k=32))
    
    @staticmethod
    def generate_vless(user_id, server_ip, server_port, uuid=None):
        if not uuid:
            uuid = ConfigGenerator.generate_uuid()
        
        # ساخت کانفیگ VLESS
        config = f"vless://{uuid}@{server_ip}:{server_port}?encryption=none&security=reality&sni=cdn.steamstatic.com&fp=chrome&pbk=3DYkxUg9fBA6cONioJOPrsklcMQEImEsurR6air4swo&sid=&type=tcp&host=cdn.steamstatic.com&path=/&mode=auto#REZA_GROOTZ_{user_id}"
        return config
    
    @staticmethod
    def generate_vmess(user_id, server_ip, server_port, uuid=None):
        if not uuid:
            uuid = ConfigGenerator.generate_uuid()
        
        # ساخت کانفیگ VMess
        config = f"vmess://{base64.b64encode(json.dumps({{
            'v': '2',
            'ps': f'REZA_GROOTZ_{user_id}',
            'add': server_ip,
            'port': server_port,
            'id': uuid,
            'aid': '0',
            'net': 'tcp',
            'type': 'none',
            'host': 'cdn.steamstatic.com',
            'path': '/',
            'tls': 'reality'
        }}).encode()).decode()}"
        return config
    
    @staticmethod
    def generate_trojan(user_id, server_ip, server_port):
        password = ConfigGenerator.generate_uuid()[:16]
        config = f"trojan://{password}@{server_ip}:{server_port}?security=reality&sni=cdn.steamstatic.com&fp=chrome&type=tcp&host=cdn.steamstatic.com#REZA_GROOTZ_{user_id}"
        return config
    
    @staticmethod
    def generate_shadowsocks(user_id, server_ip, server_port):
        password = ConfigGenerator.generate_uuid()[:12]
        method = "chacha20-ietf-poly1305"
        config = f"ss://{base64.b64encode(f'{method}:{password}'.encode()).decode()}@{server_ip}:{server_port}#REZA_GROOTZ_{user_id}"
        return config

# ==================== کیبوردهای رنگی ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🟢 ساخت کانفیگ جدید", callback_data="new_config"),
        InlineKeyboardButton("📋 لیست کانفیگ‌ها", callback_data="my_configs"),
        InlineKeyboardButton("🛒 خرید پلن", callback_data="buy_plan"),
        InlineKeyboardButton("💰 شارژ کیف پول", callback_data="charge_wallet"),
        InlineKeyboardButton("📊 وضعیت اکانت", callback_data="my_status"),
        InlineKeyboardButton("🎫 تیکت پشتیبانی", callback_data="tickets"),
        InlineKeyboardButton("🌍 انتخاب زبان", callback_data="change_lang"),
        InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel")
    )
    return keyboard

def config_type_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔴 VLESS", callback_data="config_vless"),
        InlineKeyboardButton("🟠 VMess", callback_data="config_vmess"),
        InlineKeyboardButton("🟡 Trojan", callback_data="config_trojan"),
        InlineKeyboardButton("🟢 Shadowsocks", callback_data="config_ss"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
    )
    return keyboard

def server_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    servers = db.get_servers()
    if servers:
        for server in servers:
            keyboard.add(
                InlineKeyboardButton(
                    f"🌍 {server[2]} ({server[5]})", 
                    callback_data=f"server_{server[0]}"
                )
            )
    else:
        keyboard.add(
            InlineKeyboardButton("🚫 سروری موجود نیست", callback_data="no_server")
        )
    keyboard.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_config")
    )
    return keyboard

def plan_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    plans = db.get_plans()
    if plans:
        for plan in plans:
            keyboard.add(
                InlineKeyboardButton(
                    f"💰 {plan[1]} - {plan[2]:,} تومان", 
                    callback_data=f"plan_{plan[0]}"
                )
            )
    else:
        keyboard.add(
            InlineKeyboardButton("🚫 پلنی موجود نیست", callback_data="no_plan")
        )
    keyboard.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
    )
    return keyboard

def admin_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats"),
        InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_users"),
        InlineKeyboardButton("➕ افزودن سرور", callback_data="admin_add_server"),
        InlineKeyboardButton("➕ افزودن پلن", callback_data="admin_add_plan"),
        InlineKeyboardButton("🎫 تیکت‌ها", callback_data="admin_tickets"),
        InlineKeyboardButton("📨 ارسال همگانی", callback_data="admin_broadcast"),
        InlineKeyboardButton("🤖 پاسخ خودکار", callback_data="admin_auto_reply"),
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
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name)
    
    # بررسی ریفرال
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
        if ref_code.startswith('ref_'):
            referrer_id = int(ref_code.split('_')[1])
            if referrer_id != user.id:
                db.update_user(referrer_id, referral_count=db.get_user(referrer_id)[9] + 1)
                db.update_user(user.id, referred_by=referrer_id)
                # پاداش ریفرال
                db.add_transaction(referrer_id, 5000, 'bonus', 'پاداش ریفرال')
                db.update_user(referrer_id, balance=db.get_user(referrer_id)[3] + 5000)
    
    text = """
🌟 <b>به پنل مدیریت کانفیگ REZA GROOTZ خوش آمدید!</b> 🌟

⚡️ <b>امکانات پنل:</b>
✅ ساخت کانفیگ VLESS/VMess/Trojan/SS
✅ سرورهای اختصاصی و پرسرعت
✅ سیستم خرید پلن
✅ کیف پول داخلی
✅ پشتیبانی ۲۴ ساعته
✅ کاملاً رایگان

📌 <b>از منوی زیر استفاده کنید:</b>
"""
    bot.reply_to(message, text, reply_markup=main_menu())

# ==================== کال‌بک‌ها ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: CallbackQuery):
    user_id = call.from_user.id
    data = call.data
    
    # ===== بازگشت =====
    if data == "back_main":
        text = "🌟 <b>منوی اصلی</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data == "back_config":
        text = "🔄 <b>نوع کانفیگ را انتخاب کنید:</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=config_type_menu())
        bot.answer_callback_query(call.id)
        return
    
    # ===== ساخت کانفیگ جدید =====
    if data == "new_config":
        text = "🔧 <b>نوع کانفیگ را انتخاب کنید:</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=config_type_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("config_"):
        config_type = data.split("_")[1]
        # ذخیره نوع کانفیگ در کش
        db.set_cache(f"config_type_{user_id}", config_type, 300)
        
        text = "🌍 <b>سرور مورد نظر را انتخاب کنید:</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=server_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("server_"):
        server_id = int(data.split("_")[1])
        server = db.cursor.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
        if not server:
            bot.answer_callback_query(call.id, "❌ سرور یافت نشد!")
            return
        
        config_type = db.get_cache(f"config_type_{user_id}")
        if not config_type:
            bot.answer_callback_query(call.id, "❌ نوع کانفیگ مشخص نشده!")
            return
        
        # ساخت کانفیگ
        uuid = ConfigGenerator.generate_uuid()
        config_data = {
            'vless': ConfigGenerator.generate_vless,
            'vmess': ConfigGenerator.generate_vmess,
            'trojan': ConfigGenerator.generate_trojan,
            'ss': ConfigGenerator.generate_shadowsocks
        }
        
        if config_type in config_data:
            if config_type in ['vless', 'vmess']:
                config = config_data[config_type](user_id, server[2], server[3], uuid)
            else:
                config = config_data[config_type](user_id, server[2], server[3])
            
            # ذخیره در دیتابیس
            expires_at = int(time.time()) + 30 * 86400  # 30 روز
            config_id = db.add_config(
                user_id, 
                f"{config_type.upper()}_{server[1]}", 
                config_type, 
                config, 
                server[2], 
                server[3], 
                expires_at
            )
            
            # کیلید بورد
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("📋 کپی کانفیگ", callback_data=f"copy_config_{config_id}"),
                InlineKeyboardButton("📱 دریافت QR", callback_data=f"qr_config_{config_id}"),
                InlineKeyboardButton("🗑️ حذف کانفیگ", callback_data=f"delete_config_{config_id}"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
            )
            
            text = f"""
✅ <b>کانفیگ با موفقیت ساخته شد!</b>

📋 <b>اطلاعات کانفیگ:</b>
🔹 نوع: {config_type.upper()}
🔹 سرور: {server[1]} ({server[4]})
🔹 آی پی: {server[2]}
🔹 پورت: {server[3]}
🔹 انقضا: {datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M')}

<code>{config}</code>

💡 روی دکمه کپی کلیک کنید.
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            bot.answer_callback_query(call.id, "✅ کانفیگ ساخته شد!")
        return
    
    # ===== کپی کانفیگ =====
    if data.startswith("copy_config_"):
        config_id = int(data.split("_")[2])
        config = db.get_config(config_id)
        if config:
            bot.send_message(
                call.message.chat.id,
                f"📋 <b>کانفیگ شما:</b>\n\n<code>{config[4]}</code>",
                parse_mode='HTML'
            )
            bot.answer_callback_query(call.id, "✅ کانفیگ کپی شد!")
        else:
            bot.answer_callback_query(call.id, "❌ کانفیگ یافت نشد!")
        return
    
    # ===== حذف کانفیگ =====
    if data.startswith("delete_config_"):
        config_id = int(data.split("_")[2])
        db.deactivate_config(config_id)
        bot.answer_callback_query(call.id, "✅ کانفیگ حذف شد!")
        bot.edit_message_text(
            "🗑️ کانفیگ با موفقیت حذف شد.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        return
    
    # ===== لیست کانفیگ‌ها =====
    if data == "my_configs":
        configs = db.get_user_configs(user_id)
        if not configs:
            text = "❌ شما هیچ کانفیگی ندارید!\nاز دکمه 'ساخت کانفیگ جدید' استفاده کنید."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
            bot.answer_callback_query(call.id)
            return
        
        text = "📋 <b>لیست کانفیگ‌های شما</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for idx, cfg in enumerate(configs[:10], 1):
            expires = datetime.fromtimestamp(cfg[8]).strftime('%Y-%m-%d')
            text += f"{idx}. {cfg[3].upper()} - {cfg[2]} (انقضا: {expires})\n"
        
        if len(configs) > 10:
            text += f"\n... و {len(configs) - 10} کانفیگ دیگر"
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🗑️ پاک کردن همه", callback_data="delete_all_configs"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)
        return
    
    if data == "delete_all_configs":
        db.cursor.execute("UPDATE configs SET is_active = 0 WHERE user_id = ?", (user_id,))
        db.conn.commit()
        bot.answer_callback_query(call.id, "✅ همه کانفیگ‌ها پاک شدند!")
        bot.edit_message_text(
            "🗑️ همه کانفیگ‌های شما پاک شدند.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        return
    
    # ===== خرید پلن =====
    if data == "buy_plan":
        text = "🛒 <b>پلن‌های موجود:</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=plan_menu())
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("plan_"):
        plan_id = int(data.split("_")[1])
        plan = db.cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            bot.answer_callback_query(call.id, "❌ پلن یافت نشد!")
            return
        
        user = db.get_user(user_id)
        if user[3] < plan[2]:
            text = f"""
❌ <b>موجودی کافی نیست!</b>

💰 موجودی شما: {user[3]:,} تومان
💰 قیمت پلن: {plan[2]:,} تومان
💰 مبلغ مورد نیاز: {plan[2] - user[3]:,} تومان

🔹 برای شارژ کیف پول از دکمه زیر استفاده کنید:
"""
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("💰 شارژ کیف پول", callback_data="charge_wallet"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            bot.answer_callback_query(call.id)
            return
        
        # ساخت سفارش
        order_id = db.add_order(user_id, plan_id, plan[2])
        
        # کم کردن از کیف پول
        db.update_user(user_id, balance=user[3] - plan[2], total_spent=user[4] + plan[2])
        db.add_transaction(user_id, -plan[2], 'purchase', f'خرید پلن {plan[1]}')
        
        # ساخت کانفیگ
        servers = db.get_servers()
        if servers:
            server = random.choice(servers)
            uuid = ConfigGenerator.generate_uuid()
            config = ConfigGenerator.generate_vless(user_id, server[2], server[3], uuid)
            expires_at = int(time.time()) + plan[3] * 86400
            
            config_id = db.add_config(
                user_id,
                plan[1],
                'vless',
                config,
                server[2],
                server[3],
                expires_at,
                plan[4]
            )
            
            db.update_order_status(order_id, 'completed')
            
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("📋 کپی کانفیگ", callback_data=f"copy_config_{config_id}"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
            )
            
            text = f"""
✅ <b>خرید با موفقیت انجام شد!</b>

📋 <b>اطلاعات سفارش:</b>
🔹 پلن: {plan[1]}
🔹 مبلغ: {plan[2]:,} تومان
🔹 مدت: {plan[3]} روز
🔹 ترافیک: {plan[4]} GB

<code>{config}</code>

💡 کانفیگ در لیست کانفیگ‌های شما ذخیره شد.
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        else:
            bot.edit_message_text("❌ سروری برای ساخت کانفیگ موجود نیست!", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    # ===== شارژ کیف پول =====
    if data == "charge_wallet":
        text = """
💰 <b>شارژ کیف پول</b>

🔹 شماره کارت: <code>6037-9918-1234-5678</code>
🔹 به نام: <b>REZA GROOTZ</b>
🔹 بانک: <b>ملی</b>

📌 بعد از واریز، مبلغ را به همراه کد زیر ارسال کنید:

<code>CHARGE_{user_id}</code>

✅ مبلغ به کیف پول شما اضافه خواهد شد.
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    # ===== وضعیت اکانت =====
    if data == "my_status":
        user = db.get_user(user_id)
        configs = db.get_user_configs(user_id)
        text = f"""
📊 <b>وضعیت اکانت شما</b>
━━━━━━━━━━━━━━━━━━━━━━
🆔 آیدی: <code>{user_id}</code>
👤 نام: {user[2]}
💰 موجودی: {user[3]:,} تومان
💸 کل خرید: {user[4]:,} تومان
📋 تعداد کانفیگ‌ها: {len(configs)}
📅 تاریخ عضویت: {datetime.fromtimestamp(user[5]).strftime('%Y-%m-%d')}
📌 کد معرف: <code>ref_{user_id}</code>
👥 تعداد معرف‌ها: {user[9]}
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # ===== تیکت‌ها =====
    if data == "tickets":
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("➕ تیکت جدید", callback_data="new_ticket"),
            InlineKeyboardButton("📋 تیکت‌های من", callback_data="my_tickets"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        bot.edit_message_text("🎫 <b>سیستم پشتیبانی</b>", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)
        return
    
    if data == "new_ticket":
        bot.send_message(call.message.chat.id, "📝 لطفاً موضوع تیکت خود را به همراه پیام ارسال کنید:\nمثال:\n<code>مشکل در اتصال</code>\n<code>کانفیگ من کار نمیکنه</code>")
        bot.answer_callback_query(call.id)
        return
    
    if data == "my_tickets":
        tickets = db.get_tickets(user_id)
        if not tickets:
            text = "📭 شما هیچ تیکتی ندارید."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
            bot.answer_callback_query(call.id)
            return
        
        text = "🎫 <b>لیست تیکت‌های شما</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for ticket in tickets[:10]:
            status = "🟢 باز" if ticket[4] == "open" else "🔴 بسته"
            priority = "🔴" if ticket[5] == "high" else "🟡" if ticket[5] == "medium" else "🟢"
            text += f"{priority} #{ticket[0]} - {ticket[2]} ({status})\n"
        
        if len(tickets) > 10:
            text += f"\n... و {len(tickets) - 10} تیکت دیگر"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # ===== انتخاب زبان =====
    if data == "change_lang":
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
        )
        keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("🌍 <b>انتخاب زبان / Choose Language</b>", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)
        return
    
    # ===== پنل ادمین =====
    if data == "admin_panel":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
            return
        
        text = "👑 <b>پنل مدیریت</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
        bot.answer_callback_query(call.id)
        return
    
    # ===== آمار ادمین =====
    if data == "admin_stats":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
            return
        
        total_users = db.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_configs = db.cursor.execute("SELECT COUNT(*) FROM configs WHERE is_active = 1").fetchone()[0]
        total_orders = db.cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        total_revenue = db.cursor.execute("SELECT SUM(amount) FROM orders WHERE status = 'completed'").fetchone()[0]
        total_servers = db.cursor.execute("SELECT COUNT(*) FROM servers WHERE is_active = 1").fetchone()[0]
        
        text = f"""
📊 <b>آمار کلی پنل</b>
━━━━━━━━━━━━━━━━━━━━━━
👥 کاربران کل: {total_users}
📋 کانفیگ‌های فعال: {total_configs}
🛒 سفارشات: {total_orders}
💰 درآمد کل: {total_revenue or 0:,} تومان
🌍 سرورهای فعال: {total_servers}
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
        bot.answer_callback_query(call.id)
        return
    
    # ===== بقیه دکمه‌های ادمین =====
    if data in ["admin_users", "admin_add_server", "admin_add_plan", "admin_tickets", "admin_broadcast", "admin_auto_reply"]:
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ شما دسترسی ندارید!")
            return
        
        if data == "admin_users":
            users = db.cursor.execute("SELECT user_id, first_name FROM users ORDER BY id DESC LIMIT 20").fetchall()
            text = "👥 <b>۲۰ کاربر اخیر</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
            for idx, user in enumerate(users, 1):
                text += f"{idx}. {user[1]} - <code>{user[0]}</code>\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
            bot.answer_callback_query(call.id)
            return
        
        elif data == "admin_add_server":
            bot.send_message(call.message.chat.id, """
📝 <b>افزودن سرور جدید</b>

لطفاً اطلاعات سرور را به صورت زیر ارسال کنید:
<code>نام | آی‌پی | پورت | لوکیشن | کد کشور</code>

مثال:
<code>سرور اصلی | 192.168.1.1 | 443 | ایران | IR</code>
""")
            bot.answer_callback_query(call.id)
            return
        
        elif data == "admin_add_plan":
            bot.send_message(call.message.chat.id, """
📝 <b>افزودن پلن جدید</b>

لطفاً اطلاعات پلن را به صورت زیر ارسال کنید:
<code>نام | قیمت | مدت(روز) | ترافیک(GB) | سرعت(Mbps) | توضیحات</code>

مثال:
<code>پلن طلایی | 50000 | 30 | 100 | 1000 | بهترین پلن</code>
""")
            bot.answer_callback_query(call.id)
            return
        
        elif data == "admin_tickets":
            tickets = db.get_all_tickets()
            if not tickets:
                text = "📭 هیچ تیکت باز وجود ندارد."
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
                bot.answer_callback_query(call.id)
                return
            
            text = "🎫 <b>تیکت‌های باز</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
            for ticket in tickets[:10]:
                text += f"#{ticket[0]} - {ticket[2]} (کاربر: {ticket[1]}) - {ticket[4]}\n"
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
            bot.answer_callback_query(call.id)
            return
        
        elif data == "admin_broadcast":
            bot.send_message(call.message.chat.id, "📨 لطفاً پیام همگانی خود را ارسال کنید:")
            bot.answer_callback_query(call.id)
            return
        
        elif data == "admin_auto_reply":
            bot.send_message(call.message.chat.id, """
🤖 <b>مدیریت پاسخ‌های خودکار</b>

📝 برای افزودن پاسخ جدید:
<code>addreply | کلیدواژه | پاسخ</code>

📋 برای مشاهده پاسخ‌ها:
<code>listreplies</code>

❌ برای حذف پاسخ:
<code>delreply | کلیدواژه</code>
""")
            bot.answer_callback_query(call.id)
            return
    
    # ===== پاسخ به دکمه‌های خالی =====
    if data in ["no_server", "no_plan"]:
        bot.answer_callback_query(call.id, "❌ موردی یافت نشد!")
        return

# ==================== دریافت پیام‌ها ====================
@bot.message_handler(func=lambda message: True)
def handle_messages(message: Message):
    user_id = message.from_user.id
    
    # ===== پاسخ به تیکت =====
    if message.reply_to_message and message.reply_to_message.text and "لطفاً موضوع تیکت" in message.reply_to_message.text:
        lines = message.text.split('\n')
        if len(lines) >= 2:
            subject = lines[0].strip()
            msg = '\n'.join(lines[1:]).strip()
            ticket_id = db.add_ticket(user_id, subject, msg)
            bot.reply_to(message, f"✅ تیکت شما با شماره #{ticket_id} ثبت شد.\nبه زودی پاسخ داده می‌شود.")
            # اطلاع به ادمین
            for admin in ADMIN_IDS:
                try:
                    bot.send_message(admin, f"🎫 تیکت جدید #{ticket_id}\nکاربر: {user_id}\nموضوع: {subject}")
                except:
                    pass
            return
    
    # ===== افزودن سرور توسط ادمین =====
    if "|" in message.text and message.text.count("|") >= 4:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) >= 5:
            name, ip, port, location, country = parts[:5]
            try:
                port = int(port)
                server_id = db.add_server(name, ip, port, location, country)
                bot.reply_to(message, f"✅ سرور '{name}' با موفقیت اضافه شد! (شناسه: {server_id})")
            except:
                bot.reply_to(message, "❌ خطا در افزودن سرور! پورت باید عدد باشد.")
            return
    
    # ===== افزودن پلن توسط ادمین =====
    if message.text.count("|") >= 5:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) >= 6:
            name, price, duration, traffic, speed, desc = parts[:6]
            try:
                price = int(price)
                duration = int(duration)
                traffic = int(traffic)
                speed = int(speed)
                plan_id = db.add_plan(name, price, duration, traffic, speed, desc)
                bot.reply_to(message, f"✅ پلن '{name}' با موفقیت اضافه شد! (شناسه: {plan_id})")
            except:
                bot.reply_to(message, "❌ خطا در افزودن پلن! قیمت، مدت، ترافیک و سرعت باید عدد باشند.")
            return
    
    # ===== ارسال همگانی =====
    if message.from_user.id in ADMIN_IDS and message.text and not message.text.startswith('/'):
        # بررسی اینکه کاربر در حالت ارسال همگانی هست
        if message.text.startswith('addreply'):
            # پاسخ خودکار
            parts = message.text.split('|')
            if len(parts) >= 3:
                trigger = parts[1].strip()
                response = parts[2].strip()
                db.add_auto_reply(trigger, response)
                bot.reply_to(message, f"✅ پاسخ خودکار برای '{trigger}' اضافه شد.")
            else:
                bot.reply_to(message, "❌ فرمت صحیح: addreply | کلیدواژه | پاسخ")
            return
        
        if message.text.startswith('listreplies'):
            replies = db.cursor.execute("SELECT id, trigger, response FROM auto_replies WHERE is_active = 1").fetchall()
            if replies:
                text = "🤖 <b>پاسخ‌های خودکار:</b>\n"
                for r in replies:
                    text += f"#{r[0]}: {r[1]} -> {r[2][:30]}...\n"
                bot.reply_to(message, text, parse_mode='HTML')
            else:
                bot.reply_to(message, "📭 هیچ پاسخی وجود ندارد.")
            return
        
        if message.text.startswith('delreply'):
            parts = message.text.split()
            if len(parts) >= 2:
                trigger = parts[1].strip()
                db.cursor.execute("UPDATE auto_replies SET is_active = 0 WHERE trigger = ?", (trigger,))
                db.conn.commit()
                bot.reply_to(message, f"✅ پاسخ '{trigger}' حذف شد.")
            else:
                bot.reply_to(message, "❌ فرمت: delreply کلیدواژه")
            return
        
        # پاسخ خودکار
        auto_reply = db.get_auto_reply(message.text)
        if auto_reply:
            bot.reply_to(message, auto_reply[0])
            return
        
        # ارسال همگانی
        if message.reply_to_message and message.reply_to_message.text and "لطفاً پیام همگانی" in message.reply_to_message.text:
            users = db.cursor.execute("SELECT user_id FROM users").fetchall()
            sent = 0
            failed = 0
            for user in users:
                try:
                    bot.send_message(user[0], f"📢 <b>پیام همگانی</b>\n\n{message.text}", parse_mode='HTML')
                    sent += 1
                    time.sleep(0.05)
                except:
                    failed += 1
            bot.reply_to(message, f"✅ ارسال شد!\n✓ موفق: {sent}\n✗ ناموفق: {failed}")
            return
        
        if len(message.text) > 100 and "شارژ" not in message.text:
            # ممکنه پیام همگانی باشه
            users = db.cursor.execute("SELECT user_id FROM users").fetchall()
            sent = 0
            failed = 0
            for user in users[:50]:  # تست با ۵۰ نفر
                try:
                    bot.send_message(user[0], f"📢 <b>پیام همگانی</b>\n\n{message.text}", parse_mode='HTML')
                    sent += 1
                    time.sleep(0.05)
                except:
                    failed += 1
            bot.reply_to(message, f"✅ تست ارسال به ۵۰ کاربر:\n✓ موفق: {sent}\n✗ ناموفق: {failed}")
            return
    
    # ===== پاسخ‌های معمولی =====
    if message.text and message.text.lower() in ['سلام', 'درود', 'hi', 'hello', 'سلامتی']:
        bot.reply_to(message, "👋 سلام! به پنل کانفیگ REZA GROOTZ خوش آمدی!\nبرای شروع /start رو بزن.")
        return
    
    if message.text and 'کانفیگ' in message.text:
        bot.reply_to(message, "🔗 برای دریافت کانفیگ از منوی اصلی استفاده کن:\n/start")
        return

# ==================== اجرا ====================
if __name__ == "__main__":
    print("=" * 70)
    print("🌟 پنل مدیریت کانفیگ REZA GROOTZ")
    print("=" * 70)
    print("👑 ادمین: @rezagrootz")
    print("💎 قابلیت‌ها:")
    print("  ✅ ساخت کانفیگ VLESS/VMess/Trojan/SS")
    print("  ✅ مدیریت سرورها و پلن‌ها")
    print("  ✅ سیستم خرید و کیف پول")
    print("  ✅ سیستم تیکت پشتیبانی")
    print("  ✅ ارسال همگانی")
    print("  ✅ پاسخ‌های خودکار")
    print("  ✅ دکمه‌های رنگی")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)