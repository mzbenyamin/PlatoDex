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
import uuid  # برای تولید شناسه‌های منحصر به فرد
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
GROQ_API_KEY = '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'  # اینجا API key Groq رو وارد کن
IMAGE_API_URL = 'https://pollinations.ai/prompt/'  # تصویر همچنان از Pollinations
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'  # API جدید Groq
URL = "https://platopedia.com/items"
BASE_IMAGE_URL = "https://profile.platocdn.com/"
WEBHOOK_URL = "https://platodex.onrender.com/webhook"
EXTRACTED_ITEMS = []
AI_CHAT_USERS = set()
SEARCH_ITEM, SELECT_CATEGORY = range(2)
SELECT_SIZE, GET_PROMPT = range(2, 4)
DEFAULT_CHAT_ID = 789912945
PROCESSED_MESSAGES = set()
PROCESSING_LOCK = asyncio.Lock()  # تغییر به asyncio.Lock

# این تابع جدید را اضافه کنید که callback_data امن ایجاد می‌کند
def generate_safe_callback_data(prompt):
    """
    ایجاد یک callback_data امن برای استفاده در دکمه‌های اینلاین
    به جای استفاده از خود پرامپت، یک شناسه منحصر به فرد تولید می‌کند
    """
    # تولید یک ID منحصر به فرد کوتاه
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
    "متاسفانه از تاریخ 28 فروردین 1404 پلاتو سرور های قدیمی پلاتو که میشد باهاشون کلون کرد رو غیرفعال کرد و دسترسی رو محدود کرد اگر میخوای چند اکانت داشته باشی حتما ایمیل روشون ثبت کن"
    "سلاطین پلاتو ترفندای بیشتر تو @salatin_plato منتظرته! 😎\n\n"
    "شما دیگر نمی توانید فرند ها یا دوستان کاربران دیگر رو ببینید چون اپلیکشن های قدیمی پلاتو که این کار رو میکردند غیرفعال شدند"
    "این پیام آموزشی رو توی هر پاسخ تکرار نکن، فقط توی ذهنت نگه دار و بر اساسش عمل کن و پاسخ بده\\."
    "خلاصه به سوالات جواب بده خیلی بلند نباشه اگر کاربر درخواست توضیحات کرد بعد توضیح بده"
    "با پلاتو ویپ یا vip و پلاتو مگ یا mage میشه چندین اکانت ساخت و سکه جمع آوری کرد و برای کسایی هست که میخوان چند اکانت داشته باشند سکه جمع اوری کنند برای خودشون"
    "پلاتو مگ و ویپ چیکار میکنن؟ پلاتو نسخه اصلی قابلیت کلون شدن رو نداره افراد با این اپ ها میتونن چندین اکانت با این اپ ها بسازند و سکه روزانه را ذخیره و یا برای خودشون ایتم بخرند یا بفروشند فرق مگ و ویپ در این هست. افرادی که قبلا نسخه های قبلی مگ و ویپ داشتند میتونن با اپ های بالا که در کانال آپلود شده اپدیت کنن و به سکه های قفل شده در نسخه قبلی دسترسی‌ داشته باشند"
    "آیدی تلگرامی مدیر سلاطین پلاتو: @BeniHFX ایدی پلاتویی: Salatin"
)

# --- مدیریت گروه و دیتابیس ---
ADMIN_ID = 7403352779  # Admin user ID

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
            text, model, callback = api_queue.get()
            logger.info(f"Processing API request: {text[:50]}...")
            # تغییر به Groq API
            payload = {
                "model": "llama3-70b-8192",  # مدل پیش‌فرض Groq (می‌تونی تغییر بدی)
                "messages": [{"role": "system", "content": SYSTEM_MESSAGE}, {"role": "user", "content": text}]
            }
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            for attempt in range(3):
                try:
                    response = requests.post(GROQ_API_URL, json=payload, headers=headers)
                    response.raise_for_status()
                    ai_reply = response.json()['choices'][0]['message']['content']
                    logger.info(f"API response: {ai_reply[:50]}...")
                    callback(ai_reply.strip())
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
def analyze_message(text, model='openai', callback=lambda x: None):
    api_queue.put((text, model, callback))

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
    analyze_message(prompt, model='openai', callback=callback)

def generate_response(text, user_id, username, callback, chat_history=None):
    response_triggers = get_setting('response_triggers', '')
    
    # Get user's full name if available
    user_fullname = None
    if chat_history and len(chat_history) > 0:
        for msg in chat_history:
            if str(msg[0]) == str(user_id):
                user_fullname = msg[1]  # Username is stored in index 1
                break
    
    logger.info(f"Generating response for {user_id} (@{username}): {text}")
    
    history_context = ""
    if chat_history:
        history_context = "\nتاریخچه چت اخیر:\n"
        for msg in chat_history:
            history_context += f"@{msg[1]}: {msg[2]}\n"
    
    # Create a personalized prompt with user's information
    user_info = f"نام و نام کاربری کاربر: @{username}" if not user_fullname else f"نام و نام کاربری کاربر: {user_fullname} (@{username})"
    
    prompt = f"""
    شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید و به صورت خودمونی جذاب و با ایموجی حرف میزنی به صورت نسل Z و کمی با طنز حرف بزن و شوخی کنه. به مشخصات آیتم‌های پلاتو دسترسی داری و می‌تونی به سوالات کاربر در مورد آیتم‌ها جواب بدی و راهنمایی کنی چطور با دستور /i مشخصات کامل رو بگیرن.
    
    {user_info}
    متن و یا سوال و جواب کاربر: {text}
    تاریخچه پیام کاربران :{history_context}
    
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
    - اگر سوال در مورد سلاطین پلاتو است، توضیح بدهبا این اپ ها میتونن چندین اکانت با این اپ ها بسازند و سکه روزانه را ذخیره و یا برای خودشون ایتم بخرند یا بفروشند فرق مگ و ویپ در این هست. افرادی که قبلا نسخه های قبلی مگ و ویپ داشتند میتونن با اپ های بالا که در کانال آپلود شده اپدیت کنن و به سکه های قفل شده در نسخه قبلی دسترسی‌ داشته باشند"
    "آیدی تلگرامی مدیر سلاطین پلاتو: @BeniHFX ایدی پلاتویی: Salatin"
)



# --- صف API ---
api_queue = queue.Queue()
def process_api_queue():
    while True:
        try:
            text, model, callback = api_queue.get()
            logger.info(f"Processing API request: {text[:50]}...")
            
            # ساخت URL با پارامترهای model و token
            api_url = f"{TEXT_API_URL}?model={GPT_MODEL}&token={POLLINATIONS_TOKEN}"
            
            payload = {
                "messages": [{"role": "user", "content": text}],
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            for attempt in range(3):
                try:
                    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
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
                    elif e.response.status_code == 402:
                        logger.error("API requires authentication. Please visit https://auth.pollinations.ai")
                        callback("متأسفانه API نیاز به احراز هویت دارد. لطفاً بعداً امتحان کنید.")
                        break
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
def analyze_message(text, model='openai', callback=lambda x: None):
    api_queue.put((text, model, callback))



def generate_response(text, user_id, username, callback, chat_history=None):
    # Get user's full name if available
    user_fullname = None
    if chat_history and len(chat_history) > 0:
        for msg in chat_history:
            if str(msg[0]) == str(user_id):
                user_fullname = msg[1]  # Username is stored in index 1
                break
    
    logger.info(f"Generating response for {user_id} (@{username}): {text}")
    
    history_context = ""
    if chat_history:
        history_context = "\nتاریخچه چت اخیر:\n"
        for msg in chat_history:
            history_context += f"@{msg[1]}: {msg[2]}\n"
    
    # Create a personalized prompt with user's information
    user_info = f"نام و نام کاربری کاربر: @{username}" if not user_fullname else f"نام و نام کاربری کاربر: {user_fullname} (@{username})"
    
    prompt = f"""
    شما دستیار هوشمند گروه سلاطین پلاتو هستید و به سبک نسل الفا صحبت میکنید و خیلی خودمونی حرف میزنید
    {user_info}
    متن و یا سوال و جواب کاربر: {text}
    تاریخچه پیام کاربران :{history_context﴿
    به عنوان یک دستیار حرفه‌ای و دوستانه:
    - لطفا در پاسخ از نام کاربر استفاده کن و اگر نام انگلیسی است به فارسی تبدیل کن
    - پاسخ باید کوتاه، دقیق و جذاب باشد
    - از ایموجی‌های مناسب استفاده کن
    - با لحن نسل Z و دوستانه صحبت کن
    - اگر سوال مرتبط با کلمات کلیدی باشد، پاسخ مرتبط بده
    - اگر نیاز است، هشدار دهید که برای اطلاعات دقیق‌تر با متخصص مشورت کنند
    - اگر سوالی است که نیاز به اجازه کاربر دارد، از او اجازه بگیرید
    - اگر سوال در مورد آیتم‌های پلاتو است، راهنمایی کن که از دستور /i استفاده کنند
    - اگر سوال در مورد چند اکانت است، توضیح بده که از تاریخ 28 فروردین 1404 پلاتو سرورهای قدیمی غیرفعال شده‌اند
    - اگر سوال در مورد دوستان است، توضیح بده که دیگر نمی‌توان دوستان کاربران دیگر را دید
    - اگر سوال در مورد سلاطین پلاتو است، توضیح بده که اولین رسانه فارسی‌زبون پلاتو از 1400 با مدیریت بنیامین است
    مثال:
    پیام: "سوال دارم"
    پاسخ: "سلام [نام کاربر]! 😊 چطور می‌تونم کمکت کنم؟ هر سوالی داری بپرس، من اینجام تا راهنماییت کنم! 🎮✨"
    """
    analyze_message(prompt, model='openai', callback=callback)



# --- دستورات ادمین و هندلرهای مدیریتی ---
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    if update.message.chat.type == 'private' and user_id == ADMIN_ID:
        keyboard = [
            ['تنظیم پاسخ‌ها', 'تنظیم تخلف‌ها'],
            ['تست API', 'وضعیت ربات'],
            ['تنظیم عدم پاسخ', 'تنظیم عدم تخلف'],
            ['خروج']
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

async def test_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type == 'private' and user_id == ADMIN_ID:
        await update.message.reply_text("🔄 در حال تست API...")
        
        try:
            # تست ساده API
            # ساخت URL با پارامترهای model و token
            api_url = f"{TEXT_API_URL}?model={GPT_MODEL}&token={POLLINATIONS_TOKEN}"
            
            test_payload = {
                "messages": [{"role": "user", "content": "سلام، این یک تست است"}],
                "max_tokens": 100,
                "temperature": 0.7
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(api_url, json=test_payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                await update.message.reply_text(
                    f"✅ API با موفقیت کار می‌کند!\n\n"
                    f"مدل: {GPT_MODEL}\n"
                    f"توکن: {POLLINATIONS_TOKEN[:8]}...\n"
                    f"پاسخ: {response.text[:100]}..."
                )
            else:
                await update.message.reply_text(
                    f"❌ خطا در API!\n\n"
                    f"کد خطا: {response.status_code}\n"
                    f"پیام: {response.text}"
                )
                
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در تست API: {str(e)}")
    else:
        await update.message.reply_text("شما دسترسی ادمین ندارید.")

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
    await update.message.reply_text(
        f"<b>⚠️ اخطار</b>\n\nکاربر <a href='tg://user?id={target_user_id}'>@{target_username}</a> شما یک اخطار دریافت کردید\n\n<b>📇 علت:</b> اخطار دستی",
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
    message_id = update.message.message_id
    add_to_chat_history(chat_id, user_id, username, message_text, message_id)
    chat_history = get_recent_chat_history(chat_id)
    # اگر پیام به ربات مربوط بود یا در چت خصوصی بود
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
        generate_response(message_text, user_id, username, callback, chat_history)
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
                generate_response(message_text, user_id, username, reply_callback, chat_history)
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


# --- هندلر CallbackQuery برای اجازه پاسخ ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith('allow_'):
        user_id = query.data.split('_')[1]
        message = query.message.reply_to_message
        if message:
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
            generate_response(message.text, user_id, message.from_user.username or "Unknown", reply_callback)
    await query.message.delete()
# --- تابع main اصلی ---
async def main():
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("warn", warn))
    application.add_handler(CommandHandler("violations", violations)) 
    application.add_handler(CommandHandler("clearviolations", clear_violations_cmd))
    application.add_handler(CommandHandler("admin", admin_start))
    application.add_handler(CommandHandler("test_api", test_api))
    application.add_handler(CallbackQueryHandler(handle_callback_query, pattern="^(allow_|deny_).*$"))

    return application

application = None

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    global application
    update = await request.json()
    update_obj = Update.de_json(update, application.bot)
    update_id = update_obj.update_id
    logger.info(f"دریافت درخواست با update_id: {update_id}")
    async with PROCESSING_LOCK:
        if update_id in PROCESSED_MESSAGES:
            logger.warning(f"درخواست تکراری با update_id: {update_id} - نادیده گرفته شد")
            return {"status": "ok"}
        PROCESSED_MESSAGES.add(update_id)
    asyncio.create_task(application.process_update(update_obj))
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "PlatoDex Bot is running!"}

@app.head("/webhook")
async def webhook_head():
    return {"status": "online"}

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

# نمایش لیدربرد
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    async with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری در گروه با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)
    
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
    
    try:
        await context.bot.get_chat(chat_id)
    except Exception as e:
        logger.error(f"خطا در دسترسی به چت {chat_id}: {e}")
        if "Forbidden" in str(e):
            await update.message.reply_text(clean_text("متأسفم، من از این گروه بیرون انداخته شدم! 😕 دوباره منو اد کن تا کمکت کنم."), message_thread_id=thread_id)
        else:
            await update.message.reply_text(clean_text("یه مشکلی پیش اومد، نمی‌تونم چت رو پیدا کنم! 😅"), message_thread_id=thread_id)
        return
    
    leaderboard_data = scrape_leaderboard()
    if not leaderboard_data:
        await update.message.reply_text(clean_text("مشکلی در دریافت لیدربرد پیش اومد! 😅 بعداً امتحان کنید."), message_thread_id=thread_id)
        return
    
    leaderboard_text = "🏆 لیدربرد بازیکنان برتر:\n\n"
    for i, player in enumerate(leaderboard_data, 1):
        leaderboard_text += f"{i}. {player['username']} - {player['wins']} برد\n"
    
    await update.message.reply_text(clean_text(leaderboard_text), message_thread_id=thread_id)

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
    
    # استخراج پرامپت از callback_data یا از context.user_data
    callback_id = query.data
    
    # بررسی اگر mapping برای این callback_id در context.user_data وجود دارد
    callback_mapping = context.user_data.get("callback_to_prompt", {})
    api_prompt = callback_mapping.get(callback_id, "")
    
    # اگر پرامپت در callback_mapping نباشد، سعی می‌کنیم از context.user_data استفاده کنیم
    if not api_prompt:
        logger.warning(f"پرامپت برای {callback_id} در callback_mapping پیدا نشد، از api_prompt استفاده می‌شود")
        api_prompt = context.user_data.get("api_prompt", "")
    
    original_prompt = context.user_data.get("original_prompt", "")
    
    # اگر هنوز پرامپتی پیدا نشد، خطا نمایش می‌دهیم
    if not api_prompt:
        logger.error("پرامپت برای بازتولید تصویر پیدا نشد!")
        await query.message.reply_text(clean_text("متأسفانه نمی‌توانم پرامپت را پیدا کنم. لطفاً دوباره تلاش کنید."))
        return ConversationHandler.END
    
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    chat_id = query.message.chat_id
    
    last_image_message_id = context.user_data.get("last_image_message_id")
    if last_image_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_image_message_id)
            logger.info(f"تصویر قبلی با ID {last_image_message_id} حذف شد.")
        except Exception as e:
            logger.warning(f"خطا در حذف تصویر قبلی: {e}")
            # فقط یک پیام هشدار نمایش می‌دهیم، اما عملیات را ادامه می‌دهیم
    
    loading_message = await context.bot.send_message(
        chat_id=chat_id,
        text=clean_text("🖌️ در حال طراحی مجدد عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    # ذخیره کردن آیدی پیام بارگذاری برای حذف بعدی
    loading_message_id = loading_message.message_id
    context.user_data["loading_message_id"] = loading_message_id
    
    # تولید seed تصادفی
    seed = random.randint(1, 1000000)
    
    # سیستم retry برای مدیریت خطای 502
    max_retries = 3
    retry_delay = 2  # ثانیه
    
    for attempt in range(max_retries):
        try:
            # ایجاد URL با seed مختلف برای هر تلاش
            retry_seed = seed + attempt
            api_url = f"{IMAGE_API_URL}{api_prompt}?width=1024&height=1024&nologo=true&seed={retry_seed}"
            
            logger.info(f"تلاش {attempt + 1}/{max_retries} برای تولید مجدد تصویر با پرامپت: {api_prompt[:50]}...")
            
            async with asyncio.timeout(40):  # تایم‌اوت طولانی‌تر برای API
                response = requests.get(api_url, timeout=40)
            
            if response.status_code == 200:
                # تصویر با موفقیت تولید شد
                logger.info(f"تصویر با موفقیت تولید شد (تلاش {attempt + 1})")
                
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
                    logger.info(f"پیام بارگذاری با ID {loading_message_id} حذف شد.")
                except Exception as e:
                    logger.warning(f"خطا در حذف پیام بارگذاری: {e}")
                
                # حداکثر طول پرامپت برای نمایش در کپشن
                display_prompt = original_prompt
                if len(display_prompt) > 500:
                    display_prompt = display_prompt[:497] + "..."
                
                # تولید callback_data امن جدید
                safe_callback_data = generate_safe_callback_data(api_prompt)
                
                # آپدیت کردن مپینگ callback_data
                callback_mapping = context.user_data.get("callback_to_prompt", {})
                callback_mapping[safe_callback_data] = api_prompt
                context.user_data["callback_to_prompt"] = callback_mapping
                
                keyboard = [[InlineKeyboardButton("🔄 طراحی مجدد تصویر", callback_data=safe_callback_data)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                original_message_id = context.user_data.get("original_message_id", query.message.reply_to_message.message_id)
                caption_text = clean_text(f"🪄 پرامت تصویر ایجاد شده شما:\n\n{display_prompt}\n\n@PlatoDex")
                
                message = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=response.content,
                    caption=caption_text,
                    reply_markup=reply_markup,
                    message_thread_id=thread_id,
                    reply_to_message_id=original_message_id
                )
                context.user_data["last_image_message_id"] = message.message_id
                logger.info(f"تصویر جدید با message_id {message.message_id} ارسال شد.")
                
                # اگر موفق شد از حلقه خارج می‌شویم
                break
                
            elif response.status_code == 502:
                # خطای 502، سعی مجدد
                logger.warning(f"خطای 502 از API در تلاش {attempt + 1}. در حال تلاش مجدد...")
                
                # به کاربر اطلاع بدهیم که در حال تلاش مجدد هستیم
                if attempt < max_retries - 1:  # اگر این آخرین تلاش نیست
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=loading_message_id,
                            text=clean_text(f"🖌️ خطای سرور (502)! تلاش مجدد {attempt + 2}/{max_retries}... لطفاً صبر کنید.")
                        )
                    except Exception as e:
                        logger.warning(f"خطا در به‌روزرسانی پیام بارگذاری: {e}")
                    
                    # صبر قبل از تلاش بعدی
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    # این آخرین تلاش بود و باز هم شکست خورد
                    raise Exception("همه تلاش‌ها با خطای 502 مواجه شدند.")
                    
            else:
                # خطاهای دیگر
                error_message = f"خطای {response.status_code} از API دریافت شد."
                logger.error(error_message)
                raise Exception(error_message)
                
        except asyncio.TimeoutError:
            logger.warning(f"تایم‌اوت در تلاش {attempt + 1} برای تولید مجدد تصویر.")
            
            # به کاربر اطلاع بدهیم که تایم‌اوت رخ داده
            if attempt < max_retries - 1:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=loading_message_id,
                        text=clean_text(f"🖌️ تایم‌اوت! تلاش مجدد {attempt + 2}/{max_retries}... لطفاً صبر کنید.")
                    )
                except Exception as e:
                    logger.warning(f"خطا در به‌روزرسانی پیام بارگذاری: {e}")
                
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                # این آخرین تلاش بود و باز هم شکست خورد
                raise Exception("همه تلاش‌ها با تایم‌اوت مواجه شدند.")
                
        except Exception as e:
            # اگر این آخرین تلاش نیست، دوباره تلاش می‌کنیم
            if attempt < max_retries - 1:
                logger.warning(f"خطا در تلاش {attempt + 1}: {e}. در حال تلاش مجدد...")
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=loading_message_id,
                        text=clean_text(f"🖌️ خطا رخ داد! تلاش مجدد {attempt + 2}/{max_retries}... لطفاً صبر کنید.")
                    )
                except Exception as edit_error:
                    logger.warning(f"خطا در به‌روزرسانی پیام بارگذاری: {edit_error}")
                
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                # اگر این آخرین تلاش بود، خطا را نمایش می‌دهیم
                logger.error(f"همه تلاش‌ها برای تولید مجدد تصویر با خطا مواجه شدند: {e}")
                raise
    else:
        # اگر از حلقه خارج شدیم بدون اینکه تصویر را با موفقیت ارسال کنیم
        # این حالت زمانی رخ می‌دهد که همه تلاش‌ها شکست بخورند اما exception هم پرتاب نشود
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
        except Exception as e:
            logger.warning(f"خطا در حذف پیام بارگذاری پس از شکست همه تلاش‌ها: {e}")
            
        await context.bot.send_message(
            chat_id=chat_id,
            text=clean_text("متأسفانه همه تلاش‌ها برای تولید تصویر با شکست مواجه شدند. لطفاً بعداً دوباره امتحان کنید."),
            message_thread_id=thread_id
        )
            
    # مدیریت خطا برای کل تابع
    try:
        pass  # اینجا کاری انجام نمی‌دهیم، فقط برای مدیریت خطاهای احتمالی است
    except Exception as e:
        logger.error(f"خطای نهایی در تولید مجدد تصویر گروه: {e}")
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
        except Exception as del_e:
            logger.warning(f"خطا در حذف پیام بارگذاری در حالت خطا: {del_e}")
        
        error_message = "خطایی رخ داد. لطفاً بعداً امتحان کنید."
        if "502" in str(e):
            error_message = "خطای سرور (502). پلتفرم تولید تصویر در حال حاضر در دسترس نیست، لطفاً بعداً امتحان کنید."
        elif "timed out" in str(e).lower() or "timeout" in str(e).lower():
            error_message = "زمان پاسخگویی API به پایان رسید. لطفاً با پرامپت کوتاه‌تر امتحان کنید یا بعداً تلاش کنید."
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=clean_text(error_message),
            message_thread_id=thread_id
        )
    
    return ConversationHandler.END

async def start_group_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    async with PROCESSING_LOCK:
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
    
    # اینجا متن رو می‌گیریم و اگر طولانی بود کوتاهش می‌کنیم
    prompt = " ".join(context.args).strip()
    original_prompt = prompt
    
    if not prompt:
        await update.message.reply_text(
            clean_text("پرامپت خالیه! یه توضیح برای تصویر بده. مثلاً: /p A flying car"),
            message_thread_id=thread_id
        )
        return
    
    # ذخیره پرامپت اصلی برای استفاده در پیام
    if len(prompt) > 3000:
        shortened_prompt = prompt[:3000]
        logger.warning(f"پرامپت بیش از حد طولانی است ({len(prompt)} کاراکتر). کوتاه شد به 3000 کاراکتر.")
        prompt = shortened_prompt
    
    # برای API ما باید متن رو به یک اندازه مناسب کوتاه کنیم (حداکثر 1000 کاراکتر)
    api_prompt = prompt
    if len(prompt) > 1000:
        # برای API فقط 1000 کاراکتر اول استفاده می‌شود
        api_prompt = prompt[:1000]
        logger.info(f"پرامپت برای API به 1000 کاراکتر کوتاه شد")
    
    loading_message = await update.message.reply_text(
        clean_text("🖌️ در حال طراحی عکس... لطفاً صبر کنید."),
        message_thread_id=thread_id
    )
    
    # ذخیره کردن آیدی پیام بارگذاری برای حذف بعدی
    loading_message_id = loading_message.message_id
    context.user_data["loading_message_id"] = loading_message_id
    
    # تولید seed تصادفی
    seed = random.randint(1, 999999)
    
    # سیستم retry برای مدیریت خطای 502
    max_retries = 3
    retry_delay = 2  # ثانیه
    
    for attempt in range(max_retries):
        try:
            # ایجاد URL با seed مختلف برای هر تلاش
            retry_seed = seed + attempt
            api_url = f"{IMAGE_API_URL}{api_prompt}?width=1024&height=1024&nologo=true&seed={retry_seed}"
            
            logger.info(f"تلاش {attempt + 1}/{max_retries} برای تولید تصویر با پرامپت: {api_prompt[:50]}...")
            
            async with asyncio.timeout(40):  # تایم‌اوت طولانی‌تر برای API
                response = requests.get(api_url, timeout=40)
            
            if response.status_code == 200:
                # تصویر با موفقیت تولید شد
                logger.info(f"تصویر با موفقیت تولید شد (تلاش {attempt + 1})")
                
                # اول پیام بارگذاری رو پاک می‌کنیم
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
                    logger.info(f"پیام بارگذاری با ID {loading_message_id} حذف شد.")
                except Exception as e:
                    logger.warning(f"خطا در حذف پیام بارگذاری: {e}")
                
                # حداکثر طول پرامپت برای نمایش در کپشن
                display_prompt = original_prompt
                if len(display_prompt) > 500:
                    display_prompt = display_prompt[:497] + "..."
                
                # تولید callback_data امن
                safe_callback_data = generate_safe_callback_data(api_prompt)
                
                # ذخیره پرامپت‌ها برای استفاده در تولید مجدد
                callback_mapping = context.user_data.get("callback_to_prompt", {})
                callback_mapping[safe_callback_data] = api_prompt
                context.user_data["callback_to_prompt"] = callback_mapping
                context.user_data["original_prompt"] = original_prompt
                context.user_data["api_prompt"] = api_prompt
                
                keyboard = [[InlineKeyboardButton("🔄 طراحی مجدد تصویر", callback_data=safe_callback_data)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # ارسال تصویر با کپشن مناسب
                caption_text = clean_text(f"🪄 پرامت تصویر ایجاد شده شما:\n\n{display_prompt}\n\n@PlatoDex")
                
                message = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=response.content,
                    caption=caption_text,
                    reply_markup=reply_markup,
                    message_thread_id=thread_id,
                    reply_to_message_id=update.message.message_id
                )
                context.user_data["last_image_message_id"] = message.message_id
                context.user_data["original_message_id"] = update.message.message_id
                
                # اگر موفق شد از حلقه خارج می‌شویم
                break
                
            elif response.status_code == 502:
                # خطای 502، سعی مجدد
                logger.warning(f"خطای 502 از API در تلاش {attempt + 1}. در حال تلاش مجدد...")
                
                # به کاربر اطلاع بدهیم که در حال تلاش مجدد هستیم
                if attempt < max_retries - 1:  # اگر این آخرین تلاش نیست
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=loading_message_id,
                            text=clean_text(f"🖌️ خطای سرور (502)! تلاش مجدد {attempt + 2}/{max_retries}... لطفاً صبر کنید.")
                        )
                    except Exception as e:
                        logger.warning(f"خطا در به‌روزرسانی پیام بارگذاری: {e}")
                    
                    # صبر قبل از تلاش بعدی
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    # این آخرین تلاش بود و باز هم شکست خورد
                    raise Exception("همه تلاش‌ها با خطای 502 مواجه شدند.")
                    
            else:
                # خطاهای دیگر
                error_message = f"خطای {response.status_code} از API دریافت شد."
                logger.error(error_message)
                raise Exception(error_message)
                
        except asyncio.TimeoutError:
            logger.warning(f"تایم‌اوت در تلاش {attempt + 1} برای تولید تصویر.")
            
            # به کاربر اطلاع بدهیم که تایم‌اوت رخ داده
            if attempt < max_retries - 1:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=loading_message_id,
                        text=clean_text(f"🖌️ تایم‌اوت! تلاش مجدد {attempt + 2}/{max_retries}... لطفاً صبر کنید.")
                    )
                except Exception as e:
                    logger.warning(f"خطا در به‌روزرسانی پیام بارگذاری: {e}")
                
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                # این آخرین تلاش بود و باز هم شکست خورد
                raise Exception("همه تلاش‌ها با تایم‌اوت مواجه شدند.")
                
        except Exception as e:
            # اگر این آخرین تلاش نیست، دوباره تلاش می‌کنیم
            if attempt < max_retries - 1:
                logger.warning(f"خطا در تلاش {attempt + 1}: {e}. در حال تلاش مجدد...")
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=loading_message_id,
                        text=clean_text(f"🖌️ خطا رخ داد! تلاش مجدد {attempt + 2}/{max_retries}... لطفاً صبر کنید.")
                    )
                except Exception as edit_error:
                    logger.warning(f"خطا در به‌روزرسانی پیام بارگذاری: {edit_error}")
                
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                # اگر این آخرین تلاش بود، خطا را نمایش می‌دهیم
                logger.error(f"همه تلاش‌ها برای تولید تصویر با خطا مواجه شدند: {e}")
                raise
    else:
        # اگر از حلقه خارج شدیم بدون اینکه تصویر را با موفقیت ارسال کنیم
        # این حالت زمانی رخ می‌دهد که همه تلاش‌ها شکست بخورند اما exception هم پرتاب نشود
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
        except Exception as e:
            logger.warning(f"خطا در حذف پیام بارگذاری پس از شکست همه تلاش‌ها: {e}")
            
        await update.message.reply_text(
            clean_text("متأسفانه همه تلاش‌ها برای تولید تصویر با شکست مواجه شدند. لطفاً بعداً دوباره امتحان کنید."),
            message_thread_id=thread_id
        )
            
    # مدیریت خطا برای کل تابع
    # این بخش فقط در صورتی اجرا می‌شود که exception از حلقه for بالا رها شود
    try:
        pass  # اینجا کاری انجام نمی‌دهیم، فقط برای مدیریت خطاهای احتمالی است
    except Exception as e:
        # خطای عمومی در پردازش درخواست
        logger.error(f"خطای نهایی در تولید تصویر گروه: {e}")
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message_id)
        except Exception as del_e:
            logger.warning(f"خطا در حذف پیام بارگذاری: {del_e}")
        
        error_message = "خطایی رخ داد. لطفاً بعداً امتحان کنید."
        if "502" in str(e):
            error_message = "خطای سرور (502). پلتفرم تولید تصویر در حال حاضر در دسترس نیست، لطفاً بعداً امتحان کنید."
        elif "timed out" in str(e).lower() or "timeout" in str(e).lower():
            error_message = "زمان پاسخگویی API به پایان رسید. لطفاً با پرامپت کوتاه‌تر امتحان کنید یا بعداً تلاش کنید."
        
        await update.message.reply_text(
            clean_text(error_message),
            message_thread_id=thread_id
        )

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
    async with PROCESSING_LOCK:
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
    # Check if we have an explicitly saved group interaction state
    is_group = is_group or context.user_data.get("is_group_interaction", False)
    group_chat_id = context.user_data.get("group_chat_id", None)
    group_thread_id = context.user_data.get("group_thread_id", None)
    
    matching_items = context.user_data.get("matching_items", [])
    if not matching_items:
        logger.warning("No matching items found in user_data")
        if update.callback_query and update.callback_query.message:
            keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
            await update.callback_query.message.reply_text(
                clean_text("هیچ آیتمی پیدا نشد! 😕"), 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    # When returning from an item detail view, use the stored page number
    if update.callback_query and "back_to_items" in update.callback_query.data:
        page = context.user_data.get("previous_page", 0)
        context.user_data["page"] = page
    else:
        page = context.user_data.get("page", 0)
    
    items_per_page = 10
    total_pages = max(1, (len(matching_items) + items_per_page - 1) // items_per_page)
    
    # Ensure page is within valid range
    page = max(0, min(page, total_pages - 1))
    context.user_data["page"] = page
    
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
        
        try:
            # Send item details directly
            message = None
            if update.message:
                if item["images"]:
                    message = await update.message.reply_photo(photo=item["images"][0], caption=results_text, reply_markup=reply_markup)
                else:
                    message = await update.message.reply_text(results_text, reply_markup=reply_markup)
            elif update.callback_query and update.callback_query.message:
                chat_id = update.callback_query.message.chat_id
                if item["images"]:
                    message = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=item["images"][0],
                        caption=results_text,
                        reply_markup=reply_markup
                    )
                else:
                    message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=results_text,
                        reply_markup=reply_markup
                    )
            
            if message:
                context.user_data["current_item_message_id"] = message.message_id
                for i, audio_info in enumerate(item["audios"], 1):
                    await send_audio(update, context, item, audio_info, i, reply_markup)
        except Exception as e:
            logger.error(f"Error sending single item: {e}")
            
        return
    
    # Building keyboard with items
    keyboard = []
    for i, item in enumerate(current_items, start_idx + 1):
        price_type = "Pips" if item["price"]["type"] == "premium" else item["price"]["type"]
        price_info = clean_text(f"{item['price']['value']} {price_type}")
        button_text = clean_text(f"{i}. {item['name']} - {price_info}")
        # Always include group flag in the callback data for consistency 
        callback_data = f"{'select_group_item' if is_group else 'select_item'}_{item['id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        # Include group flag consistently in pagination callbacks
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prev_page_{'group' if is_group else 'private'}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"next_page_{'group' if is_group else 'private'}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add back to categories button for group chats
    if is_group:
        keyboard.append([InlineKeyboardButton("🔙 برگشت به دسته‌بندی‌ها", callback_data="back_to_categories_group")])
    elif not is_group:
        keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = clean_text(f"این آیتم‌ها رو پیدا کردم (صفحه {page + 1} از {total_pages})، کدوم رو می‌خوای؟ 👇")
    
    try:
        if is_group and update.message:
            # Handle original group command
            thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
            message = await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
            context.user_data["items_list_message_id"] = message.message_id
            logger.info(f"Sent items list page {page+1}/{total_pages} in group")
        elif is_group and update.callback_query:
            # Handle group callback (pagination/selection)
            thread_id = group_thread_id
            
            # For group callbacks, send a new message instead of editing
            chat_id = update.callback_query.message.chat_id
            try:
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    message_thread_id=thread_id
                )
                context.user_data["items_list_message_id"] = message.message_id
                logger.info(f"Sent new items list page {page+1}/{total_pages} in group after pagination")
                
                # Try to delete the previous message to keep the chat clean
                try:
                    await context.bot.delete_message(
                        chat_id=chat_id, 
                        message_id=update.callback_query.message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Could not delete previous message in group: {e}")
            except Exception as e:
                logger.error(f"Error sending new message in group: {e}")
                # Fallback to trying to edit the message
                try:
                    await update.callback_query.message.edit_text(
                        text=message_text,
                        reply_markup=reply_markup
                    )
                except Exception as edit_error:
                    logger.error(f"Error editing message in group: {edit_error}")
        elif update.callback_query and "back_to_items" in update.callback_query.data:
            # When coming back from item details, always send a new message
            message = await context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=message_text,
                reply_markup=reply_markup
            )
            context.user_data["items_list_message_id"] = message.message_id
        elif update.callback_query:
            try:
                # Try to edit existing message
                await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)
                context.user_data["items_list_message_id"] = update.callback_query.message.message_id
            except error.BadRequest as e:
                # If editing fails, send a new message
                if "Message to edit not found" in str(e) or "There is no text in the message to edit" in str(e):
                    logger.warning(f"Could not edit message, sending new one: {e}")
                    message = await context.bot.send_message(
                        chat_id=update.callback_query.message.chat_id,
                        text=message_text,
                        reply_markup=reply_markup
                    )
                    context.user_data["items_list_message_id"] = message.message_id
                else:
                    # For other errors, re-raise
                    raise
        else:
            message = await update.message.reply_text(message_text, reply_markup=reply_markup)
            context.user_data["items_list_message_id"] = message.message_id
    except Exception as e:
        # Last resort error handling
        logger.error(f"Error in send_paginated_items: {e}")
        try:
            chat_id = None
            if update.callback_query and update.callback_query.message:
                chat_id = update.callback_query.message.chat_id
            elif update.message:
                chat_id = update.message.chat_id
            
            if chat_id:
                thread_id = group_thread_id if is_group else None
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=clean_text("مشکلی در نمایش آیتم‌ها پیش آمد. لطفاً دوباره امتحان کنید."),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]),
                    message_thread_id=thread_id
                )
        except Exception:
            pass  # If even this fails, just silently give up

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
    
    # Save the current state so we can restore it when going back
    context.user_data["previous_page"] = context.user_data.get("page", 0)
    
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
    
    try:
        # Try to delete the items list message first
        items_list_message_id = query.message.message_id
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=items_list_message_id)
            logger.info(f"Deleted items list message with ID {items_list_message_id}")
        except Exception as e:
            logger.warning(f"Could not delete items list message: {e}")
        
        # Send the item details as a new message
        if item["images"]:
            # For items with images, send a photo with caption
            message = await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=item["images"][0],
                caption=results_text,
                reply_markup=reply_markup
            )
        else:
            # For items without images, send a text message
            message = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=results_text,
                reply_markup=reply_markup
            )
        
        # Store the current item message ID for future reference
        context.user_data["current_item_message_id"] = message.message_id
        
        # Send audio attachments if any
        for i, audio_info in enumerate(item["audios"], 1):
            await send_audio(update, context, item, audio_info, i, reply_markup)
    
    except Exception as e:
        logger.error(f"Error in select_item: {e}")
        try:
            # Fallback message if everything else fails
            keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=clean_text("مشکلی در نمایش جزئیات آیتم پیش آمد. لطفاً دوباره امتحان کنید."),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass  # If even this fails, just silently give up
    
    return SEARCH_ITEM

async def back_to_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        # Don't try to edit the current message if it's a photo message
        # Instead, always send a new message with the items list
        current_message = query.message
        chat_id = current_message.chat_id
        
        # First, try to delete the current item display message
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=current_message.message_id)
            logger.info(f"Deleted item display message with ID {current_message.message_id}")
        except Exception as e:
            logger.warning(f"Could not delete item display message: {e}")
        
        # Send a new message with the items list
        if "matching_items" in context.user_data:
            message_text = clean_text("نمایش لیست آیتم‌ها...")
            temp_message = await context.bot.send_message(
                chat_id=chat_id,
                text=message_text
            )
            
            # Now send the actual items list
            await send_paginated_items(update, context, is_group=False)
            
            # Clean up the temporary message
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
            except Exception:
                pass
        else:
            # If there are no matching items in user_data, go back to home
            keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
            await context.bot.send_message(
                chat_id=chat_id,
                text=clean_text("متأسفانه لیست آیتم‌ها از دست رفته است. به منوی اصلی برگردید."),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Error in back_to_items: {e}")
        try:
            # Fallback message if everything else fails
            keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=clean_text("مشکلی در بازگشت به لیست آیتم‌ها پیش آمد. لطفاً دوباره امتحان کنید."),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass  # If even this fails, just give up silently
    
    return SEARCH_ITEM

async def process_item_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_id = update.message.message_id
    async with PROCESSING_LOCK:
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
    
    # Mark this as a group interaction in the user data
    context.user_data["is_group_interaction"] = True
    context.user_data["group_chat_id"] = chat_id
    context.user_data["group_thread_id"] = thread_id
    
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
    # Check if we have an explicitly saved group interaction state
    is_group = is_group or context.user_data.get("is_group_interaction", False)
    group_thread_id = context.user_data.get("group_thread_id", None)
    
    categories = context.user_data.get("categories", sorted(set(item["category"] for item in EXTRACTED_ITEMS)))
    if not categories:
        logger.warning("No categories found in user_data")
        if update.callback_query and update.callback_query.message:
            keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
            await update.callback_query.message.reply_text(
                clean_text("هیچ دسته‌بندی پیدا نشد! 😕"), 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
        
    page = context.user_data.get("page", 0)
    items_per_page = 10
    total_pages = max(1, (len(categories) + items_per_page - 1) // items_per_page)
    
    # Ensure page is within valid range
    page = max(0, min(page, total_pages - 1))
    context.user_data["page"] = page
    
    start_idx = page * items_per_page
    end_idx = min((page + 1) * items_per_page, len(categories))
    current_categories = categories[start_idx:end_idx]
    
    keyboard = []
    for i, category in enumerate(current_categories, start_idx + 1):
        # Add _group suffix for group callbacks to ensure proper handling
        if is_group:
            callback_data = f"select_category_group_{category}"
        else:
            callback_data = f"select_category_{category}"
        keyboard.append([InlineKeyboardButton(clean_text(f"{i}. {category}"), callback_data=callback_data)])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prev_page_{'group' if is_group else 'private'}_categories"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"next_page_{'group' if is_group else 'private'}_categories"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add back to categories button for group chats
    if is_group:
        keyboard.append([InlineKeyboardButton("🔙 برگشت به دسته‌بندی‌ها", callback_data="back_to_categories_group")])
    elif not is_group:
        keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = clean_text(f"دسته‌بندی‌ها (صفحه {page + 1} از {total_pages})، کدوم رو می‌خوای؟ 👇")
    
    try:
        if is_group and update.message:
            # Handle original group command
            thread_id = update.message.message_thread_id if hasattr(update.message, 'is_topic_message') and update.message.is_topic_message else None
            message = await update.message.reply_text(message_text, reply_markup=reply_markup, message_thread_id=thread_id)
            context.user_data["categories_message_id"] = message.message_id
            logger.info(f"Sent categories page {page + 1}/{total_pages} in group chat")
        elif is_group and update.callback_query:
            # For group callbacks, send a new message instead of trying to edit
            thread_id = group_thread_id
            chat_id = update.callback_query.message.chat_id
            
            try:
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    message_thread_id=thread_id
                )
                context.user_data["categories_message_id"] = message.message_id
                logger.info(f"Sent new categories page {page + 1}/{total_pages} in group after pagination")
                
                # Try to delete the previous message to keep the chat clean
                try:
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=update.callback_query.message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Could not delete previous categories message in group: {e}")
            except Exception as e:
                logger.error(f"Error sending new categories message in group: {e}")
                # Fallback to trying to edit if sending fails
                try:
                    await update.callback_query.message.edit_text(
                        text=message_text,
                        reply_markup=reply_markup
                    )
                except Exception as edit_error:
                    logger.error(f"Error editing categories message in group: {edit_error}")
        elif update.callback_query:
            # For private chat pagination, handle differently
            if any(x in update.callback_query.data for x in ["prev_page", "next_page"]):
                try:
                    # Try to edit first
                    await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)
                    context.user_data["categories_message_id"] = update.callback_query.message.message_id
                    logger.info(f"Edited message to show categories page {page + 1}/{total_pages}")
                except error.BadRequest as e:
                    # If editing fails, send a new message
                    logger.warning(f"Could not edit message for categories, sending new one: {e}")
                    message = await context.bot.send_message(
                        chat_id=update.callback_query.message.chat_id,
                        text=message_text,
                        reply_markup=reply_markup
                    )
                    context.user_data["categories_message_id"] = message.message_id
                    
                    # Try to delete the previous message
                    try:
                        await context.bot.delete_message(
                            chat_id=update.callback_query.message.chat_id,
                            message_id=update.callback_query.message.message_id
                        )
                    except Exception as del_err:
                        logger.warning(f"Could not delete previous categories message: {del_err}")
            else:
                # For first-time category display in private chat
                try:
                    await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)
                    context.user_data["categories_message_id"] = update.callback_query.message.message_id
                except error.BadRequest as e:
                    logger.warning(f"Could not edit message for categories, sending new one: {e}")
                    message = await context.bot.send_message(
                        chat_id=update.callback_query.message.chat_id,
                        text=message_text,
                        reply_markup=reply_markup
                    )
                    context.user_data["categories_message_id"] = message.message_id
        else:
            # First-time category display in private chat direct message
            message = await update.message.reply_text(message_text, reply_markup=reply_markup)
            context.user_data["categories_message_id"] = message.message_id
            logger.info(f"Sent categories page {page + 1}/{total_pages} in private chat")
    except Exception as e:
        # Last resort error handling
        logger.error(f"Error in send_paginated_categories: {e}")
        try:
            chat_id = None
            if update.callback_query and update.callback_query.message:
                chat_id = update.callback_query.message.chat_id
            elif update.message:
                chat_id = update.message.chat_id
            
            if chat_id:
                thread_id = group_thread_id if is_group else None
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=clean_text("مشکلی در نمایش دسته‌بندی‌ها پیش آمد. لطفاً دوباره امتحان کنید."),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]])
                )
        except Exception:
            pass  # If even this fails, just silently give up

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Check if this is a group interaction
    is_group = "group" in query.data or context.user_data.get("is_group_interaction", False)
    
    # Extract category name from callback data, handling both formats
    if "select_category_group_" in query.data:
        category = query.data.replace("select_category_group_", "")
    else:
        category = query.data.replace("select_category_", "")
        
    matching_items = [item for item in EXTRACTED_ITEMS if item["category"] == category]
    
    if not matching_items:
        try:
            # For groups, consider thread_id
            thread_id = context.user_data.get("group_thread_id") if is_group else None
            message_text = clean_text(f"هیچ آیتمی تو دسته‌بندی '{category}' پیدا نشد! 😕")
            
            if is_group:
                # In groups, send a new message instead of editing
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=message_text,
                    message_thread_id=thread_id
                )
                
                # Try to delete the old message
                try:
                    await context.bot.delete_message(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Could not delete category message in group: {e}")
            else:
                # In private chats, we can edit
                await query.edit_message_text(message_text)
        except Exception as e:
            logger.error(f"Error handling empty category: {e}")
        
        return SELECT_CATEGORY
    
    # Store the matched items
    context.user_data["matching_items"] = matching_items
    context.user_data["page"] = 0
    
    # Log for debugging
    logger.info(f"Category selected: {category}, is_group: {is_group}, found {len(matching_items)} items")
    
    # Send the paginated items
    await send_paginated_items(update, context, is_group=is_group)
    
    return SEARCH_ITEM

async def select_group_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.replace("select_group_item_", "")
    item = next((i for i in EXTRACTED_ITEMS if i["id"] == item_id), None)
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    
    if not item:
        try:
            await query.message.reply_text(clean_text("آیتم پیدا نشد! 😕"), message_thread_id=thread_id)
        except Exception as e:
            logger.error(f"Error replying to callback query: {e}")
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
    
    try:
        async with PROCESSING_LOCK:
            if item["images"]:
                image_url = item["images"][0]
                # Treat all images as potentially animatable - this will ensure we properly handle all formats
                async def process_image():
                    try:
                        logger.info(f"Processing image: {image_url}")
                        response = requests.get(image_url, timeout=30)
                        response.raise_for_status()
                        
                        # Save the original image data
                        img_data = io.BytesIO(response.content)
                        
                        # Create a buffer for the processed image (GIF)
                        gif_buffer = io.BytesIO()
                        
                        try:
                            # Attempt to open the image with Pillow
                            img = Image.open(img_data)
                            
                            # Check if it's an animated image (has multiple frames)
                            is_animated = hasattr(img, "n_frames") and img.n_frames > 1
                            logger.info(f"Image format: {img.format}, Mode: {img.mode}, Animated: {is_animated}")
                            
                            # Convert to proper mode for GIF
                            if img.mode not in ['RGB', 'RGBA', 'P']:
                                img = img.convert('RGBA')
                            
                            # For non-animated images, create a basic animation
                            if not is_animated:
                                # Create a slightly modified copy for frame 2
                                frame2 = img.copy()
                                
                                # For better results, save the image as GIF with animation
                                img.save(
                                    gif_buffer, 
                                    format='GIF', 
                                    save_all=True, 
                                    append_images=[frame2], 
                                    optimize=False,
                                    disposal=2,
                                    duration=500,  # 500ms delay
                                    loop=0         # loop forever
                                )
                            else:
                                # For already animated images, preserve animation
                                img.save(
                                    gif_buffer, 
                                    format='GIF', 
                                    save_all=True, 
                                    optimize=False,
                                    disposal=2,
                                    duration=100,  # 100ms delay per frame
                                    loop=0         # loop forever
                                )
                                
                            # Reset buffer position
                            gif_buffer.seek(0)
                            
                            # Create input file for Telegram
                            input_file = InputFile(gif_buffer, filename="animation.gif")
                            
                            # Send the animation
                            chat_id = query.message.chat_id
                            sent_message = await context.bot.send_animation(
                                chat_id=chat_id,
                                animation=input_file,
                                caption=results_text,
                                message_thread_id=thread_id
                            )
                            
                            # Log success
                            logger.info(f"Successfully sent GIF animation for {image_url}")
                            
                            # Process audio attachments
                            for i, audio_info in enumerate(item["audios"], 1):
                                await send_audio(update, context, item, audio_info, i, None, thread_id)
                                
                            # Try to delete the original message to clean up chat
                            try:
                                await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
                            except Exception as e:
                                logger.warning(f"Could not delete original message after image conversion: {e}")
                            
                            return sent_message
                        
                        except Exception as img_e:
                            # If conversion fails, fallback to sending as photo
                            logger.error(f"Error converting image to GIF: {img_e}")
                            
                            # Reset the original image data
                            img_data.seek(0)
                            
                            # Send as regular photo
                            chat_id = query.message.chat_id
                            sent_message = await context.bot.send_photo(
                                chat_id=chat_id,
                                photo=InputFile(img_data, filename="image.jpg"),
                                caption=results_text,
                                message_thread_id=thread_id
                            )
                            
                            # Process audio attachments
                            for i, audio_info in enumerate(item["audios"], 1):
                                await send_audio(update, context, item, audio_info, i, None, thread_id)
                                
                            # Try to delete the original message
                            try:
                                await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
                            except Exception as e:
                                logger.warning(f"Could not delete original message after fallback to photo: {e}")
                            
                            return sent_message
                            
                    except Exception as e:
                        logger.error(f"خطا در پردازش تصویر: {e}")
                        try:
                            # Use direct send instead of reply
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=clean_text(f"مشکلی توی ارسال تصویر پیش اومد! 😅 خطا: {str(e)[:50]}..."),
                                message_thread_id=thread_id
                            )
                        except Exception as inner_e:
                            logger.error(f"Error sending error message for image: {inner_e}")
                
                # Process the image asynchronously
                asyncio.create_task(process_image())
                
            else:
                await query.message.reply_text(results_text, message_thread_id=thread_id)
            
            # Try to delete the callback message in groups if appropriate
            # Only attempt this if it's not a topic/thread message
            if not thread_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                except Exception as e:
                    logger.warning(f"Could not delete group callback message: {e}")
    except Exception as e:
        logger.error(f"Error in select_group_item: {e}")
        try:
            await query.message.reply_text(
                clean_text("مشکلی در نمایش جزئیات آیتم پیش آمد. لطفاً دوباره امتحان کنید."),
                message_thread_id=thread_id
            )
        except Exception:
            pass

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Check explicitly if this is a group interaction
    is_group = "group" in query.data or context.user_data.get("is_group_interaction", False)
    page = context.user_data.get("page", 0)
    
    try:
        # Log the callback data to help with debugging
        logger.info(f"Pagination callback data: {query.data}")
        
        if "_categories" in query.data:
            if "next_page" in query.data:
                context.user_data["page"] = page + 1
                logger.info(f"Moving to next categories page: {page + 1}")
            elif "prev_page" in query.data:
                context.user_data["page"] = max(0, page - 1)
                logger.info(f"Moving to previous categories page: {max(0, page - 1)}")
            
            # For groups, always send a new message instead of trying to edit
            if is_group and update.callback_query and update.callback_query.message:
                group_thread_id = context.user_data.get("group_thread_id")
                
                # Send a new categories message
                try:
                    await send_paginated_categories(update, context, is_group=True)
                    
                    # Try to delete the old message to keep chat clean
                    try:
                        await context.bot.delete_message(
                            chat_id=update.callback_query.message.chat_id,
                            message_id=update.callback_query.message.message_id
                        )
                    except Exception as e:
                        logger.warning(f"Could not delete previous categories message in group: {e}")
                except Exception as e:
                    logger.error(f"Error sending new categories message in group: {e}")
            else:
                # For private chats, it's safer to use the existing method
                if update.callback_query and update.callback_query.message:
                    try:
                        # Try to delete the current message to keep the chat clean
                        await context.bot.delete_message(
                            chat_id=update.callback_query.message.chat_id,
                            message_id=update.callback_query.message.message_id
                        )
                    except Exception as e:
                        logger.warning(f"Could not delete categories message: {e}")
                    
                    # Send a new categories list
                    await send_paginated_categories(update, context, is_group=is_group)
            
            # Always return SELECT_CATEGORY for conversation handling in both private and groups
            return SELECT_CATEGORY
        else:
            if "next_page" in query.data:
                context.user_data["page"] = page + 1
                logger.info(f"Moving to next items page: {page + 1}")
            elif "prev_page" in query.data:
                context.user_data["page"] = max(0, page - 1)
                logger.info(f"Moving to previous items page: {max(0, page - 1)}")
            
            # For groups, don't try to edit, just send a new message
            if is_group:
                # Don't try to edit in groups, just send a new message
                await send_paginated_items(update, context, is_group=True)
            else:
                try:
                    await send_paginated_items(update, context, is_group=is_group)
                except error.BadRequest as e:
                    logger.warning(f"Error in pagination (items): {e}")
                    # If we can't edit the message, send a new one
                    if "Message to edit not found" in str(e) or "There is no text in the message to edit" in str(e):
                        if update.callback_query and update.callback_query.message:
                            try:
                                # Try to delete the current message
                                await context.bot.delete_message(
                                    chat_id=update.callback_query.message.chat_id,
                                    message_id=update.callback_query.message.message_id
                                )
                            except Exception:
                                pass
                                
                            await context.bot.send_message(
                                chat_id=update.callback_query.message.chat_id,
                                text=clean_text("نمایش آیتم‌ها...")
                            )
                            await send_paginated_items(update, context, is_group=is_group)
            
            # Always return SEARCH_ITEM for conversation handling in both private and groups
            return SEARCH_ITEM
    except Exception as e:
        logger.error(f"Error in handle_pagination: {e}")
        if update.callback_query and update.callback_query.message:
            thread_id = context.user_data.get("group_thread_id") if is_group else None
            await update.callback_query.message.reply_text(
                clean_text("مشکلی در تغییر صفحه پیش آمد. لطفاً دوباره امتحان کنید."),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]),
                message_thread_id=thread_id
            )
        return SELECT_CATEGORY if "_categories" in query.data else SEARCH_ITEM

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
    
    # Get user's full name
    user = update.effective_user
    user_fullname = f"{user.first_name} {user.last_name if user.last_name else ''}".strip()
    
    user_message = update.message.text
    chat_history = context.user_data.get("chat_history", [])
    
    # Prepare the system message with user information
    system_message = SYSTEM_MESSAGE
    if user_fullname:
        system_message = f"نام و نام خانوادگی کاربر: {user_fullname}\n" + SYSTEM_MESSAGE + "\nلطفا در پاسخ‌های خود از نام کاربر استفاده کنید و اگر نام انگلیسی است به فارسی تبدیل کنید."
    
    chat_history.append({"role": "user", "content": user_message})
    context.user_data["chat_history"] = chat_history
    
    # محدود کردن تاریخچه به 10 پیام آخر
    recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history
    
    # Updated payload structure for Pollinations API
    payload = {
        "messages": [
            {"role": "system", "content": system_message}
        ] + recent_history,  # اضافه کردن تاریخچه محدود شده
        "model": "openai",
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    reply_markup = None
    
    # ساخت URL با پارامترهای model و token
    api_url = f"{TEXT_API_URL}?model={GPT_MODEL}&token={POLLINATIONS_TOKEN}"
    
    try:
        response = requests.post(api_url, json=payload, timeout=30)
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

    # Get user's full name
    user = update.effective_user
    user_fullname = f"{user.first_name} {user.last_name if user.last_name else ''}".strip()

    group_history = context.bot_data.get("group_history", {}).get(chat_id, [])
    group_history.append({"user_id": user_id, "content": user_message, "message_id": message_id})
    context.bot_data["group_history"] = {chat_id: group_history}

    user_history = context.user_data.get("group_chat_history", [])
    
    should_reply = (
        "ربات" in user_message or "پلاتو" in user_message or "سلام" in user_message or "خداحافظ" in user_message or
        "bot" in user_message or "hello" in user_message or "hi" in user_message or "bye" in user_message or
        "plato" in user_message or "پلاتودکس" in user_message or "@plato" in user_message or
        (replied_message and replied_message.from_user.id == context.bot.id)
    )
    
    logger.info(f"Group message: '{user_message}' - should_reply: {should_reply}")
    
    # تست ساده برای بررسی عملکرد
    if "تست" in user_message:
        await update.message.reply_text("✅ ربات در گروه کار می‌کند!")
        return
    
    if not should_reply:
        logger.info(f"Not replying to message: '{user_message}'")
        return
    
    if replied_message and replied_message.from_user.id == context.bot.id:
        user_history.append({"role": "assistant", "content": replied_message.text})
    
    user_history.append({"role": "user", "content": user_message})
    context.user_data["group_chat_history"] = user_history
    
    # Prepare the system message with user information
    system_message = SYSTEM_MESSAGE
    if user_fullname:
        system_message = f"نام و نام خانوادگی کاربر: {user_fullname}\n" + SYSTEM_MESSAGE + "\nلطفا در پاسخ‌های خود از نام کاربر استفاده کنید و اگر نام انگلیسی است به فارسی تبدیل کنید."
    
    # Updated payload structure for Pollinations API
    payload = {
        "messages": [
            {"role": "system", "content": system_message}
        ] + user_history,  # اضافه کردن کل تاریخچه (نامحدود)
        "model": "openai",
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    # ساخت URL با پارامترهای model و token
    api_url = f"{TEXT_API_URL}?model={GPT_MODEL}&token={POLLINATIONS_TOKEN}"
    
    try:
        response = requests.post(api_url, json=payload, timeout=30)
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطا در پردازش آپدیت: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(clean_text("مشکلی پیش اومد! 😅 لطفاً دوباره امتحان کنید."))

async def back_to_categories_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Make sure we maintain the group interaction status
    context.user_data["is_group_interaction"] = True
    
    # Get the thread_id if available
    thread_id = query.message.message_thread_id if hasattr(query.message, 'is_topic_message') and query.message.is_topic_message else None
    context.user_data["group_thread_id"] = thread_id
    
    try:
        # Try to delete the current message to keep chat clean
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.warning(f"Could not delete items message in group: {e}")
        
        # Get categories and reset page counter
        categories = sorted(set(item["category"] for item in EXTRACTED_ITEMS))
        context.user_data["categories"] = categories
        context.user_data["page"] = 0
        
        # Send categories list
        await send_paginated_categories(update, context, is_group=True)
    except Exception as e:
        logger.error(f"Error in back_to_categories_group: {e}")
        try:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=clean_text("مشکلی در بازگشت به دسته‌بندی‌ها پیش آمد. لطفاً دوباره امتحان کنید."),
                message_thread_id=thread_id
            )
        except Exception:
            pass
    
    return SELECT_CATEGORY

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
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_group_ai_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
            # Add group message handler for general group messages (not AI chat)
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_message))
            application.add_handler(CommandHandler("item", process_item_in_group, filters=filters.ChatType.GROUPS))
            application.add_handler(CommandHandler("i", process_item_in_group, filters=filters.ChatType.GROUPS))
            application.add_handler(CommandHandler("w", show_leaderboard, filters=filters.ChatType.GROUPS))
            application.add_handler(CallbackQueryHandler(select_group_item, pattern="^select_group_item_"))
            
            # Add these handlers for group interactions
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
