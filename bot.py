import os
import time
import random
import asyncio
import json
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from colorama import init, Fore, Style

init(autoreset=True)

# توكن البوت حقك (استلمه من @BotFather)
BOT_TOKEN = "8308994457:AAGQ7QUaTgLsWybafo_cro_CuXkNAPQKYOg"

# مجلدات العمل
os.makedirs("sessions", exist_ok=True)
os.makedirs("temp", exist_ok=True)
os.makedirs("users_data", exist_ok=True)

# قاموس لتخزين بيانات المستخدمين النشطين
active_users = {}

def load_user_data(user_id):
    """تحميل بيانات المستخدم من ملف"""
    file_path = f"users_data/{user_id}.json"
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(user_id, data):
    """حفظ بيانات المستخدم في ملف"""
    file_path = f"users_data/{user_id}.json"
    with open(file_path, 'w') as f:
        json.dump(data, f)

def get_session_name(user_id):
    """إنشاء جلسة فريدة لكل مستخدم"""
    return f"sessions/user_{user_id}"

# تشغيل البوت
bot = TelegramClient(get_session_name("bot"), api_id=1, api_hash="dummy").start(bot_token=BOT_TOKEN)

print(f"{Fore.CYAN}{'='*50}")
print(f"{Fore.YELLOW}🤖 التشغيل بواسطة: @o8380")
print(f"{Fore.GREEN}💎 البوت شغال وجاهز للاستخدام!")
print(f"{Fore.CYAN}{'='*50}")

# ===================== أزرار التحكم الرئيسية =====================
def get_main_keyboard():
    """القائمة الرئيسية"""
    return {
        "inline_keyboard": [
            [{"text": "🔐 تسجيل الدخول بحساب التليجرام", "callback_data": "login"}],
            [{"text": "🎯 تحديد البوت الهدف", "callback_data": "set_target"}],
            [{"text": "⚡ اختيار سرعة الإرسال", "callback_data": "set_speed"}],
            [{"text": "📁 رفع ملف البطاقات", "callback_data": "upload_file"}],
            [{"text": "🚀 بدء الإرسال", "callback_data": "start_sending"}],
            [{"text": "🛑 إيقاف الإرسال", "callback_data": "stop_sending"}],
            [{"text": "📊 لوحة التحكم", "callback_data": "dashboard"}],
        ]
    }

def get_speed_keyboard():
    """أزرار خيارات السرعة"""
    return {
        "inline_keyboard": [
            [{"text": "🐌 بطيء (60-120 ثانية)", "callback_data": "speed_60_120"}],
            [{"text": "⚡ متوسط (30-90 ثانية)", "callback_data": "speed_30_90"}],
            [{"text": "🔥 سريع (15-45 ثانية)", "callback_data": "speed_15_45"}],
            [{"text": "💨 خارق (5-20 ثانية)", "callback_data": "speed_5_20"}],
            [{"text": "🔙 رجوع", "callback_data": "back_main"}],
        ]
    }

# ===================== أمر البدء =====================
@bot.on(events.NewMessage(pattern="/start"))
async def start_command(event):
    user_id = str(event.sender_id)
    
    # تحميل بيانات المستخدم
    if user_id not in active_users:
        active_users[user_id] = load_user_data(user_id)
    
    welcome_text = f"""
{Fore.MAGENTA}╔══════════════════════════════════╗
║     🤖 بوت الإرسال الذكي 🤖      ║
║         صنع بواسطة: @o8380         ║
╚══════════════════════════════════╝

{Fore.CYAN}📌 أهلاً بك {event.sender.first_name}!

{Fore.GREEN}✨ المميزات:
{Fore.WHITE}• تسجيل دخول آمن بحسابك الشخصي
• إرسال تلقائي لأي بوت تختاره
• تأخير عشوائي لتجنب الحظر
• لوحة تحكم متكاملة
• حفظ الجلسات والتقدم

{Fore.YELLOW}⚠️ ملاحظة: تأكد من تسجيل الدخول أولاً!
"""
    await event.respond(welcome_text, buttons=get_main_keyboard())

# ===================== تسجيل الدخول =====================
@bot.on(events.CallbackQuery(data="login"))
async def login_callback(event):
    user_id = str(event.sender_id)
    
    await event.respond(
        f"{Fore.CYAN}🔐 تسجيل الدخول إلى حساب التليجرام\n\n"
        f"{Fore.YELLOW}1️⃣ اذهب إلى {Fore.GREEN}my.telegram.org{Fore.YELLOW}\n"
        f"2️⃣ سجل دخول بحسابك\n"
        f"3️⃣ احصل على {Fore.GREEN}api_id{Fore.YELLOW} و {Fore.GREEN}api_hash{Fore.YELLOW}\n\n"
        f"{Fore.WHITE}📝 أرسل البيانات بهذا الشكل:\n"
        f"{Fore.GREEN}api_id\napi_hash",
        buttons={"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_main"}]]}
    )
    
    # وضع المستخدم في حالة انتظار الإدخال
    active_users[user_id]["waiting_for"] = "api_credentials"

@bot.on(events.NewMessage)
async def handle_messages(event):
    if event.sender_id == (await bot.get_me()).id:
        return
    
    user_id = str(event.sender_id)
    
    if user_id not in active_users:
        active_users[user_id] = load_user_data(user_id)
    
    # معالجة إدخال بيانات API
    if active_users[user_id].get("waiting_for") == "api_credentials":
        lines = event.raw_text.strip().split("\n")
        if len(lines) >= 2:
            try:
                api_id = int(lines[0].strip())
                api_hash = lines[1].strip()
                
                active_users[user_id]["api_id"] = api_id
                active_users[user_id]["api_hash"] = api_hash
                active_users[user_id]["waiting_for"] = None
                save_user_data(user_id, active_users[user_id])
                
                await event.respond(
                    f"{Fore.GREEN}✅ تم تسجيل الدخول بنجاح!\n"
                    f"{Fore.CYAN}Api ID: {api_id}\n"
                    f"الآن يمكنك تحديد البوت الهدف",
                    buttons=get_main_keyboard()
                )
            except:
                await event.respond(f"{Fore.RED}❌ خطأ: api_id يجب أن يكون رقماً")
        else:
            await event.respond(f"{Fore.RED}❌ أرسل api_id في السطر الأول و api_hash في السطر الثاني")
    
    # معالجة استقبال ملف البطاقات
    elif active_users[user_id].get("waiting_for") == "upload_file":
        if event.document and event.document.mime_type == "text/plain":
            file_path = f"temp/{user_id}_cards.txt"
            await event.download_media(file_path)
            
            with open(file_path, 'r') as f:
                cards = [line.strip() for line in f if line.strip()]
            
            active_users[user_id]["cards"] = cards
            active_users[user_id]["sent_count"] = 0
            active_users[user_id]["current_index"] = 0
            active_users[user_id]["waiting_for"] = None
            save_user_data(user_id, active_users[user_id])
            
            await event.respond(
                f"{Fore.GREEN}✅ تم رفع {len(cards)} بطاقة بنجاح!\n"
                f"📊 عدد البطاقات: {len(cards)}",
                buttons=get_main_keyboard()
            )
        else:
            await event.respond(f"{Fore.RED}❌ يرجى إرسال ملف txt صالح")

# ===================== تحديد البوت الهدف =====================
@bot.on(events.CallbackQuery(data="set_target"))
async def set_target_callback(event):
    user_id = str(event.sender_id)
    
    await event.respond(
        f"{Fore.CYAN}🎯 أرسل يوزر البوت الذي تريد الإرسال إليه\n\n"
        f"{Fore.YELLOW}مثال: {Fore.GREEN}@example_bot",
        buttons={"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_main"}]]}
    )
    
    active_users[user_id]["waiting_for"] = "target_bot"

@bot.on(events.CallbackQuery(data=lambda x: x and x.startswith("speed_")))
async def speed_callback(event):
    user_id = str(event.sender_id)
    speed_choice = event.data.decode()
    
    speed_ranges = {
        "speed_60_120": (60, 120),
        "speed_30_90": (30, 90),
        "speed_15_45": (15, 45),
        "speed_5_20": (5, 20)
    }
    
    if speed_choice in speed_ranges:
        min_delay, max_delay = speed_ranges[speed_choice]
        active_users[user_id]["min_delay"] = min_delay
        active_users[user_id]["max_delay"] = max_delay
        save_user_data(user_id, active_users[user_id])
        
        speed_names = {
            "speed_60_120": "🐌 بطيء",
            "speed_30_90": "⚡ متوسط",
            "speed_15_45": "🔥 سريع",
            "speed_5_20": "💨 خارق"
        }
        
        await event.answer()
        await event.edit(
            f"{Fore.GREEN}✅ تم ضبط السرعة: {speed_names[speed_choice]}\n"
            f"📊 التأخير بين كل بطاقة: {min_delay}-{max_delay} ثانية",
            buttons=get_main_keyboard()
        )

# ===================== رفع الملف =====================
@bot.on(events.CallbackQuery(data="upload_file"))
async def upload_file_callback(event):
    user_id = str(event.sender_id)
    
    await event.respond(
        f"{Fore.CYAN}📁 أرسل ملف txt يحتوي على البطاقات\n\n"
        f"{Fore.YELLOW}📝 كل بطاقة في سطر منفصل",
        buttons={"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_main"}]]}
    )
    
    active_users[user_id]["waiting_for"] = "upload_file"

# ===================== بدء الإرسال =====================
@bot.on(events.CallbackQuery(data="start_sending"))
async def start_sending_callback(event):
    user_id = str(event.sender_id)
    data = active_users.get(user_id, {})
    
    # التحقق من المتطلبات
    if not data.get("api_id") or not data.get("api_hash"):
        await event.answer("⚠️ يرجى تسجيل الدخول أولاً!", alert=True)
        return
    
    if not data.get("target_bot"):
        await event.answer("⚠️ يرجى تحديد البوت الهدف أولاً!", alert=True)
        return
    
    if not data.get("cards"):
        await event.answer("⚠️ يرجى رفع ملف البطاقات أولاً!", alert=True)
        return
    
    if not data.get("min_delay") or not data.get("max_delay"):
        await event.answer("⚠️ يرجى اختيار سرعة الإرسال أولاً!", alert=True)
        return
    
    if data.get("is_sending"):
        await event.answer("⚠️ عملية إرسال قيد التشغيل حالياً!", alert=True)
        return
    
    await event.answer("🚀 جاري بدء الإرسال...")
    
    # تشغيل عملية الإرسال
    asyncio.create_task(send_cards_task(user_id, event))

async def send_cards_task(user_id, event):
    """مهمة الإرسال غير المتزامنة"""
    data = active_users.get(user_id, {})
    
    # إنشاء عميل جديد للمستخدم
    session_name = get_session_name(user_id)
    client = TelegramClient(session_name, data["api_id"], data["api_hash"])
    
    try:
        await client.start()
        active_users[user_id]["is_sending"] = True
        save_user_data(user_id, active_users[user_id])
        
        cards = data["cards"]
        start_index = data.get("current_index", 0)
        
        for i in range(start_index, len(cards)):
            # التحقق من طلب الإيقاف
            if not active_users.get(user_id, {}).get("is_sending"):
                await event.respond(f"{Fore.YELLOW}🛑 تم إيقاف الإرسال بعد {i} بطاقة")
                break
            
            card = cards[i]
            
            try:
                # إرسال البطاقة إلى البوت الهدف
                await client.send_message(data["target_bot"], card)
                
                # تحديث الإحصائيات
                active_users[user_id]["sent_count"] = i + 1
                active_users[user_id]["current_index"] = i + 1
                active_users[user_id]["last_card"] = card
                active_users[user_id]["last_send_time"] = time.time()
                save_user_data(user_id, active_users[user_id])
                
                # حساب التأخير العشوائي
                delay = random.randint(data["min_delay"], data["max_delay"])
                active_users[user_id]["last_delay"] = delay
                
                # إرسال تحديث للمستخدم
                remaining = len(cards) - (i + 1)
                await event.respond(
                    f"{Fore.GREEN}✅ [{i+1}/{len(cards)}] تم الإرسال: {card[:50]}...\n"
                    f"{Fore.CYAN}⏱️ انتظر {delay} ثانية\n"
                    f"📊 متبقي: {remaining} بطاقة"
                )
                
                await asyncio.sleep(delay)
                
            except FloodWaitError as e:
                await event.respond(f"{Fore.RED}⚠️ تم حظر الإرسال لمدة {e.seconds} ثانية")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await event.respond(f"{Fore.RED}❌ خطأ: {str(e)[:100]}")
                await asyncio.sleep(10)
        
        # انتهاء الإرسال
        if active_users.get(user_id, {}).get("is_sending"):
            await event.respond(f"{Fore.GREEN}🎉 تم إرسال جميع البطاقات بنجاح! ({len(cards)} بطاقة)")
            active_users[user_id]["is_sending"] = False
            save_user_data(user_id, active_users[user_id])
            
    except Exception as e:
        await event.respond(f"{Fore.RED}❌ فشل الاتصال: {str(e)[:100]}\nتأكد من بيانات API")
    finally:
        await client.disconnect()

# ===================== إيقاف الإرسال =====================
@bot.on(events.CallbackQuery(data="stop_sending"))
async def stop_sending_callback(event):
    user_id = str(event.sender_id)
    
    if active_users.get(user_id, {}).get("is_sending"):
        active_users[user_id]["is_sending"] = False
        save_user_data(user_id, active_users[user_id])
        await event.answer("🛑 تم إيقاف الإرسال!", alert=True)
        await event.respond(f"{Fore.RED}🛑 تم إيقاف عملية الإرسال", buttons=get_main_keyboard())
    else:
        await event.answer("⚠️ لا توجد عملية إرسال نشطة", alert=True)

# ===================== لوحة التحكم =====================
@bot.on(events.CallbackQuery(data="dashboard"))
async def dashboard_callback(event):
    user_id = str(event.sender_id)
    data = active_users.get(user_id, {})
    
    cards = data.get("cards", [])
    sent = data.get("sent_count", 0)
    remaining = len(cards) - sent if cards else 0
    last_delay = data.get("last_delay", "0")
    target = data.get("target_bot", "غير محدد")
    is_sending = data.get("is_sending", False)
    last_card = data.get("last_card", "لا يوجد")
    
    status_icon = "🟢 جاري الإرسال" if is_sending else "🔴 متوقف"
    
    dashboard_text = f"""
{Fore.CYAN}╔══════════════════════════════════╗
║         📊 لوحة التحكم 📊         ║
║         @o8380 — Version 5.0      ║
╚══════════════════════════════════╝

{Fore.YELLOW}📦 الإحصائيات:
{Fore.WHITE}• إجمالي البطاقات: {Fore.GREEN}{len(cards)}
{Fore.WHITE}• تم الإرسال: {Fore.GREEN}{sent}
{Fore.WHITE}• المتبقي: {Fore.YELLOW}{remaining}
{Fore.WHITE}• آخر تأخير: {Fore.CYAN}{last_delay} ثانية

{Fore.YELLOW}⚙️ الإعدادات الحالية:
{Fore.WHITE}• البوت الهدف: {Fore.CYAN}{target}
{Fore.WHITE}• حالة الإرسال: {status_icon}
{Fore.WHITE}• آخر بطاقة مرسلة: {Fore.MAGENTA}{last_card[:40]}...

{Fore.YELLOW}💡 نسبة الإنجاز: {Fore.GREEN}{round((sent/len(cards))*100 if cards else 0, 1)}%
{Fore.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    await event.answer()
    await event.edit(dashboard_text, buttons=get_main_keyboard())

# ===================== رجوع للقائمة الرئيسية =====================
@bot.on(events.CallbackQuery(data="back_main"))
async def back_main_callback(event):
    await event.answer()
    await event.edit("📋 القائمة الرئيسية:", buttons=get_main_keyboard())

# ===================== معالجة إدخال البوت الهدف =====================
async def handle_target_bot():
    @bot.on(events.NewMessage)
    async def target_handler(event):
        user_id = str(event.sender_id)
        
        if active_users.get(user_id, {}).get("waiting_for") == "target_bot":
            target = event.raw_text.strip()
            if target.startswith('@'):
                active_users[user_id]["target_bot"] = target
                active_users[user_id]["waiting_for"] = None
                save_user_data(user_id, active_users[user_id])
                await event.respond(
                    f"{Fore.GREEN}✅ تم تعيين البوت الهدف: {target}",
                    buttons=get_main_keyboard()
                )
            else:
                await event.respond(f"{Fore.RED}❌ يرجى إرسال يوزر البوت بشكل صحيح (مثال: @bot_name)")

asyncio.create_task(handle_target_bot())

print(f"{Fore.GREEN}🚀 البوت يعمل الآن... اضغط Ctrl+C للإيقاف")

# تشغيل البوت
bot.run_until_disconnected()
