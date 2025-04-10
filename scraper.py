import requests
from bs4 import BeautifulSoup
import logging
from config import ITEMS_URL, BASE_IMAGE_URL, LEADERBOARD_URL

logger = logging.getLogger(__name__)
EXTRACTED_ITEMS = []

def scrape_items():
    global EXTRACTED_ITEMS
    EXTRACTED_ITEMS = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(ITEMS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", string=re.compile(r"var items = {"))
        if not script_tag:
            logger.error("داده‌های آیتم‌ها پیدا نشد!")
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
                    "name": columns.get("column_3", "Unknown Item"),
                    "category": columns.get("column_2", "Unknown"),
                    "description": columns.get("column_5", "No description available"),
                    "price": details.get("price", {"value": 0, "type": "unknown"}),
                    "images": images,
                    "audios": audios
                })
        logger.info(f"تعداد آیتم‌ها: {len(EXTRACTED_ITEMS)}")
    except Exception as e:
        logger.error(f"خطا در اسکرپ آیتم‌ها: {e}")

def scrape_leaderboard():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(LEADERBOARD_URL, headers=headers, timeout=20)
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
        return leaderboard_data
    except Exception as e:
        logger.error(f"خطا در اسکرپ لیدربرد: {e}")
        return None

def scrape_profile(player_link):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(player_link, headers=headers, timeout=20)
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
