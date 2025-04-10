# profile_scraper.py
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

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
