from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
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
from typing import List, Dict, Optional, Union

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
JSON_WRITE_LOCK = Lock()

# پیام سیستمی (ناقص، برای تکمیل توسط شما)
SYSTEM_MESSAGE = "شما دستیار هوشمند PlatoDex هستید و ..."

application = None
app = FastAPI()

# تعریف ساختار آیتم
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
        self.audios = audios or []

    def to_dict(self):
        """تبدیل شیء PlatoItem به دیکشنری برای ذخیره در JSON"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "price": self.price,
            "images": self.images,
            "audios": self.audios
        }

def guess_item_info(image_path: str) -> tuple[str, str]:
    """حدس زدن دسته‌بندی و نام آیتم بر اساس مسیر تصویر"""
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
            category = "Game - Pool (Cue)" if "cue" in path else "Game - Pool (Table#Table)"
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

def clean_text(text: str) -> str:
    """پاک‌سازی متن برای تلگرام"""
    return html.escape(str(text)).replace(".", "\\.").replace("-", "\\-").replace("!", "\\!").replace("(", "\\(").replace(")", "\\)")

def load_items_from_json(output_file: str):
    """بارگذاری آیتم‌ها از فایل JSON در صورت وجود"""
    global EXTRACTED_ITEMS
    try:
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                EXTRACTED_ITEMS = json.load(f)
            logger.info(f"{len(EXTRACTED_ITEMS)} آیتم از فایل {output_file} بارگذاری شد")
        else:
            logger.info(f"فایل {output_file} وجود ندارد، اسکرپ اولیه انجام خواهد شد")
    except Exception as e:
        logger.error(f"خطا در بارگذاری فایل JSON: {e}")
        EXTRACTED_ITEMS = []

async def extract_items(context: ContextTypes.DEFAULT_TYPE = None, output_file: str = "platopedia_items.json"):
    global EXTRACTED_ITEMS
    max_retries = 3
    retry_delay = 5
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    for attempt in range(max_retries):
        try:
            logger.info(f"تلاش {attempt + 1} برای اسکرپ آیتم‌ها از {URL}")
            response = requests.get(URL, headers=headers, timeout=60)
            if response.status_code != 200:
                logger.error(f"خطا در درخواست HTTP: {response.status_code} {response.reason}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

            logger.info("محتوای HTML با موفقیت دریافت شد")
            soup = BeautifulSoup(response.text, "html.parser")

            # جستجوی داده‌های آیتم‌ها در تگ‌های اسکریپت
            items_data = {}
            script_tags = soup.find_all("script")
            for tag in script_tags:
                script_content = tag.string
                if script_content and "var items = {" in script_content:
                    items_match = re.search(r"var items = ({.*?});", script_content, re.DOTALL)
                    if items_match and items_match[1]:
                        try:
                            items_data = json.loads(items_match[1])
                            logger.info(f"داده‌های آیتم‌ها پیدا شد با {len(items_data)} آیتم")
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"خطا در پارس JSON آیتم‌ها: {e}")

            # استخراج جزئیات آیتم‌ها از جدول
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
            extracted_items = []
            for item_id, item_info in items_data.items():
                med = item_info.get("med", {})
                images = [BASE_IMAGE_URL + img["uri"] for img in med.get("images", [])]
                audios = [
                    {
                        "uri": audio["uri"],
                        "type": audio.get("type", "audio/mp4"),
                        "title": audio.get("title", f"{item_id} Audio"),
                    }
                    for audio in med.get("audios", [])
                ]
                details = item_details.get(item_id, {})
                columns = details.get("columns", {})
                if columns:
                    category, name_guess = guess_item_info(images[0] if images else "")
                    extracted_item = PlatoItem(
                        id=item_id,
                        name=columns.get("column_3", name_guess),
                        category=columns.get("column_2", category),
                        description=columns.get("column_5", "بدون توضیحات"),
                        price=details.get("price", {"value": 0, "type": "unknown"}),
                        images=images,
                        audios=audios,
                    )
                    extracted_items.append(extracted_item)

            # ذخیره در فایل JSON
            items_dict = [item.to_dict() for item in extracted_items]
            try:
                with JSON_WRITE_LOCK:
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(items_dict, f, ensure_ascii=False, indent=4)
                logger.info(f"{len(extracted_items)} آیتم در فایل {output_file} ذخیره شد")
            except Exception as e:
                logger.error(f"خطا در ذخیره فایل JSON: {e}")

            EXTRACTED_ITEMS = items_dict
            logger.info(f"{len(EXTRACTED_ITEMS)} آیتم با اطلاعات کامل استخراج شد")
            if context and hasattr(context.bot, "send_message"):
                await context.bot.send_message(
                    chat_id=DEFAULT_CHAT_ID,
                    text=clean_text(f"آیتم‌ها به‌روز شدند! تعداد: {len(EXTRACTED_ITEMS)}")
                )
            return

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
        "• آیتم‌ها رو ببین 🎲\n• رتبه‌بندی بازیکن‌ها رو چک کن 🏆\n• اخبار رو دنبال کن 😎\n"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://v0-gram-file-mini-app.vercel.app"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

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
    await query.message.reply_text(
        clean_text("اسم آیتم یا دسته‌بندی رو بفرست تا برات پیدا کنم! 😎"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]])
    )
    return SEARCH_ITEM

async def send_paginated_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, is_group=False):
    categories = context.user_data["categories"]
    page = context.user_data.get("page", 0)
    categories_per_page = 10
    total_pages = (len(categories) + categories_per_page - 1) // categories_per_page
    
    start_idx = page * categories_per_page
    end_idx = min((page + 1) * categories_per_page, len(categories))
    current_categories = categories[start_idx:end_idx]
    
    keyboard = []
    for i, category in enumerate(current_categories, start_idx + 1):
        button_text = clean_text(f"{i}. {category}")
        callback_data = f"select{'_group' if is_group else ''}_category_{category}"
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
    category = query.data.split("select_category_")[-1].split("select_group_category_")[-1]
    matching_items = [item for item in EXTRACTED_ITEMS if item["category"] == category]
    
    if not matching_items:
        keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
        await query.edit_message_text(
            clean_text("هیچ آیتمی تو این دسته‌بندی پیدا نشد! 😕"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_CATEGORY
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    await send_paginated_items(update, context, is_group="group" in query.data)
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
    total_pages = (len(matching_items) +ificate items_per_page - 1) // items_per_page
    
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
        for i, audio_info in enumerate(item["audios"] or [], 1):
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

async def select_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split("select_item_")[-1].split("select_group_item_")[-1]
    item = next((item for item in EXTRACTED_ITEMS if item["id"] == item_id), None)
    
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
        message = await query.message.reply_photo(photo=item["images"][0], caption=results_text, reply_markup=reply_markup)
    else:
        message = await query.message.reply_text(results_text, reply_markup=reply_markup)
    
    context.user_data["last_item_message_id"] = message.message_id
    for i, audio_info in enumerate(item["audios"] or [], 1):
        await send_audio(update, context, item, audio_info, i, reply_markup)
    
    return SEARCH_ITEM

async def send_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, item: Dict, audio_info: Dict, index: int, reply_markup:create InlineKeyboardMarkup):
    try:
        audio_url = audio_info["uri"]
        if not audio_url.startswith("http"):
            audio_url = BASE_IMAGE_URL + audio_url
        audio_title = clean_text(audio_info["title"])
        caption = clean_text(f"🎵 فایل صوتی {index} برای {item['name']}")
        await update.message.reply_audio(audio=audio_url, title=audio_title, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"خطا در ارسال فایل صوتی {audio_info['uri']}: {e}")

async def process_item_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    user_input = update.message.text.replace("/i ", "").strip().lower()
    if not user_input:
        categories = sorted(set(item["category"] for item in EXTRACTED_ITEMS))
        context.user_data["categories"] = categories
        context.user_data["page"] = 0
        await send_paginated_categories(update, context, is_group=True)
        return
    
    matching_items = [item for item in EX EsauTRACTED_ITEMS if user_input in item["name"].lower() or user_input in item["category"].lower()]
    
    if not matching_items:
        thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
        await update.message.reply_text(
            clean_text("هیچ آیتمی پیدا نشد! 😕"),
            message_thread_id=thread_id
        )
        return
    
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    await send_paginated_items(update, context, is_group=True)

async def select_group_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split("select_group_item_")[-1]
    item = next((item for item in EXTRACTED_ITEMS if item["id"] == item_id), None)
    
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
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    keyboard = [[InlineKeyboardButton("↩️ برگشت به لیست آیتم‌ها", callback_data="back_to_items")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if item["images"]:
        message = await query.message.reply_photo(
            photo=item["images"][0],
            caption=results_text,
            reply_markup=reply_markup,
            message_thread_id=thread_id
        )
    else:
        message = await query.message.reply_text(
            results_text,
            reply_markup=reply_markup,
            message_thread_id=thread_id
        )
    
    context.user_data["last_item_message_id"] = message.message_id
    for i, audio_info in enumerate(item["audios"] or [], 1):
        await send_audio(update, context, item, audio_info, i, reply_markup)

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, scope = query.data.split("_page_")
    is_group = "group" in scope
    is_categories = "categories" in scope
    
    page = context.user_data.get("page", 0)
    if action == "prev":
        page = max(0, page - 1)
    elif action == "next":
        page += 1
    context.user_data["page"] = page
    
    if is_categories:
        await send_paginated_categories(update, context, is_group=is_group)
    else:
        await send_paginated_items(update, context, is_group=is_group)

async def back_to_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["page"] = 0
    await send_paginated_items(update, context, is_group=False)
    return SEARCH_ITEM

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    welcome_message = clean_text(
        "به PlatoDex خوش برگشتی! 😎\nچی دوست داری انجام بدی؟"
    )
    keyboard = [
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://v0-gram-file-mini-app.vercel.app"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await query.edit_message_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    AI_CHAT_USERS.add(user_id)
    await query.edit_message_text(
        clean_text("بگو چی تو سرته؟ 😎 هر چی بخوای برات توضیح میدم یا گپ حسابی می‌زنیم!"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]])
    )

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS:
        return
    user_input = update.message.text
    response = "این فقط یه دموئه! 😜 بعداً کلی چرت و پرت باحال برات دارم!"
    await update.message.reply_text(clean_text(response))

async def handle_group_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.startswith("@PlatoDex"):
        return
    user_input = update.message.text.replace("@PlatoDex", "").strip()
    if not user_input:
        return
    response = "این فقط یه دموئه! 😜 بعداً کلی چرت و پرت باحال برات دارم!"
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    await update.message.reply_text(clean_text(response), message_thread_id=thread_id)

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip().lower()
    if not query:
        return
    matching_items = [item for item in EXTRACTED_ITEMS if query in item["name"].lower() or query in item["category"].lower()]
    results = []
    for item in matching_items[:50]:
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = clean_text(f"{item['price']['value']} {price_type}")
        description = (
            f"🗃 {item['category']}\n"
            f"📃 {item['description']}\n"
            f"💸 {price_info}"
        )
        results.append(
            InlineQueryResultArticle(
                id=item["id"],
                title=clean_text(item["name"]),
                description=clean_text(description),
                thumb_url=item["images"][0] if item["images"] else None,
                input_message_content=InputTextMessageContent(
                    clean_text(
                        f"🔖 نام: {item['name']}\n"
                        f"\n"
                        f"🗃 دسته‌بندی: {item['category']}\n"
                        f"📃 توضیحات: {item['description']}\n"
                        f"\n"
                        f"💸 قیمت: {price_info}\n"
                        f"📣 @PlatoDex"
                    )
                )
            )
        )
    await update.inline_query.answer(results)

async def handle_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if "🔖 نام" not in message_text:
        return
    item_name = message_text.split("🔖 نام: ")[1].split("\n")[0].strip()
    item = next((item for item in EXTRACTED_ITEMS if item["name"] == item_name), None)
    if not item:
        return
    keyboard = [[InlineKeyboardButton("↩️ برگشت به لیست آیتم‌ها", callback_data="back_to_items")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    for i, audio_info in enumerate(item["audios"] or [], 1):
        await send_audio(update, context, item, audio_info, i, reply_markup)

async def show_weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    keyboard = [
        [InlineKeyboardButton("Pool 🎱", callback_data="leader_pool")],
        [InlineKeyboardButton("Ocho 🃏", callback_data="leader_ocho")],
        [InlineKeyboardButton("Table Soccer ⚽", callback_data="leader_tablesoccer")],
        [InlineKeyboardButton("4 in a Row 🔢", callback_data="leader_fourinarow")]
    ]
    await update.message.reply_text(
        clean_text("🏆 کدوم لیدربرد رو می‌خوای ببینی؟"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        message_thread_id=thread_id
    )

async def handle_leaderboard_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split("leader_")[-1]
    game_name = {
        "pool": "Pool",
        "ocho": "Ocho",
        "tablesoccer": "Table Soccer",
        "fourinarow": "4 in a Row"
    }.get(game, "Unknown")
    leaderboard_text = clean_text(f"🏆 لیدربرد هفتگی {game_name}\nاین فقط یه دموئه! 😜")
    keyboard = [[InlineKeyboardButton("↩️ Back to Leaderboards", callback_data="back_to_leaderboard")]]
    await query.edit_message_text(leaderboard_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def back_to_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Pool 🎱", callback_data="leader_pool")],
        [InlineKeyboardButton("Ocho 🃏", callback_data="leader_ocho")],
        [InlineKeyboardButton("Table Soccer ⚽", callback_data="leader_tablesoccer")],
        [InlineKeyboardButton("4 in a Row 🔢", callback_data="leader_fourinarow")]
    ]
    await query.edit_message_text(
        clean_text("🏆 کدوم لیدربرد رو می‌خوای ببینی؟"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("512x512", callback_data="size_512x512")],
        [InlineKeyboardButton("1024x1024", callback_data="size_1024x1024")],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]
    ]
    await query.edit_message_text(
        clean_text("📏 چه سایزی برای عکس می‌خوای؟"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_SIZE

async def select_image_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    size = query.data.split("size_")[-1]
    context.user_data["image_size"] = size
    await query.edit_message_text(
        clean_text("🖌️ حالا بگو چه عکسی دوست داری بسازم؟ (توضیح بده چی تو سرته!)"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]])
    )
    return GET_PROMPT

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    size = context.user_data.get("image_size", "512x512")
    try:
        response = requests.get(f"{IMAGE_API_URL}{prompt}?size={size}", timeout=30)
        if response.status_code != 200:
            await update.message.reply_text(clean_text("خطا تو ساخت عکس! 😕 بعداً امتحان کن."))
            return GET_PROMPT
        image = Image.open(io.BytesIO(response.content))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            image.save(temp_file.name)
            with open(temp_file.name, "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=clean_text(f"📸 اینم عکست: {prompt}"))
            os.unlink(temp_file.name)
    except Exception as e:
        logger.error(f"خطا در تولید تصویر: {e}")
        await update.message.reply_text(clean_text("خطا تو ساخت عکس! 😕 بعداً امتحان کن."))
    return GET_PROMPT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(clean_text("عملیات لغو شد! 😎"))
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطا: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(clean_text("یه مشکلی پیش اومد! 😕 بعداً امتحان کن."))

@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), application.bot)
    await application.process_update(update)
    return {"status": "ok"}

async def main():
    global application
    max_retries = 3
    retry_delay = 5
    
    # بارگذاری اولیه آیتم‌ها از فایل JSON
    parser = argparse.ArgumentParser(description="اسکرپ آیتم‌های Platopedia و ذخیره در فایل JSON")
    parser.add_argument(
        "--output",
        default=os.path.join(tempfile.gettempdir(), "platopedia_items.json"),
        help="نام فایل JSON برای ذخیره آیتم‌ها (پیش‌فرض: platopedia_items.json در دایرکتوری موقت)"
    )
    args = parser.parse_args()
    load_items_from_json(args.output)
    
    for attempt in range(max_retries):
        try:
            application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
            
            if application.job_queue is None:
                logger.error("JobQueue فعال نیست!")
                raise RuntimeError("JobQueue فعال نیست!")
            
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"Webhook روی {WEBHOOK_URL} تنظیم شد.")
            
            schedule_scraping(application)
            await extract_items(output_file=args.output)
            
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
            application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
            application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
            application.add_handler(InlineQueryHandler(inline_query))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))
            application.add_handler(MessageHandler(filters.Regex(r"🔖 نام"), handle_inline_selection))
            application.add_handler(MessageHandler(filters.Regex(r"(?i)(لیدربرد|رهبری|رتبه|Leaderboard)"), show_weekly_leaderboard))
            application.add_handler(MessageHandler(filters.Regex(r"(?i)(آیتم|item)"), process_item_in_group))
            application.add_handler(CallbackQueryHandler(start_item_search, pattern="^search_items$"))
            application.add_handler(CommandHandler("cancel", cancel))
            application.add_handler(CallbackQueryHandler(start_generate_image, pattern="^generate_image$"))
            application.add_handler(CallbackQueryHandler(select_image_size, pattern="^size_"))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_image))
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
    import argparse
    parser = argparse.ArgumentParser(description="اسکرپ آیتم‌های Platopedia و ذخیره در فایل JSON")
    parser.add_argument(
        "--output",
        default=os.path.join(tempfile.gettempdir(), "platopedia_items.json"),
        help="نام فایل JSON برای ذخیره آیتم‌ها (پیش‌فرض: platopedia_items.json در دایرکتوری موقت)"
    )
    args = parser.parse_args()
    asyncio.run(main())
