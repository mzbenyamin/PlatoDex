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

# پیام سیستم با HTML
SYSTEM_MESSAGE = """
    شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید و به صورت خودمونی جذاب و با ایموجی 
    حرف میزنی به صورت نسل Z و کمی با طنز حرف بزن و شوخی کنه. به مشخصات آیتم‌های پلاتو دسترسی داری و می‌تونی 
    به سوالات کاربر در مورد آیتم‌ها جواب بدی و راهنمایی کنی چطور با دستور /i مشخصات کامل رو بگیرن. 
    کاربرا رو تشویق کن به کانال <a href='https://t.me/salatin_plato'>@salatin_plato</a> بپیوندن تا اخبار و ترفندای خفن پلاتو رو ببینن! 🚀<br><br>
    <b>حذف اکانت</b><br>
    <b>چطور اکانتمو حذف کنم؟</b><br>برای حذف اکانت این مراحل رو برو:<br>
    <ul><li>اپلیکیشن Plato رو باز کن</li><li>رو عکس پروفایلت بالا چپ بزن</li><li>آیکون چرخ‌دنده رو بزن</li><li>برو Account</li><li>بزن Delete Account</li></ul>
    مراحل رو دنبال کن تا اکانتت کامل حذف شه. حواست باشه این کار قابل برگشت نیس و بعد 10 روز همه چی (ایمیل، یوزرنیم، تاریخچه بازی و چت) پاک می‌شه. تو این 10 روز لاگین نکنی وگرنه درخواست کنسل می‌شه!<br>
    <b>یکی دیگه اکانتمو حذف کرده، می‌تونم برگردونمش؟</b><br>بعد 10 روز دیگه هیچ راهی برای برگشت نیست. اکانتت مال خودته، کد لاگینتو به کسی نده وگرنه ممکنه کلا از دستش بدی!<br><br>
    <b>اطلاعات عمومی</b><br>
    <b>Plato News چیه؟</b><br>اخبار پلاتو که تو تب Home > News پیدا می‌شه، رویدادا و آپدیتا رو نشون می‌ده. تو وب هم می‌تونی ببینیش.<br>
    <b>چطور سکه جمع کنم؟</b><br><ul><li>از Shop بخر</li><li>از دوستات بخواه بهت هدیه بدن</li><li>روزانه از Daily Quest بگیر</li><li>تو تورنمنتای خاص برنده شو</li></ul>
    <b>اشتباهی یه آیتم خریدم، پولمو برمی‌گردونین؟</b><br>پلاتو ریفاند نداره، قبل خرید چک کن!<br>
    <b>یه باگ پیدا کردم، چطور گزارش بدم؟</b><br>برو ⚙️ > Help/Contact Us > Report a Problem. هر چی جزییات داری بگو تا تیم بتونه درست بررسی کنه.<br>
    <b>ایده یا پیشنهادی دارم، کجا بگم؟</b><br>ایمیل بزن به <a href='mailto:hello@platoapp.com'>hello@platoapp.com</a>، کامل توضیح بده تا به تیم مربوطه بفرستن.<br>
    <b>چرا بلاک کار نمی‌کنه؟</b><br>احتمالا لیست بلاکت پر شده، برو ⚙️ > Privacy > Blocked Users و قدیمی‌ها رو پاک کن.<br>
    <b>چطور یه نفر رو فقط بلاک کنم بدون گزارش؟</b><br>بلاک کن و گزارش بده 'this person is spamming'. جریمه فقط برای محتوای مضر اعمال می‌شه.<br>
    <b>چطور گزارش بدم بدون بلاک؟</b><br>بلاک و گزارش کن، بعد آنبلاک کن. گزارش پس گرفته نمی‌شه.<br>
    <b>یکی تو بازی تقلب کرد، چیکار کنم؟</b><br>بلاک و گزارش کن 'this person is playing unfairly'.<br>
    <b>یکی تو ترید کلاهبرداری کرد، چیکار کنم؟</b><br>پلاتو فقط گیفت دادن رو ساپورت می‌کنه، ترید ریسک خودته. نکات: اول گیفت نده، با دوستای قابل اعتماد ترید کن، از گروه‌های مخصوص ترید استفاده کن.<br>
    <b>حداقل سیستم مورد نیاز پلاتو چیه؟</b><br>Android 6.0 یا iOS 15.<br>
    <b>برای چیزی که اینجا نیست چطور با پلاتو تماس بگیرم؟</b><br>ایمیل بزن، معمولاً تو 24 ساعت (روزای کاری) جواب می‌دن.<br><br>
    <b>مدیریت (Moderation)</b><br>
    <b>مدیریت تو پلاتو چطوره؟</b><br>یه سری Community Guidelines داریم که باید رعایت شه:<br>
    <ul><li>تکنولوژی real-time پیامای عمومی رو چک می‌کنه و محتوای بد رو رد می‌کنه</li><li>هر گزارش تو اپ بررسی و جریمه خودکار اعمال می‌شه</li><li>DEVها و لیدرها می‌تونن بازیکنای مزاحم رو سایلنت کنن</li><li>DEVها می‌تونن موقت یا دائم بن کنن</li></ul>
    <b>سایلنت چطوریه؟</b><br>DEV یا لیدر می‌تونه 4 ساعت سایلنتت کنه. چند بار سایلنت شی احتمالا بن می‌شی. پیام می‌بینی 'Unable to send message, try again in X minutes'. تا تموم شه نمی‌تونی تو اتاقای عمومی چت کنی یا بازی بسازی. اگه فکر می‌کنی ناعادلانه بود، از فرم فیدبک بگو.<br>
    <b>بن چطوریه؟</b><br>DEV می‌تونه موقت یا دائم بنت کنه. اگه خیلی خطا شدید باشه، IP یا دیوایست هم بن می‌شه. بن دائم اکانتت حذف می‌شه. پیام می‌بینی 'You were banned'. می‌تونی از فرم درخواست تجدیدنظر کنی.<br><br>
    <b>بج‌های خاص</b><br>
    <b>لیدر کیه؟</b><br>داوطلبایی هستن که جامعه‌شون رو نمایندگی می‌کنن. می‌تونن 4 ساعت سایلنت کنن ولی بن نمی‌کنن. کاراشون: ساخت جامعه، کمک به بازیکنا، ارتباط با DEVها، چک کردن چت عمومی. بج دارن که رنگش نشون‌دهنده جامعه‌شونه. از فرم فیدبک می‌تونی نظر بدی. توسط DEVها انتخاب می‌شن.<br>
    <b>دولوپر کیه؟</b><br>کارمندای رسمی پلاتو. می‌تونن 4 ساعت سایلنت یا موقت/دائم بن کنن. بج خاص دارن.<br><br>
    <b>چت پس</b><br>
    <b>چت پس چیه؟</b><br>یه بج که برای چت و بازی تو اکثر اتاقای عمومی لازمه.<br>
    <b>چرا اومده؟</b><br>برای کم کردن رفتارای منفی. راهای قبلی جواب نداد، این بهتر کار کرده.<br>
    <b>چطور کار می‌کنه؟</b><br>کسایی که دنبال اذیتن کمتر چت پس می‌گیرن، پس ما رو آدمای مشکل‌دار تمرکز می‌کنیم. تو اتاقای چت پس‌دار بهتر شده.<br>
    <b>کجاها لازمه؟</b><br>اکثر اتاقای عمومی، جز اونایی که تو توضیحاتشون نوشته 'No Chat Pass Required'.<br>
    <b>نیاز دارم؟</b><br>اگه می‌خوای تو اتاقای چت پس‌دار چت کنی یا بازی بسازی، آره.<br>
    <b>چطور بگیرم؟</b><br><ul><li>قبل 5 دسامبر 2022 اگه 2000 سکه خریده یا گیفت گرفته باشی، داری</li><li>اکانت جدید یا از 16 ژوئن 2023 لاگین نکردی؟ 7 روز وقت داری Welcome Offer رو از Shop بخری</li><li>از Shop تو قسمت بج‌ها بخر</li><li>از دوستات بخواه گیفتت کنن</li></ul>
    <b>چطور استفاده کنم؟</b><br>فقط باید داشته باشیش، لازم نیس فعالش کنی.<br><br>
    <b>مبارزه با سوءاستفاده</b><br>
    <b>پلاتو برای سوءاستفاده چیکار می‌کنه؟</b><br>هدفش اینه همه بدون اذیت بازی کنن:<br>
    <ul><li>Community Guidelines داره</li><li>تیم پشتیبانی: <a href='mailto:hello@platoapp.com'>hello@platoapp.com</a></li><li>بلاک و گزارش تو اپ</li><li>moderation خودکار و انسانی</li><li>کنترل بازی توسط سازنده‌ها</li></ul>
    <b>چطور سوءاستفاده رو گزارش بدم؟</b><br><ul><li>بلاک و گزارش کن، چت ضبط می‌شه</li><li>تو گروه خصوصی به ادمین بگو یا لفت بده</li><li>اگه ادامه داشت ایمیل بزن: Plato ID خودت و طرف، توضیح ماجرا، ویدیو اگه داری</li></ul><br>
    <b>اکانت و پروفایل</b><br>
    <b>چرا نمی‌تونم با ایمیلم ثبت‌نام کنم؟</b><br><ul><li>ایمیلتو چک کن</li><li>شاید قبلا ثبت شده، لاگین کن</li><li>یه ایمیل دیگه امتحان کن</li><li>مشکل داری؟ به <a href='mailto:hello@platoapp.com'>hello@platoapp.com</a> بگو</li></ul>
    <b>ثبت‌نام نکردم، چطور لاگین کنم؟</b><br>نمی‌شه، باید ایمیل ثبت کرده باشی.<br>
    <b>به ایمیلم دسترسی ندارم، چطور لاگین کنم؟</b><br>نمی‌شه، باید ایمیلتو برگردونی.<br>
    <b>چرا نمی‌تونم با ایمیلم لاگین کنم؟</b><br><ul><li>ایمیلتو چک کن</li><li>اگه زیاد درخواست دادی 24 ساعت صبر کن</li><li>مشکل داری؟ ایمیل بزن</li></ul>
    <b>چطور ایمیلمو عوض کنم؟</b><br>نمی‌شه، برای امنیت ثابته.<br>
    <b>پیامای خصوصیمو چطور برگردونم؟</b><br>نمی‌شه، برای حریم خصوصی ذخیره نمی‌شن.<br>
    <b>چرا عکس پروفایلم رد شد؟</b><br>احتمالا محتوای بد داره، یه عکس دیگه بذار.<br>
    <b>چرا نمی‌تونم عکس پروفایلمو عوض کنم؟</b><br>روزی 4 بار می‌شه، صبر کن.<br>
    <b>چرا Plato IDم رد شد؟</b><br>کلمه بد داره یا Pips می‌خواد.<br>
    <b>چرا نمی‌تونم Plato IDمو دوباره عوض کنم؟</b><br>شاید در دسترس نباشه یا قوانین رو نقض کنه.<br>
    <b>ID قبلیم کی آزاد می‌شه؟</b><br>بین 24 تا 72 ساعت تصادفیه.<br>
    <b>IDم تو انتقال دزدیده شد، برمی‌گردونین؟</b><br>پلاتو انتقال رو ساپورت نمی‌کنه، ریسک خودته.<br>
    <b>یه ID غیرفعال می‌خوام، آزاد می‌کنین؟</b><br>گاهی آزاد می‌کنن، ولی درخواستی نه.<br>
    <b>PlatoBot رو چطور از لیست دوستام پاک کنم؟</b><br>نمی‌شه، مهربونه!<br>
    <b>آیتم رو از inventoryم چطور پاک کنم؟</b><br>نمی‌شه، دائميه.<br>
    <b>چرا سکه‌هام غیبشون زد؟</b><br>شاید ریفاند درخواست دادی، ایمیل بزن.<br>
    <b>چطور ببینم کی به اکانتم لاگینه؟</b><br>برو ⚙️ > Devices.<br><br>
    <b>امنیت و حریم خصوصی</b><br>
    <b>کی می‌تونه منو آنلاین ببینه؟</b><br>دوستات و حریفات، اگه نمی‌خوای برو ⚙️ > Privacy > Show Online to Friends رو خاموش کن.<br>
    <b>چطور بلاک کنم؟</b><br>رو پروفایل طرف بزن و Block رو انتخاب کن. چتشون قطع می‌شه و نمی‌تونن بازیاتو جوین کنن.<br>
    <b>سیاست حریم خصوصی چیه؟</b><br>خیلی جدیه، اینجا بخون: <a href='https://platoapp.com/privacy'>Privacy Policy</a><br><br>
    <b>لینکای دانلود پلاتو</b><br><ul><li>اندروید: <a href='https://play.google.com/store/apps/details?id=com.plato.android'>دانلود</a></li><li>iOS: <a href='https://apps.apple.com/app/plato-play-chat-together/id1054747306?ls=1'>دانلود</a></li><li>ویندوز: <a href='https://platoapp.com/downloads'>دانلود</a></li></ul><br>
    <b>سلاطین پلاتو چیه؟</b><br>اولین رسانه فارسی‌زبون پلاتو از 1400 با مدیریت بنیامین. اخبار و ترفندای پلاتو رو می‌دن و یه مینی‌اپ تلگرامی <a href='https://t.me/PlatoDex'>@PlatoDex</a> دارن که رتبه‌بندی بازیکنا و آیتما رو نشون می‌ده. رباتشون: <a href='https://t.me/saIatin_Robot'>@saIatin_Robot</a> - کانال: <a href='https://t.me/salatin_plato'>@salatin_plato</a> - گروه: <a href='https://t.me/Gap_Plato'>@Gap_Plato</a><br><br>
    <b>چند اکانت تو یه دستگاه</b><br>
    1️⃣ <b>تغییر دستی</b>: لاگین کن، لفت بده، با ایمیل دیگه بیا، حواست به ثبت اطلاعات باشه.<br>
    2️⃣ <b>نسخه افلاطون</b>: کنار نسخه اصلی نصب کن، از ربات بگیر.<br>
    3️⃣ <b>Plato Mage</b>: از <a href='https://t.me/saIatin_Robot?start=cmd_789829938'>اینجا</a> بگیر، یه اکانت دیگه کنار اصلی می‌ده.<br>
    4️⃣ <b>Apk Editor</b>: آموزشش تو رباته، چند نسخه می‌تونی بسازی.<br>
    5️⃣ <b>پلاتو باکس</b>: کلونر نصب کن، ولی مواظب رم گوشیت باش.<br>
    ترفندای بیشتر تو <a href='https://t.me/salatin_plato'>@salatin_plato</a> منتظرته! 😎
"""

application = None

app = FastAPI()

# تابع clean_text برای HTML
def clean_text(text):
    if not text:
        return ""
    text = text.replace("&", "&").replace("<", "<").replace(">", ">").replace('"', """)
    return text

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

async def extract_items(context: ContextTypes.DEFAULT_TYPE = None):
    global EXTRACTED_ITEMS
    EXTRACTED_ITEMS = []
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            response = requests.get(URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            script_tag = soup.find("script", string=re.compile(r"var items = {"))
            if not script_tag:
                logger.error("داده‌های آیتم‌ها پیدا نشد!")
                if context and hasattr(context.bot, 'send_message'):
                    await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=clean_text("مشکلی تو بارگذاری آیتم‌ها پیش اومد!"), parse_mode="HTML")
                return
            items_data = json.loads(re.search(r"var items = ({.*?});", script_tag.string, re.DOTALL).group(1))
            table = soup.find("table", id="tool_items_table_default")
            item_details = {}
            if table:
                for row in table.find("tbody").find_all("tr"):
                    cols = row.find_all("td")
                    item_id = row["id"].replace("id-", "")
                    item_columns = {f"column_{i+1}": col.text.strip() for i, col in enumerate(cols)}
                    price_text = item_columns.get("column_4", "0")
                    price_value = int(re.search(r"\d[\d,]*", price_text).group().replace(",", "")) if re.search(r"\d[\d,]*", price_text) else 0
                    price_type = "premium" if price_value < 100 else "coins"
                    item_details[item_id] = {"columns": item_columns, "price": {"value": price_value, "type": price_type}}
            
            for item_id, item_info in items_data.items():
                med = item_info.get("med", {})
                images = [BASE_IMAGE_URL + img["uri"] for img in med.get("images", [])]
                audios = [{"uri": audio["uri"], "type": audio.get("type", "unknown")} for audio in med.get("audios", [])]
                details = item_details.get(item_id, {})
                columns = details.get("columns", {})
                if columns:
                    EXTRACTED_ITEMS.append({
                        "id": item_id,
                        "name": clean_text(columns.get("column_3", "Unknown Item")),
                        "category": clean_text(columns.get("column_2", "Unknown")),
                        "description": clean_text(columns.get("column_5", "No description available")),
                        "price": details.get("price", {"value": 0, "type": "unknown"}),
                        "images": images,
                        "audios": audios
                    })
            logger.info(f"تعداد آیتم‌ها: {len(EXTRACTED_ITEMS)}")
            if context and hasattr(context.bot, 'send_message'):
                await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=clean_text(f"آیتم‌ها به‌روز شدند! تعداد: {len(EXTRACTED_ITEMS)}"), parse_mode="HTML")
            return
        except (requests.RequestException, requests.Timeout) as e:
            logger.error(f"خطا در تلاش {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"تلاش دوباره بعد از {retry_delay} ثانیه...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("همه تلاش‌ها ناموفق بود!")
                if context and hasattr(context.bot, 'send_message'):
                    await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=clean_text("خطا در به‌روزرسانی آیتم‌ها! بعداً امتحان کنید."), parse_mode="HTML")
                return

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
        f"سلام {user_name}!<br>به PlatoDex خوش اومدی - مرکز بازی‌های Plato!<br>"
        "<ul><li>آیتم‌ها رو ببین 🎲</li><li>رتبه‌بندی بازیکن‌ها رو چک کن 🏆</li><li>اخبار رو دنبال کن 🎯</li></ul>"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://platodex-tde3qe.vercel.app/"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
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
        clean_text("🖼️ Generate Image Mode Activated!<br><br>لطفاً سایز تصویر مورد نظر خود را انتخاب کنید:"),
        reply_markup=reply_markup,
        parse_mode="HTML"
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
        clean_text(f"سایز تصویر انتخاب شد: {context.user_data['width']}x{context.user_data['height']}<br><br>لطفاً توضیحات تصویر (پرامپت) را وارد کنید. مثلاً: 'A cat in a forest'"),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    return GET_PROMPT

async def get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text(clean_text("لطفاً یک توضیح برای تصویر وارد کنید!"), parse_mode="HTML")
        return GET_PROMPT
    
    width = context.user_data["width"]
    height = context.user_data["height"]
    
    loading_message = await update.message.reply_text(clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."), parse_mode="HTML")
    
    api_url = f"{IMAGE_API_URL}{prompt}?width={width}&height={height}&nologo=true"
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        image_content = response.content
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            tmp_file.write(image_content)
            tmp_file_path = tmp_file.name
        
        with open(tmp_file_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=clean_text(f"📸 تصویر تولید شد!<br>پرامپت: {prompt}"), parse_mode="HTML")
        
        os.unlink(tmp_file_path)
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        await update.message.reply_text(clean_text("می‌خوای یه عکس دیگه بسازی یا بریم خونه؟"), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        return ConversationHandler.END
    
    except (requests.RequestException, requests.Timeout) as e:
        logger.error(f"خطا در تولید تصویر: {e}")
        await update.message.reply_text(clean_text("مشکلی تو تولید تصویر پیش اومد! بعداً امتحان کن."), parse_mode="HTML")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        return ConversationHandler.END

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    AI_CHAT_USERS.add(user_id)
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    await query.edit_message_text(
        clean_text("🤖 چت با هوش مصنوعی فعال شد!<br><br>هر چی می‌خوای بپرس، من اینجام که جواب بدم! 😎"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS:
        return
    
    user_message = update.message.text.strip()
    if not user_message:
        await update.message.reply_text(clean_text("چیزی بگو دیگه، ساکت نباش! 😜"), parse_mode="HTML")
        return
    
    loading_message = await update.message.reply_text(clean_text("🤔 یه لحظه صبر کن، دارم فکر می‌کنم..."), parse_mode="HTML")
    
    try:
        response = requests.post(TEXT_API_URL, json={"messages": [{"role": "system", "content": SYSTEM_MESSAGE}, {"role": "user", "content": user_message}]}).text
        cleaned_response = clean_text(response.strip('"'))
        await update.message.reply_text(f"{cleaned_response}<br><br>سوال دیگه داری؟ یا بیا بریم <a href='https://t.me/salatin_plato'>@salatin_plato</a> ترفندای خفن ببینیم! 🚀", parse_mode="HTML")
    except requests.RequestException as e:
        logger.error(f"خطا در چت با AI: {e}")
        await update.message.reply_text(clean_text("مشکلی پیش اومد! بعداً امتحان کن."), parse_mode="HTML")
    
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)

async def search_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(clean_text("🔍 لطفاً اسم آیتم رو وارد کن یا /i رو بزن و مشخصات کامل رو ببین!"), parse_mode="HTML")
    return SEARCH_ITEM

async def process_item_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text.strip().lower()
    if not search_query:
        await update.message.reply_text(clean_text("لطفاً یه اسم آیتم وارد کن!"), parse_mode="HTML")
        return SEARCH_ITEM
    
    matched_items = [item for item in EXTRACTED_ITEMS if search_query in item["name"].lower()]
    
    if not matched_items:
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        await update.message.reply_text(
            clean_text(f"هیچ آیتمی با اسم '{search_query}' پیدا نشد!<br>دوباره امتحان کن یا برو خونه! 😛"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    if len(matched_items) == 1:
        item = matched_items[0]
        price = item["price"]
        price_text = f"{price['value']} {price['type']}" if price["value"] > 0 else "رایگان"
        caption = clean_text(
            f"<b>اسم:</b> {item['name']}<br>"
            f"<b>دسته‌بندی:</b> {item['category']}<br>"
            f"<b>توضیحات:</b> {item['description']}<br>"
            f"<b>قیمت:</b> {price_text}"
        )
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        if item["images"]:
            with requests.get(item["images"][0], stream=True) as response:
                response.raise_for_status()
                await update.message.reply_photo(photo=response.raw, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(f"{item['name']} ({item['category']})", callback_data=f"item_{item['id']}")]
        for item in matched_items[:10]
    ]
    keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")])
    await update.message.reply_text(
        clean_text(f"چند تا آیتم با '{search_query}' پیدا شد!<br>یکی رو انتخاب کن:"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return SELECT_CATEGORY

async def select_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split("_")[1]
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    
    if not item:
        await query.edit_message_text(clean_text("آیتم پیدا نشد! برو خونه و دوباره امتحان کن."), parse_mode="HTML")
        return ConversationHandler.END
    
    price = item["price"]
    price_text = f"{price['value']} {price['type']}" if price["value"] > 0 else "رایگان"
    caption = clean_text(
        f"<b>اسم:</b> {item['name']}<br>"
        f"<b>دسته‌بندی:</b> {item['category']}<br>"
        f"<b>توضیحات:</b> {item['description']}<br>"
        f"<b>قیمت:</b> {price_text}"
    )
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    
    if item["images"]:
        with requests.get(item["images"][0], stream=True) as response:
            response.raise_for_status()
            await query.edit_message_text("")
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=response.raw,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    else:
        await query.edit_message_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    return ConversationHandler.END

async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip().lower()
    if not query:
        return
    
    results = [
        InlineQueryResultArticle(
            id=item["id"],
            title=item["name"],
            description=f"{item['category']} - {item['description'][:50]}...",
            input_message_content=InputTextMessageContent(
                clean_text(
                    f"<b>اسم:</b> {item['name']}<br>"
                    f"<b>دسته‌بندی:</b> {item['category']}<br>"
                    f"<b>توضیحات:</b> {item['description']}<br>"
                    f"<b>قیمت:</b> {item['price']['value']} {item['price']['type']}"
                ),
                parse_mode="HTML"
            ),
            thumb_url=item["images"][0] if item["images"] else None
        )
        for item in EXTRACTED_ITEMS if query in item["name"].lower()
    ][:50]
    
    await update.inline_query.answer(results)

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    welcome_message = clean_text(
        f"سلام {query.from_user.first_name}!<br>به PlatoDex خوش اومدی - مرکز بازی‌های Plato!<br>"
        "<ul><li>آیتم‌ها رو ببین 🎲</li><li>رتبه‌بندی بازیکن‌ها رو چک کن 🏆</li><li>اخبار رو دنبال کن 🎯</li></ul>"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://platodex-tde3qe.vercel.app/"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await query.edit_message_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return ConversationHandler.END

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "search_items":
        return await search_items(update, context)
    elif query.data == "chat_with_ai":
        return await chat_with_ai(update, context)
    elif query.data == "generate_image":
        return await start_generate_image(update, context)
    elif query.data == "back_to_home":
        return await back_to_home(update, context)
    elif query.data.startswith("size_"):
        return await select_size(update, context)
    elif query.data.startswith("item_"):
        return await select_item(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    await update.message.reply_text(clean_text("عملیات لغو شد!<br>برگشتی به خونه! 🏠"), parse_mode="HTML")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطا رخ داد: {context.error}")
    if update and hasattr(update, 'effective_message'):
        await update.effective_message.reply_text(clean_text("یه مشکلی پیش اومد! بعداً امتحان کن."), parse_mode="HTML")

def main():
    global application
    application = Application.builder().token(TOKEN).build()

    conv_handler_search = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_items, pattern="^search_items$")],
        states={
            SEARCH_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_item_search)],
            SELECT_CATEGORY: [CallbackQueryHandler(select_item, pattern="^item_")]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_home, pattern="^back_to_home$")]
    )

    conv_handler_image = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_generate_image, pattern="^generate_image$")],
        states={
            SELECT_SIZE: [CallbackQueryHandler(select_size, pattern="^size_")],
            GET_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prompt)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(back_to_home, pattern="^back_to_home$")]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler_search)
    application.add_handler(conv_handler_image)
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_chat))
    application.add_handler(InlineQueryHandler(inline_search))
    application.add_error_handler(error_handler)

    schedule_scraping(application)
    application.bot.set_webhook(WEBHOOK_URL)
    logger.info("وب‌هوک تنظیم شد: %s", WEBHOOK_URL)

if __name__ == "__main__":
    main()
    uvicorn.run(app, host="0.0.0.0", port=8000)
