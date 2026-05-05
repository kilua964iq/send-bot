import os
import time
import random
import asyncio
import json
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
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

# توكن البوت
BOT_TOKEN = "8308994457:AAEqW53IYfDcDNiB50hf0HhMgU2y1Ktomyk"

# قاموس لتخزين بيانات المستخدمين النشطين
active_users = {}

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

def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔐 تسجيل الدخول", "callback_data": "login"}],
            [{"text": "🎯 البوت الهدف", "callback_data": "set_target"}],
            [{"text": "⚡ سرعة الإرسال", "callback_data": "set_speed"}],
            [{"text": "📁 رفع ملف البطاقات", "callback_data": "upload_file"}],
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

# تشغيل البوت
bot = TelegramClient(get_session_name("bot"), api_id=1, api_hash="dummy").start(bot_token=BOT_TOKEN)

print(f"{Fore.GREEN}✅ البوت شغال وجاهز!")

# ===================== الأوامر =====================
@bot.on(events.NewMessage(pattern="/start"))
async def start_command(event):
    user_id = str(event.sender_id)
    if user_id not in active_users:
        active_users[user_id] = load_user_data(user_id)
    
    text = "🤖 بوت الإرسال الذكي\nصنع بواسطة: @o8380\n\nاختر أحد الخيارات:"
    await event.respond(text, buttons=get_main_keyboard())

# ===================== تسجيل الدخول =====================
@bot.on(events.CallbackQuery(data="login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    await event.respond(
        "🔐 أرسل api_id و api_hash بهذا الشكل:\n\n`123456`\n`abcdef123456`\n\n(خذهم من my.telegram.org)",
        parse_mode='md'
    )
    active_users[user_id]["waiting_for"] = "api"

# ===================== تحديد البوت الهدف =====================
@bot.on(events.CallbackQuery(data="set_target"))
async def set_target_callback(event):
    user_id = str(event.sender_id)
    await event.respond("🎯 أرسل يوزر البوت الهدف (مثال: @example_bot)")
    active_users[user_id]["waiting_for"] = "target"

# ===================== اختيار السرعة =====================
@bot.on(events.CallbackQuery(data="set_speed"))
async def set_speed_callback(event):
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

# ===================== رفع الملف =====================
@bot.on(events.CallbackQuery(data="upload_file"))
async def upload_file_callback(event):
    user_id = str(event.sender_id)
    await event.respond("📁 أرسل ملف txt يحتوي على البطاقات (كل بطاقة بسطر)")
    active_users[user_id]["waiting_for"] = "file"

# ===================== بدء الإرسال =====================
@bot.on(events.CallbackQuery(data="start_sending"))
async def start_sending_callback(event):
    user_id = str(event.sender_id)
    data = active_users.get(user_id, {})
    
    if not data.get("api_id"):
        await event.answer("⚠️ سجل دخول أولاً!", alert=True)
        return
    if not data.get("target_bot"):
        await event.answer("⚠️ حدد البوت الهدف!", alert=True)
        return
    if not data.get("cards"):
        await event.answer("⚠️ ارفع ملف البطاقات!", alert=True)
        return
    if not data.get("min_delay"):
        await event.answer("⚠️ اختر سرعة الإرسال!", alert=True)
        return
    if data.get("is_sending"):
        await event.answer("⚠️ يوجد إرسال قيد التشغيل!", alert=True)
        return
    
    await event.answer("🚀 جاري البدء...")
    asyncio.create_task(send_cards_task(user_id, event))

async def send_cards_task(user_id, event):
    data = active_users.get(user_id, {})
    session_name = get_session_name(user_id)
    
    try:
        client = TelegramClient(session_name, data["api_id"], data["api_hash"])
        await client.start()
        
        active_users[user_id]["is_sending"] = True
        cards = data["cards"]
        start_idx = data.get("current_index", 0)
        
        for i in range(start_idx, len(cards)):
            if not active_users.get(user_id, {}).get("is_sending"):
                await event.respond("🛑 تم الإيقاف")
                break
            
            try:
                await client.send_message(data["target_bot"], cards[i])
                active_users[user_id]["sent_count"] = i + 1
                active_users[user_id]["current_index"] = i + 1
                save_user_data(user_id, active_users[user_id])
                
                delay = random.randint(data["min_delay"], data["max_delay"])
                await event.respond(f"✅ [{i+1}/{len(cards)}] {cards[i][:30]}...\n⏱ انتظر {delay} ثانية")
                await asyncio.sleep(delay)
                
            except FloodWaitError as e:
                await event.respond(f"⚠️ انتظر {e.seconds} ثانية")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await event.respond(f"❌ خطأ: {str(e)[:50]}")
                await asyncio.sleep(5)
        
        active_users[user_id]["is_sending"] = False
        await event.respond("🎉 تم الانتهاء من الإرسال!")
        
    except Exception as e:
        await event.respond(f"❌ فشل الاتصال: {str(e)[:100]}")
    finally:
        await client.disconnect()

# ===================== إيقاف الإرسال =====================
@bot.on(events.CallbackQuery(data="stop_sending"))
async def stop_sending_callback(event):
    user_id = str(event.sender_id)
    if active_users.get(user_id, {}).get("is_sending"):
        active_users[user_id]["is_sending"] = False
        await event.answer("🛑 تم الإيقاف", alert=True)
    else:
        await event.answer("⚠️ لا توجد عملية نشطة", alert=True)

# ===================== لوحة التحكم =====================
@bot.on(events.CallbackQuery(data="dashboard"))
async def dashboard_callback(event):
    user_id = str(event.sender_id)
    data = active_users.get(user_id, {})
    cards = data.get("cards", [])
    sent = data.get("sent_count", 0)
    remaining = len(cards) - sent if cards else 0
    status = "🟢 يعمل" if data.get("is_sending") else "🔴 متوقف"
    
    text = f"""
📊 **لوحة التحكم**
━━━━━━━━━━━━━━
📦 إجمالي: {len(cards)}
✅ تم الإرسال: {sent}
⏳ المتبقي: {remaining}
⚙️ الحالة: {status}
🎯 البوت الهدف: {data.get('target_bot', 'غير محدد')}
"""
    await event.edit(text, buttons=get_main_keyboard())

# ===================== رجوع =====================
@bot.on(events.CallbackQuery(data="back_main"))
async def back_main_callback(event):
    await event.edit("📋 القائمة الرئيسية:", buttons=get_main_keyboard())

# ===================== معالجة الرسائل النصية =====================
@bot.on(events.NewMessage)
async def handle_text(event):
    if event.sender_id == (await bot.get_me()).id:
        return
    
    user_id = str(event.sender_id)
    if user_id not in active_users:
        active_users[user_id] = load_user_data(user_id)
    
    waiting = active_users[user_id].get("waiting_for")
    
    if waiting == "api":
        lines = event.raw_text.strip().split()
        if len(lines) >= 2:
            try:
                active_users[user_id]["api_id"] = int(lines[0])
                active_users[user_id]["api_hash"] = lines[1]
                active_users[user_id]["waiting_for"] = None
                save_user_data(user_id, active_users[user_id])
                await event.respond("✅ تم حفظ بيانات الدخول!", buttons=get_main_keyboard())
            except:
                await event.respond("❌ خطأ: api_id يجب أن يكون رقماً")
        else:
            await event.respond("❌ أرسل api_id ثم api_hash في سطرين")
    
    elif waiting == "target":
        target = event.raw_text.strip()
        if target.startswith("@"):
            active_users[user_id]["target_bot"] = target
            active_users[user_id]["waiting_for"] = None
            save_user_data(user_id, active_users[user_id])
            await event.respond(f"✅ تم تعيين {target}", buttons=get_main_keyboard())
        else:
            await event.respond("❌ أرسل يوزر يبدأ بـ @")
    
    elif waiting == "file":
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
            await event.respond(f"✅ تم رفع {len(cards)} بطاقة", buttons=get_main_keyboard())
        else:
            await event.respond("❌ أرسل ملف txt فقط")

# تشغيل البوت
print(f"{Fore.GREEN}🚀 البوت يعمل...")
bot.run_until_disconnected()
