from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, InputFile
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import requests
from bs4 import BeautifulSoup  # اضافه شده
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
from leaderboard_scraper import scrape_leaderboard
from profile_scraper import scrape_profile
from utils import clean_text

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
            logger.warning(f"درخواست تکراری با update_id: {update_id}")
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
                    await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=clean_text("مشکلی تو بارگذاری آیتم‌ها پیش اومد!"))
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
                await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=clean_text(f"آیتم‌ها به‌روز شدند! تعداد: {len(EXTRACTED_ITEMS)}"))
            return
        except (requests.RequestException, requests.Timeout) as e:
            logger.error(f"خطا در تلاش {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error("همه تلاش‌ها ناموفق بود!")
                if context and hasattr(context.bot, 'send_message'):
                    await context.bot.send_message(chat_id=DEFAULT_CHAT_ID, text=clean_text("خطا در به‌روزرسانی آیتم‌ها! بعداً امتحان کنید."))
                return

def schedule_scraping(app: Application):
    if app.job_queue is None:
        logger.error("JobQueue فعال نیست!")
        raise RuntimeError("JobQueue فعال نیست!")
    app.job_queue.run_repeating(extract_items, interval=12*60*60, first=0)

# دستورات موجود (بدون تغییر)
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
        [InlineKeyboardButton("Run App 📱", web_app={"url": "https://platodex-tde3qe.vercel.app/"})],
        [InlineKeyboardButton("Search Items 🔍", callback_data="search_items")],
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("Generate Image 🖼️", callback_data="generate_image")]
    ]
    await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# ... بقیه توابع موجود مثل start_generate_image، select_size، get_prompt و غیره بدون تغییر ...

# توابع جدید برای لیدربرد
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
    
    message_text = clean_text("جدول امتیازات\nبرندگان برتر رتبه‌بندی هفتگی - همه بازی‌ها")
    keyboard = []
    for player in leaderboard:
        button_text = clean_text(f"{player['username']} - {player['wins']} برد")
        callback_data = f"leader_{player['player_id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)

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
        f"آیدی بازیکن: {player['username']}\n"
        f"تعداد بردها: {player['wins']}"
    )
    
    profile_data = scrape_profile(player['player_link'])
    keyboard = []
    if profile_data:
        for game in profile_data:
            button_text = clean_text(f"{game['game_name']} - بازی: {game['played']} - برد: {game['won']}")
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"game_{player_id}_{game['game_name']}")])
    
    keyboard.append([InlineKeyboardButton("🏠 برگشت به لیدربرد", callback_data="back_to_leaderboard")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    if player['profile_image']:
        try:
            response = requests.get(player['profile_image'], timeout=10)
            if response.status_code == 200:
                await query.message.reply_photo(
                    photo=response.content,
                    caption=player_text,
                    reply_markup=reply_markup,
                    message_thread_id=thread_id
                )
            else:
                await query.message.reply_text(player_text, reply_markup=reply_markup, message_thread_id=thread_id)
        except Exception as e:
            logger.error(f"خطا در ارسال عکس: {e}")
            await query.message.reply_text(player_text, reply_markup=reply_markup, message_thread_id=thread_id)
    else:
        await query.message.reply_text(player_text, reply_markup=reply_markup, message_thread_id=thread_id)
    
    await query.message.delete()

async def back_to_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    leaderboard = scrape_leaderboard()
    if not leaderboard:
        await query.edit_message_text(clean_text("مشکلی تو گرفتن لیدربرد پیش اومد! 😅"))
        return
    
    message_text = clean_text("جدول امتیازات\nبرندگان برتر رتبه‌بندی هفتگی - همه بازی‌ها")
    keyboard = []
    for player in leaderboard:
        button_text = clean_text(f"{player['username']} - {player['wins']} برد")
        callback_data = f"leader_{player['player_id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message_text, reply_markup=reply_markup)

async def detect_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            return
        PROCESSED_MESSAGES.add(message_id)
    
    text = update.message.text.lower()
    if "لیدربرد" in text or "لیدر برد" in text:
        await show_weekly_leaderboard(update, context)

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
