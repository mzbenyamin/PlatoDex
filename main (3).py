from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, InputFile, error
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
import random
import uuid
from typing import List, Dict, Optional, Union
import uvicorn
import sqlite3
import queue
import threading

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
PROCESSING_LOCK = asyncio.Lock()

# تابع تولید callback_data امن
def generate_safe_callback_data(prompt):
    callback_id = str(uuid.uuid4())[:8]
    return f"regenerate_image_{callback_id}"

SYSTEM_MESSAGE = (
    "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید با ایموجی "
    "حرف میزنی به صورت حکیمانه و انگار ۶۰ سال ست داری صحبت میکنی و فوق العاده خنده دار و طنز حرف میزنی و شوخی کن\\. به مشخصات آیتم‌های پلاتو دسترسی داری و می‌تونی "
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
    "لینکای دانلود پلاتو\n- اندروید: https://play.google.com/store/apps/details?id=com.plato.android\n- iOS: https://apps.apple.com/app/plato-play-chat-together/id1054747306?ls=1\n"
    "سلاطین پلاتو چیه؟\nاولین رسانه فارسی‌زبون پلاتو از 1400 با مدیریت بنیامین\\. اخبار و ترفندای پلاتو رو می‌دن و یه مینی‌اپ تلگرامی @PlatoDex دارن که رتبه‌بندی بازیکنا و آیتما رو نشون می‌ده\\ - کانال: @salatin_plato - گروه: @Gap_Plato\n\n"
    "چند اکانت تو یه دستگاه\n"
    "نسخه افلاطون: کنار نسخه اصلی نصب کن، از ربات بگیر\\.\\n"
    "متاسفانه از تاریخ 28 فروردین 1404 پلاتو سرورهای قدیمی پلاتو که میشد باهاشون کلون کرد رو غیرفعال کرد و دسترسی رو محدود کرد اگر میخوای چند اکانت داشته باشی حتما ایمیل روشون ثبت کن"
    "سلاطین پلاتو ترفندای بیشتر تو @salatin_plato منتظرته! 😎\n\n"
    "شما دیگر نمی‌توانید فرندها یا دوستان کاربران دیگر رو ببینید چون اپلیکیشن‌های قدیمی پلاتو که این کار رو می‌کردند غیرفعال شدند"
    "این پیام آموزشی رو توی هر پاسخ تکرار نکن، فقط توی ذهنت نگه دار و بر اساسش عمل کن و پاسخ بده\\."
    "خلاصه به سوالات جواب بده خیلی بلند نباشه اگر کاربر درخواست توضیحات کرد بعد توضیح بده"
    "با پلاتو ویپ یا vip و پلاتو مگ یا mage میشه چندین اکانت ساخت و سکه جمع‌آوری کرد و برای کسایی هست که می‌خوان چند اکانت داشته باشند سکه جمع‌آوری کنند برای خودشون"
    "پلاتو مگ و ویپ چیکار میکنن؟ پلاتو نسخه اصلی قابلیت کلون شدن رو نداره افراد با این اپ‌ها می‌تونن چندین اکانت بسازند و سکه روزانه رو ذخیره و یا برای خودشون آیتم بخرند یا بفروشند فرق مگ و ویپ در این هست. افرادی که قبلا نسخه‌های قبلی مگ و ویپ داشتند می‌تونن با اپ‌های بالا که در کانال آپلود شده آپدیت کنن و به سکه‌های قفل شده در نسخه قبلی دسترسی‌ داشته باشند"
    "آیدی تلگرامی مدیر سلاطین پلاتو: @BeniHFX آیدی پلاتویی: Salatin"
)

# --- مدیریت گروه و دیتابیس ---
ADMIN_ID = 7403352779

def init_db():
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS violations (
            user_id TEXT,
            username TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            user_id TEXT,
            username TEXT,
            message TEXT,
            reply_to_message_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('response_triggers', ''))
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('no_response_triggers', ''))
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('violation_triggers', ''))
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('no_violation_triggers', ''))
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_setting(key, default=''):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def update_setting(key, value):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
    logger.info(f"Setting updated: {key} = {value}")

def count_violations(user_id):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM violations WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def log_violation(user_id, username, message):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO violations (user_id, username, message) VALUES (?, ?, ?)',
                   (user_id, username, message))
    conn.commit()
    conn.close()
    logger.info(f"Violation logged for user {user_id} ({username}): {message}")

def clear_violations(user_id):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM violations WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Violations cleared for user {user_id}")

def add_to_chat_history(chat_id, user_id, username, message, reply_to_message_id=None):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM chat_history')
    count = cursor.fetchone()[0]
    if count >= 1000:
        cursor.execute('DELETE FROM chat_history WHERE id = (SELECT MIN(id) FROM chat_history)')
    cursor.execute('''
        INSERT INTO chat_history (chat_id, user_id, username, message, reply_to_message_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, user_id, username, message, reply_to_message_id))
    conn.commit()
    conn.close()
    logger.info(f"Message added to chat history for user {user_id} (@{username})")

def get_recent_chat_history(chat_id, limit=10):
    conn = sqlite3.connect('violations.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, message, reply_to_message_id, timestamp
        FROM chat_history
        WHERE chat_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (chat_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

# --- صف API ---
api_queue = queue.Queue()
def process_api_queue():
    while True:
        try:
            text, callback = api_queue.get()
            logger.info(f"Processing API request: {text[:50]}...")
            for attempt in range(3):
                try:
                    response = requests.post(TEXT_API_URL, json={"prompt": text, "model": "openai-large"}, timeout=30)
                    response.raise_for_status()
                    logger.info(f"API response: {response.text[:50]}...")
                    callback(response.text.strip())
                    time.sleep(2)
                    break
                except requests.HTTPError as e:
                    if e.response.status_code == 429:
                        logger.warning(f"Rate limit hit, retrying after {2 * (attempt + 1)} seconds...")
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        logger.error(f"HTTP Error: {e}")
                        callback(None)
                        break
                except requests.RequestException as e:
                    logger.error(f"Request Error: {e}")
                    callback(None)
                    break
            else:
                logger.error("Failed after retries.")
                callback(None)
            api_queue.task_done()
        except Exception as e:
            logger.error(f"Error in API queue: {e}")
threading.Thread(target=process_api_queue, daemon=True).start()

def analyze_message(text, callback):
    api_queue.put((text, callback))

def should_respond_or_violate(text, bot_username, user_id, username, callback):
    response_triggers = get_setting('response_triggers', '')
    no_response_triggers = get_setting('no_response_triggers', '')
    violation_triggers = get_setting('violation_triggers', '')
    no_violation_triggers = get_setting('no_violation_triggers', '')
    logger.info(f"Analyzing message from {user_id} (@{username}): {text}")
    prompt = f"""
    شما یک دستیار هوشمند در گروه‌های تلگرامی هستید که به مدیریت گروه کمک می‌کنید و به سوالات کاربران پاسخ می‌دهید.
    پیام زیر را تحلیل کنید و تصمیم بگیرید:
    1. اگر پیام شامل کلمات کلیدی یا الگوهای زیر باشد: {response_triggers}، یا مستقیماً خطاب به ربات باشد (مثلاً با منشن یا در چت خصوصی)، پاسخ دهید.
    2. اگر پیام شامل کلمات کلیدی زیر باشد: {no_response_triggers}، پاسخ ندهید.
    3. اگر پیام شامل کلمات کلیدی یا الگوهای زیر باشد: {violation_triggers}، آن را به عنوان تخلف علامت‌گذاری کنید.
    4. اگر پیام شامل کلمات کلیدی زیر باشد: {no_violation_triggers}، آن را به عنوان تخلف علامت‌گذاری نکنید.
    همچنین، اگر پیام یک سوال مهم است که نیاز به پاسخ دارد، اما مطمئن نیستید که باید پاسخ دهید، از کاربر اجازه بگیرید.
    متن پیام: {text}
    پاسخ شما باید یکی از موارد زیر باشد:
    - 'پاسخ بده': اگر باید مستقیماً پاسخ دهید
    - 'اجازه بگیر': اگر باید از کاربر اجازه بگیرید
    - 'تخلف': اگر پیام تخلف است
    - 'هیچی': اگر هیچ کدام از موارد بالا صدق نمی‌کند
    """
    analyze_message(prompt, callback)

def generate_response(text, user_id, username, user_fullname, callback, chat_history=None):
    response_triggers = get_setting('response_triggers', '')
    
    logger.info(f"Generating response for {user_id} (@{username}): {text}")
    
    history_context = ""
    if chat_history:
        history_context = "\nتاریخچه چت اخیر:\n"
        for msg in chat_history:
            history_context += f"@{msg[1]}: {msg[2]}\n"
    
    user_info = f"نام و نام کاربری کاربر: {user_fullname} (@{username})"
    
    prompt = f"""
    {SYSTEM_MESSAGE}
    
    {user_info}
    متن و یا سوال و جواب کاربر: {text}
    تاریخچه پیام کاربران: {history_context}
    
    به عنوان یک دستیار حرفه‌ای و دوستانه:
    - لطفا در پاسخ از نام کاربر استفاده کن و اگر نام انگلیسی است به فارسی تبدیل کن
    - پاسخ باید کوتاه، دقیق و جذاب باشد
    - از ایموجی‌های مناسب استفاده کن
    - با لحن نسل Z و دوستانه صحبت کن
    - اگر سوال مرتبط با کلمات کلیدی ({response_triggers}) باشد، پاسخ مرتبط بده
    - اگر نیاز است، هشدار دهید که برای اطلاعات دقیق‌تر با متخصص مشورت کنند
    - اگر سوالی است که نیاز به اجازه کاربر دارد، از او اجازه بگیرید
    - اگر سوال در مورد آیتم‌های پلاتو است، راهنمایی کن که از دستور /i استفاده کنند
    - اگر سوال در مورد چند اکانت است، توضیح بده که از تاریخ 28 فروردین 1404 پلاتو سرورهای قدیمی غیرفعال شده‌اند
    - اگر سوال در مورد دوستان است، توضیح بده که دیگر نمی‌توان دوستان کاربران دیگر را دید
    - اگر سوال در مورد سلاطین پلاتو است، توضیح بده که اولین رسانه فارسی‌زبون پلاتو از 1400 با مدیریت بنیامین است
    """
    analyze_message(prompt, callback)

def generate_violation_reason(text, callback):
    prompt = f"""
    شما یک دستیار هوشمند در گروه‌های تلگرامی هستید که به مدیریت گروه کمک می‌کنید.
    پیام زیر را تحلیل کنید و دلیل دقیق تخلف را توضیح دهید:
    - دلیل باید واضح و حرفه‌ای باشد
    - حداکثر 50 کلمه باشد
    - از کلمات توهین‌آمیز استفاده نکنید
    - دلیل باید به صورت مستقیم و بدون ابهام باشد
    متن پیام: {text}
    مثال:
    پیام: "سلام به همه"
    دلیل: پیام خالی یا بی‌محتوا
    پیام: "لینک دانلود فیلم"
    دلیل: ارسال لینک غیرمجاز و تبلیغات
    """
    analyze_message(prompt, callback)

# --- دستورات ادمین و هندلرهای مدیریتی ---
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    if update.message.chat.type == 'private' and user_id == ADMIN_ID:
        keyboard = [
            ['تنظیم پاسخ‌ها', 'تنظیم تخلف‌ها'],
            ['تنظیم عدم پاسخ', 'تنظیم عدم تخلف'],
            ['وضعیت ربات', 'خروج']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "<b>پنل مدیریتی ربات</b>\nاز این منو می‌تونید تنظیمات ربات رو تغییر بدید.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "<b>سلام!</b> من ربات گروه هستم. برای سوال، من رو منشن کنید یا توی چت خصوصی پیام بدید.",
            parse_mode='HTML'
        )

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    if not update.message.from_user:
        await update.message.reply_text("کاربر شناسایی نشد.", parse_mode='HTML')
        return
    if not context.args:
        await update.message.reply_text("لطفاً نام کاربری رو ذکر کنید، مثلاً: /warn @username", parse_mode='HTML')
        return
    target_username = context.args[0].replace('@', '')
    target_user_id = None
    async for member in context.bot.get_chat_members(update.message.chat_id):
        if member.user.username == f"@{target_username}":
            target_user_id = str(member.user.id)
            break
    if not target_user_id:
        await update.message.reply_text("کاربر پیدا نشد.", parse_mode='HTML')
        return
    log_violation(target_user_id, target_username, "اخطار دستی توسط ادمین")
    violation_count = count_violations(target_user_id)
    await update.message.reply_text(
        f"<b>⚠️ تخلف و اخطار</b>\n\nکاربر <a href='tg://user?id={target_user_id}'>@{target_username}</a> شما یک خطا دریافت کردید\n\n<b>📇 علت:</b> اخطار دستی\n\n<b>❗️اخطارهای شما:</b> {violation_count}",
        parse_mode='HTML'
    )

async def violations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    if not context.args:
        await update.message.reply_text("لطفاً نام کاربری رو ذکر کنید، مثلاً: /violations @username", parse_mode='HTML')
        return
    target_username = context.args[0].replace('@', '')
    target_user_id = None
    async for member in context.bot.get_chat_members(update.message.chat_id):
        if member.user.username == f"@{target_username}":
            target_user_id = str(member.user.id)
            break
    if not target_user_id:
        await update.message.reply_text("کاربر پیدا نشد.", parse_mode='HTML')
        return
    count = count_violations(target_user_id)
    await update.message.reply_text(
        f"کاربر <a href='tg://user?id={target_user_id}'>@{target_username}</a> <b>{count}</b> تخلف داره.",
        parse_mode='HTML'
    )

async def clear_violations_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    if not context.args:
        await update.message.reply_text("لطفاً نام کاربری رو ذکر کنید، مثلاً: /clearviolations @username", parse_mode='HTML')
        return
    target_username = context.args[0].replace('@', '')
    target_user_id = None
    async for member in context.bot.get_chat_members(update.message.chat_id):
        if member.user.username == f"@{target_username}":
            target_user_id = str(member.user.id)
            break
    if not target_user_id:
        await update.message.reply_text("کاربر پیدا نشد.", parse_mode='HTML')
        return
    clear_violations(target_user_id)
    await update.message.reply_text(
        f"تخلف‌های <a href='tg://user?id={target_user_id}'>@{target_username}</a> پاک شد.",
        parse_mode='HTML'
    )

# --- هندلر پیام متنی هوشمند ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    bot_username = context.bot.username
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    user_fullname = f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    message_id = update.message.message_id
    add_to_chat_history(chat_id, user_id, username, message_text, message_id)
    chat_history = get_recent_chat_history(chat_id)
    if f"@{bot_username}" in message_text or update.message.chat.type == 'private':
        def callback(reply):
            if reply and context.job_queue:
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.send_message(
                        chat_id=chat_id,
                        text=reply,
                        parse_mode='HTML',
                        reply_to_message_id=message_id
                    ),
                    0
                )
        generate_response(message_text, user_id, username, user_fullname, callback, chat_history)
    else:
        def callback(decision):
            if not decision:
                return
            decision = decision.lower()
            if 'پاسخ بده' in decision:
                def reply_callback(reply):
                    if reply and context.job_queue:
                        context.job_queue.run_once(
                            lambda ctx: ctx.bot.send_message(
                                chat_id=chat_id,
                                text=reply,
                                parse_mode='HTML',
                                reply_to_message_id=message_id
                            ),
                            0
                        )
                generate_response(message_text, user_id, username, user_fullname, reply_callback, chat_history)
            elif 'اجازه بگیر' in decision:
                keyboard = [[InlineKeyboardButton("بله", callback_data=f"allow_{user_id}"),
                           InlineKeyboardButton("خیر", callback_data=f"deny_{user_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.send_message(
                        chat_id=chat_id,
                        text=f"کاربر {update.message.from_user.mention_html()}، آیا می‌خواهید به سوال شما پاسخ دهم؟",
                        parse_mode='HTML',
                        reply_to_message_id=message_id,
                        reply_markup=reply_markup
                    ),
                    0
                )
            elif 'تخلف' in decision:
                log_violation(str(user_id), username, message_text)
                violation_count = count_violations(str(user_id))
                def violation_reason_callback(reason):
                    if not reason:
                        reason = "محتوای غیرمجاز یا تخلف از قوانین"
                    context.job_queue.run_once(
                        lambda ctx: ctx.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ <b>اخطار</b>\n\n"
                                 f"{update.message.from_user.mention_html()} شما یک اخطار دریافت کردید\n\n"
                                 f"📇 <b>علت:</b> {reason}\n\n"
                                 f"❗️<b>تعداد اخطارهای شما:</b> {violation_count}",
                            parse_mode='HTML',
                            reply_to_message_id=message_id
                        ),
                        0
                    )
                generate_violation_reason(message_text, violation_reason_callback)
        should_respond_or_violate(message_text, bot_username, user_id, username, callback)

# --- هندلر CallbackQuery برای اجازه پاسخ ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith('allow_'):
        user_id = query.data.split('_')[1]
        message = query.message.reply_to_message
        if message:
            user_fullname = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            def reply_callback(reply):
                if reply and context.job_queue:
                    context.job_queue.run_once(
                        lambda ctx: ctx.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=reply,
                            parse_mode='HTML',
                            reply_to_message_id=message.message_id
                        ),
                        0
                    )
            generate_response(message.text, user_id, message.from_user.username or "Unknown", user_fullname, reply_callback)
    await query.message.delete()

# --- بقیه توابع بدون تغییر باقی می‌مانند ---
# (برای جلوگیری از تکرار، توابع دیگر مانند scrape_leaderboard، extract_items و غیره که تغییر نکرده‌اند، حذف شده‌اند)

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
    
    user = update.effective_user
    user_fullname = f"{user.first_name} {user.last_name if user.last_name else ''}".strip()
    
    user_message = update.message.text
    chat_history = context.user_data.get("chat_history", [])
    
    system_message = SYSTEM_MESSAGE
    if user_fullname:
        system_message = f"نام و نام خانوادگی کاربر: {user_fullname}\n" + SYSTEM_MESSAGE + "\nلطفا در پاسخ‌های خود از نام کاربر استفاده کنید و اگر نام انگلیسی است به فارسی تبدیل کن."
    
    chat_history.append({"role": "user", "content": user_message})
    history_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-5:]])
    
    payload = {
        "prompt": f"{system_message}\n\n{history_context}\n\nUser: {user_message}\n\nAssistant:",
        "model": "openai-large",
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            ai_response = clean_text(response.text.strip())
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history
            await update.message.reply_text(ai_response, reply_markup=reply_markup)
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
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
    async with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    user_message = update.message.text.lower()
    replied_message = update.message.reply_to_message

    user = update.effective_user
    user_fullname = f"{user.first_name} {user.last_name if user.last_name else ''}".strip()

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
    history_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in user_history[-5:]])
    context.user_data["group_chat_history"] = user_history
    
    system_message = SYSTEM_MESSAGE
    if user_fullname:
        system_message = f"نام و نام خانوادگی کاربر: {user_fullname}\n" + SYSTEM_MESSAGE + "\nلطفا در پاسخ‌های خود از نام کاربر استفاده کنید و اگر نام انگلیسی است به فارسی تبدیل کن."
    
    payload = {
        "prompt": f"{system_message}\n\n{history_context}\n\nUser: {user_message}\n\nAssistant:",
        "model": "openai-large",
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            ai_response = clean_text(response.text.strip())
            user_history.append({"role": "assistant", "content": ai_response})
            context.user_data["group_chat_history"] = user_history
            await update.message.reply_text(ai_response, message_thread_id=thread_id)
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
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

async def main():
    global application
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
            
            await application.initialize()
            logger.info("Application با موفقیت مقداردهی شد.")
            
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

            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("cancel", cancel))
            application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
            application.add_handler(search_conv_handler)
            application.add_handler(image_conv_handler)
            application.add_handler(group_image_conv_handler)
            application.add_handler(InlineQueryHandler(inline_query))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^@PlatoDex\s+\w+'), handle_inline_selection))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_message))
            application.add_handler(CommandHandler("item", process_item_in_group, filters=filters.ChatType.GROUPS))
            application.add_handler(CommandHandler("i", process_item_in_group, filters=filters.ChatType.GROUPS))
            application.add_handler(CommandHandler("w", show_leaderboard, filters=filters.ChatType.GROUPS))
            application.add_handler(CallbackQueryHandler(select_group_item, pattern="^select_group_item_"))
            application.add_handler(CallbackQueryHandler(select_category, pattern="^select_category_"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^prev_page_group"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^next_page_group"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^prev_page_private"))
            application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^next_page_private"))
            application.add_handler(CallbackQueryHandler(back_to_categories_group, pattern="^back_to_categories_group$"))
            
            application.add_error_handler(error_handler)

            port = int(os.getenv("PORT", 8000))
            config = uvicorn.Config(app, host="0.0.0.0", port=port)
            server = uvicorn.Server(config)
            await server.serve()

            return

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