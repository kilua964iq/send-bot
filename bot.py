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

# ========== دوال التخزين ==========
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

# ========== الأزرار ==========
def get_main_keyboard(user_data):
    if not user_data.get('logged_in'):
        return [[Button.inline("🔐 تسجيل الدخول", "login")]]
    return [
        [Button.inline("📊 الحالة", "status")],
        [Button.inline("🚪 تسجيل الخروج", "logout")]
    ]

def get_back_button():
    return [[Button.inline("🔙 رجوع", "back")]]

# ========== تشغيل البوت ==========
bot = TelegramClient(os.path.join(SESSIONS_DIR, "bot_main"), API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)

print("✅ البوت شغال...")

# قاموس لتخزين جلسات المستخدمين المؤقتة
user_steps = {}

# ========== أمر /start ==========
@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if user_data.get('logged_in'):
        text = "✅ مرحباً! أنت مسجل دخول.\n\nاضغط على 📊 الحالة لمتابعة الفحص"
    else:
        text = "🔐 أهلاً بك!\n\nاضغط على زر تسجيل الدخول للمتابعة"
    
    await event.respond(text, buttons=get_main_keyboard(user_data))

# ========== أمر /reset ==========
@bot.on(events.NewMessage(pattern="/reset"))
async def reset_cmd(event):
    user_id = str(event.sender_id)
    session_file = get_user_session_name(user_id) + ".session"
    if os.path.exists(session_file):
        os.remove(session_file)
    save_user_data(user_id, {})
    await event.respond("✅ تم مسح جلستك! استخدم /start لتسجيل الدخول مرة أخرى")

# ========== الأزرار ==========
@bot.on(events.CallbackQuery(data="login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    await event.respond(
        "🔐 **تسجيل الدخول**\n\nأرسل رقم هاتفك مع رمز البلد\nمثال: +9647123456789",
        parse_mode='md',
        buttons=get_back_button()
    )
    user_steps[user_id] = {"step": "phone"}

@bot.on(events.CallbackQuery(data="logout"))
async def logout_callback(event):
    user_id = str(event.sender_id)
    session_file = get_user_session_name(user_id) + ".session"
    if os.path.exists(session_file):
        os.remove(session_file)
    save_user_data(user_id, {})
    await event.answer("✅ تم تسجيل الخروج", alert=True)
    await event.respond("تم تسجيل الخروج بنجاح!", buttons=get_main_keyboard({}))

@bot.on(events.CallbackQuery(data="status"))
async def status_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    
    if not user_data.get('logged_in'):
        await event.respond("❌ أنت غير مسجل دخول!", buttons=get_main_keyboard({}))
        return
    
    cards = user_data.get('cards', [])
    sent = user_data.get('sent_count', 0)
    delay = user_data.get('delay_range', ['-', '-'])
    command = user_data.get('command', '-')
    target = user_data.get('target_bot', '-')
    
    text = f"""
📊 **حالة الحساب**
━━━━━━━━━━━━━━
🔐 مسجل دخول: ✅ نعم
🎯 البوت الهدف: {target}
📝 أمر الفحص: {command}
⏱ وقت التأخير: {delay[0]} - {delay[1]} ث
━━━━━━━━━━━━━━
📦 عدد البطاقات: {len(cards)}
✅ تم الإرسال: {sent}
⏳ المتبقي: {len(cards) - sent}
"""
    await event.edit(text, buttons=get_main_keyboard(user_data))

@bot.on(events.CallbackQuery(data="back"))
async def back_callback(event):
    user_id = str(event.sender_id)
    user_data = load_user_data(user_id)
    await event.edit("📋 القائمة الرئيسية:", buttons=get_main_keyboard(user_data))

# ========== معالجة الرسائل ==========
@bot.on(events.NewMessage)
async def handle_messages(event):
    if event.sender_id == (await bot.get_me()).id:
        return
    
    user_id = str(event.sender_id)
    text = event.raw_text.strip()
    
    # إذا كان المستخدم في جلسة
    if user_id in user_steps:
        step = user_steps[user_id].get("step")
        
        # تسجيل الدخول
        if step == "phone":
            phone = text if text.startswith('+') else '+' + text
            user_steps[user_id]["phone"] = phone
            user_steps[user_id]["step"] = "code"
            
            client = TelegramClient(get_user_session_name(user_id), API_ID, API_HASH)
            await client.connect()
            user_steps[user_id]["client"] = client
            
            try:
                await client.send_code_request(phone)
                await event.respond("📨 تم إرسال رمز التحقق!\nأرسل الرمز الآن:", buttons=get_back_button())
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:100]}")
                del user_steps[user_id]
            return
        
        if step == "code":
            client = user_steps[user_id].get("client")
            phone = user_steps[user_id].get("phone")
            
            try:
                await client.sign_in(phone, text)
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
                del user_steps[user_id]
                
                await event.respond(
                    f"✅ تم تسجيل الدخول بنجاح!\n👤 {me.first_name}\n\n📁 **أرسل ملف txt الآن**",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                user_steps[user_id] = {"step": "file"}
                
            except SessionPasswordNeededError:
                user_steps[user_id]["step"] = "password"
                await event.respond("🔐 مطلوب كلمة مرور (2FA)\nأرسل كلمة المرور:", buttons=get_back_button())
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:100]}")
                del user_steps[user_id]
            return
        
        if step == "password":
            client = user_steps[user_id].get("client")
            try:
                await client.sign_in(password=text)
                me = await client.get_me()
                
                user_data = {
                    'logged_in': True,
                    'setup_complete': False,
                    'phone': user_steps[user_id].get("phone"),
                    'target_bot': None,
                    'command': None,
                    'cards': [],
                    'sent_count': 0,
                    'current_index': 0,
                    'delay_range': [50, 140],
                    'is_sending': False
                }
                save_user_data(user_id, user_data)
                del user_steps[user_id]
                
                await event.respond(
                    f"✅ تم تسجيل الدخول بنجاح!\n👤 {me.first_name}\n\n📁 **أرسل ملف txt الآن**",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                user_steps[user_id] = {"step": "file"}
            except Exception as e:
                await event.respond(f"❌ كلمة مرور خاطئة: {str(e)[:100]}")
            return
        
        # رفع الملف
        if step == "file":
            if event.document and event.document.file_name.endswith('.txt'):
                file_path = os.path.join(TEMP_DIR, f"{user_id}.txt")
                await event.download_media(file_path)
                
                with open(file_path, 'r') as f:
                    cards = [line.strip() for line in f if line.strip()]
                os.remove(file_path)
                
                user_data = load_user_data(user_id)
                user_data['cards'] = cards
                user_data['sent_count'] = 0
                user_data['current_index'] = 0
                save_user_data(user_id, user_data)
                
                del user_steps[user_id]
                
                await event.respond(
                    f"✅ تم رفع {len(cards)} بطاقة\n\n"
                    "🎯 **أرسل يوزر البوت الهدف**\nمثال: @example_bot",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                user_steps[user_id] = {"step": "target"}
            else:
                await event.respond("❌ يرجى إرسال ملف txt صالح")
            return
        
        # البوت الهدف
        if step == "target":
            if text.startswith('@'):
                user_data = load_user_data(user_id)
                user_data['target_bot'] = text
                save_user_data(user_id, user_data)
                
                del user_steps[user_id]
                
                await event.respond(
                    f"✅ تم تعيين البوت الهدف: {text}\n\n"
                    "⏱ **أرسل وقت التأخير** (أقل شيء 50 ثانية)\n"
                    "أرسل رقمين بينهم مسافة\nمثال: 50 140",
                    parse_mode='md',
                    buttons=get_back_button()
                )
                user_steps[user_id] = {"step": "delay"}
            else:
                await event.respond("❌ يرجى إرسال يوزر يبدأ بـ @")
            return
        
        # وقت التأخير
        if step == "delay":
            parts = text.split()
            if len(parts) >= 2:
                try:
                    min_d = int(parts[0])
                    max_d = int(parts[1])
                    if min_d < 50:
                        min_d = 50
                    if max_d < min_d:
                        max_d = min_d + 30
                    
                    user_data = load_user_data(user_id)
                    user_data['delay_range'] = [min_d, max_d]
                    save_user_data(user_id, user_data)
                    
                    del user_steps[user_id]
                    
                    await event.respond(
                        f"✅ تم ضبط التأخير: {min_d} - {max_d} ثانية\n\n"
                        "📝 **أرسل أمر الفحص**\nمثال: /ad  أو  /cc",
                        parse_mode='md',
                        buttons=get_back_button()
                    )
                    user_steps[user_id] = {"step": "command"}
                except:
                    await event.respond("❌ أرسل رقمين صحيحين (مثال: 50 140)")
            else:
                await event.respond("❌ أرسل رقمين بينهم مسافة (مثال: 50 140)")
            return
        
        # أمر الفحص
        if step == "command":
            command = text if text.startswith('/') else '/' + text
            
            user_data = load_user_data(user_id)
            user_data['command'] = command
            user_data['setup_complete'] = True
            save_user_data(user_id, user_data)
            
            del user_steps[user_id]
            
            cards_count = len(user_data.get('cards', []))
            target = user_data.get('target_bot')
            delay = user_data.get('delay_range', [50, 140])
            
            await event.respond(
                f"✅ **اكتمل الإعداد!**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 البوت الهدف: {target}\n"
                f"📝 أمر الفحص: {command}\n"
                f"⏱ التأخير: {delay[0]} - {delay[1]} ثانية\n"
                f"📦 عدد البطاقات: {cards_count}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🚀 **جاري بدء الفحص...**",
                parse_mode='md'
            )
            
            asyncio.create_task(send_task(user_id, event))
            return

# ========== مهمة الإرسال ==========
async def send_task(user_id, event):
    user_data = load_user_data(user_id)
    session_file = get_user_session_name(user_id) + ".session"
    
    # حذف الجلسة القديمة إن وجدت
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except:
            pass
    
    client = None
    
    try:
        client = TelegramClient(get_user_session_name(user_id), API_ID, API_HASH)
        await client.start()
        
        cards = user_data.get('cards', [])
        target = user_data.get('target_bot')
        command = user_data.get('command', '/ad')
        delay_range = user_data.get('delay_range', [50, 140])
        start_idx = user_data.get('current_index', 0)
        
        total = len(cards)
        
        for i in range(start_idx, total):
            # التحقق من الإيقاف
            current_data = load_user_data(user_id)
            if not current_data.get('is_sending', True):
                await event.respond("🛑 تم إيقاف الإرسال")
                break
            
            try:
                await client.send_message(target, f"{command} {cards[i]}")
                
                user_data['sent_count'] = i + 1
                user_data['current_index'] = i + 1
                save_user_data(user_id, user_data)
                
                delay = random.randint(delay_range[0], delay_range[1])
                await event.respond(f"✅ [{i+1}/{total}] تم الإرسال\n⏱ انتظر {delay} ثانية")
                
                await asyncio.sleep(delay)
                
            except FloodWaitError as e:
                await event.respond(f"⚠️ انتظر {e.seconds} ثانية")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:50]}")
                await asyncio.sleep(5)
        
        await event.respond("🎉 **تم الانتهاء من الإرسال!**")
        
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}\nيرجى استخدام /reset ثم /start")
    finally:
        if client:
            await client.disconnect()
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except:
                pass

# ========== تشغيل البوت ==========
print("🚀 البوت يعمل 24/7...")
print("✅ يدعم عدة مستخدمين")

while True:
    try:
        bot.run_until_disconnected()
    except Exception as e:
        print(f"❌ خطأ: {e}")
        time.sleep(5)
