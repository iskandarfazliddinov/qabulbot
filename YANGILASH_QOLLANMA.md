# @qabulakadembot — yangi versiyani serverga o'rnatish bo'yicha qo'llanma

Bu qo'llanma botni serverda yangilash uchun. Botning yangi versiyasida ikkita
yangi buyruq qo'shildi: **/send** (barcha obunachilarga xabar tarqatish) va
**/status** (bot ishlayaptimi, bazada nechta yozuv bor).

---

## 0. Arxivda nima bor

`qabulbot.zip` ichida `oqim_bot` papkasi, unda 9 ta fayl:

| Fayl | Nima uchun | Serverga yuklash kerakmi? |
|---|---|---|
| `bot.py` | **Botning asosiy kodi** — o'zgargan | **HA, majburiy** |
| `README.md` | Qo'llanma (ruscha) | ixtiyoriy |
| `YANGILASH_QOLLANMA.md` | Shu qo'llanma | ixtiyoriy |
| `requirements.txt` | Kutubxonalar ro'yxati (aiogram, openpyxl) | o'zgarmagan, agar serverda bo'lsa — kerak emas |
| `Dockerfile`, `Procfile`, `.python-version` | Server sozlamalari | o'zgarmagan |
| `start.bat` | Faqat Windows kompyuterda ishga tushirish uchun | serverga kerak emas |
| `config.txt` | Token va admin ID | **YO'Q! Serverdagi eskisini qoldiring** (pastga qarang) |

> ⚠️ **Eng muhimi:** arxivdagi `config.txt` bo'sh shablon. Serverdagi `config.txt`
> ichida haqiqiy token bor. Agar uni arxivdagisi bilan almashtirsangiz — bot ishlamay
> qoladi. Shuning uchun `config.txt` ni **umuman tegmang**.
>
> Agar token `config.txt` da emas, server panelidagi *Variables / Environment*
> bo'limida yozilgan bo'lsa — unda `config.txt` haqida o'ylamasangiz ham bo'ladi.

---

## 1. Yangilash tartibi (qadam-baqadam)

### 1-qadam. Hozirgi bazadan zaxira nusxa oling
Hech narsa qilishdan oldin Telegramda botga admin akkauntidan `/backup` deb yozing.
Bot `oqim.db` faylini yuboradi va chatda pin qiladi. Bot javob bermasa — demak u
to'xtab qolgan, 2-qadamga o'ting (baza chatdagi oldingi pin qilingan xabarda saqlanib
qolgan).

### 2-qadam. Arxivni oching
`qabulbot.zip` ni kompyuterda oching (o'ng tugma → Extract / Chiqarish). `oqim_bot`
papkasi paydo bo'ladi.

### 3-qadam. Serverga kiring
Bot turgan server paneliga (Railway / Render / Koyeb / PythonAnywhere / VPS — qaysi
bo'lsa) kiring va bot fayllari turgan joyni oching.

### 4-qadam. `bot.py` ni almashtiring
Serverdagi eski `bot.py` o'rniga arxivdagi yangi `bot.py` ni yuklang (ustidan yozing).

- **Panel orqali fayl yuklash bo'lsa** (PythonAnywhere, Beget va h.k.): Upload →
  `bot.py` tanlang → eskisini almashtirishga rozilik bering.
- **VPS (SSH) bo'lsa:** `scp bot.py user@server:/path/to/oqim_bot/bot.py`
- **GitHub orqali deploy bo'lsa** (Railway, Render, Koyeb): repozitoriyadagi `bot.py`
  ni yangisi bilan almashtiring → commit → push. Server o'zi qayta deploy qiladi.

`README.md` va `YANGILASH_QOLLANMA.md` ni ham yuklasangiz bo'ladi — ular ishga ta'sir
qilmaydi, faqat qo'llanma.

### 5-qadam. `config.txt` joyida va to'g'ri ekanini tekshiring
Serverdagi `config.txt` ni oching. Ichida uch qator bo'lishi kerak:
```
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=205409821
OQIM=III oqim
```
`=` dan keyin haqiqiy token va ID turgan bo'lsa — yaxshi. Agar `VSTAVTE_...` degan
yozuv turgan bo'lsa — demak faylni adashib almashtirib yuborgansiz; tokenni
@BotFather dan (`/mytoken`), ID ni @userinfobot dan olib qayta yozing.

### 6-qadam. Botni qayta ishga tushiring
Server panelida **Restart** / **Redeploy** / **Reload** tugmasini bosing.
VPS da: `systemctl restart <servis nomi>` yoki jarayonni o'ldirib `python bot.py`
ni qayta ishga tushiring.

### 7-qadam. Tekshiring
Telegramda botga admin akkauntidan `/status` deb yozing. Shunday javob kelishi kerak:
```
🟢 Bot ishlayapti
Ishga tushgan: ...
Baza: oqim.db, NN KB
Obunachilar (xabar oladi): NNN
Ro'yxatdan o'tganlar — jami: NNN
...
```
- Javob keldi → **hammasi tayyor.**
- Javob kelmadi → server logini oching (Logs bo'limi) va oxirgi qatorlardagi xatoni
  o'qing. Eng ko'p uchraydiganlari pastda.

Agar bot qayta ishga tushganda baza bo'sh bo'lsa, u avtomatik ravishda admin chatidagi
pin qilingan `oqim.db` faylini yuklab oladi va «♻️ Bot qayta ishga tushdi, baza
tiklandi: N ta yozuv» deb yozadi. Bu normal holat.

---

## 2. Tez-tez uchraydigan xatolar (logda)

| Logdagi xato | Sababi | Yechim |
|---|---|---|
| `XATO: config.txt faylida BOT_TOKEN kiritilmagan` | Token yo'q yoki config.txt almashib ketgan | 5-qadam |
| `TelegramConflictError` / `Conflict: terminated by other getUpdates request` | Bot **ikki joyda** bir vaqtda ishlayapti (masalan, serverda va kimningdir kompyuterida) | Faqat bitta nusxani qoldiring, qolganini to'xtating |
| `ModuleNotFoundError: No module named 'aiogram'` | Kutubxonalar o'rnatilmagan | `pip install -r requirements.txt` |
| `Unauthorized` | Token noto'g'ri | @BotFather → `/mytoken` → qayta yozing |
| Log tinch, xato yo'q, lekin bot javob bermaydi | Bepul server botni "uxlatib" qo'ygan | Restart bosing; agar servis turi **web** bo'lsa, uni **worker / background** ga o'zgartiring — botga port kerak emas |

---

## 3. Server haqida muhim eslatma

- Bot **worker / background service** sifatida ishlashi kerak, **web service** emas.
  Web service bo'lsa, bepul tariflar 15 daqiqa so'rov bo'lmasa uni uxlatadi — bot
  "qotib qoladi".
- Bot **faqat bitta joyda** ishlashi kerak. Ikki nusxa = ikkalasi ham ishlamaydi.
- Bepul serverlarda disk qayta ishga tushganda tozalanadi. Shuning uchun bot bazani
  admin Telegram chatiga yuborib pin qiladi va ishga tushganda o'sha yerdan tiklaydi.
  **Admin chatidagi pin qilingan `oqim.db` xabarini o'chirmang.**

---

## 4. Admin buyruqlari (faqat `ADMIN_IDS` dagi odamlar uchun ishlaydi)

| Buyruq | Nima qiladi |
|---|---|
| `/status` | Bot ishlayaptimi, bazada nechta yozuv, nechta obunachi |
| `/stats` | Tumanlar, yo'nalishlar va smenalar bo'yicha hisob |
| `/export` | Har bir tuman bo'yicha Excel fayl |
| `/export parkent` | Faqat bitta tuman (`parkent`, `bostonliq`, `other`) |
| `/backup` | Bazani hoziroq yuborish va pin qilish |
| `/send` | Obunachilarga xabar tarqatish (pastga qarang) |
| `/close` | Ro'yxatdan o'tishni **yopish** — /start bosganlar «hali boshlanmadi» xabarini ko'radi |
| `/open` | Ro'yxatdan o'tishni **ochish** |
| `/oqim IV oqim` | Joriy oqim nomini o'zgartirish (`/oqim` — hozirgisini ko'rsatadi) |
| `/cancel` | Joriy amalni bekor qilish |

### Oqimni yopish va yangisini kutish rejimiga qo'yish (hozirgi vazifa)
Yangilashdan keyin admin botga ketma-ket yozadi:
1. `/export` — III oqim ro'yxatini Excel qilib olib qo'ying (keyin ham olish mumkin, lekin hozir qulay).
2. `/oqim IV oqim` — joriy oqim endi IV.
3. `/close` — ro'yxat yopiladi. Endi /start bosgan har bir odam shu xabarni ko'radi:
   «IV oqimga ro'yxatdan o'tish hali boshlanmadi. Ochilishi bilan sizga xabar yuboramiz».
   Bunday odamlar ham bazaga tushadi va keyin /send orqali xabar oladi.
4. `/status` — tekshiring: «Joriy oqim: IV oqim — ro'yxat 🔒 YOPIQ» bo'lishi kerak.

Dekabrda ro'yxat boshlanganda: `/open` → keyin `/send` bilan hammaga «ro'yxat ochildi» deb xabar yuboring.
Bu sozlamalar bazada saqlanadi — server qayta ishga tushsa ham yo'qolmaydi.

> Eslatma: `/stats` va `/export` faqat **joriy** oqimni ko'rsatadi. IV oqimga o'tgandan keyin
> III oqim ro'yxati kerak bo'lsa: `/oqim III oqim` → `/export` → `/oqim IV oqim`.

### /send qanday ishlaydi
1. Botga `/send` deb yozing.
2. Kimga yuborishni tanlang: Hammaga / Bo'stonliq / Parkent / Boshqa tumanlar. Har bir
   tugma yonida nechta odam olishi yozilgan.
3. Yuboriladigan xabarni botga yuboring — matn, rasm (izoh bilan), hujjat, video.
   Xabar aynan shu ko'rinishda ketadi.
4. «✅ Ha, yuborish» tugmasini bosing. Bot jarayonni ko'rsatadi va oxirida: nechtaga
   yetkazildi, nechta odam botni bloklagan.

Oluvchilar — botga kamida bir marta `/start` bosgan hamma + ro'yxatdan o'tganlar.
Eski versiya faqat ro'yxatdan to'liq o'tganlarni eslab qolgan edi; `/start` bosib
ketganlar yangi versiyada botga qayta yozganidan keyin ro'yxatga tushadi.
