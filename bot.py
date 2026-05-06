import os
import time
import random
import asyncio
import json
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from colorama import init, Fore, Style

init(autoreset=True)

# ========== إعدادات التخزين الدائم ==========
DATA_DIR = os.environ.get('DATA_DIR', '.')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
USERS_DIR = os.path.join(DATA_DIR, 'users_data')
# ===========================================

# إنشاء المجلدات
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)

# توكن البوت (ضعه في متغيرات Railway)
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'ضع_توكنك_هنا')

# قاموس لتخزين بيانات المستخدمين
active_users = {}

# قاموس لحفظ عمليات التسجيل النشطة
login_sessions = {}

# ========== دوال مساعدة ==========
def load_user_data(user_id):
    file_path = os.path.join(USERS_DIR, f"{user_id}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(user_id, data):
    file_path = os.path.join(USERS_DIR, f"{user_id}.json")
    with open(file_path, 'w') as f:
        json.dump(data, f)

def get_session_name(user_id):
    return os.path.join(SESSIONS_DIR, f"user_{user_id}")

# ========== أزرار القائمة الرئيسية ==========
def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔐 تسجيل الدخول", "callback_data": "login"}],
            [{"text": "🎯 البوت الهدف", "callback_data": "set_target"}],
            [{"text": "⚡ سرعة الإرسال", "callback_data": "set_speed"}],
            [{"text": "📁 رفع الملفات", "callback_data": "upload_file"}],
            [{"text": "🚀 بدء الإرسال", "callback_data": "start_sending"}],
            [{"text": "🛑 إيقاف الإرسال", "callback_data": "stop_sending"}],
            [{"text": "📊 لوحة التحكم", "callback_data": "dashboard"}],
        ]
    }

def get_speed_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🐌 60-120 ثانية", "callback_data": "speed_60_120"}],
            [{"text": "⚡ 30-90 ثانية", "callback_data": "speed_30_90"}],
            [{"text": "🔥 15-45 ثانية", "callback_data": "speed_15_45"}],
            [{"text": "💨 5-20 ثانية", "callback_data": "speed_5_20"}],
            [{"text": "🔙 رجوع", "callback_data": "back_main"}],
        ]
    }

# ========== تشغيل البوت ==========
bot = TelegramClient(os.path.join(SESSIONS_DIR, "bot_main"), api_id=1, api_hash="dummy")
bot.start(bot_token=BOT_TOKEN)

print(f"{Fore.GREEN}✅ البوت شغال وجاهز!")

# ========== أمر /start ==========
@bot.on(events.NewMessage(pattern="/start"))
async def start_command(event):
    user_id = str(event.sender_id)
    
    # تحميل بيانات المستخدم
    if user_id not in active_users:
        active_users[user_id] = load_user_data(user_id)
    
    # التحقق إذا كان المستخدم مسجل دخول
    if active_users[user_id].get("is_logged_in"):
        text = f"✅ مرحباً {event.sender.first_name}!\nأنت مسجل الدخول بالفعل.\n\nاختر ما تريد:"
    else:
        text = f"""🤖 بوت الإرسال الذكي
صنع بواسطة: @o8380

⚠️ أنت غير مسجل الدخول بعد!
اضغط على زر "تسجيل الدخول" للمتابعة."""
    
    await event.respond(text, buttons=get_main_keyboard())

# ========== تسجيل الدخول ==========
@bot.on(events.CallbackQuery(data="login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    
    # إرسال رسالة توضح الخطوات
    await event.respond(
        "🔐 **تسجيل الدخول إلى حساب التليجرام**\n\n"
        "سأطلب منك الآن:\n"
        "1️⃣ رقم الهاتف (مثال: 961XXXXXXXX أو +961XXXXXXXX)\n"
        "2️⃣ رمز التحقق (سيصلك على التليجرام)\n"
        "3️⃣ كلمة المرور (إذا كان حسابك مفعل به 2-Step Verification)\n\n"
        "⌨️ **أرسل رقم هاتفك الآن:**",
        parse_mode='md'
    )
    
    # بدء عملية التسجيل
    login_sessions[user_id] = {"step": "phone"}
    await event.answer("📱 جاري طلب رقم الهاتف...")

# ========== معالجة رسائل تسجيل الدخول ==========
@bot.on(events.NewMessage)
async def handle_login_messages(event):
    if event.sender_id == (await bot.get_me()).id:
        return
    
    user_id = str(event.sender_id)
    
    # تحميل بيانات المستخدم
    if user_id not in active_users:
        active_users[user_id] = load_user_data(user_id)
    
    # التحقق إذا كان المستخدم في عملية تسجيل دخول
    if user_id not in login_sessions:
        # ليس في عملية تسجيل، تعامل مع الأوامر الأخرى
        waiting = active_users[user_id].get("waiting_for")
        await handle_other_messages(event, user_id, waiting)
        return
    
    login_step = login_sessions[user_id].get("step")
    
    # خطوة 1: استلام رقم الهاتف
    if login_step == "phone":
        phone = event.raw_text.strip()
        
        # تنظيف رقم الهاتف
        if not phone.startswith('+'):
            phone = '+' + phone
        
        login_sessions[user_id]["phone"] = phone
        login_sessions[user_id]["step"] = "code"
        
        # إنشاء عميل جديد لهذا المستخدم
        session_name = get_session_name(user_id)
        client = TelegramClient(session_name, api_id=1, api_hash="dummy")
        login_sessions[user_id]["client"] = client
        
        await client.connect()
        
        try:
            # طلب إرسال رمز التحقق
            await client.send_code_request(phone)
            await event.respond(
                "📨 **تم إرسال رمز التحقق!**\n\n"
                "أرسل الرمز الذي وصل إلى حساب التليجرام الخاص بك:\n"
                "(مثال: 12345)",
                parse_mode='md'
            )
        except Exception as e:
            await event.respond(f"❌ خطأ: {str(e)[:100]}")
            del login_sessions[user_id]
            
    # خطوة 2: استلام رمز التحقق
    elif login_step == "code":
        code = event.raw_text.strip()
        client = login_sessions[user_id].get("client")
        
        if not client:
            await event.respond("❌ انتهت الجلسة، أعد المحاولة بـ /start")
            del login_sessions[user_id]
            return
        
        try:
            await client.sign_in(login_sessions[user_id]["phone"], code)
            
            # تم تسجيل الدخول بنجاح
            await finalize_login(event, user_id, client)
            
        except SessionPasswordNeededError:
            # يحتاج كلمة مرور
            login_sessions[user_id]["step"] = "password"
            await event.respond(
                "🔐 **مطلوب كلمة المرور**\n\n"
                "حسابك مفعل بالمصادقة الثنائية (2FA).\n"
                "أرسل كلمة المرور الخاصة بحسابك:",
                parse_mode='md'
            )
        except Exception as e:
            await event.respond(f"❌ رمز خاطئ أو انتهت صلاحيته: {str(e)[:100]}")
            # إعادة طلب الرمز
            await event.respond("📨 أرسل رمز التحقق مرة أخرى:")
            
    # خطوة 3: استلام كلمة المرور (2FA)
    elif login_step == "password":
        password = event.raw_text.strip()
        client = login_sessions[user_id].get("client")
        
        if not client:
            await event.respond("❌ انتهت الجلسة، أعد المحاولة بـ /start")
            del login_sessions[user_id]
            return
        
        try:
            await client.sign_in(password=password)
            await finalize_login(event, user_id, client)
        except Exception as e:
            await event.respond(f"❌ كلمة المرور خاطئة: {str(e)[:100]}")
            await event.respond("🔐 أرسل كلمة المرور الصحيحة:")

async def finalize_login(event, user_id, client):
    """إنهاء عملية تسجيل الدخول وحفظ البيانات"""
    try:
        me = await client.get_me()
        
        # حفظ بيانات المستخدم
        active_users[user_id]["is_logged_in"] = True
        active_users[user_id]["phone"] = login_sessions[user_id].get("phone")
        active_users[user_id]["client"] = client  # حفظ العميل
        active_users[user_id]["sent_count"] = active_users[user_id].get("sent_count", 0)
        active_users[user_id]["cards"] = active_users[user_id].get("cards", [])
        
        save_user_data(user_id, active_users[user_id])
        
        # حذف جلسة التسجيل
        del login_sessions[user_id]
        
        await event.respond(
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"👤 {me.first_name}\n"
            f"🆔 {me.id}\n\n"
            f"الآن يمكنك استخدام جميع الميزات.",
            parse_mode='md',
            buttons=get_main_keyboard()
        )
        
    except Exception as e:
        await event.respond(f"❌ خطأ في حفظ الجلسة: {str(e)[:100]}")

# ========== معالجة بقية الرسائل ==========
async def handle_other_messages(event, user_id, waiting):
    """معالجة الرسائل العادية (تحديد البوت، رفع الملف، إلخ)"""
    
    # تحديد البوت الهدف
    if waiting == "target":
        target = event.raw_text.strip()
        if target.startswith("@"):
            active_users[user_id]["target_bot"] = target
            active_users[user_id]["waiting_for"] = None
            save_user_data(user_id, active_users[user_id])
            await event.respond(f"✅ تم تعيين البوت الهدف: {target}", buttons=get_main_keyboard())
        else:
            await event.respond("❌ يرجى إرسال يوزر البوت بشكل صحيح (مثال: @bot_name)")
        return
    
    # رفع ملف البطاقات
    if waiting == "file":
        if event.document and event.document.mime_type == "text/plain":
            file_path = os.path.join(TEMP_DIR, f"{user_id}_cards.txt")
            await event.download_media(file_path)
            
            with open(file_path, 'r') as f:
                cards = [line.strip() for line in f if line.strip()]
            
            active_users[user_id]["cards"] = cards
            active_users[user_id]["sent_count"] = 0
            active_users[user_id]["current_index"] = 0
            active_users[user_id]["waiting_for"] = None
            save_user_data(user_id, active_users[user_id])
            
            await event.respond(
                f"✅ تم رفع {len(cards)} بطاقة بنجاح!\n"
                f"عدد البطاقات: {len(cards)}",
                buttons=get_main_keyboard()
            )
        else:
            await event.respond("❌ يرجى إرسال ملف txt صالح")
        return
    
    # إذا كانت الرسالة غير مفهومة
    if waiting:
        await event.respond("❌ إدخال غير صحيح، حاول مرة أخرى أو اضغط /start")

# ========== الأزرار الأخرى ==========
@bot.on(events.CallbackQuery(data="set_target"))
async def set_target_callback(event):
    user_id = str(event.sender_id)
    
    if not active_users.get(user_id, {}).get("is_logged_in"):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond("🎯 أرسل يوزر البوت الذي تريد الإرسال إليه (مثال: @example_bot)")
    active_users[user_id]["waiting_for"] = "target"

@bot.on(events.CallbackQuery(data="set_speed"))
async def set_speed_callback(event):
    user_id = str(event.sender_id)
    
    if not active_users.get(user_id, {}).get("is_logged_in"):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.edit("⚡ اختر سرعة الإرسال:", buttons=get_speed_keyboard())

@bot.on(events.CallbackQuery(data=lambda x: x and x.startswith("speed_")))
async def speed_choice_callback(event):
    user_id = str(event.sender_id)
    choice = event.data.decode()
    
    speeds = {
        "speed_60_120": (60, 120),
        "speed_30_90": (30, 90),
        "speed_15_45": (15, 45),
        "speed_5_20": (5, 20)
    }
    
    if choice in speeds:
        min_d, max_d = speeds[choice]
        active_users[user_id]["min_delay"] = min_d
        active_users[user_id]["max_delay"] = max_d
        save_user_data(user_id, active_users[user_id])
        await event.answer(f"✅ تم ضبط {min_d}-{max_d} ثانية")
        await event.edit("✅ تم حفظ الإعدادات", buttons=get_main_keyboard())

@bot.on(events.CallbackQuery(data="upload_file"))
async def upload_file_callback(event):
    user_id = str(event.sender_id)
    
    if not active_users.get(user_id, {}).get("is_logged_in"):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond("📁 أرسل ملف txt يحتوي على البطاقات (كل بطاقة في سطر):")
    active_users[user_id]["waiting_for"] = "file"

@bot.on(events.CallbackQuery(data="start_sending"))
async def start_sending_callback(event):
    user_id = str(event.sender_id)
    data = active_users.get(user_id, {})
    
    if not data.get("is_logged_in"):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    if not data.get("target_bot"):
        await event.answer("⚠️ حدد البوت الهدف أولاً!", alert=True)
        return
    if not data.get("cards"):
        await event.answer("⚠️ ارفع ملف البطاقات أولاً!", alert=True)
        return
    if not data.get("min_delay"):
        await event.answer("⚠️ اختر سرعة الإرسال أولاً!", alert=True)
        return
    if data.get("is_sending"):
        await event.answer("⚠️ يوجد إرسال قيد التشغيل!", alert=True)
        return
    
    await event.answer("🚀 جاري البدء...")
    asyncio.create_task(send_cards_task(user_id, event))

async def send_cards_task(user_id, event):
    """مهمة إرسال البطاقات"""
    data = active_users.get(user_id, {})
    client = data.get("client")
    
    if not client or not client.is_connected():
        # محاولة إعادة الاتصال
        session_name = get_session_name(user_id)
        client = TelegramClient(session_name, api_id=1, api_hash="dummy")
        await client.start()
        active_users[user_id]["client"] = client
    
    try:
        active_users[user_id]["is_sending"] = True
        cards = data["cards"]
        start_idx = data.get("current_index", 0)
        
        for i in range(start_idx, len(cards)):
            if not active_users.get(user_id, {}).get("is_sending"):
                await event.respond("🛑 تم إيقاف الإرسال")
                break
            
            try:
                await client.send_message(data["target_bot"], cards[i])
                
                active_users[user_id]["sent_count"] = i + 1
                active_users[user_id]["current_index"] = i + 1
                save_user_data(user_id, active_users[user_id])
                
                delay = random.randint(data["min_delay"], data["max_delay"])
                await event.respond(f"✅ [{i+1}/{len(cards)}] {cards[i][:40]}...\n⏱ انتظر {delay} ثانية")
                await asyncio.sleep(delay)
                
            except FloodWaitError as e:
                await event.respond(f"⚠️ انتظر {e.seconds} ثانية ثم أكمل")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:50]}")
                await asyncio.sleep(5)
        
        active_users[user_id]["is_sending"] = False
        save_user_data(user_id, active_users[user_id])
        await event.respond("🎉 تم الانتهاء من إرسال جميع البطاقات!")
        
    except Exception as e:
        await event.respond(f"❌ فشل الاتصال: {str(e)[:100]}")
        active_users[user_id]["is_sending"] = False

@bot.on(events.CallbackQuery(data="stop_sending"))
async def stop_sending_callback(event):
    user_id = str(event.sender_id)
    
    if active_users.get(user_id, {}).get("is_sending"):
        active_users[user_id]["is_sending"] = False
        await event.answer("🛑 تم إيقاف الإرسال", alert=True)
        await event.respond("🛑 تم إيقاف الإرسال", buttons=get_main_keyboard())
    else:
        await event.answer("⚠️ لا توجد عملية إرسال نشطة", alert=True)

@bot.on(events.CallbackQuery(data="dashboard"))
async def dashboard_callback(event):
    user_id = str(event.sender_id)
    data = active_users.get(user_id, {})
    
    cards = data.get("cards", [])
    sent = data.get("sent_count", 0)
    remaining = len(cards) - sent if cards else 0
    status = "🟢 يعمل" if data.get("is_sending") else "🔴 متوقف"
    logged_in = "✅ نعم" if data.get("is_logged_in") else "❌ لا"
    
    text = f"""
📊 **لوحة التحكم**
━━━━━━━━━━━━━━
🔐 مسجل دخول: {logged_in}
🎯 البوت الهدف: {data.get('target_bot', 'غير محدد')}
⚡ السرعة: {data.get('min_delay', '?')}-{data.get('max_delay', '?')} ثانية

📦 إجمالي البطاقات: {len(cards)}
✅ تم الإرسال: {sent}
⏳ المتبقي: {remaining}

⚙️ حالة الإرسال: {status}
"""
    await event.edit(text, buttons=get_main_keyboard())

@bot.on(events.CallbackQuery(data="back_main"))
async def back_main_callback(event):
    await event.edit("📋 القائمة الرئيسية:", buttons=get_main_keyboard())

# ========== تشغيل البوت ==========
print(f"{Fore.GREEN}🚀 البوت يعمل...")
bot.run_until_disconnected()
