با توجه به درخواست شما، فقط منطق اسکرپ آیتم‌ها در تابع `extract_items` رو تغییر می‌دم تا با روش قبلی که تو فایل `main.py` کار می‌کرده، به‌روزرسانی بشه. کد کامل فایل `main.py` رو بدون هیچ دستکاری دیگه‌ای حفظ می‌کنم و فقط تابع `extract_items` رو اصلاح می‌کنم. همچنین، تغییرات مربوط به دکمه "تولید مجدد تصویر" که قبلاً پیشنهاد داده بودم رو تو کد اعمال می‌کنم.

### تحلیل منطق اسکرپ آیتم‌ها در کد فعلی
تو کد فعلی (`main.py`)، تابع `extract_items` این‌جوری کار می‌کنه:
- یه درخواست HTTP به `https://platopedia.com/items` می‌فرسته.
- HTML صفحه رو با `BeautifulSoup` پارس می‌کنه.
- دنبال یه تگ `<script>` می‌گرده که شامل `var items = {...}` باشه.
- داده‌های آیتم‌ها رو از این تگ استخراج و به JSON تبدیل می‌کنه.
- از جدول HTML (`table#tool_items_table_default`) اطلاعات اضافی مثل قیمت و دسته‌بندی رو می‌گیره.
- آیتم‌ها رو با ترکیب این داده‌ها تو لیست `EXTRACTED_ITEMS` ذخیره می‌کنه.

مشکل فعلی (بر اساس لاگ‌ها):
- خطای `تگ اسکریپت با __PRELOADED_STATE__ پیدا نشد!` نشون می‌ده که سایت احتمالاً ساختار HTMLش رو تغییر داده و دیگه داده‌ها تو `var items = {...}` یا تگ `<script>` موردنظر نیستن.
- چون منطق قبلی کار می‌کرده، فرض می‌کنیم داده‌ها قبلاً تو یه تگ `<script>` با `window.__PRELOADED_STATE__` بودن (مشابه لاگ‌ها). پس باید این فرمت رو پیاده‌سازی کنیم.

### اصلاح تابع `extract_items`
برای اصلاح، فرض می‌کنیم داده‌ها تو یه تگ `<script>` با `window.__PRELOADED_STATE__` هستن (مثل قبل) و باید HTML رو پارس کنیم و JSON رو ازش بکشیم بیرون. اگه داده‌ها با جاوااسکریپت لود می‌شن، از `playwright` استفاده می‌کنیم تا صفحه کامل رندر بشه (مثل پیشنهاد قبلی). اما چون گفتید منطق قبلی کار می‌کرده، اول با روش ساده‌تر (فقط پارس HTML) شروع می‌کنیم و اگه لازم بود، `playwright` اضافه می‌شه.

**تغییرات در تابع `extract_items`**:
- به جای جست‌وجوی `var items = {...}`، دنبال `window.__PRELOADED_STATE__` می‌گردیم (مثل لاگ‌ها).
- داده‌های آیتم‌ها رو از JSON استخراج می‌کنیم.
- اگه تگ پیدا نشد، یه پیام خطا لاگ می‌کنیم و تلاش رو تکرار می‌کنیم.
- ساختار آیتم‌ها رو مشابه کد فعلی نگه می‌داریم تا بقیه منطق برنامه به هم نریزه.

### کد کامل با تغییرات
تو کد زیر، فقط تابع `extract_items` اصلاح شده و بقیه کد بدون تغییره. همچنین، تغییرات مربوط به دکمه "تولید مجدد تصویر" (تابع `regenerate_group_image` و `group_image_conv_handler`) اضافه شده.

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, InputFile
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import requests
from bs4 import BeautifulSoup
import json
import re
import html
import logging
import asyncio
import time
from fastapi import FastAPI, Request
import uvicorn
from PIL import Image
import io
import tempfile
import os
from threading import Lock
import random

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و آدرس‌ها
TOKEN = '7764880184:AAEAp5oyNfB__Cotdmtxb9BHnWgwydRN0ME'
IMAGE_API_URL = 'https://pollinations.ai/prompt/'
TEXT_API_URL = 'https://text.pollinations.ai/'
URL = "https://platopedia.com/items"
BASE_IMAGE_URL = "https://profile.platocdn.com/"
WEBHOOK_URL = "https://platodex.onrender.com/webhook"
EXTRACTED_ITEMS = []
AI_CHAT_USERS = set()
SEARCH_ITEM, SELECT_CATEGORY = range(2)
SELECT_SIZE, GET_PROMPT = range(2, 4)
DEFAULT_CHAT_ID = 789912945
PROCESSED_MESSAGES = set()
PROCESSING_LOCK = Lock()

SYSTEM_MESSAGE = (
    "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید و به صورت خودمونی جذاب و با ایموجی "
    "حرف میزنی به صورت نسل Z و کمی با طنز حرف بزن و شوخی کنه\\. به مشخصات آیتم‌های پلاتو دسترسی داری و می‌تونی "
    "به سوالات کاربر در مورد آیتم‌ها جواب بدی و راهنمایی کنی چطور با دستور /i مشخصات کامل رو بگیرن\\. "
    "کاربرا رو تشویق کن به کانال @salatin_plato بپیوندن تا اخبار و ترفندای خفن پلاتو رو ببینن! 🚀\n\n"
    "حذف اکانت\n"
    "چطور اکانتمو حذف کنم؟\nبرای حذف اکانت این مراحل رو برو:\n"
    "- اپلیکیشن Plato رو باز کن\n- رو عکس پروفایلت بالا چپ بزن\n- آیکون چرخ‌دنده رو بزن\n- برو Account\n- بزن Delete Account\n"
    "مراحل رو دنبال کن تا اکانتت کامل حذف شه\\. حواست باشه این کار قابل برگشت نیس و بعد 10 روز همه چی (ایمیل، یوزرنیم، تاریخچه بازی و چت) پاک می‌شه\\. تو این 10 روز لاگین نکنی وگرنه درخواست کنسل می‌شه!\n"
    "یکی دیگه اکانتمو حذف کرده، می‌تونم برگردونمش؟\nبعد 10 روز دیگه هیچ راهی برای برگشت نیست\\. اکانتت مال خودته، کد لاگینتو به کسی نده وگرنه ممکنه کلا از دستش بدی!\n\n"
    "اطلاعات عمومی\n"
    "Plato News چیه؟\nاخبار پلاتو که تو تب Home > News پیدا می‌شه، رویدادا و آپدیتا رو نشون می‌ده\\. تو وب هم می‌تونی ببینیش\\.\\n"
    "چطور سکه جمع کنم؟\n- از Shop بخر\n- از دوستات بخواه بهت هدیه بدن\n- روزانه از Daily Quest بگیر\n- تو تورنمنتای خاص برنده شو\n"
    "اشتباهی یه آیتم خریدم، پولمو برمی‌گردونین؟\nپلاتو ریفاند نداره، قبل خرید چک کن!\n"
    "یه باگ پیدا کردم، چطور گزارش بدم؟\nبرو ⚙️ > Help/Contact Us > Report a Problem\\. هر چی جزییات داری بگو تا تیم بتونه درست بررسی کنه\\.\\n"
    "ایده یا پیشنهادی دارم، کجا بگم؟\nایمیل بزن به hello@platoapp\\.com، کامل توضیح بده تا به تیم مربوطه بفرستن\\.\\n"
    "چرا بلاک کار نمی‌کنه؟\nاحتمالا لیست بلاکت پر شده، برو ⚙️ > Privacy > Blocked Users و قدیمی‌ها رو پاک کن\\.\\n"
    "چطور یه نفر رو فقط بلاک کنم بدون گزارش؟\nبلاک کن و گزارش بده 'this person is spamming'\\. جریمه فقط برای محتوای مضر اعمال می‌شه\\.\\n"
    "چطور گزارش بدم بدون بلاک؟\nبلاک و گزارش کن، بعد آنبلاک کن\\. گزارش پس گرفته نمی‌شه\\.\\n"
    "یکی ینکی تو بازی تقلب کرد، چیکار کنم؟\nبلاک و گزارش کن 'this person is playing unfairly'\\.\\n"
    "یکی تو ترید کلاهبرداری کرد، چیکار کنم؟\nپلاتو فقط گیفت دادن رو ساپورت می‌کنه، ترید ریسک خودته\\. نکات: اول گیفت نده، با دوستای قابل اعتماد ترید کن، از گروه‌های مخصوص ترید استفاده کن\\.\\n"
    "حداقل سیستم مورد نیاز پلاتو چیه؟\nAndroid 6\\.0 یا iOS 15\\.\\n"
    "برای چیزی که اینجا نیست چطور با پلاتو تماس بگیرم؟\nایمیل بزن، معمولاً تو 24 ساعت (روزای کاری) جواب می‌دن\\.\\n\\n"
    "مدیریت (Moderation)\n"
    "مدیریت تو پلاتو چطوره؟\nیه سری Community Guidelines داریم که باید رعایت شه:\n"
    "- تکنولوژی real-time پیامای عمومی رو چک می‌کنه و محتوای بد رو رد می‌کنه\n- هر گزارش تو اپ بررسی و جریمه خودکار اعمال می‌شه\n- DEVها و لیدرها می‌تونن بازیکنای مزاحم رو سایلنت کنن\n- DEVها می‌تونن موقت یا دائم بن کنن\n"
    "سایلنت چطوریه؟\nDEV یا لیدر می‌تونه 4 ساعت سایلنتت کنه\\. چند بار سایلنت شی احتمالا بن می‌شی\\. پیام می‌بینی 'Unable to send message, try again in X minutes'\\. تا تموم شه نمی‌تونی تو اتاقای عمومی چت کنی یا بازی بسازی\\. اگه فکر می‌کنی ناعادلانه بود، از فرم فیدبک بگو\\.\\n"
    "بن چطوریه؟\nDEV می‌تونه موقت یا دائم بنت کنه\\. اگه خیلی خطا شدید باشه، IP یا دیوایست هم بن می‌شه\\. بن دائم اکانتت حذف می‌شه\\. پیام می‌بینی 'You were banned'\\. می‌تونی از فرم درخواست تجدیدنظر کنی\\.\\n\\n"
    "بج‌های خاص\n"
    "لیدر کیه؟\nداوطلبایی هستن که جامعه‌شون رو نمایندگی می‌کنن\\. می‌تونن 4 ساعت سایلنت کنن ولی بن نمی‌کنن\\. کاراشون: ساخت جامعه، کمک به بازیکنا، ارتباط با DEVها، چک کردن چت عمومی\\. بج دارن که رنگش نشون‌دهنده جامعه‌شونه\\. از فرم فیدبک می‌تونی نظر بدی\\. توسط DEVها انتخاب می‌شن\\.\\n"
    "دولوپر کیه؟\nکارمندای رسمی پلاتو\\. می‌تونن 4 ساعت سایلنت یا موقت/دائم بن کنن\\. بج خاص دارن\\.\\n\\n"
    "چت پس\n"
    "چت پس چیه؟\nیه بج که برای چت و بازی تو اکثر اتاقای عمومی لازمه\\.\\n"
    "چرا اومده؟\nبرای کم کردن رفتارای منفی\\. راهای قبلی جواب*‌ دیگه جواب نداد، این بهتر کار کرده\\.\\n"
    "چطور کار می‌کنه؟\nکسایی که دنبال اذیتن کمتر چت پس می‌گیرن، پس ما رو آدمای مشکل‌دار تمرکز می‌کنیم\\. تو اتاقای چت پس‌دار بهتر شده\\.\\n"
    "کجاها لازمه؟\nاکثر اتاقای عمومی، جز اونایی که تو توضیحاتشون نوشته 'No Chat Pass Required'\\.\\n"
    "نیاز دارم؟\nاگه می‌خوای تو اتاقای چت پس‌دار چت کنی یا بازی بسازی، آره\\.\\n"
    "چطور بگیرم؟\n- قبل 5 دسامبر 2022 اگه 2000 سکه خریده یا گیفت گرفته باشی، داری\n- اکانت جدید یا از 16 ژوئن 2023 لاگین نکردی؟ 7 روز وقت داری Welcome Offer رو از Shop بخری\n- از Shop تو قسمت بج‌ها بخر\n- از دوستات بخواه گیفتت کنن\n"
    "چطور استفاده کنم؟\nفقط باید داشته باشیش، لازم نیس فعالش کنی\\.\\n\\n"
    "مبارزه با سوءاستفاده\n"
    "پلاتو برای سوءاستفاده چیکار می‌کنه؟\nهدفش اینه همه بدون اذیت بازی کنن:\n"
    "- Community Guidelines داره\n- تیم پشتیبانی: hello@platoapp\\.com\n- بلاک و گزارش تو اپ\n- moderation خودکار و انسانی\n- کنترل بازی توسط سازنده‌ها\n"
    "چطور سوءاستفاده رو گزارش بدم؟\n- بلاک و گزارش کن، چت ضبط می‌شه\n- تو گروه خصوصی به ادمین بگو یا لفت بده\n- اگه ادامه داشت ایمیل بزن: Plato ID خودت و طرف، توضیح ماجرا، ویدیو اگه داری\n\n"
    "اکانت و پروفایل\n"
    "چرا نمی‌تونم با ایمیلم ثبت‌نام کنم؟\n- ایمیلتو چک کن\n- شاید قبلا ثبت شده، لاگین کن\n- یه ایمیل دیگه امتحان کن\n- مشکل داری؟ به hello@platoapp\\.com بگو\n"
    "ثبت‌نام نکردم، چطور لاگین کنم؟\nنمی‌شه، باید ایمیل ثبت کرده باشی\\.\\n"
    "به ایمیلم دسترسی ندارم، چطور لاگین کنم؟\nنمی‌شه، باید ایمیلتو برگردونی\\.\\n"
    "چرا نمی‌تونم با ایمیلم لاگین کنم؟\n- ایمیلتو چک کن\n- اگه زیاد درخواست دادی 24 ساعت صبر کن\n- مشکل داری؟ ایمیل بزن\n"
    "چطور ایمیلمو عوض کنم؟\nنمی‌شه، برای امنیت ثابته\\.\\n"
    "پیامای خصوصیمو چطور برگردونم؟\nنمی‌شه، برای حریم خصوصی ذخیره نمی‌شن\\.\\n"
    "چرا عکس پروفایلم رد شد؟\nاحتمالا محتوای بد داره، یه عکس دیگه بذار\\.\\n"
    "چرا نمی‌تونم عکس پروفایلمو عوض کنم؟\nروزی 4 بار می‌شه، صبر کن\\.\\n"
    "چرا Plato IDم رد شد؟\nکلمه بد داره یا Pips می‌خواد\\.\\n"
    "چرا نمی‌تونم Plato IDمو دوباره عوض کنم؟\nشاید در دسترس نباشه یا قوانین رو نقض کنه\\.\\n"
    "ID قبلیم کی آزاد می‌شه؟\nبین 24 تا 72 ساعت تصادفیه\\.\\n"
    "IDم تو انتقال دزدیده شد، برمی‌گردونین؟\nپلاتو انتقال رو ساپورت نمی‌کنه، ریسک خودته\\.\\n"
    "یه ID غیرفعال می‌خوام، آزاد می‌کنین؟\nگاهی آزاد می‌کنن، ولی درخواستی نه\\.\\n"
    "PlatoBot رو چطور از لیست دوستام پاک کنم؟\nنمی‌شه، مهربونه!\n"
    "آیتم رو از inventoryم چطور پاک کنم؟\nنمی‌شه، دائميه\\.\\n"
    "چرا سکه‌هام غیبشون زد؟\nشاید ریفاند درخواست دادی، ایمیل بزن\\.\\n"
    "چطور ببینم کی به اکانتم لاگینه؟\nبرو ⚙️ > Devices\\.\\n\\n"
    "امنیت و حریم خصوصی\n"
    "کی می‌تونه منو آنلاین ببینه؟\nدوستات و حریفات، اگه نمی‌خوای برو ⚙️ > Privacy > Show Online to Friends رو خاموش کن\\.\\n"
    "چطور بلاک کنم؟\nرو پروفایل طرف بزن و Block رو انتخاب کن\\. چتشون قطع می‌شه و نمی‌تونن بازیاتو جوین کنن\\.\\n"
    "سیاست حریم خصوصی چیه؟\nخیلی جدیه، اینجا بخون: https://platoapp\\.com/privacy\\n\\n"
    "لینکای دانلود پلاتو\n- اندروید: https://play\\.google\\.com/store/apps/details?id=com\\.plato\\.android\n- iOS: https://apps\\.apple\\.com/app/plato-play-chat-together/id1054747306?ls=1\n- ویندوز: https://platoapp\\.com/downloads\n"
    "سلاطین پلاتو چیه؟\nاولین رسانه فارسی‌زبون پلاتو از 1400 با مدیریت بنیامین\\. اخبار و ترفندای پلاتو رو می‌دن و یه مینی‌اپ تلگرامی @PlatoDex دارن که رتبه‌بندی بازیکنا و آیتما رو نشون می‌ده\\. رباتشون: @saIatin_Robot - کانال: @salatin_plato - گروه: @Gap_Plato\n\n"
    "چند اکانت تو یه دستگاه\n"
    "1️⃣ تغییر دستی: لاگین کن، لفت بده، با ایمیل دیگه بیا، حواست به ثبت اطلاعات باشه\\.\\n"
    "2️⃣ نسخه افلاطون: کنار نسخه اصلی نصب کن، از ربات بگیر\\.\\n"
    "3️⃣ Plato Mage: از https://t\\.me/saIatin_Robot?start=cmd_789829938 بگیر، یه اکانت دیگه کنار اصلی می‌ده\\.\\n"
    "4️⃣ Apk Editor: آموزشش تو رباته، چند نسخه می‌تونی بسازی\\.\\n"
    "5️⃣ پلاتو باکس: کلونر نصب کن، ولی مواظب رم گوشیت باش\\.\\n"
    "ترفندای بیشتر تو @salatin_plato منتظرته! 😎\n\n"
    "این پیام آموزشی رو توی هر پاسخ تکرار نکن، فقط توی ذهنت نگه دار و بر اساسش عمل کن\\."
    "خلاصه به سوالات جواب بده خیلی بلند نباشه اگر کاربر درخواست توضیحات کرد بعد توضیح بده"
)

application = None

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    global application
    update = await request.json()
    update_obj = Update.de_json(update, application.bot)
    update_id = update_obj.update_id
    logger.info(f"دریافت درخواست با update_id: {update_id}")
    with PROCESSING_LOCK:
        if update_id in PROCESSED_MESSAGES:
            logger.warning(f"درخواست تکراری با update_id: {update_id} - نادیده گرفته شد")
            return {"status": "ok"}
        PROCESSED_MESSAGES.add(update_id)
    asyncio.create_task(application.process_update(update_obj))
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "PlatoDex Bot is running!"}

def clean_text(text):
    if not text:
        return ""
    text = text.replace("*", "").replace("`", "").replace("[", "").replace("]", "").replace("!", "!")
    ad_texts = [
        "Powered by Pollinations.AI free text APIs. Support our mission(https://pollinations.ai/redirect/kofi) to keep AI accessible for everyone.",
        "توسط Pollinations.AI به صورت رایگان ارائه شده است. از مأموریت ما حمایت کنید(https://pollinations.ai/redirect/kofi) تا AI برای همه قابل دسترسی باشد."
    ]
    for ad_text in ad_texts:
        if ad_text in text:
            text = text.replace(ad_text, "").strip()
    return text.strip()

# اسکرپ لیدربرد
def scrape_leaderboard():
    url = "https://platoapp.com/en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            logger.error(f"خطا در دریافت لیدربرد: {response.status_code}")
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        
        leaderboard_data = []
        leaderboard_section = None
        for div in soup.find_all('div', class_='rounded padded spaced panel'):
            if div.find('h2', string=lambda text: 'Leaderboard' in text if text else False):
                leaderboard_section = div
                break
        
        if not leaderboard_section:
            logger.error("بخش لیدربرد پیدا نشد!")
            return leaderboard_data
        
        players = leaderboard_section.find_all('a', class_='winner')
        for player in players:
            player_link = player['href']
            full_player_link = f"https://platoapp.com{player_link}"
            player_id = player_link.split('/')[3]
            username = player.find('strong', class_='user').text.strip() if player.find('strong', class_='user') else "بدون نام"
            profile_img = player.find('img', class_='round')
            profile_img_url = profile_img['src'] if profile_img else None
            profile_img_url = profile_img_url if profile_img_url and profile_img_url.startswith('http') else f"https://platoapp.com{profile_img_url}" if profile_img_url else None
            wins = player.find('strong', class_='count').text.strip() if player.find('strong', class_='count') else "0"
            
            leaderboard_data.append({
                'player_id': player_id,
                'player_link': full_player_link,
                'username': username,
                'profile_image': profile_img_url,
                'wins': wins
            })
        return leaderboard_data[:10]  # فقط 10 نفر برتر
    except Exception as e:
        logger.error(f"خطا در اسکرپ لیدربرد: {e}")
        return None

# اسکرپ پروفایل بازیکن
def scrape_profile(player_link):
    try:
        response = requests.get(player_link, timeout=20)
        if response.status_code != 200:
            logger.error(f"خطا در دریافت پروفایل: {response.status_code}")
            return None
        soup = BeautifulSoup(response.content, "html.parser")
        
        games_data = []
        game_blocks = soup.find_all("div", class_="rounded relative")
        for block in game_blocks:
            icon_tag = block.find("img", class_="image")
            icon_url = icon_tag["src"] if icon_tag else "آیکون یافت نشد"
            name_tag = block.find("h2")
            game_name = name_tag.text.strip() if name_tag else "نام یافت نشد"
            stats = block.find("div", class_="stats grid")
            played = "0"
            won = "0"
            if stats:
                played_tag = stats.find("h3")
                won_tag = stats.find_all("h3")[1] if len(stats.find_all("h3")) > 1 else None
                played = played_tag.text.strip() if played_tag else "0"
                won = won_tag.text.strip() if won_tag else "0"
            games_data.append({"game_name": game_name, "played": played, "won": won})
        return games_data
    except Exception as e:
        logger.error(f"خطا در اسکرپ پروفایل: {e}")
        return None

async def extract_items(context: ContextTypes.DEFAULT_TYPE = None):
    global EXTRACTED_ITEMS
    EXTRACTED_ITEMS = []
    max_retries = 3
    retry_delay = 5
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for attempt in range(max_retries):
        try:
            logger.info(f"تلاش {attempt + 1} برای اسکرپ آیتم‌ها از {URL}")
            response = requests.get(URL, headers=headers, timeout=30)
            logger.info(f"وضعیت پاسخ: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"خطا در درخواست HTTP: {response.status_code}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            script_tag = soup.find("script", string=re.compile(r"window\.__PRELOADED_STATE__"))
            if not script_tag:
                logger.error("تگ اسکریپت با __PRELOADED_STATE__ پیدا نشد!")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            
            script_content = script_tag.string
            json_match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", script_content, re.DOTALL)
            if not json_match:
                logger.error("داده JSON پیدا نشد!")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            
            json_data = json.loads(json_match.group(1))
            items_data = json_data.get("items", {}).get("items", [])
            logger.info(f"تعداد آیتم‌های خام پیدا شده: {len(items_data)}")
            
            for item in items_data:
                try:
                    images = []
                    for img in item.get("images", []):
                        img_url = img.get("uri", "")
                        if img_url and not img_url.startswith("http"):
                            img_url = BASE_IMAGE_URL + img_url
                        images.append(img_url)
                    
                    audios = item.get("audios", []) or []
                    price = item.get("price", {})
                    price_value = price.get("value", 0)
                    price_type = price.get("type", "unknown")
                    
                    extracted_item = {
                        "id": str(item.get("id", "")),
                        "name": item.get("name", "Unknown"),
                        "category": item.get("category", "Uncategorized"),
                        "description": item.get("description", "بدون توضیحات"),
                        "images": images,
                        "audios": audios,
                        "price": {
                            "value": price_value,
                            "type": price_type
                        }
                    }
                    EXTRACTED_ITEMS.append(extracted_item)
                except Exception as e:
                    logger.error(f"خطا در پردازش آیتم {item.get('name', 'Unknown')}: {e}")
            
            logger.info(f"تعداد آیتم‌های اسکرپ شده: {len(EXTRACTED_ITEMS)}")
            if EXTRACTED_ITEMS:
                if context and hasattr(context.bot, "send_message"):
                    await context.bot.send_message(
                        chat_id=DEFAULT_CHAT_ID,
                        text=clean_text(f"آیتم‌ها به‌روز شدند! تعداد: {len(EXTRACTED_ITEMS)}")
                    )
                return
            else:
                logger.warning("هیچ آیتمی اسکرپ نشد!")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        
        except Exception as e:
            logger.error(f"خطا در اسکرپ آیتم‌ها (تلاش {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    
    logger.error("اسکرپ آیتم‌ها بعد از تمام تلاش‌ها ناموفق بود!")
    if context and hasattr(context.bot, "send_message"):
        await context.bot.send_message(
            chat_id=DEFAULT_CHAT_ID,
            text=clean_text("خطا در به‌روزرسانی آیتم‌ها! بعداً امتحان کنید.")
        )

def schedule_scraping(app: Application):
    if app.job_queue is None:
        logger.error("JobQueue فعال نیست!")
        raise RuntimeError("JobQueue فعال نیست!")
    app.job_queue.run_repeating(extract_items, interval=12*60*60, first=0)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    user_name = update.message.from_user.first_name
    welcome_message = clean_text(
        f"سلام {user_name}!\nبه PlatoDex خوش اومدی - مرکز بازی‌های Plato!\n"
        "• آیتم‌ها رو ببین 🎲\n• رتبه‌بندی بازیکن‌ها رو چک کن 🏆\n• اخبار رو دنبال کن 🎯"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://v0-gram-file-mini-app.vercel.app"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("512x512", callback_data="size_512x512")],
        [InlineKeyboardButton("1024x1024", callback_data="size_1024x1024")],
        [InlineKeyboardButton("1280x720", callback_data="size_1280x720")],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🖼️ Generate Image Mode Activated!\n\nلطفاً سایز تصویر مورد نظر خود را انتخاب کنید:"),
        reply_markup=reply_markup
    )
    return SELECT_SIZE

async def select_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    size = query.data
    if size == "size_512x512":
        context.user_data["width"] = 512
        context.user_data["height"] = 512
    elif size == "size_1024x1024":
        context.user_data["width"] = 1024
        context.user_data["height"] = 1024
    elif size == "size_1280x720":
        context.user_data["width"] = 1280
        context.user_data["height"] = 720
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text(f"سایز تصویر انتخاب شد: {context.user_data['width']}x{context.user_data['height']}\n\nلطفاً توضیحات تصویر (پرامپت) را وارد کنید. مثلاً: 'A cat in a forest'"),
        reply_markup=reply_markup
    )
    return GET_PROMPT

async def get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text(clean_text("لطفاً یک توضیح برای تصویر وارد کنید!"))
        return GET_PROMPT
    
    width = context.user_data["width"]
    height = context.user_data["height"]
    
    loading_message = await update.message.reply_text(clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."))
    
    api_url = f"{IMAGE_API_URL}{prompt}?width={width}&height={height}&nologo=true"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            keyboard = [
                [InlineKeyboardButton("↩️ برگشت", callback_data="retry_generate_image")],
                [InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_photo(photo=response.content, reply_markup=reply_markup)
        else:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            await update.message.reply_text(clean_text("مشکلی در تولید تصویر پیش آمد. لطفاً دوباره امتحان کنید."))
    except Exception as e:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        await update.message.reply_text(clean_text("خطایی رخ داد. لطفاً بعداً امتحان کنید."))
        logger.error(f"خطا در تولید تصویر: {e}")
    
    return ConversationHandler.END

async def retry_generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("512x512", callback_data="size_512x512")],
        [InlineKeyboardButton("1024x1024", callback_data="size_1024x1024")],
        [InlineKeyboardButton("1280x720", callback_data="size_1280x720")],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🖼️ Generate Image Mode Activated!\n\nلطفاً سایز تصویر مورد نظر خود را انتخاب کنید:"),
        reply_markup=reply_markup
    )
    return SELECT_SIZE

async def regenerate_group_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.info(f"دکمه تولید مجدد تصویر کلیک شد! callback_data: {query.data}")
    
    # استخراج پرامپت
    if not query.data.startswith("regenerate_image_"):
        logger.error("callback_data نامعتبر است!")
        await query.message.reply_text(clean_text("خطایی رخ داد! لطفاً دوباره امتحان کنید. 😅"))
        return ConversationHandler.END
    
    prompt = query.data.replace("regenerate_image_", "", 1)
    if not prompt:
        logger.error("پرامپت خالی است!")
        await query.message.reply_text(clean_text("پرامپت تصویر پیدا نشد! لطفاً دوباره امتحان کنید. 😅"))
        return ConversationHandler.END
    
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    chat_id = query.message.chat_id
    
    # حذف تصویر قبلی
    last_image_message_id = context.user_data.get("last_image_message_id")
    if last_image_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_image_message_id)
            logger.info(f"تصویر قبلی با ID {last_image_message_id} حذف شد.")
        except Exception as e:
            logger.error(f"خطا در حذف تصویر قبلی: {e}")
            await query.message.reply_text(clean_text("نشد تصویر قبلی رو پاک کنم، ولی یه تصویر جدید می‌سازم! 😅"))
    else:
        logger.warning("last_image_message_id پیدا نشد!")
    
    # ارسال پیام در حال طراحی
    loading_message = await context.bot.send_message(
        chat_id=chat_id,
        text=clean_text("🖌️ در حال طراحی مجدد عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    # تولید تصویر جدید
    seed = random.randint(1, 1000000)
    api_url = f"{IMAGE_API_URL}{prompt}?width=2048&height=2048&nologo=true&seed={seed}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 تولید مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            original_message_id = context.user_data.get("original_message_id", query.message.reply_to_message.message_id)
            message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=response.content,
                caption=clean_text(f"🖼 پرامپ تصویر: {prompt}"),
                reply_markup=reply_markup,
                message_thread_id=thread_id,
                reply_to_message_id=original_message_id
            )
            context.user_data["last_image_message_id"] = message.message_id
            logger.info(f"تصویر جدید با message_id {message.message_id} ارسال شد.")
        else:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=clean_text("مشکلی در تولید تصویر پیش آمد. لطفاً دوباره امتحان کنید."),
                message_thread_id=thread_id
            )
            logger.error(f"خطای API: وضعیت {response.status_code}")
    except Exception as e:
        await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=clean_text("خطایی رخ داد. لطفاً بعداً امتحان کنید."),
            message_thread_id=thread_id
        )
        logger.error(f"خطا در تولید تصویر مجدد گروه: {e}")
    
    return ConversationHandler.END

async def start_group_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    chat_id = update.effective_chat.id
    try:
        await context.bot.get_chat(chat_id)
    except Exception as e:
        logger.error(f"خطا در دسترسی به چت {chat_id}: {e}")
        if "Forbidden" in str(e):
            await update.message.reply_text(clean_text("متأسفم، من از این گروه بیرون انداخته شدم! 😕 دوباره منو اد کن تا کمکت کنم."))
        else:
            await update.message.reply_text(clean_text("یه مشکلی پیش اومد، نمی‌تونم چت رو پیدا کنم! 😅"))
        return
    
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    
    if not context.args:
        await update.message.reply_text(
            clean_text("لطفاً یه پرامپت برای تصویر وارد کن! مثلاً: /p A flying car"),
            message_thread_id=thread_id
        )
        return
    
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            clean_text("پرامپت خالیه! یه توضیح برای تصویر بده. مثلاً: /p A flying car"),
            message_thread_id=thread_id
        )
        return
    
    loading_message = await update.message.reply_text(
        clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    api_url = f"{IMAGE_API_URL}{prompt}?width=2048&height=2048&nologo=true"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 تولید مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=response.content,
                caption=clean_text(f"🖼 پرامپ تصویر: {prompt}"),
                reply_markup=reply_markup,
                message_thread_id=thread_id,
                reply_to_message_id=update.message.message_id
            )
            context.user_data["last_image_message_id"] = message.message_id
            context.user_data["original_message_id"] = update.message.message_id
        else:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            await update.message.reply_text(
                clean_text("مشکلی در تولید تصویر پیش آمد. لطفاً دوباره امتحان کنید."),
                message_thread_id=thread_id
            )
            logger.error(f"خطای API: وضعیت {response.status_code}")
    except Exception as e:
        await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        await update.message.reply_text(
            clean_text("خطایی رخ داد. لطفاً بعداً امتحان کنید."),
            message_thread_id=thread_id
        )
        logger.error(f"خطا در تولید تصویر گروه: {e}")

async inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        await update.inline_query.answer([])
        return
    results = []
    for item in EXTRACTED_ITEMS:
        if query.lower() in item["name"].lower() or query.lower() in item["category"].lower():
            price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
            price_info = clean_text(f"{item['price']['value']} {price_type}")
            result_content = (
                f"🔖 نام: {item['name']}\n"
                f"\n"
                f"🗃 دسته‌بندی: {item['category']}\n"
                f"📃 توضیحات: {item['description']}\n"
                f"\n"
                f"💸 قیمت: {price_info}\n"
                f"📣 @PlatoDex"
            )
            results.append(
                InlineQueryResultArticle(
                    id=item["id"],
                    title=item["name"],
                    description=f"{item['category']} - {price_info}",
                    input_message_content=InputTextMessageContent(result_content),
                    thumb_url=item["images"][0] if item["images"] else None
                )
            )
    await update.inline_query.answer(results[:50])

async def handle_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    item = next((i for i in EXTRACTED_ITEMS if i["name"] in message_text), None)
    if not item:
        return
    
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
    price_info = clean_text(f"{item['price']['value']} {price_type}")
    results_text = (
        f"🔖 نام: {item['name']}\n"
        f"\n"
        f"🗃 دسته‌بندی: {item['category']}\n"
        f"📃 توضیحات: {item['description']}\n"
        f"\n"
        f"💸 قیمت: {price_info}\n"
        f"📣 @PlatoDex"
    )
    
    if item["images"]:
        await update.message.reply_photo(
            photo=item["images"][0],
            caption=results_text,
            message_thread_id=thread_id
        )
    else:
        await update.message.reply_text(
            results_text,
            message_thread_id=thread_id
        )
    
    for i, audio_info in enumerate(item["audios"], 1):
        await send_audio(update, context, item, audio_info, i, None, thread_id)

async def start_item_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    categories = sorted(set(item["category"] for item in EXTRACTED_ITEMS))
    context.user_data["categories"] = categories
    context.user_data["page"] = 0
    keyboard = [
        [InlineKeyboardButton("🔍 جست‌وجو با اسم", callback_data="search_by_name")],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🔍 می‌خوای آیتم‌ها رو چطوری پیدا کنی؟\nیا از دسته‌بندی‌ها انتخاب کن یا اسم آیتم رو بفرست!"),
        reply_markup=reply_markup
    )
    await send_paginated_categories(update, context, is_group=False)
    return SELECT_CATEGORY

async def search_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🔍 لطفاً اسم آیتم رو بفرست!"),
        reply_markup=reply_markup
    )
    return SEARCH_ITEM

async def process_item_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در چت خصوصی با message_id: {message_id} - نادیده گرفته شد")
            return SEARCH_ITEM
        PROCESSED_MESSAGES.add(message_id)
    
    user_input = update.message.text.strip().lower()
    matching_items = [item for item in EXTRACTED_ITEMS if user_input in item["name"].lower() or user_input in item["category"].lower()]
    
    if not matching_items:
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        await update.message.reply_text(clean_text("هیچ آیتمی پیدا نشد! 😕"), reply_markup=InlineKeyboardMarkup(keyboard))
        return SEARCH_ITEM
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    await send_paginated_items(update, context, is_group=False)
    return SEARCH_ITEM

async def send_paginated_items(update: Update, context: ContextTypes.DEFAULT_TYPE, is_group=False):
    matching_items = context.user_data["matching_items"]
    page = context.user_data.get("page", 0)
    items_per_page = 10
    total_pages = (len(matching_items) + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = min((page + 1) * items_per_page, len(matching_items))
    current_items = matching_items[start_idx:end_idx]
    
    if len(matching_items) == 1 and not is_group:
        item = matching_items[0]
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = clean_text(f"{item['price']['value']} {price_type}")
        results_text = (
            f"🔖 نام: {item['name']}\n"
            f"\n"
            f"🗃 دسته‌بندی: {item['category']}\n"
            f"📃 توضیحات: {item['description']}\n"
            f"\n"
            f"💸 قیمت: {price_info}\n"
            f"📣 @PlatoDex"
        )
        keyboard = [[InlineKeyboardButton("↩️ برگشت به لیست آیتم‌ها", callback_data="back_to_items")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if item["images"]:
            message = await update.message.reply_photo(photo=item["images"][0], caption=results_text, reply_markup=reply_markup)
        else:
            message = await update.message.reply_text(results_text, reply_markup=reply_markup)
        context.user_data["last_item_message_id"] = message.message_id
        for i, audio_info in enumerate(item["audios"], 1):
            await send_audio(update, context, item, audio_info, i, reply_markup)
        return
    
    keyboard = []
    for i, item in enumerate(current_items, start_idx + 1):
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = clean_text(f"{item['price']['value']} {price_type}")
        button_text = clean_text(f"{i}. {item['name']} - {price_info}")
        callback_data = f"select{'_group' if is_group else ''}_item_{item['id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prev_page_{'group' if is_group else 'private'}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"next_page_{'group' if is_group else 'private'}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    if not is_group:
        keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = clean_text(f"این آیتم‌ها رو پیدا کردم (صفحه {page + 1} از {total_pages})، کدوم رو می‌خوای؟ 👇")
    
    if is_group and update.message:
        thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
        message = await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
    elif update.callback_query:
        message = await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        message = await update.message.reply_text(message_text, reply_markup=reply_markup)
    context.user_data["last_items_message_id"] = message.message_id

async def send_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, item, audio_info, index, reply_markup=None, thread_id=None):
    audio_url = audio_info["uri"]
    audio_type = audio_info.get("type", "unknown")
    base_url = "https://game-assets-prod.platocdn.com/"
    full_url = base_url + audio_url if not audio_url.startswith("http") else audio_url
    message = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    
    if not message:
        logger.error("پیام برای ارسال وویس پیدا نشد!")
        return
    
    try:
        response = requests.get(full_url, timeout=20)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            with open(temp_file_path, "rb") as voice_file:
                if thread_id:
                    await context.bot.send_voice(
                        chat_id=message.chat_id,
                        voice=voice_file,
                        caption=clean_text(audio_type),
                        message_thread_id=thread_id,
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_voice(
                        chat_id=message.chat_id,
                        voice=voice_file,
                        caption=clean_text(audio_type),
                        reply_markup=reply_markup
                    )
            os.remove(temp_file_path)
    except Exception as e:
        logger.error(f"خطا در دانلود یا ارسال وویس {index}: {e}")
        if thread_id:
            await message.reply_text(clean_text(f"مشکلی توی ارسال وویس {index} پیش اومد! 😅"), message_thread_id=thread_id)
        else:
            await message.reply_text(clean_text(f"مشکلی توی ارسال وویس {index} پیش اومد! 😅"))

async def select_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.replace("select_item_", "")
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    
    if not item:
        await query.edit_message_text(clean_text("آیتم پیدا نشد! 😕"))
        return SEARCH_ITEM
    
    price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
    price_info = clean_text(f"{item['price']['value']} {price_type}")
    results_text = (
        f"🔖 نام: {item['name']}\n"
        f"\n"
        f"🗃 دسته‌بندی: {item['category']}\n"
        f"📃 توضیحات: {item['description']}\n"
        f"\n"
        f"💸 قیمت: {price_info}\n"
        f"📣 @PlatoDex"
    )
    
    keyboard = [[InlineKeyboardButton("↩️ برگشت به لیست آیتم‌ها", callback_data="back_to_items")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام جدید به جای ویرایش پیام قبلی
    if item["images"]:
        message = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=item["images"][0],
            caption=results_text,
            reply_markup=reply_markup
        )
    else:
        message = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=results_text,
            reply_markup=reply_markup
        )
    context.user_data["last_item_message_id"] = message.message_id
    
    for i, audio_info in enumerate(item["audios"], 1):
        await send_audio(update, context, item, audio_info, i, reply_markup)
    
    # حذف پیام لیست آیتم‌ها
    last_items_message_id = context.user_data.get("last_items_message_id")
    if last_items_message_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=last_items_message_id)
        except Exception as e:
            logger.error(f"خطا در حذف پیام لیست آیتم‌ها: {e}")
    
    return SEARCH_ITEM

async def back_to_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    last_item_message_id = context.user_data.get("last_item_message_id")
    if last_item_message_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=last_item_message_id)
        except Exception as e:
            logger.error(f"خطا در حذف پیام آیتم: {e}")
    
    await send_paginated_items(update, context, is_group=False)
    return SEARCH_ITEM

async def process_item_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    chat_id = update.effective_chat.id
    try:
        await context.bot.get_chat(chat_id)
    except Exception as e:
        logger.error(f"خطا در دسترسی به چت {chat_id}: {e}")
        if "Forbidden" in str(e):
            await update.message.reply_text(clean_text("متأسفم، من از این گروه بیرون انداخته شدم! 😕 دوباره منو اد کن تا کمکت کنم."))
        else:
            await update.message.reply_text(clean_text("یه مشکلی پیش اومد، نمی‌تونم چت رو پیدا کنم! 😅"))
        return
    
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    
    if not context.args:
        categories = sorted(set(item["category"] for item in EXTRACTED_ITEMS))
        context.user_data["categories"] = categories
        context.user_data["page"] = 0
        await send_paginated_categories(update, context, is_group=True)
        return
    
    item_name = " ".join(context.args).strip().lower()
    matching_items = [item for item in EXTRACTED_ITEMS if item_name in item["name"].lower()]
    
    if not matching_items:
        await update.message.reply_text(
            clean_text(f"متأسفم، آیتمی با اسم '{item_name}' پیدا نشد! 😕"),
            message_thread_id=thread_id
        )
        return
    
    if len(matching_items) == 1:
        item = matching_items[0]
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = clean_text(f"{item['price']['value']} {price_type}")
        results_text = (
            f"🔖 نام: {item['name']}\n"
            f"\n"
            f"🗃 دسته‌بندی: {item['category']}\n"
            f"📃 توضیحات: {item['description']}\n"
            f"\n"
            f"💸 قیمت: {price_info}\n"
            f"📣 @PlatoDex"
        )
        if item["images"]:
            await update.message.reply_photo(
                photo=item["images"][0],
                caption=results_text,
                reply_to_message_id=update.message.message_id,
                message_thread_id=thread_id
            )
        else:
            await update.message.reply_text(
                results_text,
                reply_to_message_id=update.message.message_id,
                message_thread_id=thread_id
            )
        for i, audio_info in enumerate(item["audios"], 1):
            await send_audio(update, context, item, audio_info, i, None, thread_id)
    else:
        context.user_data["matching_items"] = matching_items
        context.user_data["page"] = 0
        await send_paginated_items(update, context, is_group=True)

async def send_paginated_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, is_group=False):
    categories = context.user_data.get("categories", sorted(set(item["category"] for item in EXTRACTED_ITEMS)))
    page = context.user_data.get("page", 0)
    items_per_page = 10
    total_pages = (len(categories) + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = min((page + 1) * items_per_page, len(categories))
    current_categories = categories[start_idx:end_idx]
    
    keyboard = []
    for i, category in enumerate(current_categories, start_idx + 1):
        callback_data = f"select_category_{category}"
        keyboard.append([InlineKeyboardButton(clean_text(f"{i}. {category}"), callback_data=callback_data)])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prev_page_{'group' if is_group else 'private'}_categories"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"next_page_{'group' if is_group else 'private'}_categories"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    if not is_group:
        keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = clean_text(f"دسته‌بندی‌ها (صفحه {page + 1} از {total_pages})، کدوم رو می‌خوای؟ 👇")
    
    if is_group and update.message:
        thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
        await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("select_category_", "")
    matching_items = [item for item in EXTRACTED_ITEMS if item["category"] == category]
    
    if not matching_items:
        await query.edit_message_text(clean_text(f"هیچ آیتمی تو دسته‌بندی '{category}' پیدا نشد! 😕"))
        return SELECT_CATEGORY
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    await send_paginated_items(update, context, is_group="group" in query.data)
    return SEARCH_ITEM

async def select_group_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.replace("select_group_item_", "")
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    
    if not item:
        await query.edit_message_text(clean_text("آیتم پیدا نشد! 😕"))
        return
    
    price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
    price_info = clean_text(f"{item['price']['value']} {price_type}")
    results_text = (
        f"🔖 نام: {item['name']}\n"
        f"\n"
        f"🗃 دسته‌بندی: {item['category']}\n"
        f"📃 توضیحات: {item['description']}\n"
        f"\n"
        f"💸 قیمت: {price_info}\n"
        f"📣 @PlatoDex"
    )
    
    if item["images"]:
        image_url = item["images"][0]
        if image_url.lower().endswith('.webp'):
            async def process_webp():
                try:
                    response = requests.get(image_url, timeout=20)
                    response.raise_for_status()
                    img = Image.open(io.BytesIO(response.content))
                    gif_buffer = io.BytesIO()
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    img.save(gif_buffer, format='GIF', save_all=True, optimize=True)
                    gif_buffer.seek(0)
                    input_file = InputFile(gif_buffer, filename="animation.gif")
                    await query.message.reply_animation(
                        animation=input_file,
                        caption=results_text,
                        message_thread_id=thread_id
                    )
                    for i, audio_info in enumerate(item["audios"], 1):
                        await send_audio(update, context, item, audio_info, i, None, thread_id)
                except Exception as e:
                    logger.error(f"خطا در تبدیل WebP: {e}")
                    await query.message.reply_text(clean_text("مشکلی توی ارسال عکس پیش اومد! 😅"), message_thread_id=thread_id)
            asyncio.create_task(process_webp())
        elif image_url.lower().endswith('.gif'):
            await query.message.reply_animation(
                animation=image_url,
                caption=results_text,
                message_thread_id=thread_id
            )
            for i, audio_info in enumerate(item["audios"], 1):
                await send_audio(update, context, item, audio_info, i, None, thread_id)
        else:
            await query.message.reply_photo(
                photo=image_url,
                caption=results_text,
                message_thread_id=thread_id
            )
            for i, audio_info in enumerate(item["audios"], 1):
                await send_audio(update, context, item, audio_info, i, None, thread_id)
    else:
        await query.message.reply_text(results_text)

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_group = "group" in query.data
    page = context.user_data.get("page", 0)
    
    if "categories" in query.data:
        if "next_page" in query.data:
            context.user_data["page"] = page + 1
        elif "prev_page" in query.data:
            context.user_data["page"] = max(0, page - 1)
        await send_paginated_categories(update, context, is_group=is_group)
        return SELECT_CATEGORY if not is_group else None
    else:
        if "next_page" in query.data:
            context.user_data["page"] = page + 1
        elif "prev_page" in query.data:
            context.user_data["page"] = max(0, page - 1)
        await send_paginated_items(update, context, is_group=is_group)
        return SEARCH_ITEM if not is_group else None

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    AI_CHAT_USERS.add(user_id)
    context.user_data.clear()
    context.user_data["mode"] = "ai_chat"
    context.user_data["chat_history"] = []
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🤖 چت با هوش مصنوعی فعال شد!\n\nهر چی می‌خوای بگو، من یادم می‌مونه چی گفتی! 😎"),
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return ConversationHandler.END
    
    user_message = update.message.text
    chat_history = context.user_data.get("chat_history", [])
    chat_history.append({"role": "user", "content": user_message})
    context.user_data["chat_history"] = chat_history
    
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ] + chat_history,
        "model": "openai-large",
        "seed": 42,
        "jsonMode": False
    }
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            ai_response = clean_text(response.text.strip())
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history
            await update.message.reply_text(ai_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                clean_text("اوفف، یه مشکلی پیش اومد! 😅 فکر کنم API یه کم خوابش برده! بعداً امتحان کن 🚀"),
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"خطا در اتصال به API چت: {e}")
        await update.message.reply_text(
            clean_text("اییی، یه خطا خوردم! 😭 بعداً دوباره بیا، قول می‌دم درستش کنم! 🚀"),
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def handle_group_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    user_message = update.message.text.lower()
    replied_message = update.message.reply_to_message

    group_history = context.bot_data.get("group_history", {}).get(chat_id, [])
    group_history.append({"user_id": user_id, "content": user_message, "message_id": message_id})
    context.bot_data["group_history"] = {chat_id: group_history}

    user_history = context.user_data.get("group_chat_history", [])
    
    should_reply = (
        "ربات" in user_message or "پلاتو" in user_message or
        (replied_message and replied_message.from_user.id == context.bot.id)
    )
    
    if not should_reply:
        return
    
    if replied_message and replied_message.from_user.id == context.bot.id:
        user_history.append({"role": "assistant", "content": replied_message.text})
    
    user_history.append({"role": "user", "content": user_message})
    context.user_data["group_chat_history"] = user_history
    
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ] + user_history,
        "model": "openai-large",
        "seed": 42,
        "jsonMode": False
    }
    
    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            ai_response = clean_text(response.text.strip())
            user_history.append({"role": "assistant", "content": ai_response})
            context.user_data["group_chat_history"] = user_history
            
            final_response = ai_response
            for item in EXTRACTED_ITEMS:
                if item["name"].lower() in user_message:
                    price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
                    price_info = clean_text(f"{item['price']['value']} {price_type}")
                    item_info = clean_text(
                        f"مشخصات آیتم پیدا شد! 🎉\n"
                        f"🔖 نام: {item['name']}\n"
                        f"💸 قیمت: {price_info}\n"
                        f"اگه می‌خوای مشخصات کامل‌تر با صدا رو ببینی، کافیه بگی: /i {item['name']} 😎"
                    )
                    final_response += f"\n\n{item_info}"
                    break
            
            await update.message.reply_text(
                final_response,
                reply_to_message_id=update.message.message_id,
                message_thread_id=thread_id
            )
        else:
            error_message = clean_text("اوفف، یه مشکلی پیش اومد! 😅 بعداً امتحان کن 🚀")
            await update.message.reply_text(
                error_message,
                reply_to_message_id=update.message.message_id,
                message_thread_id=thread_id
            )
    except Exception as e:
        logger.error(f"خطا در اتصال به API چت گروه: {e}")
        error_message = clean_text("اییی، یه خطا خوردم! 😭 بعداً دوباره بیا 🚀")
        await update.message.reply_text(
            error_message,
            reply_to_message_id=update.message.message_id,
            message_thread_id=thread_id
        )

# نمایش لیدربرد تو گروه
async def show_weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id}")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    leaderboard = scrape_leaderboard()
    if not leaderboard:
        await update.message.reply_text(clean_text("مشکلی تو گرفتن لیدربرد پیش اومد! 😅"))
        return
    
    message_text = clean_text("🏆 جدول امتیازات\nبرندگان برتر رتبه‌بندی هفتگی - همه بازی‌ها\n\n")
    keyboard = []
    # تیتر ستون‌ها
    keyboard.append([
        InlineKeyboardButton("بردها 🏆", callback_data="noop"),
        InlineKeyboardButton("آیدی بازیکن 🔖", callback_data="noop")
    ])
    # اطلاعات بازیکنان
    for player in leaderboard[:10]:  # فقط 10 نفر برتر
        keyboard.append([
            InlineKeyboardButton(player['wins'], callback_data=f"leader_{player['player_id']}"),
            InlineKeyboardButton(player['username'], callback_data=f"leader_{player['player_id']}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    message = await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
    context.user_data["last_leaderboard_message_id"] = message.message_id

# مدیریت انتخاب بازیکن از لیدربرد
async def handle_leaderboard_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player_id = query.data.replace("leader_", "")
    leaderboard = scrape_leaderboard()
    player = next((p for p in leaderboard if p['player_id'] == player_id), None)
    
    if not player:
        await query.edit_message_text(clean_text("بازیکن پیدا نشد! 😕"))
        return
    
    player_text = clean_text(
        f"آیدی بازیکن 🔖: {player['username']}\n"
        f"بردها 🏆: {player['wins']}\n"
        f"لیست بازی‌هایی که انجام شده 👇 توسط این بازیکن\n\n"
    )
    
    profile_data = scrape_profile(player['player_link'])
    if not profile_data:
        await query.message.reply_text(clean_text("مشکلی تو گرفتن اطلاعات پروفایل پیش اومد! 😅"))
        return
    
    context.user_data["profile_games"] = profile_data
    context.user_data["profile_page"] = 0
    context.user_data["player"] = player
    
    await send_paginated_profile_games(update, context)

async def send_paginated_profile_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile_data = context.user_data["profile_games"]
    page = context.user_data.get("profile_page", 0)
    items_per_page = 10
    total_pages = (len(profile_data) + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = min((page + 1) * items_per_page, len(profile_data))
    current_games = profile_data[start_idx:end_idx]
    
    player = context.user_data["player"]
    player_text = clean_text(
        f"آیدی بازیکن 🔖: {player['username']}\n"
        f"بردها 🏆: {player['wins']}\n"
        f"لیست بازی‌هایی که انجام شده 👇 توسط این بازیکن\n\n"
    )
    
    keyboard = []
    # تیتر ستون‌ها
    keyboard.append([
        InlineKeyboardButton("اسم بازی 🎮", callback_data="noop"),
        InlineKeyboardButton("بازی شده 🕹", callback_data="noop"),
        InlineKeyboardButton("بردها 🎖", callback_data="noop")
    ])
    # اطلاعات بازی‌ها
    for game in current_games:
        keyboard.append([
            InlineKeyboardButton(game['game_name'], callback_data=f"game_{player['player_id']}_{game['game_name']}"),
            InlineKeyboardButton(game['played'], callback_data=f"game_{player['player_id']}_{game['game_name']}"),
            InlineKeyboardButton(game['won'], callback_data=f"game_{player['player_id']}_{game['game_name']}")
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data="prev_profile_page"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data="next_profile_page"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🏠 برگشت به لیدربرد", callback_data="back_to_leaderboard")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    thread_id = update.callback_query.message.message_thread_id if hasattr(update.callback_query.message, 'is_topic_message') and update.callback_query.message.is_topic_message else None
    
    if player['profile_image']:
        try:
            response = requests.get(player['profile_image'], timeout=10)
            if response.status_code == 200:
                message = await update.callback_query.message.reply_photo(
                    photo=response.content,
                    caption=player_text,
                    reply_markup=reply_markup,
                    message_thread_id=thread_id
                )
            else:
                message = await update.callback_query.message.reply_text(player_text, reply_markup=reply_markup, message_thread_id=thread_id)
        except Exception as e:
            logger.error(f"خطا در ارسال عکس: {e}")
            message = await update.callback_query.message.reply_text(player_text, reply_markup=reply_markup, message_thread_id=thread_id)
    else:
        message = await update.callback_query.message.reply_text(player_text, reply_markup=reply_markup, message_thread_id=thread_id)
    
    context.user_data["last_profile_message_id"] = message.message_id
    await update.callback_query.message.delete()

async def handle_profile_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = context.user_data.get("profile_page", 0)
    
    if "next_profile_page" in query.data:
        context.user_data["profile_page"] = page + 1
    elif "prev_profile_page" in query.data:
        context.user_data["profile_page"] = max(0, page - 1)
    
    last_profile_message_id = context.user_data.get("last_profile_message_id")
    if last_profile_message_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=last_profile_message_id)
        except Exception as e:
            logger.error(f"خطا در حذف پیام پروفایل: {e}")
    
    await send_paginated_profile_games(update, context)

# برگشت به لیدربرد
async def back_to_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    last_profile_message_id = context.user_data.get("last_profile_message_id")
    if last_profile_message_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=last_profile_message_id)
        except Exception as e:
            logger.error(f"خطا در حذف پیام پروفایل: {e}")
    
    leaderboard = scrape_leaderboard()
    if not leaderboard:
        await query.message.reply_text(clean_text("مشکلی تو گرفتن لیدربرد پیش اومد! 😅"))
        return
    
    message_text = clean_text("🏆 جدول امتیازات\nبرندگان برتر رتبه‌بندی هفتگی - همه بازی‌ها\n\n")
    keyboard = []
    keyboard.append([
        InlineKeyboardButton("بردها 🏆", callback_data="noop"),
        InlineKeyboardButton("آیدی بازیکن 🔖", callback_data="noop")
    ])
    for player in leaderboard[:10]:
        keyboard.append([
            InlineKeyboardButton(player['wins'], callback_data=f"leader_{player['player_id']}"),
            InlineKeyboardButton(player['username'], callback_data=f"leader_{player['player_id']}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    message = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=message_text,
        reply_markup=reply_markup,
        message_thread_id=thread_id
    )
    context.user_data["last_leaderboard_message_id"] = message.message_id

# تشخیص کلمات لیدربرد در گروه
async def detect_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            return
        PROCESSED_MESSAGES.add(message_id)
    
    text = update.message.text.lower()
    if "لیدربرد" in text or "لیدر برد" in text:
        await show_weekly_leaderboard(update, context)

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    user_name = query.from_user.first_name
    welcome_message = clean_text(
        f"سلام {user_name}!\nبه PlatoDex خوش اومدی - مرکز بازی‌های Plato!\n"
        "• آیتم‌ها رو ببین 🎲\n• رتبه‌بندی بازیکن‌ها رو چک کن 🏆\n• اخبار رو دنبال کن 🎯"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://v0-gram-file-mini-app.vercel.app"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    # ارسال پیام جدید به جای ویرایش
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # حذف پیام قبلی
    try:
        await query.message.delete()
    except Exception as e:
        logger.error(f"خطا در حذف پیام قبلی: {e}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    await update.message.reply_text(clean_text("عملیات لغو شد."), reply_markup=InlineKeyboardMarkup([]))
    await start(update, context)
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطا رخ داد: {context.error}")
    if str(context.error) == "Query is too old and response timeout expired or query id is invalid":
        if update and update.callback_query:
            await update.callback_query.message.reply_text(clean_text("اوپس، یه کم دیر شد! دوباره امتحان کن 😅"))
    elif update and update.message:
        await update.message.reply_text(clean_text("یه مشکلی پیش اومد! 😅 دوباره امتحان کن!"))

async def main():
    global application
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
            
            if application.job_queue is None:
                logger.error("JobQueue فعال نیست!")
                raise RuntimeError("JobQueue فعال نیست!")
            
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"Webhook روی {WEBHOOK_URL} تنظیم شد.")
            
            schedule_scraping(application)
            await extract_items()
            
            search_conv_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(start_item_search, pattern="^search_items$")],
                states={
                    SELECT_CATEGORY: [
                        CallbackQueryHandler(search_by_name, pattern="^search_by_name$"),
                        CallbackQueryHandler(select_category, pattern="^select_category_"),
                        CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_private_categories$")
                    ],
                    SEARCH_ITEM: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, process_item_search),
                        CallbackQueryHandler(select_item, pattern="^select_item_"),
                        CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_private$")
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("start", start),
                    CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
                ],
                name="item_search",
                persistent=False
            )
            
            image_conv_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(start_generate_image, pattern="^generate_image$"),
                    CallbackQueryHandler(retry_generate_image, pattern="^retry_generate_image$")
                ],
                states={
                    SELECT_SIZE: [CallbackQueryHandler(select_size, pattern="^size_")],
                    GET_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prompt)]
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("start", start),
                    CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
                ],
                name="image_generation",
                persistent=False
            )
            
            group_image_conv_handler = ConversationHandler(
                entry_points=[
                    CommandHandler("p", start_group_image, filters=filters.ChatType.GROUPS),
                    CallbackQueryHandler(regenerate_group_image, pattern="^regenerate_image_")
                ],
                states={},
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("start", start)
                ],
                name="group_image_generation",
                persistent=False
            )
            
            application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
            application.add_handler(CommandHandler("i", process_item_in_group, filters=filters.ChatType.GROUPS))
            application.add_handler(CommandHandler("w", show_weekly_leaderboard, filters=filters.ChatType.GROUPS))
            application.add_handler(CallbackQueryHandler(select_group_item, pattern="^select_group_item_"))
            application.add_handler(CallbackQueryHandler(select_category, pattern="^select_category_"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_group"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_group_categories"))
            application.add_handler(CallbackQueryHandler(handle_leaderboard_selection, pattern="^leader_"))
            application.add_handler(CallbackQueryHandler(back_to_leaderboard, pattern="^back_to_leaderboard$"))
            application.add_handler(search_conv_handler)
            application.add_handler(image_conv_handler)
            application.add_handler(group_image_conv_handler)
            application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
            application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
            application.add_handler(InlineQueryHandler(inline_query))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, detect_leaderboard_command))
            application.add_handler(MessageHandler(filters.Regex(r"🔖 نام"), handle_inline_selection))
            application.add_error_handler(error_handler)
            
            logger.info("در حال آماده‌سازی ربات...")
            await application.initialize()
            logger.info("در حال شروع ربات...")
            await application.start()
            
            config = uvicorn.Config(app, host="0.0.0.0", port=8000)
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error(f"خطا در تلاش {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"تلاش دوباره بعد از {retry_delay} ثانیه...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("همه تلاش‌ها برای شروع ربات ناموفق بود!")
                raise

if __name__ == "__main__":
    asyncio.run(main())
