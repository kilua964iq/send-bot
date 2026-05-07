"""
╔══════════════════════════════════════════════════════════╗
║           Telegram Card Checker Bot  v2.0               ║
║  متغيرات البيئة:                                        ║
║    BOT_TOKEN  – توكن البوت من @BotFather               ║
║    API_ID     – من my.telegram.org                      ║
║    API_HASH   – من my.telegram.org                      ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import json
import random
import asyncio
import logging
import re
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
    UserDeactivatedBanError,
    AuthKeyUnregisteredError,
)

# ══════════════════════════════════════════════════════════
# إعداد الـ Logging
# ══════════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# متغيرات البيئة
# ══════════════════════════════════════════════════════════
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]

# ══════════════════════════════════════════════════════════
# مجلد البيانات
# ══════════════════════════════════════════════════════════
DATA_DIR = Path("user_data")
DATA_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════
# مراحل المحادثة
# ══════════════════════════════════════════════════════════
(
    WAIT_PHONE,
    WAIT_CODE,
    WAIT_2FA,
    WAIT_FILE,
    WAIT_TARGET,
    WAIT_DELAY,
    WAIT_COMMAND,
) = range(7)

# ══════════════════════════════════════════════════════════
# قواميس العملاء والمهام النشطة
# ══════════════════════════════════════════════════════════
telethon_clients: dict[int, TelegramClient] = {}
sending_tasks:    dict[int, asyncio.Task]   = {}

# ══════════════════════════════════════════════════════════
# أدوات JSON
# ══════════════════════════════════════════════════════════

def user_file(uid: int) -> Path:
    return DATA_DIR / f"{uid}.json"

def load_data(uid: int) -> dict:
    p = user_file(uid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_data(uid: int, data: dict):
    user_file(uid).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def is_logged_in(uid: int) -> bool:
    return bool(load_data(uid).get("session_string"))

# ══════════════════════════════════════════════════════════
# أدوات Telethon
# ══════════════════════════════════════════════════════════

async def get_client(uid: int) -> TelegramClient:
    existing = telethon_clients.get(uid)
    if existing and existing.is_connected():
        return existing

    session_str = load_data(uid).get("session_string", "")
    client = TelegramClient(
        StringSession(session_str),
        API_ID,
        API_HASH,
        system_version="4.16.30-vxCUSTOM",
        device_model="Desktop",
        app_version="1.0",
    )
    await client.connect()
    telethon_clients[uid] = client
    return client

async def disconnect_client(uid: int):
    client = telethon_clients.pop(uid, None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass

# ══════════════════════════════════════════════════════════
# لوحة المفاتيح الرئيسية
# ══════════════════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 الحالة",        callback_data="status"),
            InlineKeyboardButton("🚀 بدء الإرسال",   callback_data="start_sending"),
        ],
        [
            InlineKeyboardButton("⏹ إيقاف الإرسال",  callback_data="stop_sending"),
        ],
        [
            InlineKeyboardButton("🔄 مهمة جديدة",    callback_data="reset_task"),
            InlineKeyboardButton("🚪 تسجيل الخروج",  callback_data="logout"),
        ],
    ])

# ══════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_logged_in(uid):
        data = load_data(uid)
        name = data.get("name", "مستخدم")
        await update.message.reply_text(
            f"✅ مرحباً مجدداً *{name}*!\n\nاختر ما تريد:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 *مرحباً بك في بوت فحص البطاقات!*\n\n"
        "📱 أرسل رقم هاتفك مع رمز الدولة:\n"
        "مثال: `+9665XXXXXXXX`",
        parse_mode="Markdown",
    )
    return WAIT_PHONE

# ══════════════════════════════════════════════════════════
# مراحل تسجيل الدخول
# ══════════════════════════════════════════════════════════

async def wait_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    phone = update.message.text.strip()

    if not re.match(r"^\+\d{7,15}$", phone):
        await update.message.reply_text(
            "❌ رقم غير صالح.\nأرسله بالصيغة: `+9665XXXXXXXX`",
            parse_mode="Markdown",
        )
        return WAIT_PHONE

    msg = await update.message.reply_text("⏳ جارٍ إرسال رمز التحقق...")
    try:
        client = await get_client(uid)
        result = await client.send_code_request(phone)
        ctx.user_data["phone"]      = phone
        ctx.user_data["phone_hash"] = result.phone_code_hash
        await msg.edit_text(
            "📩 أرسل رمز التحقق الذي وصلك على تيليجرام:\n"
            "_(أرسل الأرقام فقط بدون مسافات)_",
            parse_mode="Markdown",
        )
        return WAIT_CODE
    except FloodWaitError as e:
        await msg.edit_text(f"⚠️ محاولات كثيرة. انتظر {e.seconds} ثانية ثم أرسل /start")
        await disconnect_client(uid)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"[{uid}] send_code_request: {e}")
        await msg.edit_text(
            f"❌ خطأ أثناء إرسال الرمز:\n`{e}`\n\nأرسل /start للمحاولة مجدداً.",
            parse_mode="Markdown",
        )
        await disconnect_client(uid)
        return ConversationHandler.END


async def wait_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    code = update.message.text.strip().replace(" ", "")

    try:
        client = await get_client(uid)
        await client.sign_in(
            phone=ctx.user_data["phone"],
            code=code,
            phone_code_hash=ctx.user_data["phone_hash"],
        )
    except SessionPasswordNeededError:
        await update.message.reply_text(
            "🔒 الحساب محمي بكلمة مرور *2FA*\n\nأرسل كلمة المرور:",
            parse_mode="Markdown",
        )
        return WAIT_2FA
    except PhoneCodeInvalidError:
        await update.message.reply_text("❌ الرمز غير صحيح. أرسله مرة أخرى:")
        return WAIT_CODE
    except PhoneCodeExpiredError:
        await update.message.reply_text(
            "❌ الرمز منتهي الصلاحية. أرسل /start للحصول على رمز جديد."
        )
        await disconnect_client(uid)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"[{uid}] sign_in code: {e}")
        await update.message.reply_text(
            f"❌ خطأ: `{e}`\n\nأرسل /start للمحاولة مجدداً.",
            parse_mode="Markdown",
        )
        await disconnect_client(uid)
        return ConversationHandler.END

    return await _finish_login(update, uid, client)


async def wait_2fa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid      = update.effective_user.id
    password = update.message.text.strip()

    try:
        client = await get_client(uid)
        await client.sign_in(password=password)
    except Exception as e:
        logger.warning(f"[{uid}] 2FA failed: {e}")
        await update.message.reply_text("❌ كلمة المرور غير صحيحة. حاول مرة أخرى:")
        return WAIT_2FA

    return await _finish_login(update, uid, client)


async def _finish_login(update: Update, uid: int, client: TelegramClient):
    me   = await client.get_me()
    data = load_data(uid)
    data["session_string"] = client.session.save()
    data["name"]           = f"{me.first_name or ''} {me.last_name or ''}".strip()
    data["telegram_id"]    = me.id
    save_data(uid, data)

    logger.info(f"[{uid}] logged in as {data['name']} (tg_id={me.id})")

    await update.message.reply_text(
        f"✅ تم تسجيل الدخول بنجاح!\n"
        f"👤 *{data['name']}*\n\n"
        f"الآن أرسل ملف `.txt` يحتوي على البطاقات:",
        parse_mode="Markdown",
    )
    return WAIT_FILE

# ══════════════════════════════════════════════════════════
# قراءة الملف (دالة مشتركة لتجنب التكرار)
# ══════════════════════════════════════════════════════════

async def _read_txt_file(update: Update) -> list[str] | None:
    """
    يقرأ ملف txt من الرسالة ويُعيد قائمة البطاقات.
    يُعيد None عند أي خطأ بعد إرسال رسالة الخطأ للمستخدم.
    """
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ يرجى إرسال ملف `.txt`.", parse_mode="Markdown")
        return None

    if not doc.file_name.lower().endswith(".txt"):
        await update.message.reply_text("❌ الملف يجب أن يكون بصيغة `.txt`.", parse_mode="Markdown")
        return None

    msg = await update.message.reply_text("📥 جارٍ قراءة الملف...")
    try:
        tg_file = await doc.get_file()
        raw     = await tg_file.download_as_bytearray()
        text    = raw.decode("utf-8", errors="ignore")
    except Exception as e:
        await msg.edit_text(f"❌ فشل تحميل الملف: `{e}`", parse_mode="Markdown")
        return None

    cards = [line.strip() for line in text.splitlines() if line.strip()]
    if not cards:
        await msg.edit_text("❌ الملف فارغ أو لا يحتوي على بطاقات.")
        return None

    await msg.edit_text(f"✅ تم قراءة *{len(cards)}* بطاقة.", parse_mode="Markdown")
    return cards

# ══════════════════════════════════════════════════════════
# ★ التعديل الأول: معالج الملفات في أي وقت (خارج المحادثة)
# ══════════════════════════════════════════════════════════

async def handle_file_anytime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    يُعالج ملفات txt المرسلة في أي وقت، حتى خارج ConversationHandler.
    يبدأ تلقائياً تسلسل الإعداد عبر ctx.user_data["awaiting"].
    """
    uid = update.effective_user.id

    if not is_logged_in(uid):
        await update.message.reply_text("❌ يجب تسجيل الدخول أولاً. أرسل /start")
        return

    cards = await _read_txt_file(update)
    if cards is None:
        return

    data          = load_data(uid)
    data["cards"] = cards
    data["sent"]  = 0
    save_data(uid, data)

    # نبدأ تسلسل الإعداد اليدوي
    ctx.user_data["awaiting"] = "target"

    await update.message.reply_text(
        f"✅ تم تحميل *{len(cards)}* بطاقة.\n\n"
        f"🎯 أرسل يوزر البوت الهدف:\nمثال: `@CheckBot`",
        parse_mode="Markdown",
    )

# ══════════════════════════════════════════════════════════
# معالج النصوص خارج المحادثة (استكمال الإعداد)
# ══════════════════════════════════════════════════════════

async def handle_text_anytime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    يكمل خطوات الإعداد (target → delay → command)
    بعد رفع الملف عبر handle_file_anytime.
    """
    uid      = update.effective_user.id
    awaiting = ctx.user_data.get("awaiting")

    if not awaiting or not is_logged_in(uid):
        return

    text = update.message.text.strip()

    # ── الخطوة 1: البوت الهدف ─────────────────────────────
    if awaiting == "target":
        if not text.startswith("@") or len(text) < 2:
            await update.message.reply_text(
                "❌ يجب أن يبدأ اليوزر بـ `@`\nمثال: `@CheckBot`",
                parse_mode="Markdown",
            )
            return
        data           = load_data(uid)
        data["target"] = text
        save_data(uid, data)
        ctx.user_data["awaiting"] = "delay"
        await update.message.reply_text(
            "⏱ أرسل وقت التأخير (رقمان بينهما مسافة، الحد الأدنى 50):\n"
            "مثال: `50 140`",
            parse_mode="Markdown",
        )

    # ── الخطوة 2: التأخير ─────────────────────────────────
    elif awaiting == "delay":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ أرسل رقمين بينهما مسافة. مثال: `50 140`",
                parse_mode="Markdown",
            )
            return
        try:
            lo, hi = int(parts[0]), int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ أرقام غير صالحة.")
            return
        if lo < 50:
            await update.message.reply_text("❌ الحد الأدنى للتأخير هو 50 ثانية.")
            return
        if hi < lo:
            await update.message.reply_text("❌ الحد الأعلى يجب أن يكون ≥ الحد الأدنى.")
            return
        data             = load_data(uid)
        data["delay_lo"] = lo
        data["delay_hi"] = hi
        save_data(uid, data)
        ctx.user_data["awaiting"] = "command"
        await update.message.reply_text(
            "✉️ أرسل أمر الفحص الذي يُرسل مع كل بطاقة:\n"
            "مثال: `/ad`",
            parse_mode="Markdown",
        )

    # ── الخطوة 3: أمر الفحص ──────────────────────────────
    elif awaiting == "command":
        data                  = load_data(uid)
        data["check_command"] = text
        save_data(uid, data)
        ctx.user_data.pop("awaiting", None)
        total = len(data.get("cards", []))
        await update.message.reply_text(
            f"🎉 *الإعداد مكتمل!*\n\n"
            f"🎯 البوت الهدف: `{data['target']}`\n"
            f"✉️ أمر الفحص: `{text}`\n"
            f"⏱ التأخير: `{data['delay_lo']}–{data['delay_hi']}` ثانية\n"
            f"🃏 عدد البطاقات: *{total}*\n\n"
            f"اضغط *🚀 بدء الإرسال* للانطلاق:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

# ══════════════════════════════════════════════════════════
# مراحل إعداد المهمة (داخل ConversationHandler)
# ══════════════════════════════════════════════════════════

async def ask_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """نقطة دخول ConversationHandler بعد الضغط على 'مهمة جديدة'."""
    query = update.callback_query
    if query:
        await query.answer()

    uid  = update.effective_user.id

    # إيقاف الإرسال إن كان جارياً
    task = sending_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()

    # مسح بيانات المهمة مع الإبقاء على الجلسة
    data = load_data(uid)
    for key in ["cards", "sent", "target", "delay_lo", "delay_hi", "check_command"]:
        data.pop(key, None)
    save_data(uid, data)

    send_fn = query.message.reply_text if query else update.message.reply_text
    await send_fn(
        "🔄 تم مسح بيانات المهمة السابقة.\n\n"
        "📂 أرسل ملف `.txt` يحتوي على البطاقات (كل بطاقة في سطر):",
        parse_mode="Markdown",
    )
    return WAIT_FILE


async def wait_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    cards = await _read_txt_file(update)
    if cards is None:
        return WAIT_FILE

    data          = load_data(uid)
    data["cards"] = cards
    data["sent"]  = 0
    save_data(uid, data)

    await update.message.reply_text(
        f"✅ تم تحميل *{len(cards)}* بطاقة.\n\n"
        f"🎯 أرسل يوزر البوت الهدف:\nمثال: `@CheckBot`",
        parse_mode="Markdown",
    )
    return WAIT_TARGET


async def wait_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid    = update.effective_user.id
    target = update.message.text.strip()

    if not target.startswith("@") or len(target) < 2:
        await update.message.reply_text(
            "❌ يجب أن يبدأ اليوزر بـ `@`\nمثال: `@CheckBot`",
            parse_mode="Markdown",
        )
        return WAIT_TARGET

    data           = load_data(uid)
    data["target"] = target
    save_data(uid, data)

    await update.message.reply_text(
        "⏱ أرسل وقت التأخير بين البطاقات:\n"
        "_(رقمان بينهما مسافة، الحد الأدنى 50 ثانية)_\n\n"
        "مثال: `50 140`",
        parse_mode="Markdown",
    )
    return WAIT_DELAY


async def wait_delay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    text  = update.message.text.strip()
    parts = text.split()

    if len(parts) != 2:
        await update.message.reply_text(
            "❌ أرسل رقمين بينهما مسافة.\nمثال: `50 140`",
            parse_mode="Markdown",
        )
        return WAIT_DELAY

    try:
        lo, hi = int(parts[0]), int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ القيم يجب أن تكون أرقاماً صحيحة.")
        return WAIT_DELAY

    if lo < 50:
        await update.message.reply_text("❌ الحد الأدنى للتأخير هو 50 ثانية.")
        return WAIT_DELAY
    if hi < lo:
        await update.message.reply_text("❌ الحد الأعلى يجب أن يكون ≥ الحد الأدنى.")
        return WAIT_DELAY

    data             = load_data(uid)
    data["delay_lo"] = lo
    data["delay_hi"] = hi
    save_data(uid, data)

    await update.message.reply_text(
        "✉️ أرسل أمر الفحص الذي يُرسل مع كل بطاقة:\n"
        "مثال: `/ad`",
        parse_mode="Markdown",
    )
    return WAIT_COMMAND


async def wait_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    command = update.message.text.strip()

    data                  = load_data(uid)
    data["check_command"] = command
    save_data(uid, data)

    total = len(data.get("cards", []))
    await update.message.reply_text(
        f"🎉 *الإعداد مكتمل!*\n\n"
        f"🎯 البوت الهدف: `{data['target']}`\n"
        f"✉️ أمر الفحص: `{command}`\n"
        f"⏱ التأخير: `{data['delay_lo']}–{data['delay_hi']}` ثانية\n"
        f"🃏 عدد البطاقات: *{total}*\n\n"
        f"اضغط *🚀 بدء الإرسال* للانطلاق:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
# الإرسال الفعلي في الخلفية
# ══════════════════════════════════════════════════════════

async def _send_cards(uid: int, bot, chat_id: int):
    """حلقة الإرسال – تعمل كـ asyncio.Task منفصلة."""
    data   = load_data(uid)
    cards  = data.get("cards", [])
    sent   = data.get("sent", 0)
    target = data.get("target")
    cmd    = data.get("check_command", "")
    lo     = data.get("delay_lo", 50)
    hi     = data.get("delay_hi", 140)
    total  = len(cards)

    if not cards or not target:
        await bot.send_message(chat_id, "❌ بيانات المهمة غير مكتملة. استخدم 'مهمة جديدة'.")
        return

    if sent >= total:
        await bot.send_message(
            chat_id,
            "✅ جميع البطاقات أُرسلت بالفعل!\n\nأرسل ملفاً جديداً أو استخدم 'مهمة جديدة'.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # التحقق من الجلسة
    try:
        client = await get_client(uid)
        if not await client.is_user_authorized():
            await bot.send_message(chat_id, "❌ الجلسة منتهية. سجّل الدخول مجدداً بـ /start")
            return
    except (UserDeactivatedBanError, AuthKeyUnregisteredError):
        await bot.send_message(chat_id, "❌ الحساب محظور أو الجلسة غير صالحة.")
        return
    except Exception as e:
        await bot.send_message(chat_id, f"❌ تعذّر الاتصال: `{e}`", parse_mode="Markdown")
        return

    progress_msg = await bot.send_message(
        chat_id,
        f"🚀 بدأ الإرسال من البطاقة *{sent + 1}* من *{total}*\n"
        f"⏱ التأخير العشوائي: {lo}–{hi} ثانية",
        parse_mode="Markdown",
    )

    consecutive_errors = 0

    try:
        for i in range(sent, total):
            card    = cards[i]
            message = f"{cmd} {card}".strip()

            # ── إرسال مع معالجة FloodWait ─────────────────
            try:
                await client.send_message(target, message)
                consecutive_errors = 0
            except FloodWaitError as e:
                wait_time = e.seconds + 5
                await bot.send_message(
                    chat_id,
                    f"⚠️ *FloodWait* – انتظار {wait_time} ثانية تلقائياً...",
                    parse_mode="Markdown",
                )
                await asyncio.sleep(wait_time)
                try:
                    await client.send_message(target, message)
                    consecutive_errors = 0
                except Exception as retry_err:
                    consecutive_errors += 1
                    logger.error(f"[{uid}] retry failed card {i+1}: {retry_err}")
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[{uid}] send card {i+1}: {e}")
                await bot.send_message(
                    chat_id,
                    f"⚠️ خطأ في البطاقة {i+1}: `{e}`",
                    parse_mode="Markdown",
                )

            # ── حفظ التقدم فوراً ──────────────────────────
            d         = load_data(uid)
            d["sent"] = i + 1
            save_data(uid, d)

            # ── إيقاف تلقائي عند 5 أخطاء متتالية ─────────
            if consecutive_errors >= 5:
                await bot.send_message(
                    chat_id,
                    f"🛑 *إيقاف تلقائي* بسبب 5 أخطاء متتالية.\n"
                    f"✅ تم حفظ التقدم عند البطاقة {i+1}.",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(),
                )
                return

            # ── تحديث رسالة التقدم كل 10 بطاقات ──────────
            if (i + 1) % 10 == 0 or (i + 1) == total:
                filled = int(10 * (i + 1) / total)
                bar    = "█" * filled + "░" * (10 - filled)
                pct    = round((i + 1) / total * 100, 1)
                try:
                    await progress_msg.edit_text(
                        f"📤 *جارٍ الإرسال...*\n\n"
                        f"✅ {i+1} / {total}\n"
                        f"`[{bar}]` {pct}%",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

            # ── تأخير عشوائي ──────────────────────────────
            if i < total - 1:
                delay = random.randint(lo, hi)
                await asyncio.sleep(delay)

        # ── اكتمل الإرسال ─────────────────────────────────
        await bot.send_message(
            chat_id,
            f"🎉 *تم إرسال جميع البطاقات بنجاح!*\n\n🃏 المجموع: {total} بطاقة",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    except asyncio.CancelledError:
        current = load_data(uid).get("sent", 0)
        await bot.send_message(
            chat_id,
            f"⏹ *تم إيقاف الإرسال يدوياً.*\n"
            f"✅ تم حفظ التقدم عند البطاقة {current}.\n\n"
            f"اضغط *🚀 بدء الإرسال* للاستئناف.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"[{uid}] unexpected error in _send_cards: {e}")
        await bot.send_message(
            chat_id,
            f"❌ خطأ غير متوقع: `{e}`",
            parse_mode="Markdown",
        )
    finally:
        sending_tasks.pop(uid, None)

# ══════════════════════════════════════════════════════════
# معالجات أزرار الـ Inline Keyboard
# ══════════════════════════════════════════════════════════

async def cb_start_sending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    uid     = update.effective_user.id
    chat_id = query.message.chat_id

    if not is_logged_in(uid):
        await query.message.reply_text("❌ سجّل الدخول أولاً بـ /start")
        return

    data = load_data(uid)
    if not data.get("cards"):
        await query.message.reply_text(
            "❌ لا توجد بطاقات. أرسل ملف `.txt` أولاً.",
            parse_mode="Markdown",
        )
        return
    if not data.get("target"):
        await query.message.reply_text("❌ لم يتم تحديد البوت الهدف. استخدم 'مهمة جديدة'.")
        return
    if not data.get("check_command"):
        await query.message.reply_text("❌ لم يتم تحديد أمر الفحص. استخدم 'مهمة جديدة'.")
        return

    if uid in sending_tasks and not sending_tasks[uid].done():
        await query.message.reply_text("⚡ الإرسال جارٍ بالفعل!")
        return

    task = asyncio.create_task(_send_cards(uid, ctx.bot, chat_id))
    sending_tasks[uid] = task


async def cb_stop_sending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = update.effective_user.id

    task = sending_tasks.get(uid)
    if task and not task.done():
        task.cancel()
        # رسالة الإيقاف تُرسَل من داخل _send_cards
    else:
        await query.message.reply_text(
            "ℹ️ لا يوجد إرسال جارٍ حالياً.",
            reply_markup=main_menu_keyboard(),
        )


async def cb_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = update.effective_user.id
    data  = load_data(uid)

    if not data:
        await query.message.reply_text("❌ لا توجد بيانات. أرسل /start أولاً.")
        return

    total   = len(data.get("cards", []))
    sent    = data.get("sent", 0)
    remain  = total - sent
    running = uid in sending_tasks and not sending_tasks[uid].done()
    pct     = round(sent / total * 100, 1) if total else 0
    filled  = int(10 * sent / total) if total else 0
    bar     = "█" * filled + "░" * (10 - filled)
    status  = "🟢 يعمل" if running else "🔴 متوقف"

    text = (
        f"📊 *حالة المهمة*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 الحساب: `{data.get('name', '—')}`\n"
        f"🎯 البوت الهدف: `{data.get('target', 'غير محدد')}`\n"
        f"✉️ أمر الفحص: `{data.get('check_command', 'غير محدد')}`\n"
        f"⏱ التأخير: `{data.get('delay_lo', '—')}–{data.get('delay_hi', '—')}` ثانية\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🃏 الإجمالي: *{total}*\n"
        f"✅ المُرسَل: *{sent}*\n"
        f"⏳ المتبقي: *{remain}*\n"
        f"📈 `[{bar}]` {pct}%\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"الحالة: {status}"
    )
    await query.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def cb_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = update.effective_user.id

    task = sending_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()

    try:
        client = await get_client(uid)
        await client.log_out()
    except Exception:
        pass
    await disconnect_client(uid)

    p = user_file(uid)
    if p.exists():
        p.unlink()

    await query.message.reply_text(
        "👋 *تم تسجيل الخروج بنجاح.*\n\n"
        "تم حذف الجلسة وجميع البيانات.\n"
        "أرسل /start للبدء من جديد.",
        parse_mode="Markdown",
    )

# ══════════════════════════════════════════════════════════
# /reset
# ══════════════════════════════════════════════════════════

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    task = sending_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()
    await disconnect_client(uid)
    p = user_file(uid)
    if p.exists():
        p.unlink()
    ctx.user_data.clear()
    await update.message.reply_text(
        "🗑 تم مسح جميع بياناتك.\n\nأرسل /start للبدء من جديد."
    )
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
# ConversationHandlers
# ══════════════════════════════════════════════════════════

login_conv = ConversationHandler(
    entry_points=[CommandHandler("start", cmd_start)],
    states={
        WAIT_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_phone)],
        WAIT_CODE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_code)],
        WAIT_2FA:     [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_2fa)],
        WAIT_FILE:    [MessageHandler(filters.Document.ALL, wait_file)],
        WAIT_TARGET:  [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_target)],
        WAIT_DELAY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_delay)],
        WAIT_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_command)],
    },
    fallbacks=[CommandHandler("reset", cmd_reset)],
    per_message=False,
    allow_reentry=True,
)

task_setup_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_file, pattern="^reset_task$")],
    states={
        WAIT_FILE:    [MessageHandler(filters.Document.ALL, wait_file)],
        WAIT_TARGET:  [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_target)],
        WAIT_DELAY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_delay)],
        WAIT_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_command)],
    },
    fallbacks=[CommandHandler("reset", cmd_reset)],
    per_message=False,
    allow_reentry=True,
)

# ══════════════════════════════════════════════════════════
# ★ التعديل الثاني: main() المحسّنة مع جميع المعالجات
# ══════════════════════════════════════════════════════════

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # ── group=0 : ConversationHandlers (أعلى أولوية) ─────
    app.add_handler(login_conv,      group=0)
    app.add_handler(task_setup_conv, group=0)

    # ── group=1 : أوامر نصية ─────────────────────────────
    app.add_handler(CommandHandler("reset", cmd_reset), group=1)

    # ── group=2 : أزرار Inline ───────────────────────────
    app.add_handler(CallbackQueryHandler(cb_status,        pattern="^status$"),        group=2)
    app.add_handler(CallbackQueryHandler(cb_start_sending, pattern="^start_sending$"), group=2)
    app.add_handler(CallbackQueryHandler(cb_stop_sending,  pattern="^stop_sending$"),  group=2)
    app.add_handler(CallbackQueryHandler(cb_logout,        pattern="^logout$"),        group=2)

    # ── group=3 : ★ معالج الملفات في أي وقت ──────────────
    # يعمل حتى خارج أي محادثة – يأتي بعد ConversationHandlers
    # لكن إذا كان المستخدم داخل محادثة، سيتولى ConversationHandler الأمر (group=0)
    app.add_handler(
        MessageHandler(filters.Document.ALL, handle_file_anytime),
        group=3,
    )

    # ── group=3 : ★ معالج النصوص خارج المحادثة ───────────
    # لاستكمال الإعداد بعد رفع الملف عبر handle_file_anytime
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_anytime),
        group=3,
    )

    logger.info("=" * 55)
    logger.info("  ✅  Card Checker Bot v2.0 started successfully!")
    logger.info("=" * 55)

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
