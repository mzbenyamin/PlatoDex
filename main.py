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
from PIL import Image
import io
import tempfile
import os
from threading import Lock
import random
from typing import List, Dict, Optional, Union
import uvicorn

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

# پیام سیستم (خالی برای وارد کردن دستی)
SYSTEM_MESSAGE = (
    "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید و به صورت خودمونی جذاب و با ایموجی "
    "حرف میزنی به صورت نسل Z و کمی با طنز حرف بزن و شوخی کنه\\. به مشخصات آیتم‌های پلاتو دسترسی داری و می‌تونی "
    "به سوالات کاربر در مورد آیتم‌ها جواب بدی و راهنمایی کنی چطور با دستور /i مشخصات کامل رو بگیرن\\. "
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
    "نسخه افلاطون: کنار نسخه اصلی نصب کن، از ربات بگیر\\.\\n"
    "متاسفانه از تاریخ 28 فروردین 1404 پلاتو سرور های قدیمی پلاتو که میشد باهاشون کلون کرد رو غیرفعال کرد و دسترسی رو محدود کرد اگر میخوای چند اکانت داشته باشی حتما ایمیل روشون ثبت کن"
    "سلاطین پلاتو ترفندای بیشتر تو @salatin_plato منتظرته! 😎\n\n"
    "شما دیگر نمی توانید فرند ها یا دوستان کاربران دیگر رو ببینید چون اپلیکشن های قدیمی پلاتو که این کار رو میکردند غیرفعال شدند"
    "این پیام آموزشی رو توی هر پاسخ تکرار نکن، فقط توی ذهنت نگه دار و بر اساسش عمل کن و پاسخ بده\\."
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

# تعریف کلاس PlatoItem
class PlatoItem:
    def __init__(
        self,
        id: str,
        name: str,
        category: str,
        description: str,
        price: Dict[str, Union[int, str]],
        images: List[str],
        audios: Optional[List[Dict[str, str]]] = None
    ):
        self.id = id
        self.name = name
        self.category = category
        self.description = description
        self.price = price
        self.images = images
        self.audios = audios

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "price": self.price,
            "images": self.images,
            "audios": self.audios
        }

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
        return leaderboard_data[:10]
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
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

            # استخراج داده‌های آیتم‌ها از اسکریپت
            items_data = {}
            script_tags = soup.find_all("script")
            for tag in script_tags:
                script_content = tag.string or ""
                # بررسی برای var items
                if "var items = {" in script_content:
                    match = re.search(r"var items = ({.*?});", script_content, re.DOTALL)
                    if match and match.group(1):
                        try:
                            items_data = json.loads(match.group(1))
                            logger.info(f"داده‌های آیتم‌ها پیدا شد (var items): {len(items_data)} آیتم")
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"خطا در تجزیه JSON آیتم‌ها (var items): {e}")
                            continue
                # بررسی برای __PRELOADED_STATE__
                elif "__PRELOADED_STATE__" in script_content:
                    match = re.search(r"window\.__PRELOADED_STATE__ = ({.*?});", script_content, re.DOTALL)
                    if match and match.group(1):
                        try:
                            preload_data = json.loads(match.group(1))
                            items_data = preload_data.get("items", {}) or preload_data.get("data", {}).get("items", {})
                            logger.info(f"داده‌های آیتم‌ها پیدا شد (__PRELOADED_STATE__): {len(items_data)} آیتم")
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"خطا در تجزیه JSON آیتم‌ها (__PRELOADED_STATE__): {e}")
                            continue

            if not items_data:
                logger.error("داده‌های آیتم‌ها در اسکریپت پیدا نشد!")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            # استخراج جزئیات آیتم‌ها از جدول
            item_details = {}
            table = soup.find(id="tool_items_table_default")
            if table:
                rows = table.find("tbody").find_all("tr")
                logger.info(f"تعداد ردیف‌های جدول: {len(rows)}")
                for row in rows:
                    item_id = row.get("id", "").replace("id-", "")
                    if not item_id:
                        continue
                    cols = row.find_all("td")
                    item_columns = {f"column_{i+1}": col.get_text(strip=True) for i, col in enumerate(cols)}
                    price_text = item_columns.get("column_4", "0")
                    price_match = re.search(r"\d[\d,]*", price_text)
                    price_value = int(price_match.group(0).replace(",", "")) if price_match else 0
                    price_type = "premium" if price_value < 100 else "coins"
                    item_details[item_id] = {
                        "columns": item_columns,
                        "price": {"value": price_value, "type": price_type}
                    }

            # پردازش آیتم‌ها
            extracted_items = []
            for item_id, item_info in items_data.items():
                med = item_info.get("med", {})
                images = [BASE_IMAGE_URL + img["uri"] for img in med.get("images", [])]
                audios = [
                    {
                        "uri": audio["uri"],
                        "type": audio.get("type", "audio/mp4"),
                        "title": audio.get("title", f"{item_id} Audio")
                    }
                    for audio in med.get("audios", []) if med.get("audios")
                ] or []

                details = item_details.get(item_id, {})
                columns = details.get("columns", {})
                if columns:
                    extracted_item = PlatoItem(
                        id=item_id,
                        name=columns.get("column_3", "Unknown Item"),
                        category=columns.get("column_2", "Unknown"),
                        description=columns.get("column_5", "No description available"),
                        price=details.get("price", {"value": 0, "type": "unknown"}),
                        images=images,
                        audios=audios
                    )
                    extracted_items.append(extracted_item)

            EXTRACTED_ITEMS = [item.to_dict() for item in extracted_items]
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
    seed = random.randint(1, 999999)
    
    loading_message = await update.message.reply_text(clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."))
    
    api_url = f"{IMAGE_API_URL}{prompt}?width={width}&height={height}&nologo=true&seed={seed}"
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
    
    last_image_message_id = context.user_data.get("last_image_message_id")
    if last_image_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_image_message_id)
            logger.info(f"تصویر قبلی با ID {last_image_message_id} حذف شد.")
        except Exception as e:
            logger.error(f"خطا در حذف تصویر قبلی: {e}")
            await query.message.reply_text(clean_text("نشد تصویر قبلی رو پاک کنم، ولی یه تصویر جدید می‌سازم! 😅"))
    
    loading_message = await context.bot.send_message(
        chat_id=chat_id,
        text=clean_text("🖌️ در حال طراحی مجدد عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    seed = random.randint(1, 1000000)
    api_url = f"{IMAGE_API_URL}{prompt}?width=1024&height=1024&nologo=true&seed={seed}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 طراحی مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            original_message_id = context.user_data.get("original_message_id", query.message.reply_to_message.message_id)
            message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=response.content,
                caption=clean_text(f"🪄 پرامت تصویر ایجاد شده شما:\n\n{prompt}\n\n@PlatoDex"),
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
            clean_text(
                "🖌️ لطفاً متنی که می‌خوای به عکس تبدیل بشه رو به انگلیسی بفرست!\n\n"
                "مثلاً:\n/p a woman"
            ),
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
    seed = random.randint(1, 999999)
    loading_message = await update.message.reply_text(
        clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    api_url = f"{IMAGE_API_URL}{prompt}?width=1024&height=1024&nologo=true&seed={seed}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 طراحی مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=response.content,
                caption=clean_text(f"🪄 پرامت تصویر ایجاد شده شما:\n\n{prompt}\n\n@PlatoDex"),
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
    except Exception as e:
        await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        await update.message.reply_text(
            clean_text("خطایی رخ داد. لطفاً بعداً امتحان کنید."),
            message_thread_id=thread_id
        )
        logger.error(f"خطا در تولید تصویر گروه: {e}")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.message.reply_text(results_text, message_thread_id=thread_id)

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
        "ربات" in user_message or "پلاتو" in user_message or "سلام" in user_message or "خداحافظ" in user_message or
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
            await update.message.reply_text(ai_response, message_thread_id=thread_id)
        else:
            await update.message.reply_text(
                clean_text("مشکلی پیش اومد! 😅 بعداً دوباره امتحان کن 🚀"),
                message_thread_id=thread_id
            )
    except Exception as e:
        logger.error(f"خطا در اتصال به API چت گروه: {e}")
        await update.message.reply_text(
            clean_text("خطایی رخ داد! 😭 بعداً دوباره امتحان کن 🚀"),
            message_thread_id=thread_id
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    await update.message.reply_text(clean_text("عملیات لغو شد! 😊 هر وقت خواستی برگرد!"))
    return ConversationHandler.END

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    welcome_message = clean_text(
        "🏠 به منوی اصلی خوش اومدی!\n\nچی دوست داری انجام بدیم؟ 😎"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://v0-gram-file-mini-app.vercel.app"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await query.edit_message_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

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
                        CallbackQueryHandler(back_to_items, pattern="^back_to_items$"),
                        CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_private$")
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("start", start),
                    CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
                ],
                name="item_search",
                persistent=False,
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
                persistent=False,
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
                persistent=False,
            )

            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("cancel", cancel))
            application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
            application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
            application.add_handler(search_conv_handler)
            application.add_handler(image_conv_handler)
            application.add_handler(group_image_conv_handler)
            application.add_handler(InlineQueryHandler(inline_query))
            application.add_handler(MessageHandler(filters.Regex(r'^@PlatoDex\s+\w+'), process_item_in_group))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^@PlatoDex'), process_item_in_group))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inline_selection))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^@PlatoDex'), handle_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))

            port = int(os.getenv("PORT", 8000))
            config = uvicorn.Config(app, host="0.0.0.0", port=port)
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
