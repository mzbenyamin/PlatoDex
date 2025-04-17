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
import random  # برای تولید seed تصادفی

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
GET_GROUP_PROMPT = range(1)
DEFAULT_CHAT_ID = 789912945
PROCESSED_MESSAGES = set()
PROCESSING_LOCK = Lock()

SYSTEM_MESSAGE = (
    "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید و به صورت خودمونی جذاب و با ایموجی "
    "حرف میزنی به صورت نسل Z و کمی با طنز حرف بزن و شوخی کنه\\. به مشخصات آیتم‌های پلاتو دسترسی داری و می‌تونی "
    "به سوالات کاربر در مورد آیتم‌ها جواب بدی و راهنمایی کنی چطور با دستور /i مشخصات کامل رو بگیرن\\. "
    "کاربرا رو تشویق کن به کانال @salatin_plato بپیوندن تا اخبار و ترفندای خفن پلاتو رو ببینن! 🚀\n\n"
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

# توابع اسکرپ لیدربرد و پروفایل (بدون تغییر)
def scrape_leaderboard():
    # ... (مانند کد قبلی، بدون تغییر)
    return leaderboard_data[:10]

def scrape_profile(player_link):
    # ... (مانند کد قبلی، بدون تغییر)
    return games_data

async def extract_items(context: ContextTypes.DEFAULT_TYPE = None):
    global EXTRACTED_ITEMS
    EXTRACTED_ITEMS = []
    max_retries = 3
    retry_delay = 5
    # ... (مانند کد قبلی، بدون تغییر)
    logger.info(f"تعداد آیتم‌ها: {len(EXTRACTED_ITEMS)}")
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
        clean_text("📝 حالا یه توضیح (پرامپت) به انگلیسی برای تصویر بنویس! مثلاً: A flying car"),
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
    seed = random.randint(1, 1000000)  # تولید seed تصادفی
    
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
            await update.message.reply_photo(
                photo=response.content,
                caption=clean_text(f"🖼 پرامپ تصویر: {prompt}"),
                reply_markup=reply_markup
            )
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

async def start_group_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    
    if not context.args:
        await update.message.reply_text(
            clean_text("لطفاً یه توضیح برای تصویر بنویس به انگلیسی! مثلاً:\n/p A flying car"),
            message_thread_id=thread_id
        )
        return GET_GROUP_PROMPT
    
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            clean_text("لطفاً یه توضیح برای تصویر بنویس به انگلیسی! مثلاً:\n/p A flying car"),
            message_thread_id=thread_id
        )
        return GET_GROUP_PROMPT
    
    loading_message = await update.message.reply_text(
        clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    seed = random.randint(1, 1000000)  # تولید seed تصادفی
    api_url = f"{IMAGE_API_URL}{prompt}?width=2048&height=2048&nologo=true&seed={seed}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 تولید مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await update.message.reply_photo(
                photo=response.content,
                caption=clean_text(f"🖼 پرامپ تصویر: {prompt}"),
                reply_markup=reply_markup,
                message_thread_id=thread_id,
                reply_to_message_id=update.message.message_id
            )
            context.user_data["last_image_message_id"] = message.message_id
        else:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            await update.message.reply_text(
                clean_text("مشکلی در تولید تصویر پیش آمد. لطفاً دوباره امتحان کنید."),
                message_thread_id=thread_id
            )
    except Exception as e:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        await update.message.reply_text(
            clean_text("خطایی رخ داد. لطفاً بعداً امتحان کنید."),
            message_thread_id=thread_id
        )
        logger.error(f"خطا در تولید تصویر گروه: {e}")
    
    return ConversationHandler.END

async def get_group_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return GET_GROUP_PROMPT
        PROCESSED_MESSAGES.add(message_id)
    
    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text(
            clean_text("لطفاً یه توضیح برای تصویر بنویس به انگلیسی! مثلاً:\n/p A flying car")
        )
        return GET_GROUP_PROMPT
    
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    
    loading_message = await update.message.reply_text(
        clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    seed = random.randint(1, 1000000)  # تولید seed تصادفی
    api_url = f"{IMAGE_API_URL}{prompt}?width=2048&height=2048&nologo=true&seed={seed}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 تولید مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await update.message.reply_photo(
                photo=response.content,
                caption=clean_text(f"🖼 پرامپ تصویر: {prompt}"),
                reply_markup=reply_markup,
                message_thread_id=thread_id,
                reply_to_message_id=update.message.message_id
            )
            context.user_data["last_image_message_id"] = message.message_id
        else:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
            await update.message.reply_text(
                clean_text("مشکلی در تولید تصویر پیش آمد. لطفاً دوباره امتحان کنید."),
                message_thread_id=thread_id
            )
    except Exception as e:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        await update.message.reply_text(
            clean_text("خطایی رخ داد. لطفاً بعداً امتحان کنید."),
            message_thread_id=thread_id
        )
        logger.error(f"خطا در تولید تصویر گروه: {e}")
    
    return ConversationHandler.END

async def regenerate_group_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prompt = query.data.replace("regenerate_image_", "")
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    chat_id = query.message.chat_id
    
    # حذف تصویر قبلی
    last_image_message_id = context.user_data.get("last_image_message_id")
    if last_image_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_image_message_id)
        except Exception as e:
            logger.error(f"خطا در حذف تصویر قبلی: {e}")
    
    # ارسال پیام در حال طراحی مجدد
    loading_message = await context.bot.send_message(
        chat_id=chat_id,
        text=clean_text("🖌️ در حال طراحی مجدد عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    # تولید تصویر جدید با seed جدید
    seed = random.randint(1, 1000000)  # seed تصادفی جدید
    api_url = f"{IMAGE_API_URL}{prompt}?width=2048&height=2048&nologo=true&seed={seed}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
            keyboard = [[InlineKeyboardButton("🔄 تولید مجدد تصویر", callback_data=f"regenerate_image_{prompt}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # پیدا کردن پیام اصلی کاربر برای ریپلای
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
    
    user_input = " ".join(context.args).strip().lower()
    matching_items = [item for item in EXTRACTED_ITEMS if user_input in item["name"].lower() or user_input in item["category"].lower()]
    
    if not matching_items:
        await update.message.reply_text(
            clean_text(f"متأسفم، آیتمی با اسم '{user_input}' پیدا نشد! 😕"),
            message_thread_id=thread_id
        )
        return
    
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
    matching_items = [item for item in EXTRACTED_ITEMS if item["category"].lower() == category.lower()]
    
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
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    message = await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
    context.user_data["last_leaderboard_message_id"] = message.message_id

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
    keyboard.append([
        InlineKeyboardButton("اسم بازی 🎮", callback_data="noop"),
        InlineKeyboardButton("بازی شده 🕹", callback_data="noop"),
        InlineKeyboardButton("بردها 🎖", callback_data="noop")
    ])
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
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
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
            
            logger.info("مقداردهی اولیه Application...")
            await application.initialize()
            logger.info("Application با موفقیت مقداردهی شد.")
            
            logger.info(f"تنظیم وب‌هوک روی {WEBHOOK_URL}...")
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info("وب‌هوک با موفقیت تنظیم شد.")
            
            schedule_scraping(application)
            asyncio.create_task(extract_items())
            
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
                        CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_private$"),
                        CallbackQueryHandler(back_to_items, pattern="^back_to_items$")
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
                    SELECT_SIZE: [
                        CallbackQueryHandler(select_size, pattern="^size_"),
                        CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
                    ],
                    GET_PROMPT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_prompt),
                        CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
                    ]
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
                entry_points=[CommandHandler("p", start_group_image)],
                states={
                    GET_GROUP_PROMPT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_prompt),
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("start", start),
                    CallbackQueryHandler(regenerate_group_image, pattern="^regenerate_image_"),
                    CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
                ],
                name="group_image_generation",
                persistent=False
            )
            
            application.add_handler(CommandHandler("start", start))
            application.add_handler(search_conv_handler)
            application.add_handler(image_conv_handler)
            application.add_handler(group_image_conv_handler)
            application.add_handler(InlineQueryHandler(inline_query))
            application.add_handler(MessageHandler(filters.Regex(r'^@PlatoDex\s+.*'), process_item_in_group))
            application.add_handler(MessageHandler(filters.Regex(r'^/i($|\s+.*)'), process_item_in_group))
            application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'لیدربرد|لیدر برد'), detect_leaderboard_command))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))
            application.add_handler(MessageHandler(filters.Regex(r'^@saIatin_Robot\s+.*'), handle_inline_selection))
            application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
            application.add_handler(CallbackQueryHandler(select_group_item, pattern="^select_group_item_"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_group"))
            application.add_handler(CallbackQueryHandler(handle_leaderboard_selection, pattern="^leader_"))
            application.add_handler(CallbackQueryHandler(handle_profile_pagination, pattern="^(prev|next)_profile_page$"))
            application.add_handler(CallbackQueryHandler(back_to_leaderboard, pattern="^back_to_leaderboard$"))
            application.add_handler(CallbackQueryHandler(lambda update, context: None, pattern="^noop$"))
            application.add_error_handler(error_handler)
            
            logger.info("بات آماده است!")
            
            port = int(os.environ.get("PORT", 8000))
            config = uvicorn.Config(app=app, host="0.0.0.0", port=port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()
            
            break
            
        except Exception as e:
            logger.error(f"خطا در تلاش {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"تلاش دوباره بعد از {retry_delay} ثانیه...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("همه تلاش‌ها ناموفق بود!")
                raise

if __name__ == "__main__":
    asyncio.run(main())
