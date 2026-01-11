#!/usr/bin/env python3
"""
MathonGo JEE Papers Telegram Bot
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


# ==================== TELEGRAM ====================

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
        response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
        result = response.json()
        if not result.get('ok'):
            print(f"Send message error: {result}")
        return result
    except Exception as e:
        print(f"Send error: {e}")
        return None


def get_updates(offset=None):
    """Get updates from Telegram"""
    params = {'timeout': 5}
    if offset:
        params['offset'] = offset
    
    try:
        response = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Get updates error: {e}")
        return {'ok': False, 'result': []}


def answer_callback(callback_id):
    """Answer callback query"""
    try:
        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={'callback_query_id': callback_id},
            timeout=5
        )
    except:
        pass


# ==================== SCRAPING ====================

def convert_drive_link(url):
    """Convert Google Drive link to direct download"""
    if not url:
        return url
    
    if 'drive.google.com' in url:
        # /file/d/ID/ format
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
        
        # ?id=ID format
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    
    if 'dropbox.com' in url:
        return url.replace('dl=0', 'dl=1')
    
    return url


def scrape_papers(filter_year=None):
    """Scrape MathonGo for papers"""
    papers = []
    seen = set()
    
    try:
        print(f"Fetching: {MATHONGO_URL}")
        response = requests.get(MATHONGO_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Skip invalid links
            if not href or href.startswith('#') or href.startswith('javascript'):
                continue
            
            # Make absolute URL
            if not href.startswith('http'):
                href = urljoin(MATHONGO_URL, href)
            
            # Check if it's a paper link
            text_lower = text.lower()
            is_paper = (
                '.pdf' in href.lower() or
                'drive.google.com' in href or
                any(kw in text_lower for kw in ['paper', 'question', 'solution', 'download', 'pdf', 'pyq'])
            )
            
            if not is_paper or href in seen:
                continue
            
            seen.add(href)
            
            # Extract year
            year_match = re.search(r'20[1-2][0-9]', text + href)
            year = year_match.group(0) if year_match else 'Other'
            
            # Apply year filter
            if filter_year and year != filter_year:
                continue
            
            # Clean name
            name = text[:60] if text else 'JEE Paper'
            name = re.sub(r'\s+', ' ', name).strip()
            
            papers.append({
                'name': name,
                'url': convert_drive_link(href),
                'year': year
            })
        
        # Also check for embedded JSON data
        for script in soup.find_all('script'):
            if script.string:
                urls = re.findall(r'https?://[^"\'<>\s]+\.pdf', script.string)
                for url in urls:
                    if url not in seen:
                        seen.add(url)
                        year_match = re.search(r'20[1-2][0-9]', url)
                        year = year_match.group(0) if year_match else 'Other'
                        if filter_year and year != filter_year:
                            continue
                        papers.append({
                            'name': 'JEE Paper',
                            'url': convert_drive_link(url),
                            'year': year
                        })
        
        print(f"Found {len(papers)} papers")
        
    except Exception as e:
        print(f"Scrape error: {e}")
    
    return papers


# ==================== HANDLERS ====================

def handle_start(chat_id, name):
    """Handle /start command"""
    keyboard = {
        'inline_keyboard': [
            [{'text': '📚 Get All Papers', 'callback_data': 'papers'}],
            [{'text': '📅 Select Year', 'callback_data': 'years'}],
            [{'text': '❓ Help', 'callback_data': 'help'}]
        ]
    }
    
    send_message(chat_id, f"""🎓 *Welcome {name}!*

I'm your *JEE Main PYQ Papers* bot!

📄 Direct PDF downloads
📅 Papers from 2015-2024
✅ Questions & Solutions

⚠️ *Note:* I check messages every 2 mins, so please be patient!

Click a button below to start 👇""", reply_markup=keyboard)


def handle_papers(chat_id, year=None):
    """Handle getting papers"""
    year_text = f" for {year}" if year else ""
    send_message(chat_id, f"🔄 *Fetching papers{year_text}...*\n\nPlease wait!")
    
    papers = scrape_papers(year)
    
    if not papers:
        send_message(chat_id, f"""❌ *No papers found{year_text}*

Possible reasons:
• Website structure changed
• Network issues

Try /papers to get all papers.""")
        return
    
    send_message(chat_id, f"✅ Found *{len(papers)} papers*!\n\nSending links...")
    
    # Group by year
    grouped = {}
    for p in papers:
        y = p['year']
        if y not in grouped:
            grouped[y] = []
        grouped[y].append(p)
    
    # Send grouped papers
    for year_key in sorted(grouped.keys(), reverse=True):
        year_papers = grouped[year_key]
        msg = f"📅 *JEE Main {year_key}*\n\n"
        
        for p in year_papers[:10]:  # Max 10 per year
            # Escape markdown special chars in name
            safe_name = p['name'].replace('[', '(').replace(']', ')').replace('*', '')
            msg += f"📄 [{safe_name}]({p['url']})\n\n"
        
        if len(year_papers) > 10:
            msg += f"_...and {len(year_papers) - 10} more_\n"
        
        send_message(chat_id, msg)
        time.sleep(0.5)  # Avoid rate limiting
    
    send_message(chat_id, """✅ *All papers sent!*

💡 Click the links to download PDFs directly.

Good luck with your preparation! 🎯""")


def handle_years(chat_id):
    """Handle year selection"""
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '📅 2024', 'callback_data': 'y_2024'},
                {'text': '📅 2023', 'callback_data': 'y_2023'}
            ],
            [
                {'text': '📅 2022', 'callback_data': 'y_2022'},
                {'text': '📅 2021', 'callback_data': 'y_2021'}
            ],
            [
                {'text': '📅 2020', 'callback_data': 'y_2020'},
                {'text': '📅 2019', 'callback_data': 'y_2019'}
            ],
            [
                {'text': '📅 2018', 'callback_data': 'y_2018'},
                {'text': '📅 2017', 'callback_data': 'y_2017'}
            ],
            [
                {'text': '📅 2016', 'callback_data': 'y_2016'},
                {'text': '📅 2015', 'callback_data': 'y_2015'}
            ],
            [{'text': '📚 All Papers', 'callback_data': 'papers'}]
        ]
    }
    
    send_message(chat_id, "📅 *Select a Year:*", reply_markup=keyboard)


def handle_help(chat_id):
    """Handle /help command"""
    send_message(chat_id, """📖 *Help & Commands*

*Commands:*
/start - Start the bot
/papers - Get all papers
/years - Select by year
/help - Show this help

*How it works:*
• I run every 2 minutes on GitHub Actions
• So responses may take up to 2 mins
• Papers are fetched from MathonGo
• Click links to download PDFs

*Having issues?*
• Try again after few minutes
• Some links may redirect to Google Drive""")


# ==================== MAIN ====================

def get_last_update_id():
    """Read last update ID from file"""
    try:
        with open('last_update_id.txt', 'r') as f:
            content = f.read().strip()
            return int(content) if content else 0
    except FileNotFoundError:
        return 0
    except Exception as e:
        print(f"Error reading last_update_id: {e}")
        return 0


def save_last_update_id(update_id):
    """Save last update ID to file"""
    try:
        with open('last_update_id.txt', 'w') as f:
            f.write(str(update_id))
        print(f"Saved last update ID: {update_id}")
    except Exception as e:
        print(f"Error saving last_update_id: {e}")


def process_update(update):
    """Process a single update"""
    
    # Handle callback query (button press)
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
            year = data[2:]
            handle_papers(chat_id, year)
        
        return
    
    # Handle message
    if 'message' not in update:
        return
    
    msg = update['message']
    chat_id = msg['chat']['id']
    text = msg.get('text', '').lower().strip()
    name = msg.get('from', {}).get('first_name', 'Student')
    
    print(f"Message from {name}: {text}")
    
    if text == '/start':
        handle_start(chat_id, name)
    elif text == '/papers':
        handle_papers(chat_id)
    elif text == '/years':
        handle_years(chat_id)
    elif text == '/help':
        handle_help(chat_id)
    else:
        send_message(chat_id, "❓ Unknown command.\n\nTry /start or /help")


def main():
    """Main function"""
    print("=" * 50)
    print("MathonGo Telegram Bot Starting...")
    print("=" * 50)
    
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set!")
        return
    
    # Create file if not exists
    if not os.path.exists('last_update_id.txt'):
        save_last_update_id(0)
    
    last_id = get_last_update_id()
    print(f"Last update ID: {last_id}")
    
    # Get updates
    offset = last_id + 1 if last_id > 0 else None
    result = get_updates(offset=offset)
    
    if not result.get('ok'):
        print(f"Failed to get updates: {result}")
        return
    
    updates = result.get('result', [])
    print(f"Found {len(updates)} new updates")
    
    if not updates:
        print("No new messages to process")
        save_last_update_id(last_id)
        return
    
    # Process each update
    new_last_id = last_id
    for update in updates:
        update_id = update['update_id']
        print(f"\nProcessing update {update_id}...")
        
        try:
            process_update(update)
            new_last_id = max(new_last_id, update_id)
        except Exception as e:
            print(f"Error processing update {update_id}: {e}")
            new_last_id = max(new_last_id, update_id)  # Still update ID to avoid reprocessing
    
    # Save the new last update ID
    save_last_update_id(new_last_id)
    
    print("\n" + "=" * 50)
    print("Bot finished successfully!")
    print("=" * 50)


if __name__ == '__main__':
    main()
