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

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و آدرس‌ها
TOKEN = '8011536409:AAGUT4m9BFxnQxppgBtbIrMXV-wF19txobs'
IMAGE_API_URL = 'https://pollinations.ai/prompt/'
TEXT_API_URL = 'https://text.pollinations.ai/'
URL = "https://platopedia.com/items"
BASE_IMAGE_URL = "https://profile.platocdn.com/"
WEBHOOK_URL = "https://platodex.onrender.com/webhook"
EXTRACTED_ITEMS = []
AI_CHAT_USERS = set()
SEARCH_ITEM = 1
SELECT_SIZE, GET_PROMPT = range(2)
DEFAULT_CHAT_ID = 789912945  # آیدی چت پیش‌فرض (باید آیدی خودت رو بذاری)

# پیام سیستمی برای چت
SYSTEM_MESSAGE = (
    "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید و به صورت خودمونی جذاب و با ایموجی "
    "حرف میزنی به صورت نسل z و کمی با طنز حرف بزن و شوخی کنه"
)

# متغیر جهانی برای application
application = None

# ایجاد سرور FastAPI
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    global application
    update = await request.json()
    update_obj = Update.de_json(update, application.bot)
    asyncio.create_task(application.process_update(update_obj))
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "PlatoDex Bot is running!"}

def clean_text(text):
    if not text:
        return ""
    return text.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

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
                    try:
                        await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text="مشکلی تو بارگذاری آیتم‌ها پیش اومد!")
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام: {e}")
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
                try:
                    await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=f"آیتم‌ها به‌روز شدند! تعداد: {len(EXTRACTED_ITEMS)}")
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام: {e}")
            return
        except (requests.RequestException, requests.Timeout) as e:
            logger.error(f"خطا در تلاش {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"تلاش دوباره بعد از {retry_delay} ثانیه...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("همه تلاش‌ها ناموفق بود!")
                if context and hasattr(context.bot, 'send_message'):
                    try:
                        await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text="خطا در به‌روزرسانی آیتم‌ها! بعداً امتحان کنید.")
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام: {e}")
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
    welcome_message = (
        f"سلام {user_name}!\nبه PlatoDex خوش اومدی - مرکز بازی‌های Plato!\n"
        "• آیتم‌ها رو ببین 🎲\n• رتبه‌بندی بازیکن‌ها رو چک کن 🏆\n• اخبار رو دنبال کن 🎯"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://platodex-tde3qe.vercel.app/"})],
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
        "🖼️ Generate Image Mode Activated!\n\n"
        "لطفاً سایز تصویر مورد نظر خود را انتخاب کنید:",
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
        f"سایز تصویر انتخاب شد: {context.user_data['width']}x{context.user_data['height']}\n\n"
        "لطفاً توضیحات تصویر (پرامپت) را وارد کنید. مثلاً: 'A cat in a forest'",
        reply_markup=reply_markup
    )
    return GET_PROMPT

async def get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text("لطفاً یک توضیح برای تصویر وارد کنید!")
        return GET_PROMPT
    
    width = context.user_data["width"]
    height = context.user_data["height"]
    
    loading_message = await update.message.reply_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید.")
    
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
            await update.message.reply_text("مشکلی در تولید تصویر پیش آمد. لطفاً دوباره امتحان کنید.")
    except Exception as e:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_message.message_id)
        await update.message.reply_text("خطایی رخ داد. لطفاً بعداً امتحان کنید.")
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
        "🖼️ Generate Image Mode Activated!\n\n"
        "لطفاً سایز تصویر مورد نظر خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return SELECT_SIZE

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        await update.inline_query.answer([])
        return
    results = []
    for item in EXTRACTED_ITEMS:
        if query.lower() in item["name"].lower() or query.lower() in item["category"].lower():
            price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
            price_info = f"{item['price']['value']} {price_type}"
            result_content = (
                f"🏷 نام : {item['name']}\n\n"
                f"🗃 دسته‌بندی : {item['category']}\n"
                f"📃 توضیحات : {item['description']}\n\n"
                f"💸 قیمت : {price_info}"
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

async def start_item_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🔍 لطفاً اسم آیتم رو بفرست!",
        reply_markup=reply_markup
    )
    return SEARCH_ITEM

async def process_item_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "processed_message_id" in context.user_data and context.user_data["processed_message_id"] == update.message.message_id:
        return SEARCH_ITEM  # جلوگیری از پردازش دوباره
    
    user_input = update.message.text.strip().lower()
    matching_items = [item for item in EXTRACTED_ITEMS if user_input in item["name"].lower() or user_input in item["category"].lower()]
    
    if not matching_items:
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        await update.message.reply_text("هیچ آیتمی پیدا نشد! 😕", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["processed_message_id"] = update.message.message_id
        return SEARCH_ITEM
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    context.user_data["processed_message_id"] = update.message.message_id
    await send_paginated_items(update, context, is_group=False)
    return SEARCH_ITEM

async def send_paginated_items(update: Update, context: ContextTypes.DEFAULT_TYPE, is_group=False):
    matching_items = context.user_data["matching_items"]
    page = context.user_data["page"]
    items_per_page = 10
    total_pages = (len(matching_items) + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = min((page + 1) * items_per_page, len(matching_items))
    current_items = matching_items[start_idx:end_idx]
    
    if len(matching_items) == 1:
        item = matching_items[0]
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = f"{item['price']['value']} {price_type}"
        results_text = (
            f"🏷 نام : {item['name']}\n"
            f"🗃 دسته‌بندی : {item['category']}\n"
            f"📃 توضیحات : {item['description']}\n"
            f"💸 قیمت : {price_info}"
        )
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_group:
            thread_id = update.message.message_thread_id if update.message and hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
            if item["images"]:
                await update.message.reply_photo(photo=item["images"][0], caption=results_text, reply_markup=reply_markup, message_thread_id=thread_id)
            for i, audio_info in enumerate(item["audios"], 1):
                await send_audio(update, context, item, audio_info, i, reply_markup, thread_id)
            if not item["images"] and not item["audios"]:
                await update.message.reply_text(results_text, reply_markup=reply_markup, message_thread_id=thread_id)
        else:
            if item["images"]:
                await update.message.reply_photo(photo=item["images"][0], caption=results_text, reply_markup=reply_markup)
            for i, audio_info in enumerate(item["audios"], 1):
                await send_audio(update, context, item, audio_info, i, reply_markup)
            if not item["images"] and not item["audios"]:
                await update.message.reply_text(results_text, reply_markup=reply_markup)
        return
    
    keyboard = []
    for i, item in enumerate(current_items, start_idx + 1):
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = f"{item['price']['value']} {price_type}"
        button_text = f"{i}. {item['name']} - {price_info}"
        callback_data = f"select{'_group' if is_group else ''}_item_{item['id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prev_page_{'group' if is_group else 'private'}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"next_page_{'group' if is_group else 'private'}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = f"این آیتم‌ها رو پیدا کردم (صفحه {page + 1} از {total_pages})، کدوم رو می‌خوای؟ 👇"
    
    if is_group and update.message:
        thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
        await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

async def send_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, item, audio_info, index, reply_markup, thread_id=None):
    audio_url = audio_info["uri"]
    audio_type = audio_info.get("type", "unknown")
    base_url = "https://game-assets-prod.platocdn.com/"
    full_url = base_url + audio_url if not audio_url.startswith("http") else audio_url
    try:
        response = requests.get(full_url, timeout=10)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            with open(temp_file_path, "rb") as voice_file:
                if thread_id:
                    await update.message.reply_voice(
                        voice=voice_file,
                        caption=f"🎙 وویس {index} آیتم: {item['name']} (نوع: {audio_type})",
                        reply_markup=reply_markup,
                        message_thread_id=thread_id
                    )
                elif update.message:
                    await update.message.reply_voice(
                        voice=voice_file,
                        caption=f"🎙 وویس {index} آیتم: {item['name']} (نوع: {audio_type})",
                        reply_markup=reply_markup
                    )
            os.remove(temp_file_path)
    except Exception as e:
        logger.error(f"خطا در دانلود یا ارسال وویس {index}: {e}")
        if thread_id and update.message:
            await update.message.reply_text(f"مشکلی توی ارسال وویس {index} پیش اومد! 😅", reply_markup=reply_markup, message_thread_id=thread_id)
        elif update.message:
            await update.message.reply_text(f"مشکلی توی ارسال وویس {index} پیش اومد! 😅", reply_markup=reply_markup)

async def select_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.replace("select_item_", "")
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    
    if not item:
        await query.edit_message_text("آیتم پیدا نشد! 😕")
        return SEARCH_ITEM
    
    price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
    price_info = f"{item['price']['value']} {price_type}"
    results_text = (
        f"🏷 نام : {item['name']}\n"
        f"🗃 دسته‌بندی : {item['category']}\n"
        f"📃 توضیحات : {item['description']}\n"
        f"💸 قیمت : {price_info}"
    )
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if item["images"]:
        await query.message.reply_photo(photo=item["images"][0], caption=results_text, reply_markup=reply_markup)
    for i, audio_info in enumerate(item["audios"], 1):
        await send_audio(update, context, item, audio_info, i, reply_markup)
    if not item["images"] and not item["audios"]:
        await query.edit_message_text(results_text, reply_markup=reply_markup)
    
    return SEARCH_ITEM

async def process_item_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "processed_message_id" in context.user_data and context.user_data["processed_message_id"] == update.message.message_id:
        return  # جلوگیری از پردازش دوباره
    
    chat_id = update.effective_chat.id
    try:
        await context.bot.get_chat(chat_id)
    except Exception as e:
        logger.error(f"خطا در دسترسی به چت {chat_id}: {e}")
        if "Forbidden" in str(e):
            await update.message.reply_text("متأسفم، من از این گروه بیرون انداخته شدم! 😕 دوباره منو اد کن تا کمکت کنم.")
        else:
            await update.message.reply_text("یه مشکلی پیش اومد، نمی‌تونم چت رو پیدا کنم! 😅")
        return
    
    if not context.args:
        thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
        await update.message.reply_text(
            "لطفاً اسم آیتم رو بعد از /i بنویس! مثلاً: /i Macaron",
            message_thread_id=thread_id
        )
        return
    
    item_name = " ".join(context.args).strip().lower()
    matching_items = [item for item in EXTRACTED_ITEMS if item_name in item["name"].lower()]
    
    if not matching_items:
        thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
        await update.message.reply_text(
            f"متأسفم، آیتمی با اسم '{item_name}' پیدا نشد! 😕",
            message_thread_id=thread_id
        )
        return
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    context.user_data["processed_message_id"] = update.message.message_id
    await send_paginated_items(update, context, is_group=True)
    return

async def select_group_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.replace("select_group_item_", "")
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    
    if not item:
        await query.edit_message_text("آیتم پیدا نشد! 😕")
        return
    
    price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
    price_info = f"{item['price']['value']} {price_type}"
    results_text = (
        f"🏷 نام : {item['name']}\n"
        f"🗃 دسته‌بندی : {item['category']}\n"
        f"📃 توضیحات : {item['description']}\n"
        f"💸 قیمت : {price_info}"
    )
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if item["images"]:
        image_url = item["images"][0]
        if image_url.lower().endswith('.webp'):
            response = requests.get(image_url, timeout=10)
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
                reply_markup=reply_markup,
                message_thread_id=thread_id
            )
        elif image_url.lower().endswith('.gif'):
            await query.message.reply_animation(
                animation=image_url,
                caption=results_text,
                reply_markup=reply_markup,
                message_thread_id=thread_id
            )
        else:
            await query.message.reply_photo(
                photo=image_url,
                caption=results_text,
                reply_markup=reply_markup,
                message_thread_id=thread_id
            )
    for i, audio_info in enumerate(item["audios"], 1):
        await send_audio(update, context, item, audio_info, i, reply_markup, thread_id)
    if not item["images"] and not item["audios"]:
        await query.edit_message_text(results_text, reply_markup=reply_markup)
    return

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_group = "group" in query.data
    if "next_page" in query.data:
        context.user_data["page"] += 1
    elif "prev_page" in query.data:
        context.user_data["page"] -= 1
    
    await send_paginated_items(update, context, is_group=is_group)
    return SEARCH_ITEM if not is_group else None

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    AI_CHAT_USERS.add(user_id)
    context.user_data.clear()
    context.user_data["mode"] = "ai_chat"
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🤖 چت با هوش مصنوعی فعال شد!\n\n",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return ConversationHandler.END
    
    user_message = update.message.text
    
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_message}
        ],
        "model": "mistral",
        "seed": 42,
        "jsonMode": False
    }
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            ai_response = response.text.strip()
            final_response = f"{ai_response}"
            await update.message.reply_text(final_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                "اوفف، یه مشکلی پیش اومد! 😅 فکر کنم API یه کم خوابش برده! بعداً امتحان کن 🚀",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"خطا در اتصال به API چت: {e}")
        await update.message.reply_text(
            "اییی، یه خطا خوردم! 😭 بعداً دوباره بیا، قول می‌دم درستش کنم! 🚀",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    user_name = query.from_user.first_name
    welcome_message = (
        f"سلام {user_name}!\nبه PlatoDex خوش اومدی - مرکز بازی‌های Plato!\n"
        "• آیتم‌ها رو ببین 🎲\n• رتبه‌بندی بازیکن‌ها رو چک کن 🏆\n• اخبار رو دنبال کن 🎯"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://platodex-tde3qe.vercel.app/"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await query.edit_message_text(
        text=welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    await update.message.reply_text("عملیات لغو شد.", reply_markup=InlineKeyboardMarkup([]))
    await start(update, context)
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطا رخ داد: {context.error}")

async def main():
    global application
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            application = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).build()
            
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
                    SEARCH_ITEM: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, process_item_search),
                        CallbackQueryHandler(select_item, pattern="^select_item_"),
                        CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_private$"),
                        CallbackQueryHandler(back_to_home, pattern="^back_to_home$")
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
            
            application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
            application.add_handler(CommandHandler("i", process_item_in_group))
            application.add_handler(CallbackQueryHandler(select_group_item, pattern="^select_group_item_"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^(prev|next)_page_group$"))
            application.add_handler(search_conv_handler)
            application.add_handler(image_conv_handler)
            application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
            application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
            application.add_handler(InlineQueryHandler(inline_query))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
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
