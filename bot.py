#!/usr/bin/env python3
"""
MathonGo JEE Papers Telegram Bot - GitHub Actions Version
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
MATHONGO_URL = "https://www.mathongo.com/iit-jee/jee-main-previous-year-question-paper"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


# ============ TELEGRAM FUNCTIONS ============

def send_message(chat_id, text, parse_mode='Markdown', reply_markup=None):
    """Send message to Telegram"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
    except Exception as e:
        print(f"Send error: {e}")


def get_updates(offset=None):
    """Get updates from Telegram"""
    params = {'timeout': 5}
    if offset:
        params['offset'] = offset
    
    try:
        r = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=10)
        return r.json()
    except:
        return {'ok': False, 'result': []}


def answer_callback(callback_id):
    """Answer callback query"""
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", 
                     json={'callback_query_id': callback_id}, timeout=5)
    except:
        pass


# ============ SCRAPING FUNCTIONS ============

def convert_drive_link(url):
    """Convert Google Drive link to direct download"""
    if 'drive.google.com' in url:
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return url


def scrape_papers(filter_year=None):
    """Scrape MathonGo for papers"""
    papers = []
    seen = set()
    
    try:
        print("Fetching MathonGo...")
        r = requests.get(MATHONGO_URL, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'lxml')
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            if not href or href.startswith('#') or href.startswith('javascript'):
                continue
            
            # Check if paper link
            is_paper = (
                '.pdf' in href.lower() or
                'drive.google.com' in href or
                any(kw in text.lower() for kw in ['paper', 'question', 'solution', 'download', 'pdf'])
            )
            
            if is_paper and href not in seen:
                seen.add(href)
                
                if not href.startswith('http'):
                    href = urljoin(MATHONGO_URL, href)
                
                # Extract year
                year_match = re.search(r'20[1-2][0-9]', text + href)
                year = year_match.group(0) if year_match else 'Other'
                
                if filter_year and year != filter_year:
                    continue
                
                papers.append({
                    'name': text[:60] if text else 'JEE Paper',
                    'url': convert_drive_link(href),
                    'year': year
                })
        
        print(f"Found {len(papers)} papers")
        
    except Exception as e:
        print(f"Scrape error: {e}")
    
    return papers


# ============ COMMAND HANDLERS ============

def handle_start(chat_id, name):
    """Handle /start"""
    keyboard = {
        'inline_keyboard': [
            [{'text': '📚 Get All Papers', 'callback_data': 'papers'}],
            [{'text': '📅 Select Year', 'callback_data': 'years'}],
            [{'text': '❓ Help', 'callback_data': 'help'}]
        ]
    }
    
    send_message(chat_id, f"""🎓 *Welcome {name}!*

I fetch *JEE Main PYQ Papers* from MathonGo!

📄 Direct PDF downloads
📅 Papers from 2015-2024
✅ Questions & Solutions

⚡ *Note:* I check messages every 2 mins, so please wait for response!

Click below to start 👇""", reply_markup=keyboard)


def handle_papers(chat_id, year=None):
    """Handle getting papers"""
    year_text = f" for {year}" if year else ""
    send_message(chat_id, f"🔄 Fetching papers{year_text}... Please wait!")
    
    papers = scrape_papers(year)
    
    if not papers:
        send_message(chat_id, f"❌ No papers found{year_text}. Try /papers for all.")
        return
    
    send_message(chat_id, f"✅ Found *{len(papers)} papers*! Sending links...")
    
    # Group by year
    grouped = {}
    for p in papers:
        y = p['year']
        if y not in grouped:
            grouped[y] = []
        grouped[y].append(p)
    
    # Send grouped
    for year in sorted(grouped.keys(), reverse=True):
        msg = f"📅 *{year}*\n\n"
        for p in grouped[year][:10]:
            msg += f"📄 [{p['name']}]({p['url']})\n\n"
        send_message(chat_id, msg)
        time.sleep(0.5)
    
    send_message(chat_id, "✅ Done! Click links to download. Good luck! 🎯")


def handle_years(chat_id):
    """Handle year selection"""
    keyboard = {
        'inline_keyboard': [
            [{'text': '2024', 'callback_data': 'y_2024'}, {'text': '2023', 'callback_data': 'y_2023'}],
            [{'text': '2022', 'callback_data': 'y_2022'}, {'text': '2021', 'callback_data': 'y_2021'}],
            [{'text': '2020', 'callback_data': 'y_2020'}, {'text': '2019', 'callback_data': 'y_2019'}],
            [{'text': '2018', 'callback_data': 'y_2018'}, {'text': '2017', 'callback_data': 'y_2017'}],
            [{'text': '📚 All Papers', 'callback_data': 'papers'}]
        ]
    }
    send_message(chat_id, "📅 *Select Year:*", reply_markup=keyboard)


def handle_help(chat_id):
    """Handle /help"""
    send_message(chat_id, """📖 *Commands*

/start - Start bot
/papers - Get all papers  
/years - Select by year
/help - This message

⚡ Bot runs every 2 mins, so responses aren't instant!

📄 Papers are from MathonGo
🔗 Click links to download PDFs""")


# ============ MAIN ============

def get_last_update_id():
    """Read last update ID from file"""
    try:
        with open('last_update_id.txt', 'r') as f:
            return int(f.read().strip())
    except:
        return 0


def save_last_update_id(update_id):
    """Save last update ID to file"""
    with open('last_update_id.txt', 'w') as f:
        f.write(str(update_id))


def main():
    if not BOT_TOKEN:
        print("ERROR: No BOT_TOKEN!")
        return
    
    last_id = get_last_update_id()
    print(f"Last update ID: {last_id}")
    
    result = get_updates(offset=last_id + 1 if last_id else None)
    
    if not result.get('ok'):
        print("Failed to get updates")
        return
    
    updates = result.get('result', [])
    print(f"Processing {len(updates)} updates")
    
    for update in updates:
        update_id = update['update_id']
        
        try:
            # Handle callback (button press)
            if 'callback_query' in update:
                cb = update['callback_query']
                chat_id = cb['message']['chat']['id']
                data = cb['data']
                answer_callback(cb['id'])
                
                if data == 'papers':
                    handle_papers(chat_id)
                elif data == 'years':
                    handle_years(chat_id)
                elif data == 'help':
                    handle_help(chat_id)
                elif data.startswith('y_'):
                    handle_papers(chat_id, data[2:])
            
            # Handle message
            elif 'message' in update:
                msg = update['message']
                chat_id = msg['chat']['id']
                text = msg.get('text', '').lower().strip()
                name = msg.get('from', {}).get('first_name', 'Student')
                
                if text == '/start':
                    handle_start(chat_id, name)
                elif text == '/papers':
                    handle_papers(chat_id)
                elif text == '/years':
                    handle_years(chat_id)
                elif text == '/help':
                    handle_help(chat_id)
                else:
                    send_message(chat_id, "❓ Unknown command. Try /help")
        
        except Exception as e:
            print(f"Error: {e}")
        
        last_id = max(last_id, update_id)
    
    save_last_update_id(last_id)
    print(f"Done! Saved ID: {last_id}")


if __name__ == '__main__':
    main()
