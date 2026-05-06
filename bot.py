import os
import time
import asyncio
import json
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, SessionPasswordNeededError

# ========== إعدادات التخزين ==========
DATA_DIR = os.environ.get('DATA_DIR', '.')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
USERS_DIR = os.path.join(DATA_DIR, 'users_data')
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)

# ========== توكن البوت ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'ضع_توكنك_هنا')

# ========== بيانات الـ API الافتراضية (حط أنت بياناتك) ==========
# هذه البيانات حق حسابك أنت (المطور)، يستخدمها البوت فقط للتشغيل
DEFAULT_API_ID = int(os.environ.get('API_ID', 0))  # حط رقمك
DEFAULT_API_HASH = os.environ.get('API_HASH', '')  # حط هاشك

# قاموس لتخزين بيانات كل مستخدم
user_sessions = {}

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

# ========== أزرار القائمة ==========
def get_main_keyboard(user_data):
    """القائمة الرئيسية تعتمد على حالة المستخدم"""
    buttons = []
    
    # زر تسجيل الدخول (إذا ما سجل)
    if not user_data.get('logged_in'):
        buttons.append([{"text": "🔐 تسجيل الدخول", "callback_data": "login"}])
        return {"inline_keyboard": buttons}
    
    # زر الخروج (إذا سجل)
    buttons.append([{"text": "🚪 تسجيل الخروج", "callback_data": "logout"}])
    buttons.append([{"text": "🎯 البوت الهدف", "callback_data": "set_target"}])
    buttons.append([{"text": "⚡ وقت التأخير", "callback_data": "set_delay"}])
    buttons.append([{"text": "📁 رفع الملف", "callback_data": "upload_file"}])
    buttons.append([{"text": "🚀 بدء الإرسال", "callback_data": "start_sending"}])
    buttons.append([{"text": "🛑 إيقاف", "callback_data": "stop_sending"}])
    buttons.append([{"text": "📊 الحالة", "callback_data": "status"}])
    
    return {"inline_keyboard": buttons}

# ========== تشغيل البوت ==========
bot = TelegramClient(os.path.join(SESSIONS_DIR, "bot_main"), DEFAULT_API_ID, DEFAULT_API_HASH)
bot.start(bot_token=BOT_TOKEN)

print("✅ البوت شغال...")

# ========== أمر /start ==========
@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('logged_in'):
        text = f"✅ مرحباً! أنت مسجل دخول كـ: {user_data.get('phone', '')}\n\nاختر ما تريد:"
    else:
        text = "🔐 أهلاً بك!\nاضغط على زر تسجيل الدخول للمتابعة."
    
    await event.respond(text, buttons=get_main_keyboard(user_data))

# ========== أزرار القائمة ==========
@bot.on(events.CallbackQuery(data="login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    
    await event.respond(
        "🔐 **تسجيل الدخول**\n\n"
        "أرسل رقم هاتفك مع رمز البلد\n"
        "مثال: +96171234567 أو 96171234567",
        parse_mode='md'
    )
    
    user_sessions[user_id] = {"step": "phone"}

@bot.on(events.CallbackQuery(data="logout"))
async def logout_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('logged_in'):
        # حذف الجلسة والبيانات
        session_file = get_user_session_name(user_id) + ".session"
        if os.path.exists(session_file):
            os.remove(session_file)
        
        user_data['logged_in'] = False
        save_user_data(user_id, user_data)
        await event.respond("✅ تم تسجيل الخروج بنجاح!", buttons=get_main_keyboard({}))
    else:
        await event.answer("أنت غير مسجل دخول!", alert=True)

@bot.on(events.CallbackQuery(data="set_target"))
async def set_target_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond("🎯 أرسل يوزر البوت الهدف (مثال: @example_bot)")
    user_sessions[user_id] = {"step": "target"}

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
        parse_mode='md'
    )
    user_sessions[user_id] = {"step": "delay"}

@bot.on(events.CallbackQuery(data="upload_file"))
async def upload_file_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    
    await event.respond("📁 أرسل ملف txt يحتوي على البطاقات (كل بطاقة في سطر)")
    user_sessions[user_id] = {"step": "file"}

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
        await event.answer("⚠️ حدد وقت التأخير أولاً!", alert=True)
        return
    
    if user_data.get('is_sending'):
        await event.answer("⚠️ يوجد إرسال قيد التشغيل!", alert=True)
        return
    
    await event.answer("🚀 جاري البدء...")
    asyncio.create_task(send_task(user_id, event))

@bot.on(events.CallbackQuery(data="stop_sending"))
async def stop_sending_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('is_sending'):
        user_data['is_sending'] = False
        save_user_data(user_id, user_data)
        await event.answer("🛑 تم الإيقاف", alert=True)
    else:
        await event.answer("⚠️ لا توجد عملية نشطة", alert=True)

@bot.on(events.CallbackQuery(data="status"))
async def status_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    text = f"""
📊 **حالة الحساب**
━━━━━━━━━━━━━━
🔐 مسجل دخول: {'✅ نعم' if user_data.get('logged_in') else '❌ لا'}
📱 رقم الهاتف: {user_data.get('phone', 'غير محدد')}
🎯 البوت الهدف: {user_data.get('target_bot', 'غير محدد')}
⏱ وقت التأخير: {user_data.get('delay_range', ['?', '?'])[0]} - {user_data.get('delay_range', ['?', '?'])[1]} ثانية
📦 عدد البطاقات: {len(user_data.get('cards', []))}
✅ تم الإرسال: {user_data.get('sent_count', 0)}
⚙️ حالة الإرسال: {'🟢 يعمل' if user_data.get('is_sending') else '🔴 متوقف'}
"""
    await event.edit(text, buttons=get_main_keyboard(user_data))

# ========== معالجة الرسائل ==========
@bot.on(events.NewMessage)
async def handle_messages(event):
    if event.sender_id == (await bot.get_me()).id:
        return
    
    user_id = str(event.sender_id)
    text = event.raw_text.strip()
    
    # جلسة تسجيل الدخول
    if user_id in user_sessions:
        step = user_sessions[user_id].get("step")
        
        # خطوة رقم الهاتف
        if step == "phone":
            phone = text
            if not phone.startswith('+'):
                phone = '+' + phone
            
            user_sessions[user_id]["phone"] = phone
            user_sessions[user_id]["step"] = "code"
            
            # إنشاء عميل جديد لهذا المستخدم
            session_name = get_user_session_name(user_id)
            client = TelegramClient(session_name, DEFAULT_API_ID, DEFAULT_API_HASH)
            user_sessions[user_id]["client"] = client
            
            await client.connect()
            await client.send_code_request(phone)
            await event.respond("📨 تم إرسال رمز التحقق!\nأرسل الرمز الآن:")
            return
        
        # خطوة رمز التحقق
        if step == "code":
            code = text
            client = user_sessions[user_id].get("client")
            phone = user_sessions[user_id].get("phone")
            
            try:
                await client.sign_in(phone, code)
                # تم بنجاح
                me = await client.get_me()
                
                # حفظ بيانات المستخدم
                user_data = {
                    'logged_in': True,
                    'phone': phone,
                    'client_session': session_name,
                    'target_bot': None,
                    'cards': [],
                    'sent_count': 0,
                    'delay_range': [30, 90],
                    'is_sending': False
                }
                save_user_data(user_id, user_data)
                
                # حذف جلسة التسجيل
                del user_sessions[user_id]
                
                await event.respond(
                    f"✅ تم تسجيل الدخول بنجاح!\n"
                    f"👤 {me.first_name}\n\n"
                    f"يمكنك الآن استخدام البوت.",
                    buttons=get_main_keyboard(user_data)
                )
                
            except SessionPasswordNeededError:
                user_sessions[user_id]["step"] = "password"
                await event.respond("🔐 مطلوب كلمة مرور (2FA)\nأرسل كلمة المرور:")
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:100]}\nأعد المحاولة بـ /start")
                del user_sessions[user_id]
            return
        
        # خطوة كلمة المرور
        if step == "password":
            password = text
            client = user_sessions[user_id].get("client")
            
            try:
                await client.sign_in(password=password)
                me = await client.get_me()
                
                user_data = {
                    'logged_in': True,
                    'phone': user_sessions[user_id].get("phone"),
                    'client_session': get_user_session_name(user_id),
                    'target_bot': None,
                    'cards': [],
                    'sent_count': 0,
                    'delay_range': [30, 90],
                    'is_sending': False
                }
                save_user_data(user_id, user_data)
                del user_sessions[user_id]
                
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
                del user_sessions[user_id]
                await event.respond(f"✅ تم تعيين البوت الهدف: {text}", buttons=get_main_keyboard(user_data))
            else:
                await event.respond("❌ يرجى إرسال يوزر يبدأ بـ @ (مثال: @bot_name)")
            return
        
        # خطوة وقت التأخير
        if step == "delay":
            parts = text.split()
            if len(parts) >= 2:
                try:
                    min_delay = int(parts[0])
                    max_delay = int(parts[1])
                    user_data = load_user_data(user_id)
                    user_data['delay_range'] = [min_delay, max_delay]
                    save_user_data(user_id, user_data)
                    del user_sessions[user_id]
                    await event.respond(f"✅ تم ضبط التأخير: {min_delay} - {max_delay} ثانية", buttons=get_main_keyboard(user_data))
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
                del user_sessions[user_id]
                
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
    client = TelegramClient(session_name, DEFAULT_API_ID, DEFAULT_API_HASH)
    await client.start()
    
    cards = user_data['cards']
    target = user_data['target_bot']
    min_d, max_d = user_data['delay_range']
    start_idx = user_data.get('current_index', 0)
    
    for i in range(start_idx, len(cards)):
        # التحقق من طلب الإيقاف
        current_data = load_user_data(user_id)
        if not current_data.get('is_sending'):
            await event.respond("🛑 تم إيقاف الإرسال")
            break
        
        try:
            await client.send_message(target, cards[i])
            
            # تحديث الإحصائيات
            user_data['sent_count'] = i + 1
            user_data['current_index'] = i + 1
            save_user_data(user_id, user_data)
            
            delay = random.randint(min_d, max_d)
            await event.respond(f"✅ [{i+1}/{len(cards)}] تم الإرسال\n⏱ انتظر {delay} ثانية")
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
bot.run_until_disconnected()
