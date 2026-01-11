#!/usr/bin/env python3
"""
MathonGo JEE Papers Telegram Bot
Runs on GitHub Actions - Fetches JEE Main PYQ papers and sends to Telegram
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import time

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
MATHONGO_URL = "https://www.mathongo.com/iit-jee/jee-main-previous-year-question-paper"
LAST_UPDATE_ID = int(os.environ.get('LAST_UPDATE_ID', '0'))

# Headers for web scraping
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.google.com/',
    'DNT': '1'
}


def send_message(chat_id, text, parse_mode='Markdown', reply_markup=None, disable_preview=True):
    """Send a message via Telegram API"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': disable_preview
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None


def get_updates(offset=None):
    """Get updates from Telegram"""
    params = {'timeout': 30, 'allowed_updates': ['message', 'callback_query']}
    if offset:
        params['offset'] = offset
    
    try:
        response = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=35)
        return response.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return {'ok': False, 'result': []}


def answer_callback_query(callback_query_id, text="Processing..."):
    """Answer a callback query"""
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            'callback_query_id': callback_query_id,
            'text': text
        }, timeout=10)
    except:
        pass


def convert_to_direct_link(url):
    """Convert sharing links to direct download links"""
    if not url:
        return url
    
    # Google Drive
    if 'drive.google.com' in url:
        # Extract file ID
        file_id = None
        
        # Format: /file/d/FILE_ID/
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
        
        # Format: ?id=FILE_ID or &id=FILE_ID
        if not file_id:
            match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
            if match:
                file_id = match.group(1)
        
        # Format: /open?id=FILE_ID
        if not file_id:
            match = re.search(r'/open\?id=([a-zA-Z0-9_-]+)', url)
            if match:
                file_id = match.group(1)
        
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    # Dropbox
    if 'dropbox.com' in url:
        return url.replace('dl=0', 'dl=1')
    
    return url


def extract_year(text):
    """Extract year from text"""
    if not text:
        return None
    match = re.search(r'20[1-2][0-9]', text)
    return match.group(0) if match else None


def scrape_mathongo(filter_year=None):
    """Scrape MathonGo for JEE papers"""
    papers = []
    seen_urls = set()
    
    try:
        print(f"Fetching: {MATHONGO_URL}")
        response = requests.get(MATHONGO_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, 'lxml')
        
        # Method 1: Find all links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Skip empty or javascript links
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            # Make absolute URL
            if not href.startswith('http'):
                href = urljoin(MATHONGO_URL, href)
            
            # Check if it's a paper link
            is_paper = False
            
            # Check for PDF links
            if '.pdf' in href.lower():
                is_paper = True
            
            # Check for Google Drive links
            if 'drive.google.com' in href:
                is_paper = True
            
            # Check for paper-related text
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in ['paper', 'question', 'solution', 'download', 'pdf', 'pyq', 'jee']):
                is_paper = True
            
            if is_paper and href not in seen_urls:
                seen_urls.add(href)
                
                # Extract year
                year = extract_year(text) or extract_year(href)
                
                # Filter by year if specified
                if filter_year and year != filter_year:
                    continue
                
                # Determine type
                paper_type = 'solution' if any(w in text_lower for w in ['solution', 'answer', 'key']) else 'question'
                
                papers.append({
                    'name': text if text else 'JEE Paper',
                    'url': href,
                    'direct_url': convert_to_direct_link(href),
                    'year': year or 'Other',
                    'type': paper_type
                })
        
        # Method 2: Check for data attributes
        for element in soup.find_all(attrs={'data-url': True}):
            url = element.get('data-url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                if not url.startswith('http'):
                    url = urljoin(MATHONGO_URL, url)
                papers.append({
                    'name': element.get_text(strip=True) or 'JEE Paper',
                    'url': url,
                    'direct_url': convert_to_direct_link(url),
                    'year': extract_year(url) or 'Other',
                    'type': 'question'
                })
        
        # Method 3: Look for embedded JSON data
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Look for JSON arrays with paper data
                json_matches = re.findall(r'\{[^{}]*"url"\s*:\s*"([^"]+)"[^{}]*\}', script.string)
                for url in json_matches:
                    url = url.replace('\\/', '/')
                    if url not in seen_urls and ('.pdf' in url or 'drive.google.com' in url):
                        seen_urls.add(url)
                        if not url.startswith('http'):
                            url = urljoin(MATHONGO_URL, url)
                        papers.append({
                            'name': 'JEE Paper',
                            'url': url,
                            'direct_url': convert_to_direct_link(url),
                            'year': extract_year(url) or 'Other',
                            'type': 'question'
                        })
        
        print(f"Found {len(papers)} papers")
        
    except Exception as e:
        print(f"Error scraping: {e}")
    
    return papers


def group_papers_by_year(papers):
    """Group papers by year"""
    grouped = {}
    for paper in papers:
        year = paper.get('year', 'Other')
        if year not in grouped:
            grouped[year] = []
        grouped[year].append(paper)
    
    # Sort by year descending
    return dict(sorted(grouped.items(), key=lambda x: x[0], reverse=True))


def handle_start(chat_id, first_name):
    """Handle /start command"""
    keyboard = {
        'inline_keyboard': [
            [{'text': '📚 Get All Papers', 'callback_data': 'get_all_papers'}],
            [{'text': '📅 Select by Year', 'callback_data': 'select_year'}],
            [{'text': '❓ Help', 'callback_data': 'help'}]
        ]
    }
    
    send_message(chat_id, f"""🎓 *Welcome {first_name}!*

I'm your *JEE Main PYQ Papers* bot!

I fetch Previous Year Question Papers from MathonGo and give you direct PDF download links.

*Features:*
📄 Direct PDF downloads
📅 Papers from 2015-2024
✅ Both Questions & Solutions
⚡ Fast & Easy access

Click a button below to get started! 👇""", reply_markup=keyboard)


def handle_get_papers(chat_id, filter_year=None):
    """Handle getting papers"""
    year_text = f" for {filter_year}" if filter_year else ""
    
    send_message(chat_id, f"🔄 *Fetching papers{year_text}...*\n\nPlease wait, this may take a few seconds.")
    
    papers = scrape_mathongo(filter_year)
    
    if not papers:
        send_message(chat_id, f"""❌ *No papers found{year_text}*

This could be because:
• The website structure changed
• Network issues
• No papers available for this selection

Try again later or use /papers for all papers.""")
        return
    
    send_message(chat_id, f"✅ *Found {len(papers)} papers{year_text}!*\n\nSending download links...")
    
    # Group by year
    grouped = group_papers_by_year(papers)
    
    # Send papers
    for year, year_papers in grouped.items():
        message = f"📅 *JEE Main {year}*\n\n"
        
        for paper in year_papers[:15]:  # Limit to avoid too long messages
            icon = "📝" if paper['type'] == 'solution' else "📄"
            name = paper['name'][:50]  # Truncate long names
            message += f"{icon} *{name}*\n"
            message += f"🔗 [Download PDF]({paper['direct_url']})\n\n"
        
        if len(year_papers) > 15:
            message += f"_...and {len(year_papers) - 15} more papers_\n"
        
        send_message(chat_id, message)
        time.sleep(0.5)  # Rate limiting
    
    send_message(chat_id, """✅ *All papers sent!*

💡 *Tips:*
• Click the links to download PDFs directly
• Use /years to filter by specific year
• Papers include both Questions & Solutions

📚 Good luck with your preparation! 🎯""")


def handle_years(chat_id):
    """Handle year selection"""
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '📅 2024', 'callback_data': 'year_2024'},
                {'text': '📅 2023', 'callback_data': 'year_2023'}
            ],
            [
                {'text': '📅 2022', 'callback_data': 'year_2022'},
                {'text': '📅 2021', 'callback_data': 'year_2021'}
            ],
            [
                {'text': '📅 2020', 'callback_data': 'year_2020'},
                {'text': '📅 2019', 'callback_data': 'year_2019'}
            ],
            [
                {'text': '📅 2018', 'callback_data': 'year_2018'},
                {'text': '📅 2017', 'callback_data': 'year_2017'}
            ],
            [
                {'text': '📅 2016', 'callback_data': 'year_2016'},
                {'text': '📅 2015', 'callback_data': 'year_2015'}
            ],
            [{'text': '📚 All Papers', 'callback_data': 'get_all_papers'}]
        ]
    }
    
    send_message(chat_id, "📅 *Select Year*\n\nChoose a year to get JEE Main papers:", reply_markup=keyboard)


def handle_help(chat_id):
    """Handle /help command"""
    send_message(chat_id, """📖 *Help & Commands*

*Available Commands:*
/start - Start the bot
/papers - Get all JEE Main papers
/years - Select papers by year
/help - Show this help message

*How to use:*
1. Send /papers to get all papers
2. Or use /years to select a specific year
3. Click on download links to get PDFs

*Note:*
• PDFs are fetched from MathonGo
• Some links redirect to Google Drive
• Bot checks for messages every 2 minutes
• If a link doesn't work, try again later""")


def process_update(update):
    """Process a single update"""
    
    # Handle callback query (button press)
    if 'callback_query' in update:
        callback = update['callback_query']
        callback_id = callback['id']
        chat_id = callback['message']['chat']['id']
        data = callback['data']
        
        answer_callback_query(callback_id)
        
        if data == 'get_all_papers':
            handle_get_papers(chat_id)
        elif data == 'select_year':
            handle_years(chat_id)
        elif data.startswith('year_'):
            year = data.replace('year_', '')
            handle_get_papers(chat_id, year)
        elif data == 'help':
            handle_help(chat_id)
        
        return
    
    # Handle message
    if 'message' not in update:
        return
    
    message = update['message']
    chat_id = message['chat']['id']
    text = message.get('text', '').strip().lower()
    first_name = message.get('from', {}).get('first_name', 'Student')
    
    if text == '/start':
        handle_start(chat_id, first_name)
    elif text in ['/papers', '/getpapers', '/get_papers']:
        handle_get_papers(chat_id)
    elif text == '/years':
        handle_years(chat_id)
    elif text == '/help':
        handle_help(chat_id)
    elif text.startswith('/year_'):
        year = text.replace('/year_', '')
        handle_get_papers(chat_id, year)
    else:
        send_message(chat_id, "❓ Unknown command. Use /help to see available commands.")


def main():
    """Main function"""
    global LAST_UPDATE_ID
    
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set!")
        return
    
    print(f"Starting bot... Last update ID: {LAST_UPDATE_ID}")
    
    # Get updates
    result = get_updates(offset=LAST_UPDATE_ID + 1 if LAST_UPDATE_ID else None)
    
    if not result.get('ok'):
        print(f"Failed to get updates: {result}")
        return
    
    updates = result.get('result', [])
    print(f"Got {len(updates)} updates")
    
    # Process each update
    for update in updates:
        update_id = update['update_id']
        print(f"Processing update {update_id}")
        
        try:
            process_update(update)
        except Exception as e:
            print(f"Error processing update {update_id}: {e}")
        
        # Update last processed ID
        LAST_UPDATE_ID = max(LAST_UPDATE_ID, update_id)
    
    # Save last update ID for next run
    with open('last_update_id.txt', 'w') as f:
        f.write(str(LAST_UPDATE_ID))
    
    print(f"Done. Last update ID: {LAST_UPDATE_ID}")


if __name__ == '__main__':
    main()
