import os
import time
import random
import asyncio
import json
from telethon import TelegramClient, events, Button
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
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')

if not BOT_TOKEN or not API_ID or not API_HASH:
    print("❌ يرجى تعيين BOT_TOKEN, API_ID, API_HASH في متغيرات البيئة")
    exit(1)

# أقفال للمستخدمين
user_locks = {}

def get_user_lock(user_id):
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]

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
        json.dump(data, f, indent=4)

def get_user_session_name(user_id):
    return os.path.join(SESSIONS_DIR, f"user_{user_id}")

# ========== دوال الأزرار ==========
def get_main_keyboard(user_data):
    if not user_data.get('logged_in'):
        return [[Button.inline("🔐 تسجيل الدخول", b"login")]]
    return [
        [Button.inline("📊 الحالة", b"status")],
        [Button.inline("🚪 تسجيل الخروج", b"logout")]
    ]

def get_back_button():
    return [[Button.inline("🔙 رجوع", b"back_main")]]

# ========== تشغيل البوت ==========
bot = TelegramClient(os.path.join(SESSIONS_DIR, "bot_main"), API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)

print("✅ البوت شغال...")

# ========== أمر /start ==========
@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    # حذف الجلسة التالفة إذا وجدت
    session_file = get_user_session_name(user_id) + ".session"
    if os.path.exists(session_file):
        try:
            # محاولة قراءة الملف للتأكد من أنه سليم
            with open(session_file, 'rb') as f:
                f.read(10)
        except:
            os.remove(session_file)
    
    if user_data.get('logged_in') and user_data.get('setup_complete'):
        text = "✅ مرحباً! أنت مسجل دخول ومكتمل الإعداد.\n\nاضغط على 📊 الحالة لمتابعة الفحص"
    elif user_data.get('logged_in'):
        text = "✅ أنت مسجل دخول!\n\nأرسل ملف `.txt` الآن لبدء الإعداد"
    else:
        text = "🔐 أهلاً بك!\n\nاضغط على زر تسجيل الدخول للمتابعة"
    
    await event.respond(text, buttons=get_main_keyboard(user_data))

# ========== أزرار القائمة ==========
@bot.on(events.CallbackQuery(data=b"login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    
    await event.respond(
        "🔐 **تسجيل الدخول**\n\nأرسل رقم هاتفك مع رمز البلد\nمثال: +96171234567",
        parse_mode='md',
        buttons=get_back_button()
    )
    login_sessions[user_id] = {"step": "phone"}

@bot.on(events.CallbackQuery(data=b"logout"))
async def logout_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('logged_in'):
        session_file = get_user_session_name(user_id) + ".session"
        if os.path.exists(session_file):
            os.remove(session_file)
        save_user_data(user_id, {})
        await event.answer("✅ تم تسجيل الخروج", alert=True)
        await event.respond("تم تسجيل الخروج بنجاح!", buttons=get_main_keyboard({}))
    else:
        await event.answer("أنت غير مسجل دخول!", alert=True)

@bot.on(events.CallbackQuery(data=b"status"))
async def status_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.respond("❌ أنت غير مسجل دخول!", buttons=get_main_keyboard({}))
        return
    
    cards = user_data.get('cards', [])
    sent = user_data.get('sent_count', 0)
    delay = user_data.get('delay_range', ['لم يحدد', 'لم يحدد'])
    command = user_data.get('command', 'لم يحدد')
    target = user_data.get('target_bot', 'لم يحدد')
    
    if user_data.get('is_sending'):
        status = "🟢 جاري الإرسال..."
    elif user_data.get('setup_complete'):
        status = "✅ جاهز للفحص"
    else:
        status = "⏳ الإعداد غير مكتمل"
    
    text = f"""
📊 **حالة الحساب**
━━━━━━━━━━━━━━
🔐 مسجل دخول: ✅ نعم
📊 الحالة: {status}
━━━━━━━━━━━━━━
🎯 البوت الهدف: {target}
📝 أمر الفحص: {command}
⏱ وقت التأخير: {delay[0]} - {delay[1]} ثانية
━━━━━━━━━━━━━━
📦 عدد البطاقات: {len(cards)}
✅ تم الإرسال: {sent}
⏳ المتبقي: {len(cards) - sent}
"""
    try:
        await event.edit(text, buttons=get_main_keyboard(user_data))
    except Exception:
        pass

@bot.on(events.CallbackQuery(data=b"back_main"))
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
    
    if user_id in login_sessions:
        step = login_sessions[user_id].get("step")
        
        if step == "phone":
            phone = text
            if not phone.startswith('+'):
                phone = '+' + phone
            
            login_sessions[user_id]["phone"] = phone
            login_sessions[user_id]["step"] = "code"
            
            session_name = get_user_session_name(user_id)
            # حذف الجلسة القديمة قبل إنشاء جديدة
            if os.path.exists(session_name + ".session"):
                os.remove(session_name + ".session")
            
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
        
        if step == "code":
            code = text
            client = login_sessions[user_id].get("client")
            phone = login_sessions[user_id].get("phone")
            
            try:
                await client.sign_in(phone, code)
                me = await client.get_me()
                
                user_data = {
                    'logged_in': True,
                    'setup_complete': False,
                    'phone': phone,
                    'target_bot': None,
                    'command': None,
                    'cards': [],
                    'sent_count': 0,
                    'current_index': 0,
                    'delay_range': [50, 140],
                    'is_sending': False
                }
                save_user_data(user_id, user_data)
                del login_sessions[user_id]
                
                await event.respond(
                    f"✅ تم تسجيل الدخول بنجاح!\n👤 {me.first_name}\n\n📁 **أرسل ملف txt الآن**",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                login_sessions[user_id] = {"step": "waiting_for_file"}
                
            except SessionPasswordNeededError:
                login_sessions[user_id]["step"] = "password"
                await event.respond("🔐 مطلوب كلمة مرور (2FA)\nأرسل كلمة المرور:", buttons=get_back_button())
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:100]}")
                del login_sessions[user_id]
            return
        
        if step == "password":
            password = text
            client = login_sessions[user_id].get("client")
            
            try:
                await client.sign_in(password=password)
                me = await client.get_me()
                
                user_data = {
                    'logged_in': True,
                    'setup_complete': False,
                    'phone': login_sessions[user_id].get("phone"),
                    'target_bot': None,
                    'command': None,
                    'cards': [],
                    'sent_count': 0,
                    'current_index': 0,
                    'delay_range': [50, 140],
                    'is_sending': False
                }
                save_user_data(user_id, user_data)
                del login_sessions[user_id]
                
                await event.respond(
                    f"✅ تم تسجيل الدخول بنجاح!\n👤 {me.first_name}\n\n📁 **أرسل ملف txt الآن**",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                login_sessions[user_id] = {"step": "waiting_for_file"}
                
            except Exception as e:
                await event.respond(f"❌ كلمة مرور خاطئة: {str(e)[:100]}")
            return
        
        if step == "waiting_for_file":
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
                
                await event.respond(
                    f"✅ تم رفع {len(cards)} بطاقة\n\n"
                    "🎯 **أرسل يوزر البوت الهدف**\nمثال: @example_bot",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                login_sessions[user_id] = {"step": "waiting_target"}
            else:
                await event.respond("❌ يرجى إرسال ملف txt صالح")
            return
        
        if step == "waiting_target":
            if text.startswith('@'):
                user_data = load_user_data(user_id)
                user_data['target_bot'] = text
                save_user_data(user_id, user_data)
                
                del login_sessions[user_id]
                
                await event.respond(
                    f"✅ تم تعيين البوت الهدف: {text}\n\n"
                    "⏱ **أرسل وقت التأخير** (أقل شيء 50 ثانية)\n"
                    "أرسل رقمين بينهم مسافة\nمثال: 50 140",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                login_sessions[user_id] = {"step": "waiting_delay"}
            else:
                await event.respond("❌ يرجى إرسال يوزر يبدأ بـ @")
            return
        
        if step == "waiting_delay":
            parts = text.split()
            if len(parts) >= 2:
                try:
                    min_d = int(parts[0])
                    max_d = int(parts[1])
                    
                    if min_d < 50:
                        await event.respond("⚠️ أقل وقت مسموح هو 50 ثانية! تم ضبطه على 50 تلقائياً")
                        min_d = 50
                    if max_d < min_d:
                        max_d = min_d + 30
                    
                    user_data = load_user_data(user_id)
                    user_data['delay_range'] = [min_d, max_d]
                    save_user_data(user_id, user_data)
                    
                    del login_sessions[user_id]
                    
                    await event.respond(
                        f"✅ تم ضبط التأخير: {min_d} - {max_d} ثانية\n\n"
                        "📝 **أرسل أمر الفحص**\nمثال: /ad  أو  /cc",
                        parse_mode='md',
                        buttons=get_back_button()
                    )
                    login_sessions[user_id] = {"step": "waiting_command"}
                except:
                    await event.respond("❌ أرسل رقمين صحيحين (مثال: 50 140)")
            else:
                await event.respond("❌ أرسل رقمين بينهم مسافة (مثال: 50 140)")
            return
        
        if step == "waiting_command":
            command = text.strip()
            if not command.startswith('/'):
                command = '/' + command
            
            user_data = load_user_data(user_id)
            user_data['command'] = command
            user_data['setup_complete'] = True
            save_user_data(user_id, user_data)
            
            del login_sessions[user_id]
            
            cards_count = len(user_data.get('cards', []))
            target = user_data.get('target_bot')
            delay = user_data.get('delay_range', [50, 140])
            
            await event.respond(
                f"✅ **اكتمل الإعداد بنجاح!**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 البوت الهدف: {target}\n"
                f"📝 أمر الفحص: {command}\n"
                f"⏱ وقت التأخير: {delay[0]} - {delay[1]} ثانية\n"
                f"📦 عدد البطاقات: {cards_count}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🚀 **جاري بدء الفحص تلقائياً...**",
                parse_mode='md',
                buttons=get_main_keyboard(user_data)
            )
            
            asyncio.create_task(send_task(user_id, event))
            return
    
    user_data = load_user_data(user_id)
    if user_data.get('logged_in') and user_id not in login_sessions:
        if text == "/start":
            return
        if user_data.get('is_sending'):
            await event.respond("⚠️ يوجد فحص قيد التشغيل! انتظر حتى ينتهي أو أوقفه من القائمة")
            return

# ========== مهمة الإرسال ==========
async def send_task(user_id, event):
    user_lock = get_user_lock(user_id)
    
    async with user_lock:
        user_data = load_user_data(user_id)
        
        if user_data.get('is_sending'):
            await event.respond("⚠️ يوجد فحص قيد التشغيل بالفعل!")
            return
        
        user_data['is_sending'] = True
        save_user_data(user_id, user_data)
        
        session_name = get_user_session_name(user_id)
        session_file = session_name + ".session"
        
        # حذف الجلسة القديمة
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except:
                pass
        
        client = None
        
        try:
            client = TelegramClient(session_name, API_ID, API_HASH)
            await client.start()
            
            cards = user_data.get('cards', [])
            target = user_data.get('target_bot')
            command = user_data.get('command', '/ad')
            delay_range = user_data.get('delay_range', [50, 140])
            start_idx = user_data.get('current_index', 0)
            
            if not cards:
                await event.respond("❌ لا توجد بطاقات!")
                user_data['is_sending'] = False
                save_user_data(user_id, user_data)
                return
            
            await event.respond(f"🚀 **بدء إرسال {len(cards)} بطاقة**\n🎯 الهدف: {target}")
            
            for i in range(start_idx, len(cards)):
                current_data = load_user_data(user_id)
                if not current_data.get('is_sending'):
                    await event.respond("🛑 تم إيقاف الإرسال")
                    break
                
                try:
                    full_message = f"{command} {cards[i]}"
                    await client.send_message(target, full_message)
                    
                    user_data['sent_count'] = i + 1
                    user_data['current_index'] = i + 1
                    save_user_data(user_id, user_data)
                    
                    delay = random.randint(delay_range[0], delay_range[1])
                    await event.respond(f"✅ [{i+1}/{len(cards)}] تم الإرسال\n⏱ انتظر {delay} ثانية")
                    
                    for _ in range(delay):
                        current = load_user_data(user_id)
                        if not current.get('is_sending'):
                            break
                        await asyncio.sleep(1)
                    
                except FloodWaitError as e:
                    await event.respond(f"⚠️ انتظر {e.seconds} ثانية")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    await event.respond(f"❌ خطأ: {str(e)[:50]}")
                    await asyncio.sleep(5)
            
            user_data['is_sending'] = False
            save_user_data(user_id, user_data)
            await event.respond("🎉 **تم الانتهاء من الإرسال!**")
            
        except Exception as e:
            await event.respond(f"❌ خطأ: {str(e)[:100]}\nيرجى إعادة تشغيل البوت باستخدام /start")
            user_data['logged_in'] = False
            user_data['is_sending'] = False
            save_user_data(user_id, user_data)
            if os.path.exists(session_file):
                os.remove(session_file)
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass

# ========== تشغيل البوت ==========
print("🚀 البوت يعمل 24/7...")

while True:
    try:
        bot.run_until_disconnected()
    except Exception as e:
        print(f"❌ خطأ: {e}")
        time.sleep(5)
