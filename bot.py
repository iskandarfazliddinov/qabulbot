"""
Telegram-bot ro'yxatga olish: Bo'stonliq, Parkent va boshqa tumanlar uchun yangi oqim.
Запуск:  start.bat  (или BOT_TOKEN=... ADMIN_IDS=... python bot.py)
"""
import asyncio
import logging
import os
import re
import sqlite3
import time
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ---------------------------------------------------------------- sozlamalar
# config.txt faylidan o'qish (BOT_TOKEN=..., ADMIN_IDS=..., OQIM=...)
_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt")
if os.path.exists(_cfg):
    for _line in open(_cfg, encoding="utf-8-sig"):
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN or "VSTAVTE" in BOT_TOKEN:
    raise SystemExit("XATO: config.txt faylida BOT_TOKEN kiritilmagan!")
_ADMIN_LIST = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
ADMIN_IDS = set(_ADMIN_LIST)
DB_PATH = os.environ.get("DB_PATH", "oqim.db")
OQIM = os.environ.get("OQIM", "III oqim")          # joriy oqim nomi

DISTRICTS = {
    "bostonliq": {"name": "Bo'stonliq", "start": "10-noyabr 2026", "venue": "Wyndham / Zafaron Premium"},
    "parkent":   {"name": "Parkent",    "start": "17-noyabr 2026", "venue": "Kumushkon Resort"},
    "other":     {"name": "Boshqa tuman", "start": "", "venue": ""},
}
DIRECTIONS = {
    "fo": "Mehmonxona qabulxonasi (Front Office)",
    "hk": "Housekeeping",
    "fb": "Umumiy ovqatlantirish xizmatlarini tashkil qilish",
}
EDUCATION = {
    "9":      "9-sinf",
    "11":     "11-sinf (o'rta)",
    "kollej": "O'rta maxsus (kollej/litsey)",
    "oliy":   "Oliy",
    "talaba": "Hozirda talaba",
}
SHIFTS = {
    "am": "Tushgacha (1-smena)",
    "pm": "Tushdan keyin (2-smena)",
}

def welcome_text() -> str:
  return (
    "<b>Hurmatli fuqaro!</b>\n\n"
    "O'zbekiston Respublikasi Turizm qo'mitasi tashabbusi bilan Toshkent viloyatining "
    "Bo'stonliq va Parkent tumanlarida mehmonxona va umumiy ovqatlantirish sohasi bo'yicha "
    "<b>BEPUL</b> qisqa muddatli malaka oshirish va qayta tayyorlash kurslari tashkil etilmoqda.\n\n"
    "Kurslarni turizm sohasida kadrlar malakasini oshirish va qayta tayyorlash bo'yicha "
    "<b>yagona akkreditatsiyadan o'tgan muassasa</b> — «Ipak yo'li» turizm va madaniy meros "
    "xalqaro universiteti huzuridagi <b>Xalqaro turizm akademiyasi</b> o'tkazadi. "
    "Kursni muvaffaqiyatli tamomlagan tinglovchilarga sertifikat beriladi.\n\n"
    "<b>Ishtirok etish shartlari:</b>\n"
    "1. Kamida 9-sinfni tamomlagan bo'lish — <b>majburiy</b>.\n"
    "2. Chet tillarini (rus, ingliz) bilish ma'qul ko'riladi.\n"
    "3. Ro'yxatdan o'tgan tinglovchi barcha mashg'ulotlarga <b>qatnashishi shart</b>.\n"
    "4. Pasport ma'lumotlari to'g'ri va to'liq kiritilishi lozim.\n\n"
    f"Joriy oqim: <b>{OQIM}</b>.\nRo'yxatdan o'tish uchun «Boshlash» tugmasini bosing."
  )

def closed_text() -> str:
    return (
        "<b>Hurmatli fuqaro!</b>\n\n"
        f"<b>{OQIM}</b>ga ro'yxatdan o'tish <b>hali boshlanmadi</b>.\n\n"
        "Ro'yxatdan o'tish ochilishi bilan sizga shu bot orqali xabar yuboramiz — "
        "botni o'chirmang va bloklamang.\n\n"
        "Kurslar O'zbekiston Respublikasi Turizm qo'mitasi tashabbusi bilan Xalqaro turizm "
        "akademiyasi tomonidan Bo'stonliq va Parkent tumanlarida bepul o'tkaziladi."
    )

def cap(s: str) -> str:
    """Har bir so'zning bosh harfi katta (apostrof buzilmaydi): o'rtaboyev -> O'rtaboyev"""
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split())

PHONE_RE = re.compile(r"^\+?998\d{9}$")
PASSPORT_RE = re.compile(r"^[A-Z]{2}\d{7}$")

logging.basicConfig(level=logging.INFO)
router = Router()

# ---------------------------------------------------------------- ma'lumotlar bazasi
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS reg (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, tg_id INTEGER, tg_username TEXT,
            oqim TEXT, district TEXT, district_name TEXT, direction TEXT,
            fio TEXT, birth TEXT, passport TEXT, education TEXT,
            phone TEXT, phone2 TEXT, shift TEXT, address TEXT, note TEXT)""")
        con.execute("CREATE INDEX IF NOT EXISTS ix_pass ON reg(passport, oqim)")
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            first_seen TEXT, last_seen TEXT, blocked INTEGER DEFAULT 0)""")
        # eski yozuvlardagi foydalanuvchilarni ham users jadvaliga qo'shamiz
        con.execute("""INSERT OR IGNORE INTO users (tg_id, username, first_seen, last_seen)
                       SELECT tg_id, tg_username, MIN(created_at), MAX(created_at) FROM reg GROUP BY tg_id""")

        con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    load_settings()

REG_OPEN = True

def get_setting(key, default=None):
    with db() as con:
        r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default

def set_setting(key, value):
    with db() as con:
        con.execute("INSERT INTO settings (key,value) VALUES (?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

def load_settings():
    """Bazadagi sozlamalar (oqim nomi, ro'yxat ochiq/yopiq) config.txt dan ustun turadi."""
    global OQIM, REG_OPEN
    OQIM = get_setting("oqim", OQIM)
    REG_OPEN = get_setting("reg_open", "1") == "1"

def touch_user(user):
    """Har bir /start bosgan odamni eslab qolamiz — keyin xabar yuborish uchun."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with db() as con:
        con.execute("""INSERT INTO users (tg_id, username, first_name, first_seen, last_seen, blocked)
                       VALUES (?,?,?,?,?,0)
                       ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username,
                       first_name=excluded.first_name, last_seen=excluded.last_seen, blocked=0""",
                    (user.id, user.username, user.first_name, now, now))

def audience(key: str):
    """key: all | bostonliq | parkent | other  ->  tg_id ro'yxati"""
    with db() as con:
        if key == "all":
            rows = con.execute("SELECT tg_id FROM users WHERE blocked=0").fetchall()
        else:
            rows = con.execute("""SELECT DISTINCT r.tg_id FROM reg r
                                  LEFT JOIN users u ON u.tg_id=r.tg_id
                                  WHERE r.district=? AND COALESCE(u.blocked,0)=0""", (key,)).fetchall()
    return [r[0] for r in rows]

def mark_blocked(tg_id: int):
    with db() as con:
        con.execute("UPDATE users SET blocked=1 WHERE tg_id=?", (tg_id,))

def save(data: dict, user) -> int:
    with db() as con:
        cur = con.execute(
            """INSERT INTO reg (created_at,tg_id,tg_username,oqim,district,district_name,direction,
               fio,birth,passport,education,phone,phone2,shift,address,note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), user.id, user.username, OQIM,
             data["district"], data["district_name"], data["direction"], data["fio"], data["birth"],
             data["passport"], data["education"], data["phone"], data.get("phone2", ""),
             data["shift"], data["address"], ""))
        return cur.lastrowid

def passport_exists(passport: str) -> bool:
    with db() as con:
        return con.execute("SELECT 1 FROM reg WHERE passport=? AND oqim=?",
                           (passport, OQIM)).fetchone() is not None

# ---------------------------------------------------------------- zaxira nusxa (Telegram orqali)
# Har bir yangi yozuvdan keyin bot bazani admin chatiga yuboradi va "pin" qiladi.
# Server o'chib qolsa, ishga tushganda bot shu pin qilingan fayldan bazani tiklaydi.
BACKUP_CHAT = _ADMIN_LIST[0] if _ADMIN_LIST else None   # birinchi admin — zaxira chati
_dirty = {"since": 0.0}
_last_pin = {"msg_id": None}

def row_count() -> int:
    with db() as con:
        return con.execute("SELECT COUNT(*) FROM reg").fetchone()[0]

async def send_backup(bot: Bot, force: bool = False):
    if not BACKUP_CHAT or not os.path.exists(DB_PATH):
        return
    if not force and not _dirty["since"]:
        return
    try:
        msg = await bot.send_document(
            BACKUP_CHAT, FSInputFile(DB_PATH, filename="oqim.db"),
            caption=f"💾 Zaxira nusxa — {row_count()} ta yozuv, {datetime.now():%d.%m.%Y %H:%M}\n"
                    f"(bu xabarni o'chirmang, bot tiklash uchun ishlatadi)",
            disable_notification=True)
        try:
            if _last_pin["msg_id"]:
                await bot.unpin_chat_message(BACKUP_CHAT, _last_pin["msg_id"])
            await bot.pin_chat_message(BACKUP_CHAT, msg.message_id, disable_notification=True)
            _last_pin["msg_id"] = msg.message_id
        except Exception as e:
            logging.warning("pin failed: %s", e)
        _dirty["since"] = 0.0
    except Exception as e:
        logging.warning("backup failed: %s", e)

async def backup_loop(bot: Bot):
    """Yangi yozuvdan 2 daqiqa o'tgach (bir nechta ro'yxatni birlashtirib) zaxira yuboradi."""
    while True:
        await asyncio.sleep(30)
        if _dirty["since"] and time.time() - _dirty["since"] > 120:
            await send_backup(bot)

async def restore_from_telegram(bot: Bot):
    """Baza bo'sh bo'lsa — admin chatidagi pin qilingan oqim.db faylini yuklab oladi."""
    if not BACKUP_CHAT:
        return
    if os.path.exists(DB_PATH) and row_count() > 0:
        return
    try:
        chat = await bot.get_chat(BACKUP_CHAT)
        pm = chat.pinned_message
        if pm and pm.document and pm.document.file_name == "oqim.db":
            await bot.download(pm.document, destination=DB_PATH)
            _last_pin["msg_id"] = pm.message_id
            logging.info("Baza Telegramdan tiklandi: %s ta yozuv", row_count())
            await bot.send_message(BACKUP_CHAT, f"♻️ Bot qayta ishga tushdi, baza tiklandi: {row_count()} ta yozuv.")
    except Exception as e:
        logging.warning("restore failed: %s", e)

# ---------------------------------------------------------------- holatlar (FSM)
class Reg(StatesGroup):
    welcome = State()
    district = State()
    district_other = State()
    direction = State()
    fio = State()
    birth = State()
    passport = State()
    education = State()
    phone = State()
    phone2 = State()
    shift = State()
    address = State()
    confirm = State()

def ikb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows])

def district_kb():
    return ikb([[(f"📍 {d['name']}", f"dist:{k}")] for k, d in DISTRICTS.items()])

def direction_kb():
    return ikb([[(v, f"dir:{k}")] for k, v in DIRECTIONS.items()])

def education_kb():
    return ikb([[(v, f"edu:{k}")] for k, v in EDUCATION.items()])

def shift_kb():
    return ikb([[(v, f"shift:{k}")] for k, v in SHIFTS.items()])

def phone_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)]])

def summary(d: dict) -> str:
    return (f"<b>Ma'lumotlaringizni tekshiring:</b>\n\n"
            f"Oqim: {OQIM}\n"
            f"Tuman: {d['district_name']}\n"
            f"Yo'nalish: {DIRECTIONS[d['direction']]}\n"
            f"F.I.O.: {d['fio']}\n"
            f"Tug'ilgan sana: {d['birth']}\n"
            f"Pasport: {d['passport']}\n"
            f"Ma'lumoti: {EDUCATION[d['education']]}\n"
            f"Telefon: {d['phone']}\n"
            f"Qo'shimcha telefon: {d.get('phone2') or '—'}\n"
            f"Smena: {SHIFTS[d['shift']]}\n"
            f"Manzil: {d['address']}")

# ---------------------------------------------------------------- foydalanuvchi oqimi
@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    touch_user(m.from_user)
    _dirty["since"] = _dirty["since"] or time.time()
    if not REG_OPEN:
        return await m.answer(closed_text())
    await m.answer(welcome_text(), reply_markup=ikb([[("▶️ Boshlash", "go")]]))
    await state.set_state(Reg.welcome)

@router.message(Command("cancel"))
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Bekor qilindi. Qaytadan boshlash uchun /start", reply_markup=ReplyKeyboardRemove())

@router.callback_query(Reg.welcome, F.data == "go")
async def go(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Qaysi tumanda o'qiysiz?", reply_markup=district_kb())
    await state.set_state(Reg.district)
    await c.answer()

@router.callback_query(Reg.district, F.data.startswith("dist:"))
async def pick_district(c: CallbackQuery, state: FSMContext):
    key = c.data.split(":")[1]
    await state.update_data(district=key)
    if key == "other":
        await c.message.edit_text("Tumaningiz nomini yozing:\n<i>Masalan: Yangiyo'l</i>")
        await state.set_state(Reg.district_other)
    else:
        await state.update_data(district_name=DISTRICTS[key]["name"])
        await c.message.edit_text(f"Tuman: <b>{DISTRICTS[key]['name']}</b>")
        await c.message.answer("Yo'nalishni tanlang:", reply_markup=direction_kb())
        await state.set_state(Reg.direction)
    await c.answer()

@router.message(Reg.district_other, F.text)
async def district_other(m: Message, state: FSMContext):
    name = " ".join(m.text.split()).strip()
    if len(name) < 3:
        return await m.answer("Tuman nomini to'liq yozing.")
    await state.update_data(district_name=cap(name))
    await m.answer("Yo'nalishni tanlang:", reply_markup=direction_kb())
    await state.set_state(Reg.direction)

@router.callback_query(Reg.direction, F.data.startswith("dir:"))
async def pick_direction(c: CallbackQuery, state: FSMContext):
    key = c.data.split(":")[1]
    await state.update_data(direction=key)
    await c.message.edit_text(f"Yo'nalish: <b>{DIRECTIONS[key]}</b>")
    await c.message.answer("Familiya, ism, otasining ismini kiriting (pasportdagidek):\n"
                           "<i>Masalan: Karimov Aziz Baxtiyorovich</i>")
    await state.set_state(Reg.fio)
    await c.answer()

@router.message(Reg.fio, F.text)
async def get_fio(m: Message, state: FSMContext):
    fio = " ".join(m.text.split())
    if len(fio.split()) < 2 or any(ch.isdigit() for ch in fio):
        return await m.answer("Iltimos, to'liq F.I.O. ni harflar bilan kiriting.")
    await state.update_data(fio=cap(fio))
    await m.answer("Tug'ilgan sanangiz (KK.OO.YYYY):\n<i>Masalan: 15.03.1998</i>")
    await state.set_state(Reg.birth)

@router.message(Reg.birth, F.text)
async def get_birth(m: Message, state: FSMContext):
    try:
        d = datetime.strptime(m.text.strip(), "%d.%m.%Y")
        assert 1940 <= d.year <= 2011
    except Exception:
        return await m.answer("Sana noto'g'ri. Format: KK.OO.YYYY, masalan 15.03.1998")
    await state.update_data(birth=d.strftime("%d.%m.%Y"))
    await m.answer("Pasport seriya va raqami (AA1234567):")
    await state.set_state(Reg.passport)

@router.message(Reg.passport, F.text)
async def get_passport(m: Message, state: FSMContext):
    p = m.text.replace(" ", "").upper()
    if not PASSPORT_RE.match(p):
        return await m.answer("Format: 2 ta harf + 7 ta raqam, masalan AA1234567")
    if passport_exists(p):
        return await m.answer("Bu pasport bilan ushbu oqimga allaqachon ro'yxatdan o'tilgan. "
                              "Xato bo'lsa, administratorga murojaat qiling.")
    await state.update_data(passport=p)
    await m.answer("Ma'lumotingiz:", reply_markup=education_kb())
    await state.set_state(Reg.education)

@router.callback_query(Reg.education, F.data.startswith("edu:"))
async def get_education(c: CallbackQuery, state: FSMContext):
    edu = c.data.split(":")[1]
    await state.update_data(education=edu)
    await c.message.edit_text(f"Ma'lumoti: <b>{EDUCATION[edu]}</b>")
    await c.message.answer("Telefon raqamingizni yuboring — pastdagi tugmani bosing 👇",
                           reply_markup=phone_kb())
    await state.set_state(Reg.phone)
    await c.answer()

@router.message(Reg.phone, F.contact)
async def get_phone_contact(m: Message, state: FSMContext):
    if m.contact.user_id != m.from_user.id:
        return await m.answer("Iltimos, o'zingizning raqamingizni tugma orqali yuboring.")
    p = re.sub(r"[^\d]", "", m.contact.phone_number)
    await state.update_data(phone="+" + p)
    await m.answer("Qo'shimcha telefon raqami (+998XXXXXXXXX). Bo'lmasa «yo'q» deb yozing:",
                   reply_markup=ReplyKeyboardRemove())
    await state.set_state(Reg.phone2)

@router.message(Reg.phone)
async def get_phone_other(m: Message):
    await m.answer("Raqamni qo'lda yozish mumkin emas — pastdagi "
                   "«📱 Telefon raqamimni yuborish» tugmasini bosing.", reply_markup=phone_kb())

@router.message(Reg.phone2, F.text)
async def get_phone2(m: Message, state: FSMContext):
    t = m.text.strip().lower()
    if t in ("yo'q", "yoq", "нет", "-", "—"):
        await state.update_data(phone2="")
    else:
        p = re.sub(r"[^\d]", "", t)
        if len(p) == 9:
            p = "998" + p
        if not PHONE_RE.match(p):
            return await m.answer("Raqam noto'g'ri. Format: +998901234567 yoki «yo'q»")
        await state.update_data(phone2="+" + p)
    await m.answer("Qaysi smenada o'qish siz uchun qulay?", reply_markup=shift_kb())
    await state.set_state(Reg.shift)

@router.callback_query(Reg.shift, F.data.startswith("shift:"))
async def get_shift(c: CallbackQuery, state: FSMContext):
    key = c.data.split(":")[1]
    await state.update_data(shift=key)
    await c.message.edit_text(f"Smena: <b>{SHIFTS[key]}</b>")
    await c.message.answer("Yashash manzilingiz (tuman, mahalla, ko'cha):")
    await state.set_state(Reg.address)
    await c.answer()

@router.message(Reg.address, F.text)
async def get_address(m: Message, state: FSMContext):
    await state.update_data(address=" ".join(m.text.split()))
    data = await state.get_data()
    await m.answer(summary(data), reply_markup=ikb([[("✅ Tasdiqlash", "ok"), ("🔄 Qaytadan", "redo")]]))
    await state.set_state(Reg.confirm)

@router.callback_query(Reg.confirm, F.data == "ok")
async def confirm(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    rid = save(data, c.from_user)
    _dirty["since"] = _dirty["since"] or time.time()
    await state.clear()
    dist = DISTRICTS[data["district"]]
    when = f"Boshlanish: {dist['start']}, {dist['venue']}\n\n" if dist["start"] else "\n"
    await c.message.edit_text(
        f"✅ Ro'yxatga olindingiz! Raqamingiz: <b>#{rid}</b>\n\n"
        f"Tuman: {data['district_name']}\nYo'nalish: {DIRECTIONS[data['direction']]}\n"
        f"Smena: {SHIFTS[data['shift']]}\n{when}"
        f"Mashg'ulot jadvali haqida Telegram orqali xabar beramiz. "
        f"Eslatma: mashg'ulotlarga qatnashish majburiy.")
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, f"🆕 #{rid} {data['district_name']} / {DIRECTIONS[data['direction']]}\n"
                                          f"{data['fio']}, {data['phone']}, {SHIFTS[data['shift']]}")
        except Exception:
            pass
    await c.answer()

@router.callback_query(Reg.confirm, F.data == "redo")
async def redo(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("Qaytadan boshlaymiz. Qaysi tumanda o'qiysiz?", reply_markup=district_kb())
    await state.set_state(Reg.district)
    await c.answer()

# ---------------------------------------------------------------- admin
def is_admin(m: Message) -> bool:
    return m.from_user.id in ADMIN_IDS

@router.message(Command("stats"))
async def stats(m: Message):
    if not is_admin(m):
        return
    with db() as con:
        rows = con.execute("SELECT district, direction, shift, COUNT(*) n FROM reg WHERE oqim=? "
                           "GROUP BY district, direction, shift", (OQIM,)).fetchall()
    out = [f"<b>{OQIM} — statistika</b>"]
    for dk, d in DISTRICTS.items():
        sub = [r for r in rows if r["district"] == dk]
        if not sub:
            continue
        out.append(f"\n📍 <b>{d['name']}</b>: {sum(r['n'] for r in sub)}")
        for dirk, dirn in DIRECTIONS.items():
            am = sum(r["n"] for r in sub if r["direction"] == dirk and r["shift"] == "am")
            pm = sum(r["n"] for r in sub if r["direction"] == dirk and r["shift"] == "pm")
            if am + pm:
                out.append(f"   • {dirn}: {am + pm} (tushgacha {am} / tushdan keyin {pm})")
    await m.answer("\n".join(out))

@router.message(Command("backup"))
async def backup_cmd(m: Message, bot: Bot):
    if not is_admin(m):
        return
    await send_backup(bot, force=True)
    await m.answer("Zaxira nusxa yuborildi va pin qilindi.")

# ---------------------------------------------------------------- xabar tarqatish (/send)
STARTED_AT = datetime.now()
AUD_NAMES = {"all": "Hammaga (barcha obunachilar)", "bostonliq": "Faqat Bo'stonliq",
             "parkent": "Faqat Parkent", "other": "Faqat boshqa tumanlar"}

class Bc(StatesGroup):
    audience = State()
    content = State()
    confirm = State()

@router.message(Command("send"))
async def send_start(m: Message, state: FSMContext):
    if not is_admin(m):
        return
    await state.clear()
    rows = [[(f"{v} — {len(audience(k))} kishi", f"aud:{k}")] for k, v in AUD_NAMES.items()]
    rows.append([("❌ Bekor qilish", "aud:cancel")])
    await m.answer("<b>Xabar tarqatish.</b> Kimga yuboramiz?", reply_markup=ikb(rows))
    await state.set_state(Bc.audience)

@router.callback_query(Bc.audience, F.data.startswith("aud:"))
async def send_pick_audience(c: CallbackQuery, state: FSMContext):
    key = c.data.split(":")[1]
    if key == "cancel":
        await state.clear()
        await c.message.edit_text("Bekor qilindi.")
        return await c.answer()
    await state.update_data(aud=key)
    await c.message.edit_text(
        f"Auditoriya: <b>{AUD_NAMES[key]}</b> ({len(audience(key))} kishi)\n\n"
        f"Endi yuboriladigan xabarni shu yerga yozing yoki yuboring.\n"
        f"Matn, rasm, hujjat, video — hammasi bo'ladi. Xabar aynan shu ko'rinishda ketadi.\n"
        f"Bekor qilish: /cancel")
    await state.set_state(Bc.content)
    await c.answer()

@router.message(Bc.content, ~F.text.startswith("/"))
async def send_got_content(m: Message, state: FSMContext):
    await state.update_data(src_chat=m.chat.id, src_msg=m.message_id)
    data = await state.get_data()
    n = len(audience(data["aud"]))
    await m.answer(f"👆 Yuqoridagi xabar <b>{n} kishiga</b> yuboriladi ({AUD_NAMES[data['aud']]}).\n"
                   f"Tasdiqlaysizmi?",
                   reply_markup=ikb([[("✅ Ha, yuborish", "bc:go"), ("❌ Yo'q", "bc:no")]]))
    await state.set_state(Bc.confirm)

@router.callback_query(Bc.confirm, F.data.startswith("bc:"))
async def send_confirm(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    if c.data == "bc:no":
        await c.message.edit_text("Bekor qilindi.")
        return await c.answer()
    ids = audience(data["aud"])
    await c.message.edit_text(f"⏳ Yuborilmoqda... 0 / {len(ids)}")
    asyncio.create_task(broadcast(bot, ids, data["src_chat"], data["src_msg"], c.message))
    await c.answer()

async def broadcast(bot: Bot, ids: list, src_chat: int, src_msg: int, status_msg: Message):
    ok = blocked = failed = 0
    for i, uid in enumerate(ids, 1):
        try:
            await bot.copy_message(uid, src_chat, src_msg)
            ok += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.copy_message(uid, src_chat, src_msg); ok += 1
            except Exception:
                failed += 1
        except TelegramForbiddenError:
            blocked += 1; mark_blocked(uid)
        except TelegramBadRequest as e:
            if "chat not found" in str(e).lower() or "deactivated" in str(e).lower():
                blocked += 1; mark_blocked(uid)
            else:
                failed += 1
        except Exception as e:
            logging.warning("broadcast %s: %s", uid, e); failed += 1
        await asyncio.sleep(0.05)        # Telegram limiti: ~20-30 xabar/sek
        if i % 50 == 0:
            try:
                await status_msg.edit_text(f"⏳ Yuborilmoqda... {i} / {len(ids)}")
            except Exception:
                pass
    try:
        await status_msg.edit_text(
            f"✅ <b>Tarqatish tugadi</b>\n"
            f"Yetkazildi: {ok}\n"
            f"Botni bloklagan / o'chirgan: {blocked}\n"
            f"Xatolik: {failed}")
    except Exception:
        pass

@router.message(Command("close"))
async def reg_close(m: Message):
    if not is_admin(m):
        return
    global REG_OPEN
    REG_OPEN = False; set_setting("reg_open", "0")
    _dirty["since"] = _dirty["since"] or time.time()
    await m.answer(f"🔒 Ro'yxatdan o'tish <b>yopildi</b>. /start bosganlar endi shu xabarni ko'radi:\n\n" + closed_text())

@router.message(Command("open"))
async def reg_open(m: Message):
    if not is_admin(m):
        return
    global REG_OPEN
    REG_OPEN = True; set_setting("reg_open", "1")
    _dirty["since"] = _dirty["since"] or time.time()
    await m.answer(f"🔓 <b>{OQIM}</b>ga ro'yxatdan o'tish <b>ochildi</b>.\n"
                   f"Obunachilarga xabar berish uchun: /send")

@router.message(Command("oqim"))
async def set_oqim(m: Message):
    """ /oqim IV oqim  — joriy oqim nomini o'zgartiradi """
    if not is_admin(m):
        return
    global OQIM
    arg = (m.text.split(maxsplit=1) + [""])[1].strip()
    if not arg:
        return await m.answer(f"Joriy oqim: <b>{OQIM}</b>\nO'zgartirish: <code>/oqim IV oqim</code>")
    OQIM = arg; set_setting("oqim", arg)
    _dirty["since"] = _dirty["since"] or time.time()
    await m.answer(f"Joriy oqim endi: <b>{OQIM}</b>. Ro'yxat {'ochiq' if REG_OPEN else 'yopiq'}.")

@router.message(Command("status"))
async def status(m: Message):
    if not is_admin(m):
        return
    with db() as con:
        users = con.execute("SELECT COUNT(*) FROM users WHERE blocked=0").fetchone()[0]
        blocked = con.execute("SELECT COUNT(*) FROM users WHERE blocked=1").fetchone()[0]
        regs = con.execute("SELECT COUNT(*) FROM reg").fetchone()[0]
        regs_now = con.execute("SELECT COUNT(*) FROM reg WHERE oqim=?", (OQIM,)).fetchone()[0]
        last = con.execute("SELECT created_at, fio FROM reg ORDER BY id DESC LIMIT 1").fetchone()
    up = datetime.now() - STARTED_AT
    size = os.path.getsize(DB_PATH) // 1024 if os.path.exists(DB_PATH) else 0
    await m.answer(
        f"🟢 <b>Bot ishlayapti</b>\n"
        f"Joriy oqim: <b>{OQIM}</b> — ro'yxat {'🔓 OCHIQ' if REG_OPEN else '🔒 YOPIQ'}\n"
        f"Ishga tushgan: {STARTED_AT:%d.%m.%Y %H:%M} ({up.days} kun {up.seconds // 3600} soat oldin)\n\n"
        f"<b>Baza:</b> oqim.db, {size} KB\n"
        f"Obunachilar (xabar oladi): {users}\n"
        f"Botni bloklaganlar: {blocked}\n"
        f"Ro'yxatdan o'tganlar — jami: {regs}, {OQIM}: {regs_now}\n"
        f"Oxirgi yozuv: {last['created_at'] + ' — ' + last['fio'] if last else '—'}\n"
        f"Zaxira pin: {'bor' if _last_pin['msg_id'] else 'hali yuborilmagan'}")

@router.message(Command("export"))
async def export(m: Message):
    if not is_admin(m):
        return
    arg = (m.text.split(maxsplit=1) + [""])[1].strip().lower()
    keys = [arg] if arg in DISTRICTS else list(DISTRICTS)
    sent = False
    for k in keys:
        path = build_xlsx(k)
        if path:
            await m.answer_document(FSInputFile(path), caption=f"{OQIM} — {DISTRICTS[k]['name']}")
            sent = True
    if not sent:
        await m.answer("Hozircha yozuvlar yo'q.")

@router.message(F.document)
async def handle_db_upload(m: Message, bot: Bot):
    if not is_admin(m):
        return
    if m.document and m.document.file_name == "oqim.db":
        await bot.download(m.document, destination=DB_PATH)
        init_db()
        c = row_count()
        await send_backup(bot, force=True)
        await m.answer(
            f"✅ <b>Baza muvaffaqiyatli tiklandi!</b>\n\n"
            f"Jami yozuvlar: <b>{c} ta</b>.\n"
            f"Yangi zaxira nusxa yaratildi va chatga qistirildi (pin qilindi)."
        )

@router.message(Command("restore"))
async def cmd_restore(m: Message, bot: Bot):
    if not is_admin(m):
        return
    await m.answer("♻️ Telegramdan zaxira bazani tiklash boshlandi...")
    try:
        chat = await bot.get_chat(BACKUP_CHAT)
        pm = chat.pinned_message
        if pm and pm.document and pm.document.file_name == "oqim.db":
            await bot.download(pm.document, destination=DB_PATH)
            _last_pin["msg_id"] = pm.message_id
            init_db()
            c = row_count()
            await m.answer(f"✅ <b>Baza muvaffaqiyatli tiklandi!</b>\n\nJami yozuvlar: <b>{c} ta</b>.")
        else:
            await m.answer("❌ Pin qilingan oqim.db fayli topilmadi.")
    except Exception as e:
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

def build_xlsx(district_key: str):
    name = DISTRICTS[district_key]["name"]
    with db() as con:
        rows = con.execute("SELECT * FROM reg WHERE oqim=? AND district=? "
                           "ORDER BY direction, shift, fio", (OQIM, district_key)).fetchall()
    if not rows:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "Baza"
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    bold = Font(name="Times New Roman", bold=True, size=11)
    norm = Font(name="Times New Roman", size=11)
    head_fill = PatternFill("solid", fgColor="D9E1F2")

    headers = ["T/r", "F.I.O.", "Tuman", "Tug'ilgan sana", "Pasport", "Ma'lumoti", "Yo'nalish",
               "Smena", "Telefon", "Qo'shimcha telefon", "Manzil", "Ro'yxat sanasi", "Telegram"]
    last = chr(ord("A") + len(headers) - 1)
    ws.merge_cells(f"A1:{last}1")
    ws["A1"] = f"{OQIM} — {name} — ro'yxatga olingan tinglovchilar"
    ws["A1"].font = Font(name="Times New Roman", bold=True, size=13)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.merge_cells(f"A2:{last}2")
    ws["A2"] = f"Eksport: {datetime.now():%d.%m.%Y %H:%M}"
    ws["A2"].font = norm
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=col, value=h)
        c.font, c.fill, c.border = bold, head_fill, border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, r in enumerate(rows, 1):
        vals = [i, r["fio"], r["district_name"], r["birth"], r["passport"], EDUCATION[r["education"]],
                DIRECTIONS[r["direction"]], SHIFTS[r["shift"]], r["phone"], r["phone2"], r["address"],
                r["created_at"], f"@{r['tg_username']}" if r["tg_username"] else str(r["tg_id"])]
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=4 + i, column=col, value=v)
            c.font, c.border = norm, border
            c.alignment = Alignment(vertical="center", wrap_text=True)

    for col, w in zip("ABCDEFGHIJKLM", [5, 32, 14, 14, 12, 22, 34, 22, 16, 18, 34, 16, 16]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"
    path = f"{OQIM.replace(' ', '_')}_{name.replace(chr(39), '').replace(' ', '_')}.xlsx"
    wb.save(path)
    return path

# ---------------------------------------------------------------- veb health-check (Koyeb / Render uchun)
async def _health_check(request):
    try:
        c = row_count()
    except Exception:
        c = "err"
    return web.Response(text=f"Bot is running! Rows: {c}")

async def start_health_server():
    try:
        port = int(os.environ.get("PORT", "8000"))
        app = web.Application()
        app.router.add_get("/", _health_check)
        app.router.add_get("/health", _health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logging.info("Health server running on port %s", port)
    except Exception as e:
        logging.warning("Health server start failed: %s", e)

# ---------------------------------------------------------------- ishga tushirish
async def main():
    init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    await restore_from_telegram(bot)
    asyncio.create_task(backup_loop(bot))
    asyncio.create_task(start_health_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
