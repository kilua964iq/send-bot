import os, time, random, asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import SendMessageRequest
from telethon.errors import FloodWaitError

# بيانات البوت الرئيسي (انت اللي تسويه من BotFather)
BOT_TOKEN = "ضع_توكن_بوتك_هنا"
# البوت الهدف (البوت اللي تريد ترسل له البطاقات)
TARGET_BOT_USERNAME = "@username_of_target_bot"

app = TelegramClient("bot_session", api_id=1, api_hash="dummy").start(bot_token=BOT_TOKEN)

user_data = {}

def get_client(user_id):
    # حساب خاص لكل يوزر
    path = f"sessions/{user_id}.session"
    if not os.path.exists("sessions"):
        os.mkdir("sessions")
    # لازم يكون عندك api_id و api_hash مسجلين لكل مستخدم
    # سنخزنهم في user_data
    return TelegramClient(path, user_data[user_id]["api_id"], user_data[user_id]["api_hash"])

@app.on(events.NewMessage(pattern="/start"))
async def start(event):
    user_id = event.sender_id
    if user_id not in user_data:
        user_data[user_id] = {}
    markup = {
        "inline_keyboard": [
            [{"text": "📝 تعيين API ID و HASH", "callback_data": "set_api"}],
            [{"text": "📤 رفع ملف البطاقات", "callback_data": "upload_file"}],
            [{"text": "🎚 اختيار سرعة الإرسال", "callback_data": "set_speed"}],
            [{"text": "🚀 بدء الإرسال", "callback_data": "start_send"}],
            [{"text": "🛑 إيقاف الإرسال", "callback_data": "stop_send"}],
            [{"text": "📊 حالة الإرسال", "callback_data": "status"}],
        ]
    }
    await event.respond("🔹 أهلاً بك في بوت الإرسال التلقائي الذكي 🔹\nاختر ما تريد:", buttons=markup)

@app.on(events.CallbackQuery)
async def callback(event):
    user_id = event.sender_id
    data = event.data.decode()
    if data == "set_api":
        await event.respond("ارسل api_id ثم api_hash في سطرين منفصلين:")
        user_data[user_id]["waiting_for_api"] = True
    elif data == "upload_file":
        await event.respond("ارسل ملف txt يحتوي على بطاقة في كل سطر:")
        user_data[user_id]["waiting_for_file"] = True
    elif data == "set_speed":
        markup = {
            "inline_keyboard": [
                [{"text": "⚡ 30-90 ثانية", "callback_data": "speed_1"}],
                [{"text": "🔥 40-120 ثانية", "callback_data": "speed_2"}],
                [{"text": "🐢 60-160 ثانية", "callback_data": "speed_3"}],
            ]
        }
        await event.respond("اختر التأخير العشوائي بين كل رسالة:", buttons=markup)
    elif data.startswith("speed_"):
        speeds = {"speed_1": (30,90), "speed_2": (40,120), "speed_3": (60,160)}
        user_data[user_id]["delay_range"] = speeds[data]
        await event.respond(f"✅ تم ضبط التأخير العشوائي بين {user_data[user_id]['delay_range'][0]} و {user_data[user_id]['delay_range'][1]} ثانية")
    elif data == "start_send":
        await start_sending(user_id, event)
    elif data == "stop_send":
        user_data[user_id]["stop"] = True
        await event.respond("🛑 تم إيقاف الإرسال.")
    elif data == "status":
        await status_report(user_id, event)

@app.on(events.NewMessage)
async def handle_messages(event):
    user_id = event.sender_id
    if user_data.get(user_id, {}).get("waiting_for_api"):
        lines = event.raw_text.split("\n")
        if len(lines) >= 2:
            api_id = int(lines[0].strip())
            api_hash = lines[1].strip()
            user_data[user_id]["api_id"] = api_id
            user_data[user_id]["api_hash"] = api_hash
            del user_data[user_id]["waiting_for_api"]
            await event.respond("✅ تم حفظ بيانات API بنجاح")
    elif user_data.get(user_id, {}).get("waiting_for_file"):
        if event.document and event.document.mime_type == "text/plain":
            path = f"temp/{user_id}.txt"
            os.makedirs("temp", exist_ok=True)
            await event.download_media(path)
            with open(path, "r") as f:
                cards = [line.strip() for line in f if line.strip()]
            user_data[user_id]["cards"] = cards
            user_data[user_id]["sent"] = 0
            user_data[user_id]["stop"] = False
            del user_data[user_id]["waiting_for_file"]
            await event.respond(f"✅ تم رفع {len(cards)} بطاقة. اضغط 'بدء الإرسال'")

async def start_sending(user_id, event):
    data = user_data.get(user_id, {})
    if "cards" not in data or "delay_range" not in data:
        await event.respond("⚠️ يرجى رفع ملف واختيار السرعة أولاً")
        return
    async with get_client(user_id) as client:
        for idx, card in enumerate(data["cards"][data["sent"]:]):
            if data.get("stop"):
                break
            try:
                await client.send_message(TARGET_BOT_USERNAME, card)
                data["sent"] += 1
                delay = random.randint(*data["delay_range"])
                await event.respond(f"✅ أرسلت: {card}\n⏱ انتظر {delay} ثانية...")
                await asyncio.sleep(delay)
            except FloodWaitError as e:
                await event.respond(f"⚠️ تم حظر الإرسال لمدة {e.seconds} ثانية")
                await asyncio.sleep(e.seconds)
        await event.respond("🏁 تم الانتهاء من إرسال جميع البطاقات")

async def status_report(user_id, event):
    data = user_data.get(user_id, {})
    total = len(data.get("cards", []))
    sent = data.get("sent", 0)
    remaining = total - sent
    delay = data.get("delay_range", ("غير محدد", "غير محدد"))
    status = "🟢 يعمل" if not data.get("stop") else "🔴 متوقف"
    await event.respond(
        f"📊 **تقرير الإرسال**\n"
        f"📦 إجمالي البطاقات: {total}\n"
        f"✅ تم الإرسال: {sent}\n"
        f"⏳ المتبقي: {remaining}\n"
        f"⏱ التأخير بين كل بطاقة: {delay[0]}-{delay[1]} ثانية\n"
        f"⚙️ الحالة: {status}"
    )

print("✅ البوت شغال ...")
app.run_until_disconnected()
