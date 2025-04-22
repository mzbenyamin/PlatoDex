from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import requests
from bs4 import BeautifulSoup
import json
import re
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
    # ... بقیه SYSTEM_MESSAGE بدون تغییر ...
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

async def extract_items(context: ContextTypes.DEFAULT_TYPE = None):
    global EXTRACTED_ITEMS
    EXTRACTED_ITEMS = []
    max_retries = 7  # افزایش تعداد تلاش‌ها
    retry_delay = random.uniform(10, 15)  # تأخیر تصادفی
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://platopedia.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    def guess_item_info(image_path: str) -> tuple[str, str]:
        path = image_path.lower()
        category = "Unknown"
        name_guess = "Unknown Item"
        if "badges" in path:
            category = "Badge"
            name_guess = "Badge " + path.split("/")[-1].replace("iap_badge_", "").replace("_preview.webp", "")
        elif "banners" in path:
            category = "Banner"
            name_guess = "Banner " + path.split("/")[-1].replace("iap_banner_", "").replace("_asset.webp", "")
        elif "frames" in path:
            category = "Frame"
            name_guess = "Frame " + path.split("/")[-1].replace("iap_frame_", "").replace("_preview.webp", "")
        elif "gameupgrades" in path:
            if "pool" in path:
                category = "Game - Pool (Cue)" if "cue" in path else "Game - Pool (Table)"
            elif "ocho" in path:
                category = "Game - Ocho"
            elif "tablesoccer" in path:
                category = "Game - Table Soccer (Team)"
            elif "fourinarow" in path:
                category = "Game - 4 in a Row (Token)"
            name_guess = f"{category} {path.split('/')[-1].replace('iap_game_', '').replace('_preview.webp', '')}"
        elif "bubbles" in path:
            category = "Chat"
            name_guess = "Chat Bubble " + path.split("/")[-1].replace("iap_bubble_", "").replace("_preview.webp", "")
        return category, name_guess

    for attempt in range(max_retries):
        try:
            logger.info(f"تلاش {attempt + 1} برای اسکرپ آیتم‌ها از {URL}")
            response = requests.get(URL, headers=headers, timeout=60)
            logger.info(f"وضعیت پاسخ: {response.status_code}, متن پاسخ: {response.text[:200]}")

            if response.status_code != 200:
                logger.error(f"خطا در درخواست HTTP: {response.status_code}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            # جستجوی داده‌های JSON
            items_data = {}
            script_tags = soup.find_all("script")
            for tag in script_tags:
                script_content = tag.string
                if script_content and "var items = {" in script_content:
                    items_match = re.search(r"var items = ({.*?});", script_content, re.DOTALL)
                    if items_match and items_match[1]:
                        try:
                            items_data = json.loads(items_match[1])
                            logger.info(f"داده‌های JSON پیدا شد با {len(items_data)} آیتم")
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"خطا در پارس JSON: {e}")

            # استخراج جزئیات از جدول
            item_details = {}
            table = soup.find(id="tool_items_table_default")
            if table:
                rows = table.find("tbody").find_all("tr")
                logger.info(f"{len(rows)} ردیف در جدول آیتم‌ها پیدا شد")
                for row in rows:
                    item_id = row.get("id", "").replace("id-", "")
                    if not item_id:
                        continue
                    cols = row.find_all("td")
                    item_columns = {}
                    for i, col in enumerate(cols, 1):
                        item_columns[f"column_{i}"] = col.get_text(strip=True)
                    price_text = item_columns.get("column_4", "0")
                    price_match = re.search(r"\d[\d,]*", price_text)
                    price_value = int(price_match.group().replace(",", "")) if price_match else 0
                    price_type = "premium" if price_value < 100 else "coins"
                    item_details[item_id] = {
                        "columns": item_columns,
                        "price": {"value": price_value, "type": price_type},
                    }

            # پردازش آیتم‌ها
            for item_id, item_info in items_data.items():
                try:
                    med = item_info.get("med", {})
                    images = [BASE_IMAGE_URL + img["uri"] for img in med.get("images", [])]
                    audios = [
                        {
                            "uri": audio["uri"],
                            "type": audio.get("type", "audio/mp4"),
                            "title": audio.get("title", f"{item_id} Audio")
                        }
                        for audio in med.get("audios", []) if audio.get("uri")
                    ]

                    details = item_details.get(item_id, {})
                    columns = details.get("columns", {})
                    category, name_guess = guess_item_info(images[0] if images else "")

                    extracted_item = {
                        "id": str(item_id),
                        "name": columns.get("column_3", name_guess),
                        "category": columns.get("column_2", category),
                        "description": columns.get("column_5", "بدون توضیحات"),
                        "images": images,
                        "audios": audios,
                        "price": details.get("price", {"value": 0, "type": "unknown"})
                    }
                    EXTRACTED_ITEMS.append(extracted_item)
                except Exception as e:
                    logger.error(f"خطا در پردازش آیتم {item_id}: {e}")

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
    
    if not query.data.startswith("regenerate_image_"):
        await query.message.reply_text(clean_text("خطایی رخ داد! لطفاً دوباره امتحان کنید. 😅"))
        return ConversationHandler.END
    
    prompt = query.data.replace("regenerate_image_", "", 1)
    if not prompt:
        await query.message.reply_text(clean_text("پرامپت تصویر پیدا نشد! لطفاً دوباره امتحان کنید. 😅"))
        return ConversationHandler.END
    
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    chat_id = query.message.chat_id
    
    last_image_message_id = context.user_data.get("last_image_message_id")
    if last_image_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_image_message_id)
        except Exception as e:
            logger.error(f"خطا در حذف تصویر قبلی: {e}")
    
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
                "🖌️ لطفاً متنی که میخوای به عکس تبدیل بشه رو به انگلیسی بفرست!\n\n"
                "برای مثال مثلا:\n/p a woman"
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
    if not EXTRACTED_ITEMS:
        await query.edit_message_text(clean_text("هیچ آیتمی پیدا نشد! 😕 لطفاً بعداً امتحان کنید."))
        return ConversationHandler.END
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
    matching_items = context.user_data.get("matching_items", [])
    if not matching_items:
        message_text = clean_text("هیچ آیتمی پیدا نشد! 😕")
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]] if not is_group else []
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_group and update.message:
            thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
            await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
        elif update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
        return
    
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
        if not EXTRACTED_ITEMS:
            await update.message.reply_text(
                clean_text("هیچ آیتمی پیدا نشد! 😕 لطفاً بعداً امتحان کنید."),
                message_thread_id=thread_id
            )
            return
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
    categories = context.user_data.get("categories", [])
    if not categories:
        message_text = clean_text("هیچ دسته‌بندی‌ای پیدا نشد! 😕 لطفاً بعداً امتحان کنید.")
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]] if not is_group else []
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_group and update.message:
            thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
            await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
        elif update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
        return
    
    page = context.user_data.get("page", 0)
    categories_per_page = 10
    total_pages = (len(categories) + categories_per_page - 1) // categories_per_page
    
    start_idx = page * categories_per_page
    end_idx = min((page + 1) * categories_per_page, len(categories))
    current_categories = categories[start_idx:end_idx]
    
    keyboard = []
    for i, category in enumerate(current_categories, start_idx + 1):
        button_text = clean_text(f"{i}. {category}")
        callback_data = f"select_category_{category}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
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
        message = await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
    elif update.callback_query:
        message = await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        message = await update.message.reply_text(message_text, reply_markup=reply_markup)
    context.user_data["last_categories_message_id"] = message.message_id

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("select_category_", "")
    matching_items = [item for item in EXTRACTED_ITEMS if item["category"] == category]
    
    if not matching_items:
        await query.edit_message_text(clean_text(f"هیچ آیتمی در دسته‌بندی '{category}' پیدا نشد! 😕"))
        return SELECT_CATEGORY
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    await send_paginated_items(update, context, is_group=False)
    return SEARCH_ITEM

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    pattern = query.data
    is_group = "group" in pattern
    is_categories = "categories" in pattern
    
    page = context.user_data.get("page", 0)
    if "prev_page" in pattern:
        page = max(0, page - 1)
    elif "next_page" in pattern:
        page += 1
    
    context.user_data["page"] = page
    
    if is_categories:
        await send_paginated_categories(update, context, is_group=is_group)
    else:
        await send_paginated_items(update, context, is_group=is_group)
    
    return SEARCH_ITEM if not is_categories else SELECT_CATEGORY

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    AI_CHAT_USERS.add(user_id)
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    await query.edit_message_text(
        clean_text("🤖 حالا می‌تونی با هوش مصنوعی گپ بزنی! هر چی دوست داری بپرس، من اینجام! 😎"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS:
        return
    
    user_message = update.message.text.strip()
    if not user_message:
        await update.message.reply_text(clean_text("چیزی نگفتی که! 😅 یه چیزی بگو!"))
        return
    
    loading_message = await update.message.reply_text(clean_text("🤖 صبر کن، دارم فکر می‌کنم..."))
    
    try:
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_message}
        ]
        headers = {"Content-Type": "application/json"}
        response = requests.post(TEXT_API_URL, json={"messages": messages}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            ai_response = response.text.strip()
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            await update.message.reply_text(clean_text(ai_response))
        else:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            await update.message.reply_text(clean_text("مشکلی پیش اومد! 😅 بعداً دوباره امتحان کن."))
    except Exception as e:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        await update.message.reply_text(clean_text("اوفف، یه خطایی پیش اومد! 😅 بعداً دوباره امتحان کن!"))
        logger.error(f"خطا در چت هوش مصنوعی: {e}")

async def handle_group_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    user_message = update.message.text.strip()
    if not user_message:
        return
    
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    
    loading_message = await update.message.reply_text(
        clean_text("🤖 صبر کن، دارم فکر می‌کنم..."),
        message_thread_id=thread_id
    )
    
    try:
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_message}
        ]
        headers = {"Content-Type": "application/json"}
        response = requests.post(TEXT_API_URL, json={"messages": messages}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            ai_response = response.text.strip()
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            await update.message.reply_text(
                clean_text(ai_response),
                message_thread_id=thread_id,
                reply_to_message_id=update.message.message_id
            )
        else:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            await update.message.reply_text(
                clean_text("مشکلی پیش اومد! 😅 بعداً دوباره امتحان کن."),
                message_thread_id=thread_id
            )
    except Exception as e:
        await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        await update.message.reply_text(
            clean_text("اوفف، یه خطایی پیش اومد! 😅 بعداً دوباره امتحان کن!"),
            message_thread_id=thread_id
        )
        logger.error(f"خطا در چت گروهی هوش مصنوعی: {e}")

async def select_group_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    item_id = query.data.replace("select_group_item_", "")
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    
    if not item:
        thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
        await query.message.reply_text(clean_text("آیتم پیدا نشد! 😕"), message_thread_id=thread_id)
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
    
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    if item["images"]:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=item["images"][0],
            caption=results_text,
            message_thread_id=thread_id
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=results_text,
            message_thread_id=thread_id
        )
    
    for i, audio_info in enumerate(item["audios"], 1):
        await send_audio(update, context, item, audio_info, i, None, thread_id)

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    welcome_message = clean_text(
        f"سلام {query.from_user.first_name}!\nبه PlatoDex خوش اومدی - مرکز بازی‌های Plato!\n"
        "• آیتم‌ها رو ببین 🎲\n• رتبه‌بندی بازیکن‌ها رو چک کن 🏆\n• اخبار رو دنبال کن 🎯"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://v0-gram-file-mini-app.vercel.app"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await query.edit_message_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطا رخ داد: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(clean_text("اوفف، یه خطایی پیش اومد! 😅 بعداً دوباره امتحان کن!"))

def main():
    global application
    application = Application.builder().token(TOKEN).build()
    
    item_search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_item_search, pattern="search_items")],
        states={
            SEARCH_ITEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_item_search),
                CallbackQueryHandler(select_item, pattern=r"select_item_"),
                CallbackQueryHandler(back_to_items, pattern="back_to_items"),
                CallbackQueryHandler(handle_pagination, pattern=r"(prev_page_private|next_page_private)")
            ],
            SELECT_CATEGORY: [
                CallbackQueryHandler(search_by_name, pattern="search_by_name"),
                CallbackQueryHandler(select_category, pattern=r"select_category_"),
                CallbackQueryHandler(handle_pagination, pattern=r"(prev_page_private_categories|next_page_private_categories)")
            ]
        },
        fallbacks=[CallbackQueryHandler(back_to_home, pattern="back_to_home")],
        per_message=True
    )
    
    generate_image_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_generate_image, pattern="generate_image")],
        states={
            SELECT_SIZE: [
                CallbackQueryHandler(select_size, pattern=r"size_\d+x\d+"),
            ],
            GET_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_prompt),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(back_to_home, pattern="back_to_home"),
            CallbackQueryHandler(retry_generate_image, pattern="retry_generate_image")
        ],
        per_message=True
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(item_search_conv)
    application.add_handler(generate_image_conv)
    application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="chat_with_ai"))
    application.add_handler(CallbackQueryHandler(select_group_item, pattern=r"select_group_item_"))
    application.add_handler(CallbackQueryHandler(handle_pagination, pattern=r"(prev_page_group|next_page_group|prev_page_group_categories|next_page_group_categories)"))
    application.add_handler(CommandHandler("i", process_item_in_group))
    application.add_handler(CommandHandler("p", start_group_image))
    application.add_handler(CallbackQueryHandler(regenerate_group_image, pattern=r"regenerate_image_"))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(MessageHandler(filters.Regex(r"@PlatoDex\s+\w+"), handle_inline_selection))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))
    application.add_error_handler(error_handler)
    
    schedule_scraping(application)
    
    application.run_webhook(
        listen="0.0.0.0",
        port=8000,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
