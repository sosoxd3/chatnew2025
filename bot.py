# -*- coding: utf-8 -*-
"""
بوت F90 — نسخة كاملة ومجهزة لـ Render

المميزات:
- رد تلقائي مثل ChatGPT (بدون حفظ ردود مسبقة)
- استخدام OpenAI للشات
- استخدام Google AI Studio للصور
- حدود مجانية: 20 رسالة / 5 صور لكل مستخدم
- اشتراك مدفوع بعد انتهاء الحد (تواصل عبر تيليجرام / واتساب)
- نظام إدمن بتسجيل دخول (يوزر + باس)
    * f90 / 9163
    * fahad / 1122
- لوحة تحكم إدمن بالأزرار
- قاعدة بيانات SQLite (ملف f90.db في نفس المجلد)
- مهيأ للعمل على Render (المفاتيح من Environment Variables)
"""

import os
import sqlite3
import requests
import base64
from io import BytesIO

import telebot
from telebot import types
from openai import OpenAI

# =============================
#   الإعدادات (من Environment)
# =============================

# مهم: في Render تضيف هذه المتغيرات:
# TELEGRAM_BOT_TOKEN
# OPENAI_API_KEY
# GOOGLE_API_KEY

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY     = os.getenv("GOOGLE_API_KEY")

BOT_NAME = "F90"

# حدود مجانية لكل مستخدم
FREE_MSG_LIMIT = 20   # عدد الرسائل
FREE_IMG_LIMIT = 5    # عدد الصور

# معلومات الاشتراك المدفوع (يظهر للمستخدم بعد انتهاء الحد)
PAY_TELEGRAM = "@F90xd"
PAY_WHATSAPP = "https://wa.me/962792681340"

# بيانات الإدمن (يوزر نيم + باسورد)
ADMINS = {
    "f90": "9163",
    "fahad": "1122"
}

# اسم ملف قاعدة البيانات (سيتم إنشاؤه تلقائياً)
DB_NAME = "f90.db"

# موديل OpenAI
OPENAI_MODEL = "gpt-4o-mini"  # يفضل استخدام هذا الموديل

# =============================
#   تهيئة البوت و OpenAI
# =============================

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("متغير TELEGRAM_BOT_TOKEN غير موجود في Environment.")

if not OPENAI_API_KEY:
    raise ValueError("متغير OPENAI_API_KEY غير موجود في Environment.")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# =============================
#   دوال قاعدة البيانات
# =============================

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_conn()
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
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO users (tg_id) VALUES (?)", (tg_id,))
        conn.commit()
        c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        row = c.fetchone()

    conn.close()
    return row    # (id, tg_id, messages_used, images_used, is_subscriber)

def update_usage(tg_id, kind):
    conn = get_conn()
    c = conn.cursor()
    if kind == "msg":
        c.execute("UPDATE users SET messages_used = messages_used + 1 WHERE tg_id=?", (tg_id,))
    elif kind == "img":
        c.execute("UPDATE users SET images_used = images_used + 1 WHERE tg_id=?", (tg_id,))
    conn.commit()
    conn.close()

def set_subscription(tg_id, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_subscriber=? WHERE tg_id=?", (1 if value else 0, tg_id))
    conn.commit()
    conn.close()

# =============================
#   نظام الإدمن (تسجيل دخول)
# =============================

admin_login_state = {}   # {chat_id: {"step": "...", ...}}
admin_sessions = set()   # chat_ids المسجلة كإدمن حالياً

@bot.message_handler(commands=["admin"])
def admin_command(message):
    chat_id = message.chat.id
    admin_login_state[chat_id] = {"step": "username"}
    bot.send_message(chat_id, "🔐 أدخل اسم المستخدم للإدمن:")

@bot.message_handler(func=lambda m: m.chat.id in admin_login_state)
def admin_login_flow(message):
    chat_id = message.chat.id
    state = admin_login_state[chat_id]

    # 1) اسم المستخدم
    if state["step"] == "username":
        state["username"] = message.text.strip()
        state["step"] = "password"
        bot.send_message(chat_id, "🔑 أدخل كلمة المرور:")
        return

    # 2) كلمة المرور
    if state["step"] == "password":
        username = state["username"]
        password = message.text.strip()

        if username in ADMINS and ADMINS[username] == password:
            admin_sessions.add(chat_id)
            admin_login_state.pop(chat_id, None)
            show_admin_panel(chat_id)
        else:
            bot.send_message(chat_id, "❌ اسم المستخدم أو كلمة المرور غير صحيحة.")
            admin_login_state.pop(chat_id, None)

# لوحة التحكم
def show_admin_panel(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 الإحصائيات")
    kb.row("👤 فحص مستخدم")
    kb.row("⭐ تفعيل اشتراك", "❌ إلغاء اشتراك")
    kb.row("📢 رسالة جماعية")
    kb.row("🔓 تسجيل خروج")
    bot.send_message(chat_id, "✅ تم تسجيل الدخول إلى لوحة التحكم.\nاختر من القائمة:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.chat.id in admin_sessions)
def admin_actions(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # تسجيل خروج
    if text == "🔓 تسجيل خروج":
        admin_sessions.discard(chat_id)
        admin_login_state.pop(chat_id, None)
        bot.send_message(chat_id, "✔️ تم تسجيل الخروج.", reply_markup=types.ReplyKeyboardRemove())
        return

    # إحصائيات عامة
    if text == "📊 الإحصائيات":
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        conn.close()
        bot.send_message(chat_id, f"📊 عدد المستخدمين المسجلين: {total_users}")
        return

    # فحص مستخدم
    if text == "👤 فحص مستخدم":
        admin_login_state[chat_id] = {"step": "check_user"}
        bot.send_message(chat_id, "أرسل ID المستخدم (رقم المحادثة):")
        return

    # تفعيل اشتراك
    if text == "⭐ تفعيل اشتراك":
        admin_login_state[chat_id] = {"step": "sub_user"}
        bot.send_message(chat_id, "أرسل ID المستخدم لتفعيل الاشتراك:")
        return

    # إلغاء اشتراك
    if text == "❌ إلغاء اشتراك":
        admin_login_state[chat_id] = {"step": "unsub_user"}
        bot.send_message(chat_id, "أرسل ID المستخدم لإلغاء الاشتراك:")
        return

    # رسالة جماعية
    if text == "📢 رسالة جماعية":
        admin_login_state[chat_id] = {"step": "broadcast"}
        bot.send_message(chat_id, "أرسل نص الرسالة التي تريد إرسالها للجميع:")
        return

    # خطوات فرعية حسب الحالة:
    state = admin_login_state.get(chat_id)

    if state:

        # فحص مستخدم
        if state["step"] == "check_user":
            try:
                tg_id = int(text)
            except:
                bot.send_message(chat_id, "❌ ID غير صالح، أرسل رقم فقط.")
                return

            user = get_user(tg_id)
            msg_used  = user[2]
            img_used  = user[3]
            sub_state = "✔️ مشترك" if user[4] else "❌ غير مشترك"
            bot.send_message(chat_id,
                             f"👤 معلومات المستخدم {tg_id}:\n"
                             f"- الرسائل المستعملة: {msg_used}/{FREE_MSG_LIMIT}\n"
                             f"- الصور المستعملة: {img_used}/{FREE_IMG_LIMIT}\n"
                             f"- حالة الاشتراك: {sub_state}")
            admin_login_state.pop(chat_id, None)
            return

        # تفعيل اشتراك
        if state["step"] == "sub_user":
            try:
                tg_id = int(text)
            except:
                bot.send_message(chat_id, "❌ ID غير صالح.")
                return
            set_subscription(tg_id, True)
            bot.send_message(chat_id, f"⭐ تم تفعيل الاشتراك للمستخدم {tg_id}.")
            try:
                bot.send_message(tg_id, "⭐ تم تفعيل اشتراكك في بوت F90. استمتع بحدود أعلى!")
            except:
                pass
            admin_login_state.pop(chat_id, None)
            return

        # إلغاء اشتراك
        if state["step"] == "unsub_user":
            try:
                tg_id = int(text)
            except:
                bot.send_message(chat_id, "❌ ID غير صالح.")
                return
            set_subscription(tg_id, False)
            bot.send_message(chat_id, f"❌ تم إلغاء الاشتراك للمستخدم {tg_id}.")
            try:
                bot.send_message(tg_id, "تم إلغاء اشتراكك في بوت F90. يمكنك الاستمرار بالحد المجاني.")
            except:
                pass
            admin_login_state.pop(chat_id, None)
            return

        # رسالة جماعية
        if state["step"] == "broadcast":
            broadcast_text = text
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT tg_id FROM users")
            rows = c.fetchall()
            conn.close()

            sent = 0
            for (uid,) in rows:
                try:
                    bot.send_message(uid, broadcast_text)
                    sent += 1
                except:
                    pass

            bot.send_message(chat_id, f"📢 تم إرسال الرسالة إلى {sent} مستخدم.")
            admin_login_state.pop(chat_id, None)
            return

# =============================
#   دوال OpenAI و Google AI
# =============================

def ask_openai(prompt_text):
    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي ترد بالعربية ببساطة ووضوح."},
                {"role": "user", "content": prompt_text}
            ]
        )
        return resp.choices[0].message.content
    except Exception as e:
        print("OpenAI error:", e)
        return "⚠️ خطأ في الاتصال بـ OpenAI، حاول مرة أخرى لاحقاً."

def generate_image_with_google(prompt_text):
    """
    تنبيه: تأكد من أن GOOGLE_API_KEY صحيح،  
    وقد تحتاج لتعديل endpoint حسب حساب Google AI Studio لديك.
    """
    if not GOOGLE_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagegeneration:generateImage?key={GOOGLE_API_KEY}"
    payload = {
        "prompt": {
            "text": prompt_text
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code != 200:
            print("Google AI error:", r.status_code, r.text)
            return None

        data = r.json()
        # هذا مثال تقريبي، قد يختلف حسب استجابة Google
        images = data.get("images") or data.get("candidates")
        if not images:
            return None
        img_b64 = images[0].get("base64")
        if not img_b64:
            return None
        return base64.b64decode(img_b64)
    except Exception as e:
        print("Google AI exception:", e)
        return None

# =============================
#   هاندلر المستخدم العادي
# =============================

@bot.message_handler(commands=["start"])
def start_handler(message):
    init_db()
    text = (
        f"أهلاً بك في بوت {BOT_NAME} 🤖✨\n\n"
        "اكتب سؤالك لبدء الدردشة.\n"
        "لإنشاء صورة اكتب:\n"
        "صورة: وصف الصورة\n\n"
        f"الحد المجاني: {FREE_MSG_LIMIT} رسالة و {FREE_IMG_LIMIT} صورة."
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def user_handler(message):
    # لا نتعامل مع رسائل الإدمن هنا
    if message.chat.id in admin_sessions:
        return  # الإدمن له هاندلر خاص

    tg_id = message.chat.id
    user = get_user(tg_id)
    msg_used = user[2]
    img_used = user[3]
    is_sub = bool(user[4])

    text = message.text.strip()

    # طلب صورة
    lower = text.lower()
    if lower.startswith("صورة:") or lower.startswith("img:"):
        if not is_sub and img_used >= FREE_IMG_LIMIT:
            bot.send_message(tg_id,
                             f"🚫 وصلت إلى الحد المجاني للصور ({FREE_IMG_LIMIT}).\n"
                             f"للاشتراك تواصل معنا:\n"
                             f"Telegram: {PAY_TELEGRAM}\n"
                             f"WhatsApp: {PAY_WHATSAPP}")
            return

        prompt = text.split(":", 1)[1].strip() if ":" in text else text
        bot.send_chat_action(tg_id, "upload_photo")
        bot.send_message(tg_id, "⏳ جاري توليد الصورة...")

        img_bytes = generate_image_with_google(prompt)
        if not img_bytes:
            bot.send_message(tg_id, "⚠️ تعذر توليد الصورة حالياً.")
            return

        bot.send_photo(tg_id, img_bytes, caption="ها هي الصورة المطلوبة 🎨")
        update_usage(tg_id, "img")
        return

    # محادثة نصية
    if not is_sub and msg_used >= FREE_MSG_LIMIT:
        bot.send_message(
            tg_id,
            f"🚫 وصلت إلى الحد المجاني للرسائل ({FREE_MSG_LIMIT}).\n"
            f"للاشتراك تواصل معنا:\n"
            f"Telegram: {PAY_TELEGRAM}\n"
            f"WhatsApp: {PAY_WHATSAPP}"
        )
        return

    bot.send_chat_action(tg_id, "typing")
    answer = ask_openai(text)
    update_usage(tg_id, "msg")
    bot.reply_to(message, answer)

# =============================
#   تشغيل البوت
# =============================

if __name__ == "__main__":
    init_db()
    print("F90 bot is running...")
    bot.infinity_polling(skip_pending=True)
