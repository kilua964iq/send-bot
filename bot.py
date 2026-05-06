import os
import time
import random
import asyncio
import json
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.utils import get_input_location

# ========== إعدادات التخزين ==========
DATA_DIR = os.environ.get('DATA_DIR', '.')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
USERS_DIR = os.path.join(DATA_DIR, 'users_data')
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)

# ========== توكن البوت ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')

if not BOT_TOKEN or not API_ID or not API_HASH:
    print("❌ يرجى تعيين BOT_TOKEN, API_ID, API_HASH في متغيرات البيئة")
    exit(1)

# قاموس لتخزين عمليات تسجيل الدخول المؤقتة
login_sessions = {}

def get_user_data_file(user_id):
    return os.path.join(USERS_DIR, f"{user_id}.json")

def load_user_data(user_id):
    file_path = get_user_data_file(user_id)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(user_id, data):
    with open(get_user_data_file(user_id), 'w') as f:
        json.dump(data, f)

def get_user_session_name(user_id):
    return os.path.join(SESSIONS_DIR, f"user_{user_id}")

# ========== دوال الأزرار (تم تصحيحها) ==========
def get_main_keyboard(user_data):
    """القائمة الرئيسية"""
    if not user_data.get('logged_in'):
        # أزرار تسجيل الدخول فقط
        return [
            [{"text": "🔐 تسجيل الدخول", "callback_data": "login"}]
        ]
    
    # أزرار القائمة الكاملة
    return [
        [{"text": "🎯 البوت الهدف", "callback_data": "set_target"}],
        [{"text": "⚡ وقت التأخير", "callback_data": "set_delay"}],
        [{"text": "📁 رفع الملف", "callback_data": "upload_file"}],
        [{"text": "🚀 بدء الإرسال", "callback_data": "start_sending"}],
        [{"text": "🛑 إيقاف الإرسال", "callback_data": "stop_sending"}],
        [{"text": "📊 الحالة", "callback_data": "status"}],
        [{"text": "🚪 تسجيل الخروج", "callback_data": "logout"}]
    ]

def get_back_button():
    return [[{"text": "🔙 رجوع", "callback_data": "back_main"}]]

# ========== تشغيل البوت ==========
bot = TelegramClient(os.path.join(SESSIONS_DIR, "bot_main"), API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)

print("✅ البوت شغال...")

# ========== أمر /start ==========
@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('logged_in'):
        text = f"✅ مرحباً! أنت مسجل دخول.\n\nاختر ما تريد:"
    else:
        text = "🔐 أهلاً بك في بوت الإرسال الذكي!\n\nاضغط على زر تسجيل الدخول للمتابعة."
    
    await event.respond(text, buttons=get_main_keyboard(user_data))

# ========== أزرار القائمة ==========
@bot.on(events.CallbackQuery(data="login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    
    await event.respond(
        "🔐 **تسجيل الدخول**\n\n"
        "أرسل رقم هاتفك مع رمز البلد\n"
        "مثال: +96171234567",
        parse_mode='md',
        buttons=get_back_button()
    )
    
    login_sessions[user_id] = {"step": "phone"}

@bot.on(events.CallbackQuery(data="logout"))
async def logout_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('logged_in'):
        # حذف الجلسة
        session_file = get_user_session_name(user_id) + ".session"
        if os.path.exists(session_file):
            os.remove(session_file)
        
        # حذف بيانات المستخدم
        user_data = {}
        save_user_data(user_id, user_data)
        
        await event.answer("✅ تم تسجيل الخروج", alert=True)
        await event.respond("تم تسجيل الخروج بنجاح!", buttons=get_main_keyboard({}))
    else:
        await event.answer("أنت غير مسجل دخول!", alert=True)

@bot.on(events.CallbackQuery(data="set_target"))
async def set_target_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond(
        "🎯 أرسل يوزر البوت الهدف\nمثال: @example_bot",
        buttons=get_back_button()
    )
    login_sessions[user_id] = {"step": "target"}

@bot.on(events.CallbackQuery(data="set_delay"))
async def set_delay_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond(
        "⏱ **وقت التأخير بين كل رسالة**\n\n"
        "أرسل رقمين بينهم مسافة\n"
        "مثال: 30 60\n"
        "(يعني من 30 إلى 60 ثانية عشوائي)",
        parse_mode='md',
        buttons=get_back_button()
    )
    login_sessions[user_id] = {"step": "delay"}

@bot.on(events.CallbackQuery(data="upload_file"))
async def upload_file_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond(
        "📁 أرسل ملف txt يحتوي على البطاقات\n(كل بطاقة في سطر)",
        buttons=get_back_button()
    )
    login_sessions[user_id] = {"step": "file"}

@bot.on(events.CallbackQuery(data="start_sending"))
async def start_sending_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    if not user_data.get('target_bot'):
        await event.answer("⚠️ حدد البوت الهدف أولاً!", alert=True)
        return
    
    if not user_data.get('cards'):
        await event.answer("⚠️ ارفع ملف البطاقات أولاً!", alert=True)
        return
    
    if not user_data.get('delay_range'):
        user_data['delay_range'] = [30, 90]
        save_user_data(user_id, user_data)
    
    if user_data.get('is_sending'):
        await event.answer("⚠️ يوجد إرسال قيد التشغيل!", alert=True)
        return
    
    await event.answer("🚀 جاري البدء...", alert=True)
    await event.respond("🚀 بدء عملية الإرسال...")
    asyncio.create_task(send_task(user_id, event))

@bot.on(events.CallbackQuery(data="stop_sending"))
async def stop_sending_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('is_sending'):
        user_data['is_sending'] = False
        save_user_data(user_id, user_data)
        await event.answer("🛑 تم إيقاف الإرسال", alert=True)
        await event.respond("🛑 تم إيقاف الإرسال", buttons=get_main_keyboard(user_data))
    else:
        await event.answer("⚠️ لا توجد عملية نشطة", alert=True)

@bot.on(events.CallbackQuery(data="status"))
async def status_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.respond("❌ أنت غير مسجل دخول!", buttons=get_main_keyboard({}))
        return
    
    cards = user_data.get('cards', [])
    sent = user_data.get('sent_count', 0)
    delay = user_data.get('delay_range', [30, 90])
    is_sending = user_data.get('is_sending', False)
    
    text = f"""
📊 **حالة الحساب**
━━━━━━━━━━━━━━
🔐 مسجل دخول: ✅ نعم
📱 رقم الهاتف: {user_data.get('phone', 'غير محدد')}
🎯 البوت الهدف: {user_data.get('target_bot', 'غير محدد')}
⏱ وقت التأخير: {delay[0]} - {delay[1]} ثانية
📦 عدد البطاقات: {len(cards)}
✅ تم الإرسال: {sent}
⏳ المتبقي: {len(cards) - sent}
⚙️ حالة الإرسال: {'🟢 يعمل' if is_sending else '🔴 متوقف'}
"""
    await event.edit(text, buttons=get_main_keyboard(user_data))

@bot.on(events.CallbackQuery(data="back_main"))
async def back_main_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    await event.edit("📋 القائمة الرئيسية:", buttons=get_main_keyboard(user_data))

# ========== معالجة الرسائل النصية ==========
@bot.on(events.NewMessage)
async def handle_messages(event):
    if event.sender_id == (await bot.get_me()).id:
        return
    
    user_id = str(event.sender_id)
    text = event.raw_text.strip()
    
    # التحقق من وجود جلسة تسجيل
    if user_id not in login_sessions:
        # رسالة عادية بدون جلسة
        return
    
    step = login_sessions[user_id].get("step")
    
    # خطوة رقم الهاتف
    if step == "phone":
        phone = text
        if not phone.startswith('+'):
            phone = '+' + phone
        
        login_sessions[user_id]["phone"] = phone
        login_sessions[user_id]["step"] = "code"
        
        # إنشاء عميل جديد
        session_name = get_user_session_name(user_id)
        client = TelegramClient(session_name, API_ID, API_HASH)
        login_sessions[user_id]["client"] = client
        
        await client.connect()
        try:
            await client.send_code_request(phone)
            await event.respond("📨 تم إرسال رمز التحقق!\nأرسل الرمز الآن:", buttons=get_back_button())
        except Exception as e:
            await event.respond(f"❌ خطأ: {str(e)[:100]}")
            del login_sessions[user_id]
        return
    
    # خطوة رمز التحقق
    if step == "code":
        code = text
        client = login_sessions[user_id].get("client")
        phone = login_sessions[user_id].get("phone")
        
        try:
            await client.sign_in(phone, code)
            me = await client.get_me()
            
            # حفظ بيانات المستخدم
            user_data = {
                'logged_in': True,
                'phone': phone,
                'target_bot': None,
                'cards': [],
                'sent_count': 0,
                'current_index': 0,
                'delay_range': [30, 90],
                'is_sending': False
            }
            save_user_data(user_id, user_data)
            
            del login_sessions[user_id]
            
            await event.respond(
                f"✅ تم تسجيل الدخول بنجاح!\n👤 {me.first_name}\n\nيمكنك الآن استخدام البوت.",
                buttons=get_main_keyboard(user_data)
            )
            
        except SessionPasswordNeededError:
            login_sessions[user_id]["step"] = "password"
            await event.respond("🔐 مطلوب كلمة مرور (2FA)\nأرسل كلمة المرور:", buttons=get_back_button())
        except Exception as e:
            await event.respond(f"❌ خطأ: {str(e)[:100]}")
            del login_sessions[user_id]
        return
    
    # خطوة كلمة المرور
    if step == "password":
        password = text
        client = login_sessions[user_id].get("client")
        
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            
            user_data = {
                'logged_in': True,
                'phone': login_sessions[user_id].get("phone"),
                'target_bot': None,
                'cards': [],
                'sent_count': 0,
                'current_index': 0,
                'delay_range': [30, 90],
                'is_sending': False
            }
            save_user_data(user_id, user_data)
            del login_sessions[user_id]
            
            await event.respond(
                f"✅ تم تسجيل الدخول بنجاح!\n👤 {me.first_name}",
                buttons=get_main_keyboard(user_data)
            )
        except Exception as e:
            await event.respond(f"❌ كلمة مرور خاطئة: {str(e)[:100]}")
        return
    
    # خطوة البوت الهدف
    if step == "target":
        if text.startswith('@'):
            user_data = load_user_data(user_id)
            user_data['target_bot'] = text
            save_user_data(user_id, user_data)
            del login_sessions[user_id]
            await event.respond(f"✅ تم تعيين البوت الهدف: {text}", buttons=get_main_keyboard(user_data))
        else:
            await event.respond("❌ يرجى إرسال يوزر يبدأ بـ @")
        return
    
    # خطوة وقت التأخير
    if step == "delay":
        parts = text.split()
        if len(parts) >= 2:
            try:
                min_d = int(parts[0])
                max_d = int(parts[1])
                user_data = load_user_data(user_id)
                user_data['delay_range'] = [min_d, max_d]
                save_user_data(user_id, user_data)
                del login_sessions[user_id]
                await event.respond(f"✅ تم ضبط التأخير: {min_d} - {max_d} ثانية", buttons=get_main_keyboard(user_data))
            except:
                await event.respond("❌ أرسل رقمين صحيحين (مثال: 30 60)")
        else:
            await event.respond("❌ أرسل رقمين بينهم مسافة (مثال: 30 60)")
        return
    
    # خطوة رفع الملف
    if step == "file":
        if event.document and event.document.mime_type == "text/plain":
            file_path = os.path.join(TEMP_DIR, f"{user_id}_cards.txt")
            await event.download_media(file_path)
            
            with open(file_path, 'r') as f:
                cards = [line.strip() for line in f if line.strip()]
            
            user_data = load_user_data(user_id)
            user_data['cards'] = cards
            user_data['sent_count'] = 0
            user_data['current_index'] = 0
            save_user_data(user_id, user_data)
            del login_sessions[user_id]
            
            await event.respond(f"✅ تم رفع {len(cards)} بطاقة", buttons=get_main_keyboard(user_data))
        else:
            await event.respond("❌ يرجى إرسال ملف txt صالح")
        return

# ========== مهمة الإرسال ==========
async def send_task(user_id, event):
    user_data = load_user_data(user_id)
    user_data['is_sending'] = True
    save_user_data(user_id, user_data)
    
    session_name = get_user_session_name(user_id)
    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.start()
    
    cards = user_data.get('cards', [])
    target = user_data.get('target_bot')
    delay_range = user_data.get('delay_range', [30, 90])
    start_idx = user_data.get('current_index', 0)
    
    for i in range(start_idx, len(cards)):
        current_data = load_user_data(user_id)
        if not current_data.get('is_sending'):
            await event.respond("🛑 تم إيقاف الإرسال")
            break
        
        try:
            await client.send_message(target, cards[i])
            
            user_data['sent_count'] = i + 1
            user_data['current_index'] = i + 1
            save_user_data(user_id, user_data)
            
            delay = random.randint(delay_range[0], delay_range[1])
            await event.respond(f"✅ [{i+1}/{len(cards)}] تم الإرسال: {cards[i][:40]}...\n⏱ انتظر {delay} ثانية")
            await asyncio.sleep(delay)
            
        except FloodWaitError as e:
            await event.respond(f"⚠️ انتظر {e.seconds} ثانية")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            await event.respond(f"❌ خطأ: {str(e)[:50]}")
            await asyncio.sleep(5)
    
    user_data['is_sending'] = False
    save_user_data(user_id, user_data)
    await event.respond("🎉 تم الانتهاء من الإرسال!")

# ========== تشغيل البوت ==========
print("🚀 البوت يعمل 24/7...")
bot.run_until_disconnected()q
