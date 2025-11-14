# -*- coding: utf-8 -*-
"""
بوت F90 — نسخة كاملة حسب طلبك

🚀 الميزات:
- نظام إدمن (يوزر + باس) — إدمنين:
    f90 / 9163
    fahad / 1122
- حدود مجانية:
    20 رسالة – 5 صور فقط
- اشتراك مدفوع بعد انتهاء الحد
- شات OpenAI
- توليد صور Google AI Studio
- لوحة تحكم إدمن بالأزرار
- قاعدة بيانات SQLite
"""

import os
import telebot
from telebot import types
import sqlite3
import datetime
import requests
import base64
from io import BytesIO
from openai import OpenAI

# =============================
#   🔧 الإعدادات (عدّل هنا)
# =============================

TELEGRAM_BOT_TOKEN = "ضع_توكن_البوت_هنا"
OPENAI_API_KEY     = "ضع_مفتاح_OPENAI_هنا"
GOOGLE_API_KEY     = "ضع_مفتاح_GOOGLE_AI_STUDIO_هنا"

BOT_NAME = "F90"

# حدود مجانية
FREE_MSG_LIMIT  = 20
FREE_IMG_LIMIT  = 5

# جهة الدفع
PAY_TELEGRAM = "@F90xd"
PAY_WHATSAPP = "https://wa.me/962792681340"

# إدمن (يوزر + باس)
ADMINS = {
    "f90": "9163",
    "fahad": "1122"
}

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

DB = "f90.db"

# =============================
#   قاعدة البيانات
# =============================

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        messages_used INTEGER DEFAULT 0,
        images_used INTEGER DEFAULT 0,
        is_subscriber INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO users (tg_id) VALUES (?)", (tg_id,))
        conn.commit()
        c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        row = c.fetchone()

    conn.close()
    return row

def update_user_usage(tg_id, kind):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if kind == "msg":
        c.execute("UPDATE users SET messages_used = messages_used + 1 WHERE tg_id=?", (tg_id,))
    else:
        c.execute("UPDATE users SET images_used = images_used + 1 WHERE tg_id=?", (tg_id,))
    conn.commit()
    conn.close()

# =============================
#   🔐 نظام تسجيل دخول الإدمن
# =============================

admin_login_state = {}   # لتخزين خطوات تسجيل الدخول
admin_sessions = set()   # جلسات الإدمن المسجلين

@bot.message_handler(commands=["admin"])
def admin_start(message):
    admin_login_state[message.chat.id] = {"step": "username"}
    bot.send_message(message.chat.id, "🔐 أدخل اسم المستخدم:")

@bot.message_handler(func=lambda m: m.chat.id in admin_login_state)
def admin_login_process(message):
    chat_id = message.chat.id
    state = admin_login_state[chat_id]

    # 1) يوزر نيم
    if state["step"] == "username":
        state["username"] = message.text.strip()
        state["step"] = "password"
        bot.send_message(chat_id, "🔑 أدخل كلمة المرور:")
        return

    # 2) باسورد
    if state["step"] == "password":
        username = state["username"]
        password = message.text.strip()

        if username in ADMINS and ADMINS[username] == password:
            admin_sessions.add(chat_id)
            admin_login_state.pop(chat_id)
            admin_panel(chat_id)
        else:
            bot.send_message(chat_id, "❌ اسم المستخدم أو كلمة المرور خاطئة.")
            admin_login_state.pop(chat_id)

# =============================
#     لوحة تحكم الإدمن
# =============================

def admin_panel(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 الإحصائيات")
    kb.row("👤 فحص مستخدم")
    kb.row("⭐ تفعيل اشتراك", "❌ إلغاء اشتراك")
    kb.row("📢 رسالة جماعية")
    kb.row("🔓 تسجيل خروج")

    bot.send_message(chat_id, "✅ تم تسجيل الدخول!\nاختر ما تريده:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🔓 تسجيل خروج")
def admin_logout(message):
    if message.chat.id in admin_sessions:
        admin_sessions.remove(message.chat.id)
        bot.send_message(message.chat.id, "✔️ تم تسجيل الخروج.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in admin_sessions)
def admin_actions(message):

    if message.text == "📊 الإحصائيات":
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        conn.close()
        bot.send_message(message.chat.id, f"📊 إجمالي المستخدمين: {total}")

    elif message.text == "👤 فحص مستخدم":
        bot.send_message(message.chat.id, "أرسل ID المستخدم:")
        admin_login_state[message.chat.id] = {"step": "check_user"}

    elif message.chat.id in admin_login_state and admin_login_state[message.chat.id].get("step") == "check_user":
        try:
            tg_id = int(message.text)
        except:
            bot.send_message(message.chat.id, "❌ ID غير صالح")
            return
        
        user = get_user(tg_id)
        bot.send_message(message.chat.id, f"""
👤 مستخدم:
الرسائل المستعملة: {user[2]}
الصور المستعملة: {user[3]}
اشتراك؟ {"✔️" if user[4] else "❌"}
""")
        admin_login_state.pop(message.chat.id)

    elif message.text == "⭐ تفعيل اشتراك":
        bot.send_message(message.chat.id, "أدخل ID المستخدم:")
        admin_login_state[message.chat.id] = {"step": "sub"}

    elif message.chat.id in admin_login_state and admin_login_state[message.chat.id].get("step") == "sub":
        tg_id = int(message.text)
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE users SET is_subscriber=1 WHERE tg_id=?", (tg_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✔️ تم التفعيل.")
        admin_login_state.pop(message.chat.id)

    elif message.text == "❌ إلغاء اشتراك":
        bot.send_message(message.chat.id, "أدخل ID المستخدم:")
        admin_login_state[message.chat.id] = {"step": "unsub"}

    elif message.chat.id in admin_login_state and admin_login_state[message.chat.id].get("step") == "unsub":
        tg_id = int(message.text)
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE users SET is_subscriber=0 WHERE tg_id=?", (tg_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✔️ تم الإلغاء.")
        admin_login_state.pop(message.chat.id)

    elif message.text == "📢 رسالة جماعية":
        bot.send_message(message.chat.id, "أرسل نص الرسالة:")
        admin_login_state[message.chat.id] = {"step": "broadcast"}

    elif message.chat.id in admin_login_state and admin_login_state[message.chat.id].get("step") == "broadcast":
        text = message.text
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT tg_id FROM users")
        ids = c.fetchall()
        conn.close()

        count = 0
        for row in ids:
            try:
                bot.send_message(row[0], text)
                count += 1
            except:
                pass

        bot.send_message(message.chat.id, f"✔️ تم الإرسال لـ {count} مستخدم.")
        admin_login_state.pop(message.chat.id)

# =============================
#     🤖 الذكاء الاصطناعي
# =============================

def ask_openai(text):
    try:
        res = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": text}]
        )
        return res.choices[0].message.content
    except:
        return "⚠️ خطأ في الاتصال بـ OpenAI."

# =============================
#     🎨 توليد الصور
# =============================

def google_generate_image(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagegeneration:generateImage?key={GOOGLE_API_KEY}"
    data = {"prompt":{"text":prompt}}
    r = requests.post(url, json=data)

    if r.status_code != 200:
        return None

    img_base64 = r.json()["images"][0]["base64"]
    return base64.b64decode(img_base64)

# =============================
#     🧠 محادثة المستخدم
# =============================

@bot.message_handler(commands=["start"])
def start_cmd(message):
    init_db()
    bot.send_message(message.chat.id, f"أهلاً بك في بوت {BOT_NAME} 🤖✨\nاكتب سؤالك لبدء الدردشة.\nلإنشاء صورة اكتب:\nصورة: وصف الصورة")

@bot.message_handler(func=lambda m: True)
def user_chat(message):
    tg_id = message.chat.id
    user = get_user(tg_id)
    txt = message.text.lower()

    # إنشاء صورة
    if txt.startswith("صورة:") or txt.startswith("img:"):
        if user[3] >= FREE_IMG_LIMIT and not user[4]:
            bot.send_message(tg_id, f"🚫 وصلت حد الصور.\nللاشتراك:\nTelegram: {PAY_TELEGRAM}\nWhatsApp: {PAY_WHATSAPP}")
            return

        prompt = message.text.split(":",1)[1]
        bot.send_message(tg_id, "⏳ جاري توليد الصورة...")
        img = google_generate_image(prompt)

        if img:
            bot.send_photo(tg_id, img)
            update_user_usage(tg_id, "img")
        else:
            bot.send_message(tg_id, "⚠️ فشل توليد الصورة.")
        return

    # نص
    if user[2] >= FREE_MSG_LIMIT and not user[4]:
        bot.send_message(tg_id,
           f"🚫 وصلت حد الرسائل.\nللاشتراك:\nTelegram: {PAY_TELEGRAM}\nWhatsApp: {PAY_WHATSAPP}")
        return

    bot.send_chat_action(tg_id, "typing")
    ans = ask_openai(message.text)
    update_user_usage(tg_id, "msg")
    bot.reply_to(message, ans)

# تشغيل البوت
bot.infinity_polling()
